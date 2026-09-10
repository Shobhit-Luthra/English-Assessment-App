# English Proficiency Assessment Tool — Fix & Build List

## 1. Bug Fixes

- [x] **Speaking recording — stop button (admin side)**
  Stop button isn't working correctly during the speaking/recording section. Needs debugging — check event handler binding and whether the recording state is properly reset after stop.
  → Fixed: explicit `prep → starting → recording → finalizing → review` phases in `SpeakingItem.jsx`; stop during mic permission discards the stream instead of hanging (see commit for `useRecorder.js`).

- [x] **Speaking report UI (admin panel)**
  Current report view for speaking submissions is hard to read. Redesign so the admin can quickly see: candidate name, audio playback, transcript, and score breakdown per attempt — in one clean card/row instead of raw data.
  → Done: `Report.jsx` speaking cards now show band, transcript, expected read-aloud text, readable stat chips, and attempt id.

- [x] ~~**Language switch timing**~~ (Not applicable)
  Hindi (or other language) selection currently happens *inside* the test flow. Move it to the onboarding/start screen, before the test begins — it shouldn't be selectable mid-test.
  → Verified: no in-test language selector exists anywhere. The only language field is `first_language` on the Profile (onboarding) page, which already sits before the test.

## 2. Speech/Scoring API

- [x] ~~Switch to the Grok API for scoring/evaluation~~ (Deferred — using local Ollama)
  > Note: Grok is a text/reasoning LLM (from xAI), not a speech-to-text engine. If the speaking section still needs audio transcribed first, keep (or pick) a dedicated speech-to-text step (e.g., Whisper, Azure Speech, Deepgram) and feed the transcript into Grok for grammar/fluency/CIR scoring. Confirm this split before building, so the pipeline is: **audio → transcript (STT) → Grok (scoring/feedback)**.
  → Pipeline confirmed: audio → Whisper (STT) → local judge. Judge is currently **Ollama `qwen3:8b`**, which required bumping `num_predict` to 2400 (qwen3 is a thinking model and exhausts small budgets before emitting JSON). Grok API path was implemented then dropped by decision; the scoring integration point is isolated to `scoring/judge.py` if we revisit (keep Whisper STT, swap the judge).

## 3. Onboarding & Auth Flow

- [x] Fix login/signup → onboarding sequence:
  1. User logs in / signs up
  2. Lands on **Name/details page** (candidate profile capture)
  3. Sees **Start Test** button
  4. Test begins
  → Done: `Start.jsx` is now an explicit Start Test gate; profile capture lives on the Profile screen; tests added.

- [x] Implement **RBAC (Role-Based Access Control)** — customizable roles, not hardcoded. Should support adding/removing roles and permissions without code changes (e.g., a roles/permissions table).
  → Done: roles + permissions tables in the DB; seeded admin (all permissions) + recruiter (`candidates.view/decide`, `analytics.view`); admin UI manages user roles.

## 4. Roles

### Recruiter (new, scoped)
- [x] Add **Recruiter** role with its own dashboard view.
- [x] Recruiter can view analytics for **every candidate** who has taken the test (scores, section breakdown, attempt history).
- [x] Per-candidate action buttons: **Hire** / **Reject** — updates candidate status.
- [x] Recruiter's view is scoped to candidates/analytics only — no access to system/admin settings.

### Admin (full access)
- [x] Admin retains full visibility: everything Recruiter sees, plus all roles' activity, RBAC/role management, and system settings.
- [x] Admin can see Hire/Reject decisions made by recruiters.

## 5. Admin Panel

- [x] General admin panel improvements (ties into speaking report UI fix above).
- [x] Ensure admin can see all roles' activity (candidates, recruiters).

## 6. Analytics Page (Overall)

- [x] Build an aggregate analytics dashboard: total candidates tested, pass/fail rate, average scores per section (speaking/listening/reading-writing/grammar), Hire vs Reject breakdown.
  → Done: `GET /api/analytics/overview` + `Analytics.jsx` (stat tiles, section bars, distributions).

## 7. UI Revamp — Clean, Minimal (avoid "AI slop" defaults)

- [x] Full UI redesign across the app (candidate-facing test flow + admin/recruiter dashboards) — not just the speaking report screen.
- [x] Direction: **clean and minimal**, not the generic AI-generated look. Explicitly avoid:
  - Rounded cards everywhere with the same soft grey drop-shadow on all of them
  - Gradient washes used as decoration
  - ALL-CAPS tracked-out labels above every heading
  - Middle-dot separators ("A · B · C") or em-dash labels ("WORD — fragment")
  - A "→" tacked onto every button/link
  - The cliché warm-cream + terracotta-accent palette, or near-black + single neon-accent palette
- [x] Instead: pick **one deliberate accent color**, a plain neutral base (white/light grey or a real dark theme, not a tinted "#111"), one type scale used consistently, and let structure (spacing, alignment, dividers) do the work instead of decoration. Differentiate hierarchy through weight/size, not by wrapping everything in a card.
  → Palette chosen: single deep-blue accent (`blue-700` #1d4ed8) on a white/gray-50 base; shadows/gradients/tracked caps removed; hierarchy via structure and borders.
- [x] Candidate-facing test screens should feel calm and distraction-free (this is a test, not a landing page) — admin/recruiter dashboards should prioritize scannable data over visual flourish.
- [x] ~~Still open: any brand colors you already use, or should this pick a fresh minimal palette from scratch?~~ → Resolved: fresh palette from scratch (deep-blue accent above).

---

## Suggested Priority Order

1. Fix stop button + report UI (blocking usability)
2. Onboarding/auth flow fix
3. RBAC + Recruiter role (scoped) + Admin (full access)
4. UI revamp
5. Analytics page
6. Language switch relocation
7. Grok integration (confirm STT pairing first)
