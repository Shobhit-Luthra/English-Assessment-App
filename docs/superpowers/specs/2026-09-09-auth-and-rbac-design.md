# Authentication, Onboarding, and Role-Based Access Control — Design

**Date:** 2026-09-09
**Status:** Draft — awaiting review
**Workstream:** WS1 of `assessment-tool-fixes.md` (auth flow + RBAC + roles).
**Relationship to the PRDs:** the production PRD (`english-proficiency-assessment-prd.md`
§6) calls for `tenants`, `users`, JWT, and Postgres row-level security. This
design delivers the **users / roles / auth** half now and **explicitly defers
multi-tenancy** (`tenant_id` on every table, RLS). The tech-stack doc
(`04-tech-stack.md` §6) already names "No auth → JWT + tenant scoping" as the
one genuine greenfield addition; this is that addition, minus tenancy.

---

## 1. Goals

1. Email + password authentication for every user, with a server-side session.
2. A data-driven RBAC model: roles and permissions live in database tables, so
   an admin adds a role or changes what a role can do **without a code change**.
3. Three seeded roles — `admin`, `recruiter`, `candidate` — with sensible
   default permission sets.
4. Onboarding sequence: sign up / log in → candidate profile capture →
   **Start Test** → test.
5. Every existing attempt/report endpoint gains authentication and an ownership
   check (fixes the current unauthenticated `/recruiter` view and the IDOR on
   `/api/attempts/{id}/*`).
6. `attempt` rows are linked to the candidate `user` who created them.

### Non-goals (deferred, not built here)

- Multi-tenancy / `tenant_id` / row-level security — production-PRD scope, its
  own workstream.
- Email-based self-serve password reset, email verification, MFA/OTP — **an
  admin sets or resets passwords** (no mail infrastructure locally).
- The recruiter dashboard, Hire/Reject UI, and aggregate analytics — WS3. This
  spec adds only the APIs and permissions they will sit on, plus placeholder
  routes.
- UI visual redesign — WS4.
- The Grok scoring swap — WS2.
- Internationalisation / language selection — separate mini-spec.
- A "drive" / campaign concept — not in the fix list; attempts remain
  standalone, owned by a candidate.

---

## 2. Data model — `backend/models.py`

New tables (SQLModel, same file):

```
role              id: int pk
                  name: str  (unique, lowercased)
                  is_system: bool = False        # admin/recruiter/candidate — cannot be deleted
                  created_at: datetime

permission        key: str pk                    # e.g. "test.take"
                  description: str

role_permission   role_id: int  fk role.id       composite pk (role_id, permission_key)
                  permission_key: str fk permission.key

user              id: str pk (uuid4)
                  email: str  (unique, stored lowercased, index)
                  password_hash: str             # Argon2id
                  display_name: str
                  role_id: int fk role.id
                  is_active: bool = True
                  created_at: datetime

candidate_profile user_id: str pk / fk user.id
                  full_name: str
                  phone: str
                  city: str | None
                  first_language: str | None
                  decision: str = "pending"      # pending | hired | rejected  (set by recruiter — WS3)
                  decided_by: str | None fk user.id
                  decided_at: datetime | None
                  updated_at: datetime

session           token: str pk                  # secrets.token_hex(32)
                  user_id: str fk user.id, index
                  created_at: datetime
                  expires_at: datetime           # created_at + 14 days
```

Change to the existing `Attempt`:

```python
user_id: str | None = Field(default=None, foreign_key="user.id", index=True)
```

`Attempt.name` is **kept** and set from `candidate_profile.full_name` at attempt
creation, so `Report`, `list_attempts`, and the seed scripts keep working with a
one-line change rather than a join everywhere.

### Why opaque session tokens instead of JWT

Each authorised request must load the `user` row anyway (to resolve
`is_active` and the permission set), so a stateless token buys nothing here. An
opaque random token in a `session` table is revocable on the spot (logout,
admin deactivation, "log out everywhere"), needs no signing secret to manage,
and adds no crypto dependency beyond `secrets`. Expiry is a stored timestamp;
expired rows are ignored on lookup and swept opportunistically.

---

## 3. Permissions (seeded)

| key | grants |
|-----|--------|
| `test.take` | create, answer, and submit one's own attempts |
| `report.view_own` | view the report for one's own attempts |
| `candidates.view` | list all candidates; view any candidate's attempts, reports, and analytics |
| `candidates.decide` | set a candidate's Hire / Reject decision (WS3) |
| `analytics.view` | view the aggregate analytics dashboard (WS3) |
| `roles.manage` | create/edit/delete roles, assign permissions, create users, assign user roles, reset passwords |
| `settings.manage` | edit system settings (pass band, retention) (WS3) |

Seeded role → permission map:

- **candidate:** `test.take`, `report.view_own`
- **recruiter:** `candidates.view`, `candidates.decide`, `analytics.view`
- **admin:** every permission above (seeded explicitly, and the seeder
  re-grants any permission the admin role is missing on each run, so a new
  permission added in a later version is picked up).

### Lock-out guards (enforced in the API, not just the UI)

- The `admin`, `recruiter`, `candidate` roles have `is_system = True` and cannot
  be deleted or renamed.
- A role cannot be deleted while any user is assigned to it.
- An admin cannot: deactivate their own account, change their own role away from
  `admin`, or remove `roles.manage` from the `admin` role.
- Signup always creates a `candidate`; the role cannot be chosen by the client.
  Recruiter and admin accounts are created only via `roles.manage`.

---

## 4. Backend modules

### `backend/security.py` (new)
- `hash_password(raw) -> str` / `verify_password(raw, hash) -> bool` — Argon2id
  via `argon2-cffi`.
- `new_session_token() -> str` — `secrets.token_hex(32)`.
- Login throttle: in-process dict keyed by `(email, client_ip)`, N=10 failures
  per 15 minutes → `429` with `Retry-After`. Documented as per-process
  (acceptable for a single-process local deployment; a durable store is a
  follow-up if this is ever load-balanced).

### `backend/rbac.py` (new)
- `get_current_user(request, session) -> User` — reads the `session` cookie,
  looks up a non-expired `session` row, loads the `user`; raises `401` if
  missing/expired, `403` if `is_active` is false.
- `require(*permission_keys)` — FastAPI dependency factory returning a dependency
  that resolves the current user, loads their role's permission set once, and
  raises `403` unless **all** required keys are present.
- `user_permissions(user, session) -> set[str]`.

### `backend/auth.py` (new — `APIRouter`, mounted at `/api/auth`)

| Endpoint | Body | Behaviour |
|----------|------|-----------|
| `POST /signup` | `email, password, display_name` | Validate (email format; password ≥ 10 chars, ≤ 200; display_name 1–120). Create `user` with the `candidate` role. Create a session, set cookie. `409` if the email is already registered (generic "This email is already registered"). |
| `POST /login` | `email, password` | Generic `401` "Invalid email or password" on any failure (unknown email, bad password, inactive). On success: new session row + cookie. Throttled. |
| `POST /logout` | — | Delete the current session row; clear the cookie. Always `204`. |
| `GET /me` | — | `{ id, email, display_name, role: {id,name}, permissions: [...], profile: {...} | null }`. `401` if unauthenticated. |

Cookie: name `session`, value = token, `HttpOnly`, `SameSite=Lax`, `Path=/`,
`Max-Age` = 14 days, `Secure` when the request scheme is https. `SameSite=Lax`
plus JSON-only request bodies (no cross-site form posts) is the CSRF stance;
residual risk on a LAN tool is minimal and noted in §9.

### `backend/candidate.py` (new — `/api/candidate`, `/api/me`)

| Endpoint | Perm | Behaviour |
|----------|------|-----------|
| `PUT /api/candidate/profile` | `test.take` | Upsert the caller's `candidate_profile` (`full_name`, `phone`, `city?`, `first_language?`). Validated lengths. |
| `GET /api/me/attempts` | `test.take` | The caller's own attempts (id, status, created_at) for a "your results" list. |

### Admin management (in `auth.py` or a `backend/admin.py`, `/api/admin`, all `require("roles.manage")`)

- `GET /users`, `POST /users` (`email, password, display_name, role_id`),
  `PATCH /users/{id}` (`role_id?`, `is_active?`, `password?`) — with the §3
  lock-out guards.
- `GET /roles`, `POST /roles` (`name`), `PATCH /roles/{id}` (`permission_keys: [...]`
  — full replace), `DELETE /roles/{id}` (non-system, no assigned users).
- `GET /permissions` — the catalogue for the role editor.

### Changes to existing endpoints in `backend/main.py`

| Endpoint | Change |
|----------|--------|
| `POST /api/attempts` | `require("test.take")`. Ignore any client-supplied `name`; require the caller has a `candidate_profile` (else `409` "Complete your profile first"). Set `attempt.user_id` and `attempt.name = profile.full_name`. Keep the `item_ids` seed-only hook. |
| `GET /api/attempts/{id}/items` | Authenticate; `404` unless `attempt.user_id == current_user.id`. (Unchanged otherwise.) |
| `POST /api/attempts/{id}/response` | Same ownership check. |
| `POST /api/attempts/{id}/audio` | Same ownership check. |
| `POST /api/attempts/{id}/submit` | Same ownership check. |
| `GET /api/attempts/{id}/report` | Allowed if (`report.view_own` **and** owner) **or** `candidates.view`. |
| `GET /api/attempts` | Now `require("candidates.view")` — this is the recruiter-facing list. Returns `name`, `status`, `created_at`, `user_id`. |

`on_startup` also calls `seed_auth()` (idempotent — see §5).

---

## 5. Seeding — `backend/seed_auth.py` (new)

Idempotent, run from `on_startup` and available as a script:

1. Upsert the permission catalogue (§3).
2. Upsert the three system roles with `is_system = True`.
3. Ensure each system role has its seeded permissions; additionally re-grant to
   `admin` any permission it is missing.
4. If **no** user with the `admin` role exists, create one from `ADMIN_EMAIL` /
   `ADMIN_PASSWORD` env vars. If those are unset, create
   `admin@example.com` with a random password **printed once to the log** and a
   loud warning to change it. Never commit a default password.

`backend/seed_attempts.py` is updated to create a throwaway candidate user +
profile and stamp `user_id` on its seeded attempts.

---

## 6. Schema handling

The dev database (`backend/demo.db`) holds only seeded / throwaway data. As with
the existing `_assert_attempt_schema_current` guard in `db.py`:

- `init_db()` calls `SQLModel.metadata.create_all` (creates the new tables) and
  then a guard that raises a clear error if the `attempt` table exists without a
  `user_id` column — message: *"delete backend/demo.db and restart to recreate
  the schema"*.
- No data migration is written. Documented in `BUILD_LOG.md`.

---

## 7. Frontend

### Routing — add `react-router-dom`

The app currently has no router (`App.jsx` switches on `window.location.pathname`
plus a `useState` screen machine). Guarded multi-page navigation with
role-dependent redirects is exactly what a router is for; hand-rolling it is the
more error-prone path (`ENGINEERING_RULES.md` §25 — the framework does not
already solve this). Add `react-router-dom`.

Routes:

| Path | Guard | Content |
|------|-------|---------|
| `/login` | public (redirect to home if authed) | `Login.jsx` |
| `/signup` | public | `Signup.jsx` |
| `/profile` | `test.take` | `Profile.jsx` — candidate details form |
| `/test` | `test.take` + profile exists | the current candidate state machine (Start → DeviceCheck → Test → Submitting → Report), moved out of `App.jsx` into `screens/CandidateFlow.jsx` |
| `/report/:attemptId` | `report.view_own` or `candidates.view` | `Report.jsx` |
| `/dashboard` | `candidates.view` | placeholder in WS1, built in WS3 |
| `/admin` | `roles.manage` | minimal role/user list in WS1, expanded in WS3/WS4 |
| `/` | authed | redirect by role: candidate → `/test` (or `/profile` if none), recruiter → `/dashboard`, admin → `/admin` |

### `src/auth/AuthContext.jsx` (new)
- On mount, `GET /api/auth/me`; expose `{ user, permissions, loading, refresh, logout }`.
- `has(permission)` helper.
- A `401` from any API call clears the context and routes to `/login`
  (interceptor in `api.js`).

### `src/auth/RequireAuth.jsx` (new)
- `<RequireAuth permission="candidates.view">` — waits for `loading`, redirects
  to `/login` when unauthenticated, renders a 403 page when authenticated but
  lacking the permission, else renders children.

### `src/api.js`
- All requests get `credentials: 'include'`.
- Add `signup`, `login`, `logout`, `getMe`, `putProfile`, `getMyAttempts`, and
  the admin calls.
- Central response handler: on `401`, dispatch a logout event.

### Screen changes
- **`Start.jsx`** currently collects the candidate's name. Name now comes from
  the profile, so Start becomes a plain "Start Test" screen (candidate name
  shown read-only, a "Begin" button). The name `<input>` is removed.
- **`Profile.jsx`** (new) — the fields from `candidate_profile`; on save →
  `/test`.
- **`App.jsx`** slims to `<BrowserRouter>` + `<AuthProvider>` + `<Routes>`. The
  `RecruiterApp` / `CandidateApp` split is replaced by routes.
- The `localStorage` resume logic (`session.js`) is kept, still keyed by
  attempt; auth persistence is the cookie's job.

---

## 8. Known limitations (stated per `ENGINEERING_RULES.md` §22)

- Single-process login throttle — resets on restart, not shared across
  processes.
- No email verification: a candidate can sign up with any address.
- Password reset is admin-mediated only.
- CSRF defense is `SameSite=Lax` + JSON-only bodies, no token — adequate for a
  LAN / single-operator tool, not for a public multi-tenant deployment.
- Multi-tenancy is absent; every recruiter/admin sees every candidate. This is
  a deliberate deferral, called out against production-PRD §6.
- Sessions are a fixed 14-day expiry with no sliding renewal.

---

## 9. Security review (`ENGINEERING_RULES.md` §9–11, §19)

- **Passwords:** Argon2id, never logged, never returned. Login and signup
  failure messages do not distinguish cause (except the deliberate signup
  `409`).
- **Session tokens:** 256-bit random, compared via `secrets.compare_digest`,
  `HttpOnly` so JS cannot read them, `Secure` on https. Logout and deactivation
  delete/deny immediately.
- **Authorization:** every endpoint declares a permission via `require(...)`;
  attempt-scoped endpoints additionally check row ownership (IDOR/BOLA — §11).
  No endpoint trusts a client-supplied role or user id.
- **Input validation:** Pydantic models on every body — email format, string
  lengths, enum values; `role_id` / `permission_key` checked to exist.
- **Privilege escalation:** client cannot pick its role at signup; the §3
  lock-out guards stop an admin from removing their own access; `PATCH /users`
  cannot set a role id that does not exist.
- **Enumeration:** login is generic; `GET /me` only ever returns the caller.
- **Secrets:** `ADMIN_PASSWORD`, and any future signing secret, come from env;
  `.env` is git-ignored; the seeder refuses to embed a default password in code.

---

## 10. Error states (`ENGINEERING_RULES.md` §20)

Unauthenticated (`401`) → redirect to `/login`. Authenticated but forbidden
(`403`) → in-app "You don't have access" page. Inactive account (`403` on
login/session) → generic message. Expired session → treated as `401`. Duplicate
signup → `409`. Throttled login → `429` + `Retry-After`. Role delete with users
→ `409`. Profile missing on attempt creation → `409` with a redirect to
`/profile`. DB failure → `500`, generic body, exception logged server-side.
Network failure in the client → existing toast pattern.

---

## 11. Testing

**Backend (pytest)**
- `security`: hash/verify round-trip; wrong password fails; throttle triggers at
  the 11th failure and clears after the window.
- `rbac`: `require` passes with the exact permission, `403` without; multi-permission
  requires all; inactive user `403`; missing or expired session `401`.
- `auth`: signup creates a `candidate` and a session; signup with an existing
  email `409`; login sets a cookie; wrong password generic `401`; logout
  invalidates the token; `/me` returns the permission set and profile.
- Onboarding: `POST /api/attempts` `409` before a profile exists, succeeds after,
  stamps `user_id` and `name`.
- IDOR: candidate A `404`s on candidate B's `/items`, `/response`, `/audio`,
  `/submit`, `/report`; a recruiter can read B's `/report` but not `/items`.
- Admin: create recruiter user; create a custom role with a chosen permission
  set and confirm a user with it is authorised accordingly; cannot delete a
  system role; cannot delete a role with users; admin cannot deactivate self or
  drop `roles.manage` from `admin`; admin resets another user's password and the
  new password works.
- Seeder: idempotent across two runs; adds a new permission to `admin` on the
  second run; creates exactly one default admin.
- Regression: the full existing attempt→score→report flow still passes with an
  authenticated candidate.

**Frontend (vitest)**
- Unauthenticated visit to a guarded route redirects to `/login`.
- After login, `/` redirects by role (candidate/recruiter/admin).
- New candidate with no profile is sent to `/profile`; after saving, reaches
  `/test`.
- `RequireAuth` renders the 403 page for a recruiter hitting `/admin`.
- A `401` from an API call logs the user out and routes to `/login`.
- `Start` no longer renders a name input; begins an attempt directly.
- Logout clears `AuthContext` and returns to `/login`.

**Manual**
- Fresh `demo.db`: seeder prints the admin password once; log in as admin,
  create a recruiter, create a candidate; candidate completes a test; recruiter
  opens the candidate's report; recruiter is blocked from `/admin`.

---

## 12. Files

**New — backend:** `security.py`, `rbac.py`, `auth.py`, `candidate.py`,
`admin.py`, `seed_auth.py`, and their tests.
**New — frontend:** `src/auth/AuthContext.jsx`, `src/auth/RequireAuth.jsx`,
`src/screens/Login.jsx`, `src/screens/Signup.jsx`, `src/screens/Profile.jsx`,
`src/screens/CandidateFlow.jsx`, `src/screens/Forbidden.jsx`, and tests.
**Modified — backend:** `models.py`, `db.py`, `main.py`, `requirements.txt`
(`argon2-cffi`), `seed_attempts.py`.
**Modified — frontend:** `App.jsx`, `main.jsx`, `api.js`, `screens/Start.jsx`,
`package.json` (`react-router-dom`).
**Modified — docs:** `BUILD_LOG.md`, `04-tech-stack.md` (§6 row: auth now
present), and this file's status.
