# English Proficiency Assessment Tool — Fix & Build List

## 1. Bug Fixes

- [ ] **Speaking recording — stop button (admin side)**
  Stop button isn't working correctly during the speaking/recording section. Needs debugging — check event handler binding and whether the recording state is properly reset after stop.

- [ ] **Speaking report UI (admin panel)**
  Current report view for speaking submissions is hard to read. Redesign so the admin can quickly see: candidate name, audio playback, transcript, and score breakdown per attempt — in one clean card/row instead of raw data.

- [ ] **Language switch timing**
  Hindi (or other language) selection currently happens *inside* the test flow. Move it to the onboarding/start screen, before the test begins — it shouldn't be selectable mid-test.

## 2. Speech/Scoring API

- [ ] Switch to the **Grok API** for scoring/evaluation.
  > Note: Grok is a text/reasoning LLM (from xAI), not a speech-to-text engine. If the speaking section still needs audio transcribed first, keep (or pick) a dedicated speech-to-text step (e.g., Whisper, Azure Speech, Deepgram) and feed the transcript into Grok for grammar/fluency/CIR scoring. Confirm this split before building, so the pipeline is: **audio → transcript (STT) → Grok (scoring/feedback)**.

## 3. Onboarding & Auth Flow

- [ ] Fix login/signup → onboarding sequence:
  1. User logs in / signs up
  2. Lands on **Name/details page** (candidate profile capture)
  3. Sees **Start Test** button
  4. Test begins

- [ ] Implement **RBAC (Role-Based Access Control)** — customizable roles, not hardcoded. Should support adding/removing roles and permissions without code changes (e.g., a roles/permissions table).

## 4. Roles

### Recruiter (new, scoped)
- [ ] Add **Recruiter** role with its own dashboard view.
- [ ] Recruiter can view analytics for **every candidate** who has taken the test (scores, section breakdown, attempt history).
- [ ] Per-candidate action buttons: **Hire** / **Reject** — updates candidate status.
- [ ] Recruiter's view is scoped to candidates/analytics only — no access to system/admin settings.

### Admin (full access)
- [ ] Admin retains full visibility: everything Recruiter sees, plus all roles' activity, RBAC/role management, and system settings.
- [ ] Admin can see Hire/Reject decisions made by recruiters.

## 5. Admin Panel

- [ ] General admin panel improvements (ties into speaking report UI fix above).
- [ ] Ensure admin can see all roles' activity (candidates, recruiters).

## 6. Analytics Page (Overall)

- [ ] Build an aggregate analytics dashboard: total candidates tested, pass/fail rate, average scores per section (speaking/listening/reading-writing/grammar), Hire vs Reject breakdown.

## 7. UI Revamp — Clean, Minimal (avoid "AI slop" defaults)

- [ ] Full UI redesign across the app (candidate-facing test flow + admin/recruiter dashboards) — not just the speaking report screen.
- [ ] Direction: **clean and minimal**, not the generic AI-generated look. Explicitly avoid:
  - Rounded cards everywhere with the same soft grey drop-shadow on all of them
  - Gradient washes used as decoration
  - ALL-CAPS tracked-out labels above every heading
  - Middle-dot separators ("A · B · C") or em-dash labels ("WORD — fragment")
  - A "→" tacked onto every button/link
  - The cliché warm-cream + terracotta-accent palette, or near-black + single neon-accent palette
- [ ] Instead: pick **one deliberate accent color**, a plain neutral base (white/light grey or a real dark theme, not a tinted "#111"), one type scale used consistently, and let structure (spacing, alignment, dividers) do the work instead of decoration. Differentiate hierarchy through weight/size, not by wrapping everything in a card.
- [ ] Candidate-facing test screens should feel calm and distraction-free (this is a test, not a landing page) — admin/recruiter dashboards should prioritize scannable data over visual flourish.
- [ ] Still open: any brand colors you already use, or should this pick a fresh minimal palette from scratch?

---

## Suggested Priority Order

1. Fix stop button + report UI (blocking usability)
2. Onboarding/auth flow fix
3. RBAC + Recruiter role (scoped) + Admin (full access)
4. UI revamp
5. Analytics page
6. Language switch relocation
7. Grok integration (confirm STT pairing first)
