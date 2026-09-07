# Question Bank, Per-Question Timers, and Test-Flow Features — Design

**Date:** 2026-09-07
**Status:** Implemented (2026-09-07)
**Relationship to demo PRD (`02-demo-prd.md`):** deliberate expansion. The demo
PRD cut "item bank CRUD / admin UI" and "adaptive selection, item rotation"
because no pool existed. This design adds a randomised pool and per-attempt
selection while keeping the "items live in a file, no admin UI" constraint.

---

## 1. Goals

1. Serve each attempt a random subset drawn from a bank of ~150 items instead
   of the same fixed 9.
2. Give every non-speaking question its own countdown timer that auto-advances
   and locks on expiry, plus a global test timer as a backstop.
3. Add three low-risk flow features: randomised MCQ option order per attempt,
   a section-aware progress bar, and resume-after-refresh.

Non-goals: admin CRUD, a `Question` database table, difficulty-adaptive
selection, tab-switch proctoring, retake prevention, expanded report
breakdowns. These are noted as possible follow-ups, not built.

---

## 2. Test shape per attempt

| Section   | Count | Notes |
|-----------|-------|-------|
| Grammar   | 5     | uniform random from ~80, one drawn per sub-skill where possible |
| Listening | 2     | the existing 2 fixed items (audio recording is the content bottleneck) |
| Writing   | 1     | uniform random from ~30 prompts |
| Speaking  | 2     | 1 read-aloud + 1 situational, uniform random from ~10 each |

Total 10 items. Global test timer: **12 minutes** (PRD target is "under 10";
the extra 2 min is slack for the added grammar item and reading time).

---

## 3. Data — `backend/bank.json`

Replaces `backend/items.json`. Same per-item shape as today plus two additions:

```json
{
  "items": [
    {
      "id": "g001",
      "section": "grammar",
      "type": "mcq",
      "subskill": "subject_verb",
      "time_limit_s": 40,
      "prompt": "...",
      "options": ["is", "are", "were", "have"],
      "answer": "a"
    }
  ]
}
```

- `subskill`: grammar uses `subject_verb | tense | preposition | vocab`.
  Informational for other sections.
- `time_limit_s`: required on every item. Grammar 40s, listening 60s (plus
  clip length), writing 180s (unchanged), speaking keeps its existing
  `time_limit_s` + `prep_s` semantics.
- `answer` stays server-side only, as today.

Content is drafted by the assistant (grammar / writing / speaking) and
reviewed by the user before merge. Listening keeps the two existing items and
their `.wav` files.

Item counts: grammar ~80, writing ~30, speaking ~10 read-aloud + ~10
situational, listening 2. The bank must always be large enough to fill
section 2's counts; a startup check enforces this.

---

## 4. Selection — `backend/selection.py` (new module)

```python
def select_items(bank_by_section: dict[str, list[dict]], rng: random.Random) -> list[str]:
    """Return an ordered list of item ids for one attempt.
    Order: grammar (5), listening (2), writing (1), speaking (read_aloud, situational).
    Raises SelectionError if any section cannot be filled."""

def option_permutations(items: list[dict], rng: random.Random) -> dict[str, list[int]]:
    """For each mcq item, a permutation of its option indices. Non-mcq items absent."""
```

- Grammar: attempt to draw one item per sub-skill first, then fill the
  remaining slots uniformly at random from the rest. Falls back to pure
  uniform random if sub-skill tags are sparse.
- RNG is seeded from the attempt id so a selection is reproducible when
  debugging a specific attempt.
- `SelectionError` → `create_attempt` returns HTTP 500 with a logged reason
  and no user-facing internals. Guarded but not expected to fire.

---

## 5. Schema — `backend/models.py`

Add to `Attempt`:

```python
item_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
option_order: dict[str, list[int]] = Field(default_factory=dict, sa_column=Column(JSON))
```

The dev SQLite file is created fresh by `init_db()` and holds only seeded /
throwaway data, so this is a table-shape change, not a data migration. The
seed scripts (`seed_attempts.py`, `seed_audio.ps1`) are updated to populate
`item_ids` for their fixed item set.

---

## 6. Endpoints — `backend/main.py`

| Endpoint | Change |
|----------|--------|
| `POST /api/attempts` | Run `select_items` + `option_permutations`, persist both on the attempt, return `attempt_id`. |
| `GET /api/items` | **Removed.** |
| `GET /api/attempts/{id}/items` | **New.** Returns only that attempt's items in attempt order, MCQ `options` reordered per `option_order`, `answer` stripped. 404 if attempt unknown; 409 if not `in_progress`. |
| `POST /api/attempts/{id}/response` | Validate `item_id ∈ attempt.item_ids` (replaces the global `_ITEM_IDS` check). Map the submitted option index back to the canonical letter using `option_order` before storing, OR store the raw selection and map at scoring time — **decision: store the canonical letter at submit time**, so `Response.text` stays comparable to `answer` and the scoring code is unchanged in shape. |
| `POST /api/attempts/{id}/audio` | Same `item_id ∈ attempt.item_ids` validation. |
| `POST /api/attempts/{id}/submit` | Build section lists from `attempt.item_ids` (look each up in `_ITEMS_BY_ID`) instead of `_ITEMS_BY_SECTION`. |
| `GET /api/attempts/{id}/report` | Unchanged. |
| `GET /api/attempts` | Unchanged. |

Startup (`on_startup`): load `bank.json`, build `_ITEMS_BY_ID` (full lookup)
and `_BANK_BY_SECTION` (for selection). Assert each section has enough items
for its selection count; log and refuse startup otherwise.

`_ITEMS_PUBLIC` / the global "serve all items" path is deleted.

---

## 7. Scoring — `backend/scoring/pipeline.py` and `objective.py`

- `submit_attempt` passes `items_by_section` scoped to the attempt (only the
  selected items), so `score_section` counts `total` correctly (e.g. 5 grammar,
  not 80). `objective.py` itself is unchanged.
- `run_scoring_pipeline` signature already takes `items_by_section`; the caller
  now passes the attempt-scoped dict. `items_by_id` stays the full bank lookup.
- Because option shuffling is resolved to the canonical letter at submit time
  (§6), `objective.score_section`'s `given == item["answer"]` comparison needs
  no change.
- `band_from_ratio` thresholds are unaffected — ratio is still correct/total
  within the attempt's items.

**Verification of D2 (scores discriminate proficiency):** selection is random
but within-section difficulty is currently untagged, so two attempts may draw
easier/harder grammar sets. This is an accepted limitation for grammar/listening
(objective, answer-key scored). Speaking — the PRD's "centre of gravity" — is
scored on fluency features and judge rubric, not item identity, so random draw
of the speaking prompt does not threaten D2. Documented in §11.

---

## 8. Timers — `frontend/src/components/Timer.jsx`, `screens/Test.jsx`

- **Per-question:** `Test.jsx` renders `<Timer>` for every non-speaking item
  from `item.time_limit_s`. On expire: persist the current answer (if any) via
  the existing `submitResponse`, then advance; last item → `onComplete()`. No
  return to a prior item.
- **Global timer:** a 12-minute countdown in the `Test` header, independent of
  item changes. On expiry → immediately call `onComplete()` (submit what
  exists). Lives in `Test.jsx` state, started when the test screen mounts.
- `Timer.jsx`: add an amber visual state under 10 seconds remaining. Existing
  `itemKey`-based restart behaviour is kept for the per-question instance; the
  global instance gets a fixed `itemKey`.
- Speaking prep/record flow (`SpeakingItem.jsx`) is unchanged.

Edge case: a slow network `submitResponse` on expiry must not block the
advance. The advance happens immediately; the save is fire-and-forget with the
existing error toast on failure (answers are also re-sent on the next
navigation, matching current behaviour).

---

## 9. Resume after refresh — `frontend/src/App.jsx`

- On entering the test, persist `{ attemptId, screen, index }` to
  `localStorage` under a single key. Update on every item advance and screen
  change.
- On app load: if the key holds an attempt whose `GET /api/attempts/{id}/items`
  still returns 200 with status `in_progress`, rehydrate — re-fetch items, set
  `screen='test'`, jump to the saved `index`. Server-side `Response` rows mean
  prior answers are already saved; only navigation state is restored.
- Clear the key on reaching the report screen, on a fresh Start, or when the
  stored attempt returns 404 / 409 (already submitted).
- Global timer after resume: restart from full 12 min (we do not persist test
  start time). Accepted — resume is an accident-recovery path, not a way to
  pause.

---

## 10. Progress bar — `frontend/src/components/Progress.jsx` (new)

- Props: the attempt's items and the current index.
- Renders section chips in order (`Grammar 3/5 · Listening · Writing ·
  Speaking`) with the active section highlighted and completed sections
  marked. Derived purely from the item list; no new state.
- Placed in the `Test` header above the item.

---

## 11. Known limitations (state aloud, per PRD §10 discipline)

- Listening stays at 2 fixed items — recorded-audio content is the bottleneck,
  same limitation the PRD already declares.
- No difficulty tags yet, so random draw can vary grammar difficulty between
  candidates. Sub-skill coverage is held constant to reduce this. Difficulty
  stratification is a follow-up once calibration data exists.
- Global timer resets on refresh-resume (no persisted start time).
- Bank content is assistant-drafted and user-reviewed, not expert-authored or
  calibrated — same status the PRD gives the existing 9 items.

---

## 12. Testing

**Backend**
- `selection.py`: exact counts per section; no duplicate ids; deterministic for
  a fixed seed; `SelectionError` when a section is underfilled; sub-skill
  spread when tags are present.
- `option_permutations`: every mcq item present, each value a valid permutation
  of its option index range; non-mcq absent.
- Endpoint: `GET /api/attempts/{id}/items` never includes `answer`; options
  match `option_order`; 404/409 paths.
- Endpoint: `submit_response` rejects an `item_id` not in the attempt; stores
  the canonical letter given a shuffled index.
- Scoring: an attempt scores the same band regardless of which subset was
  drawn, holding responses' correctness fixed; shuffled options score
  correctly against the key; `total` reflects the attempt's item count.
- Startup refuses to boot if `bank.json` cannot fill a section.

**Frontend**
- Per-question timer expiry advances and locks; last item submits.
- Global timer expiry routes to submit.
- Amber state under 10s.
- Resume: mid-test reload restores the same item index; prior answers still
  present (served by the backend); submitted/unknown attempt clears storage
  and starts fresh.
- Progress bar reflects section and position.

**Manual**
- Full attempt with wifi disabled (PRD D4) still passes.
- Full attempt completes under the global timer (PRD D5).

---

## 13. Files touched

**New:** `backend/bank.json`, `backend/selection.py`,
`frontend/src/components/Progress.jsx`, plus test files.
**Removed:** `backend/items.json`.
**Modified:** `backend/main.py`, `backend/models.py`,
`backend/scoring/pipeline.py`, `backend/seed_attempts.py`,
`backend/seed_audio.ps1`, `frontend/src/App.jsx`,
`frontend/src/api.js`, `frontend/src/screens/Test.jsx`,
`frontend/src/components/Timer.jsx`, `frontend/README.md` /
`BUILD_LOG.md` as needed.
