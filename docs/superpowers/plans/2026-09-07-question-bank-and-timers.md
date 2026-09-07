# Question Bank, Per-Question Timers, and Test-Flow Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve each attempt a random subset from a ~150-item file-based question bank, give every question its own auto-advancing countdown timer plus a global test timer, and add randomised MCQ option order, a section progress bar, and resume-after-refresh.

**Architecture:** The bank stays a JSON file (`backend/bank.json`) loaded once at startup into an id-keyed lookup. On attempt creation the server draws a per-section random subset, persists the ordered item id list and a per-MCQ option permutation on the `Attempt` row, and serves only those items with the answer key stripped and options pre-shuffled. `submit_response` resolves the shuffled option back to the canonical answer letter at write time, so the existing answer-key scoring code is unchanged in shape; scoring is scoped to the attempt's item ids. The frontend fetches items per-attempt, runs a timer per item that saves-and-advances on expiry, and persists navigation state to `localStorage` for refresh recovery.

**Tech Stack:** Backend — FastAPI, SQLModel, SQLite, pytest (new dev dependency). Frontend — React 19, Vite, Tailwind, Vitest + @testing-library/react + jsdom (new dev dependencies).

**Spec:** `docs/superpowers/specs/2026-09-07-question-bank-and-timers-design.md`

## Global Constraints

- Bank is a file (`backend/bank.json`), no `Question` DB table, no admin UI.
- The MCQ answer key (`answer` field) is NEVER sent to the client during a test.
- Test shape per attempt: **5 grammar, 2 listening, 1 writing, 2 speaking (1 read_aloud + 1 situational)** = 10 items.
- Global test timer: **12 minutes** (720 seconds).
- Per-item `time_limit_s` (seconds): grammar `40`, listening `60`, writing `180`, speaking read_aloud `30` + `prep_s` `10`, speaking situational `45` + `prep_s` `20`. (Writing/speaking values unchanged from today.)
- Grammar sub-skill tag values: `subject_verb | tense | preposition | vocab`.
- Item id conventions: grammar `g001`..`gNNN`, listening `l1`,`l2` (unchanged), writing `w001`..`wNNN`, speaking `s001`..`sNNN`. The existing seeded item ids `g1 g2 g3 g4 l1 l2 w1 s1 s2` MUST remain valid ids in the bank (seed attempts depend on them).
- No AI/Claude/Anthropic authorship or co-authorship in git commits (`ENGINEERING_RULES.md` §7). Use the repo's configured git identity.
- Security review the diff before every commit (`ENGINEERING_RULES.md` §6).
- `demo.db` and `backend/audio/` are gitignored runtime state — never commit them.

---

### Task 1: Backend test tooling, `bank.json`, startup load + validation, `Attempt` columns

**Files:**
- Create: `backend/bank.json`
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_startup.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/models.py` (add two columns to `Attempt`, lines 12-17)
- Modify: `backend/main.py` (startup + module globals, lines 21-73)
- Delete: `backend/items.json`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `backend/bank.json` shape: `{"items": [ {id, section, type, subskill?, time_limit_s, ...} ]}`.
  - `main.py` module globals: `_ITEMS_BY_ID: dict[str, dict]` (full bank, includes `answer`), `_BANK_BY_SECTION: dict[str, list[dict]]` (full bank grouped by section).
  - `main.py` constant: `SELECTION_COUNTS: dict[str, int] = {"grammar": 5, "listening": 2, "writing": 1, "speaking": 2}`.
  - `main.py` function `_load_bank() -> None` — populates the globals from `BANK_PATH`, raises `RuntimeError` if any section in `SELECTION_COUNTS` has fewer items than its count (for `speaking`, requires ≥1 `read_aloud` and ≥1 `situational`).
  - `Attempt.item_ids: list[str]` (JSON column, default `[]`), `Attempt.option_order: dict[str, list[int]]` (JSON column, default `{}`).

- [ ] **Step 1: Add pytest to requirements**

Append to `backend/requirements.txt`:

```
pytest==8.3.4
```

Install: `cd backend && .venv/Scripts/python.exe -m pip install pytest==8.3.4`

- [ ] **Step 2: Create `backend/pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 3: Create `backend/bank.json` with the existing 9 items (content expansion is Task 7)**

Port every item from the current `backend/items.json` verbatim, adding `subskill` to the four grammar items and `time_limit_s` where missing. Keep ids `g1 g2 g3 g4 l1 l2 w1 s1 s2`.

```json
{
  "items": [
    { "id": "g1", "section": "grammar", "type": "mcq", "subskill": "subject_verb", "time_limit_s": 40,
      "prompt": "Each of the employees ___ required to complete the training by Friday.",
      "options": ["is", "are", "were", "have"], "answer": "a" },
    { "id": "g2", "section": "grammar", "type": "mcq", "subskill": "tense", "time_limit_s": 40,
      "prompt": "By the time the manager arrived, the meeting ___ already started.",
      "options": ["has", "have", "had", "was"], "answer": "c" },
    { "id": "g3", "section": "grammar", "type": "mcq", "subskill": "preposition", "time_limit_s": 40,
      "prompt": "The customer complained ___ the delay in her order.",
      "options": ["about", "for", "at", "with"], "answer": "a" },
    { "id": "g4", "section": "grammar", "type": "mcq", "subskill": "vocab", "time_limit_s": 40,
      "prompt": "The representative's response was extremely ___, addressing every concern the customer raised.",
      "options": ["vague", "thorough", "brief", "delayed"], "answer": "b" },
    { "id": "l1", "section": "listening", "type": "mcq", "time_limit_s": 60,
      "audio": "/static/listening/call1.wav",
      "prompt": "What is the customer calling about?",
      "options": ["To cancel their service", "To dispute an unexpected charge on their bill",
                  "To upgrade their router", "To change their billing address"], "answer": "b" },
    { "id": "l2", "section": "listening", "type": "mcq", "time_limit_s": 60,
      "audio": "/static/listening/call2.wav",
      "prompt": "What does the representative offer to resolve the issue?",
      "options": ["A discount code for a future order",
                  "Free overnight shipping and a refund of the shipping fee",
                  "A full refund of the order", "A gift card"], "answer": "b" },
    { "id": "w1", "section": "writing", "type": "text", "time_limit_s": 180, "word_target": 100,
      "prompt": "A customer's order is 5 days late and they are frustrated. Write an email reply." },
    { "id": "s1", "section": "speaking", "type": "read_aloud", "time_limit_s": 30, "prep_s": 10,
      "reference_text": "Thank you for calling our support line. I understand how frustrating a delayed delivery can be, and I want to make this right for you. Let me look into your order right now and find the fastest way to get it to you." },
    { "id": "s2", "section": "speaking", "type": "situational", "time_limit_s": 45, "prep_s": 20,
      "prompt": "A customer calls to say a product they ordered arrived broken and they are upset. Walk me through, step by step, how you would handle this call from the moment you pick up to how you would resolve it." }
  ]
}
```

- [ ] **Step 4: Write the failing startup test**

`backend/tests/conftest.py`:

```python
import json
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent


@pytest.fixture
def bank_dict():
    return json.loads((BACKEND_DIR / "bank.json").read_text(encoding="utf-8"))
```

`backend/tests/test_startup.py`:

```python
import pytest

import main


def test_load_bank_populates_globals():
    main._ITEMS_BY_ID.clear()
    main._BANK_BY_SECTION.clear()
    main._load_bank()
    assert "g1" in main._ITEMS_BY_ID
    assert main._ITEMS_BY_ID["g1"]["answer"] == "a"
    assert len(main._BANK_BY_SECTION["grammar"]) >= main.SELECTION_COUNTS["grammar"]


def test_every_bank_item_has_time_limit_and_valid_section():
    main._load_bank()
    valid_sections = set(main.SELECTION_COUNTS)
    for item in main._ITEMS_BY_ID.values():
        assert item["section"] in valid_sections
        assert isinstance(item["time_limit_s"], int) and item["time_limit_s"] > 0


def test_load_bank_rejects_underfilled_section(tmp_path, monkeypatch):
    thin = tmp_path / "bank.json"
    thin.write_text('{"items": [{"id": "g1", "section": "grammar", "type": "mcq", '
                    '"time_limit_s": 40, "options": ["a"], "answer": "a"}]}', encoding="utf-8")
    monkeypatch.setattr(main, "BANK_PATH", thin)
    main._ITEMS_BY_ID.clear()
    main._BANK_BY_SECTION.clear()
    with pytest.raises(RuntimeError, match="grammar"):
        main._load_bank()


def test_load_bank_requires_both_speaking_types(tmp_path, monkeypatch):
    data = '{"items": [' + ",".join(
        [f'{{"id": "g{i}", "section": "grammar", "type": "mcq", "time_limit_s": 40, '
         f'"options": ["a"], "answer": "a"}}' for i in range(5)]
        + ['{"id": "l1", "section": "listening", "type": "mcq", "time_limit_s": 60, "options": ["a"], "answer": "a"}',
           '{"id": "l2", "section": "listening", "type": "mcq", "time_limit_s": 60, "options": ["a"], "answer": "a"}',
           '{"id": "w1", "section": "writing", "type": "text", "time_limit_s": 180, "prompt": "x"}',
           '{"id": "s1", "section": "speaking", "type": "read_aloud", "time_limit_s": 30, "reference_text": "x"}',
           '{"id": "s2", "section": "speaking", "type": "read_aloud", "time_limit_s": 30, "reference_text": "x"}']
    ) + ']}'
    thin = tmp_path / "bank.json"
    thin.write_text(data, encoding="utf-8")
    monkeypatch.setattr(main, "BANK_PATH", thin)
    main._ITEMS_BY_ID.clear()
    main._BANK_BY_SECTION.clear()
    with pytest.raises(RuntimeError, match="situational"):
        main._load_bank()
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_startup.py -v`
Expected: FAIL — `AttributeError: module 'main' has no attribute '_load_bank'` (and `_BANK_BY_SECTION`, `SELECTION_COUNTS`, `BANK_PATH`).

- [ ] **Step 6: Add the two columns to `Attempt` in `backend/models.py`**

Replace the `Attempt` class body (lines 12-17) with:

```python
class Attempt(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    status: str = Field(default="in_progress")  # in_progress | scoring | done | error
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    item_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    option_order: dict[str, list[int]] = Field(default_factory=dict, sa_column=Column(JSON))
```

`Column` and `JSON` are already imported on line 5. The dev SQLite file is recreated by `init_db()`; delete `backend/demo.db` after this change so the new schema is created fresh (`rm -f backend/demo.db`).

- [ ] **Step 7: Rewrite the bank load + startup in `backend/main.py`**

Replace lines 21-46 (the `BASE_DIR`/`ITEMS_PATH` block and the four `_ITEM*` globals) with:

```python
BASE_DIR = Path(__file__).parent
BANK_PATH = BASE_DIR / "bank.json"
AUDIO_DIR = BASE_DIR / "audio"

SELECTION_COUNTS: dict[str, int] = {"grammar": 5, "listening": 2, "writing": 1, "speaking": 2}

# Fields never sent to the client while a test is in progress - "answer" is
# the MCQ answer key; leaking it lets a candidate read it from the network
# tab and always score 100%.
_ANSWER_KEY_FIELDS = {"answer"}

_ITEMS_BY_ID: dict[str, dict] = {}
_BANK_BY_SECTION: dict[str, list[dict]] = {}


def _load_bank() -> None:
    items = json.loads(BANK_PATH.read_text(encoding="utf-8"))["items"]
    _ITEMS_BY_ID.clear()
    _BANK_BY_SECTION.clear()
    for item in items:
        _ITEMS_BY_ID[item["id"]] = item
        _BANK_BY_SECTION.setdefault(item["section"], []).append(item)
    for section, count in SELECTION_COUNTS.items():
        pool = _BANK_BY_SECTION.get(section, [])
        if len(pool) < count:
            raise RuntimeError(
                f"bank.json section '{section}' has {len(pool)} items, needs at least {count}"
            )
    speaking_types = {i["type"] for i in _BANK_BY_SECTION.get("speaking", [])}
    if "read_aloud" not in speaking_types or "situational" not in speaking_types:
        raise RuntimeError(
            "bank.json speaking section must contain at least one 'read_aloud' and one 'situational' item"
        )
```

Then replace the `on_startup` body (lines 61-73) so it calls `_load_bank()` instead of the old inline parsing:

```python
@app.on_event("startup")
def on_startup() -> None:
    init_db()
    _load_bank()
    # Fire-and-forget: don't block server startup on Ollama being ready.
    threading.Thread(target=_warm_up_judge_in_background, daemon=True).start()
```

Leave `_warm_up_judge_in_background` (lines 54-58) as-is. The old `GET /api/items` handler and `_ITEMS_PUBLIC` are removed in Task 4 — for now, temporarily change `get_items` (lines 84-86) to `return {"items": [{k: v for k, v in i.items() if k not in _ANSWER_KEY_FIELDS} for i in _ITEMS_BY_ID.values()]}` so the module still imports. Remove `demo.db` if present.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_startup.py -v`
Expected: PASS (4 tests).

- [ ] **Step 9: Verify the server still boots**

Run: `cd backend && .venv/Scripts/python.exe -c "import main; main.on_startup()"`
Expected: no exception, exits cleanly.

- [ ] **Step 10: Security review + commit**

Review: no secrets; `bank.json` contains no answer key exposure risk (server-side only); JSON parsing of a repo-controlled file is safe.

```bash
git rm backend/items.json
git add backend/bank.json backend/pytest.ini backend/tests/ backend/requirements.txt backend/models.py backend/main.py
git commit -m "Load items from bank.json; add pytest, startup validation, per-attempt Attempt columns"
```

---

### Task 2: `selection.py` — per-attempt item selection and option shuffling

**Files:**
- Create: `backend/selection.py`
- Create: `backend/tests/test_selection.py`

**Interfaces:**
- Consumes: `_BANK_BY_SECTION`-shaped dict (`dict[str, list[dict]]`), `SELECTION_COUNTS` (`dict[str, int]`).
- Produces:
  - `class SelectionError(Exception)`.
  - `select_items(bank_by_section: dict[str, list[dict]], counts: dict[str, int], rng: random.Random) -> list[str]` — returns an ordered list of item ids: all grammar first, then listening, then writing, then speaking (`read_aloud` before `situational`). Raises `SelectionError` if a section cannot be filled or speaking lacks a required type. Grammar draws one item per distinct `subskill` present (up to the count), then fills remaining slots uniformly at random from the rest.
  - `option_permutations(items: list[dict], rng: random.Random) -> dict[str, list[int]]` — for each item whose `type == "mcq"`, a shuffled list of that item's option indices (`list(range(len(options)))` shuffled). Non-mcq items are absent from the result.
  - `canonical_letter(display_letter: str, permutation: list[int]) -> str` — given the letter the client sent (position in the shuffled list, `"a"`..`"d"`) and that item's permutation, returns the letter of the option in the bank's original order. Example: `permutation == [2, 0, 3, 1]`, client sends `"a"` (display pos 0) → original index `2` → returns `"c"`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_selection.py`:

```python
import random

import pytest

from selection import SelectionError, canonical_letter, option_permutations, select_items

COUNTS = {"grammar": 5, "listening": 2, "writing": 1, "speaking": 2}


def _bank():
    grammar = [
        {"id": f"g{i}", "section": "grammar", "type": "mcq",
         "subskill": ["subject_verb", "tense", "preposition", "vocab"][i % 4],
         "options": ["a", "b", "c", "d"], "answer": "a"}
        for i in range(20)
    ]
    listening = [
        {"id": f"l{i}", "section": "listening", "type": "mcq", "options": ["a", "b"], "answer": "a"}
        for i in range(2)
    ]
    writing = [{"id": f"w{i}", "section": "writing", "type": "text"} for i in range(4)]
    speaking = (
        [{"id": f"sr{i}", "section": "speaking", "type": "read_aloud"} for i in range(3)]
        + [{"id": f"ss{i}", "section": "speaking", "type": "situational"} for i in range(3)]
    )
    return {"grammar": grammar, "listening": listening, "writing": writing, "speaking": speaking}


def test_select_items_returns_correct_counts_and_order():
    ids = select_items(_bank(), COUNTS, random.Random(1))
    assert len(ids) == 10
    assert len(set(ids)) == 10
    bank = _bank()
    by_id = {i["id"]: i for sec in bank.values() for i in sec}
    sections = [by_id[i]["section"] for i in ids]
    assert sections == ["grammar"] * 5 + ["listening"] * 2 + ["writing"] + ["speaking"] * 2
    speaking_ids = ids[-2:]
    assert by_id[speaking_ids[0]]["type"] == "read_aloud"
    assert by_id[speaking_ids[1]]["type"] == "situational"


def test_select_items_is_deterministic_for_a_seed():
    assert select_items(_bank(), COUNTS, random.Random(42)) == select_items(_bank(), COUNTS, random.Random(42))


def test_select_items_covers_all_subskills_when_count_allows():
    bank = _bank()
    ids = select_items(bank, COUNTS, random.Random(7))
    by_id = {i["id"]: i for sec in bank.values() for i in sec}
    grammar_subskills = {by_id[i]["subskill"] for i in ids[:5]}
    assert {"subject_verb", "tense", "preposition", "vocab"} <= grammar_subskills


def test_select_items_raises_when_section_underfilled():
    bank = _bank()
    bank["grammar"] = bank["grammar"][:3]
    with pytest.raises(SelectionError, match="grammar"):
        select_items(bank, COUNTS, random.Random(1))


def test_select_items_raises_when_speaking_type_missing():
    bank = _bank()
    bank["speaking"] = [i for i in bank["speaking"] if i["type"] == "read_aloud"]
    with pytest.raises(SelectionError, match="situational"):
        select_items(bank, COUNTS, random.Random(1))


def test_option_permutations_only_covers_mcq():
    items = [
        {"id": "g1", "type": "mcq", "options": ["a", "b", "c", "d"]},
        {"id": "w1", "type": "text"},
    ]
    perms = option_permutations(items, random.Random(1))
    assert set(perms) == {"g1"}
    assert sorted(perms["g1"]) == [0, 1, 2, 3]


def test_canonical_letter_maps_display_position_back_to_original():
    assert canonical_letter("a", [2, 0, 3, 1]) == "c"
    assert canonical_letter("b", [2, 0, 3, 1]) == "a"
    assert canonical_letter("d", [2, 0, 3, 1]) == "b"


def test_canonical_letter_identity_permutation():
    assert canonical_letter("c", [0, 1, 2, 3]) == "c"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_selection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'selection'`.

- [ ] **Step 3: Implement `backend/selection.py`**

```python
"""Per-attempt item selection from the question bank.

A bank of ~150 items is drawn down to one fixed-shape test per attempt.
Selection is seeded (from the attempt id) so a specific attempt's item set
can be reproduced when debugging. MCQ options are shuffled per attempt to
reduce answer-sharing between candidates sitting the test side by side.
"""

import random

_LETTERS = ["a", "b", "c", "d", "e", "f"]


class SelectionError(Exception):
    """Raised when the bank cannot satisfy the required test shape."""


def _pick_grammar(pool: list[dict], count: int, rng: random.Random) -> list[dict]:
    by_subskill: dict[str, list[dict]] = {}
    for item in pool:
        by_subskill.setdefault(item.get("subskill", ""), []).append(item)

    chosen: list[dict] = []
    chosen_ids: set[str] = set()
    for subskill in rng.sample(list(by_subskill), len(by_subskill)):
        if len(chosen) >= count:
            break
        candidates = by_subskill[subskill]
        pick = rng.choice(candidates)
        chosen.append(pick)
        chosen_ids.add(pick["id"])

    remaining = [i for i in pool if i["id"] not in chosen_ids]
    rng.shuffle(remaining)
    chosen.extend(remaining[: count - len(chosen)])
    return chosen


def select_items(
    bank_by_section: dict[str, list[dict]], counts: dict[str, int], rng: random.Random
) -> list[str]:
    ordered: list[dict] = []

    for section in ("grammar", "listening", "writing"):
        pool = list(bank_by_section.get(section, []))
        count = counts[section]
        if len(pool) < count:
            raise SelectionError(f"section '{section}' has {len(pool)} items, needs {count}")
        if section == "grammar":
            ordered.extend(_pick_grammar(pool, count, rng))
        else:
            ordered.extend(rng.sample(pool, count))

    speaking = list(bank_by_section.get("speaking", []))
    read_aloud = [i for i in speaking if i["type"] == "read_aloud"]
    situational = [i for i in speaking if i["type"] == "situational"]
    if not read_aloud:
        raise SelectionError("speaking section has no 'read_aloud' item")
    if not situational:
        raise SelectionError("speaking section has no 'situational' item")
    ordered.append(rng.choice(read_aloud))
    ordered.append(rng.choice(situational))

    return [i["id"] for i in ordered]


def option_permutations(items: list[dict], rng: random.Random) -> dict[str, list[int]]:
    perms: dict[str, list[int]] = {}
    for item in items:
        if item.get("type") != "mcq":
            continue
        indices = list(range(len(item["options"])))
        rng.shuffle(indices)
        perms[item["id"]] = indices
    return perms


def canonical_letter(display_letter: str, permutation: list[int]) -> str:
    display_pos = _LETTERS.index(display_letter)
    original_index = permutation[display_pos]
    return _LETTERS[original_index]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_selection.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Security review + commit**

Review: RNG is `random.Random` seeded per attempt — acceptable, this is not a security boundary (selection unpredictability is not a security control; the answer key is protected separately). No user input reaches this module yet.

```bash
git add backend/selection.py backend/tests/test_selection.py
git commit -m "Add per-attempt item selection and MCQ option shuffling"
```

---

### Task 3: `POST /api/attempts` runs selection and persists it

**Files:**
- Modify: `backend/main.py` (`create_attempt`, lines 76-95)
- Create: `backend/tests/test_attempts_api.py`

**Interfaces:**
- Consumes: `select_items`, `option_permutations`, `SelectionError` from `selection`; `_BANK_BY_SECTION`, `_ITEMS_BY_ID`, `SELECTION_COUNTS` from `main`.
- Produces:
  - `CreateAttemptRequest` gains an optional field `item_ids: list[str] | None = None`.
  - Behaviour: when `item_ids` is provided AND env var `ASSESSMENT_ALLOW_FIXED_SELECTION == "1"`, the attempt uses exactly those ids (validated to exist in `_ITEMS_BY_ID`); otherwise `item_ids` in the request is rejected with HTTP 400. This is a **seed-only** hook (Task 8 uses it); normal candidates never send it.
  - On success the `Attempt` row has `item_ids` (ordered) and `option_order` (`{item_id: [int,...]}` for MCQ items among the selection) populated.
  - `SelectionError` → HTTP 500 with detail `"Question bank misconfigured"` (logged with the real reason via `logger.exception`).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_attempts_api.py`:

```python
import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import db
import main
from models import Attempt


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)

    def _get_session():
        with Session(engine) as session:
            yield session

    main.app.dependency_overrides[main.get_session] = _get_session
    main._load_bank()
    with TestClient(main.app) as c:
        c._engine = engine
        yield c
    main.app.dependency_overrides.clear()


def test_create_attempt_persists_selection(client):
    resp = client.post("/api/attempts", json={"name": "Ada"})
    assert resp.status_code == 200
    attempt_id = resp.json()["attempt_id"]
    with Session(client._engine) as session:
        attempt = session.get(Attempt, attempt_id)
        assert len(attempt.item_ids) == 10
        assert len(set(attempt.item_ids)) == 10
        # every mcq in the selection has a permutation
        for item_id in attempt.item_ids:
            if main._ITEMS_BY_ID[item_id]["type"] == "mcq":
                assert sorted(attempt.option_order[item_id]) == list(
                    range(len(main._ITEMS_BY_ID[item_id]["options"]))
                )


def test_create_attempt_rejects_client_supplied_item_ids_without_env(client):
    resp = client.post("/api/attempts", json={"name": "Mallory", "item_ids": ["g1", "g2"]})
    assert resp.status_code == 400


def test_create_attempt_honours_fixed_selection_with_env(client, monkeypatch):
    monkeypatch.setenv("ASSESSMENT_ALLOW_FIXED_SELECTION", "1")
    ids = ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"]
    resp = client.post("/api/attempts", json={"name": "Seed", "item_ids": ids})
    assert resp.status_code == 200
    with Session(client._engine) as session:
        attempt = session.get(Attempt, resp.json()["attempt_id"])
        assert attempt.item_ids == ids


def test_create_attempt_fixed_selection_rejects_unknown_id(client, monkeypatch):
    monkeypatch.setenv("ASSESSMENT_ALLOW_FIXED_SELECTION", "1")
    resp = client.post("/api/attempts", json={"name": "Seed", "item_ids": ["nope"]})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_attempts_api.py -v`
Expected: FAIL — `test_create_attempt_persists_selection` fails (`attempt.item_ids == []`), fixed-selection tests fail (field rejected / not honoured).

- [ ] **Step 3: Implement in `backend/main.py`**

Add near the top-level imports:

```python
import os
import random

from selection import SelectionError, canonical_letter, option_permutations, select_items
```

Replace `CreateAttemptRequest` and `create_attempt` (lines 76-95) with:

```python
class CreateAttemptRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    item_ids: list[str] | None = None  # seed-only; ignored unless env flag set


class CreateAttemptResponse(BaseModel):
    attempt_id: str


def _resolve_selection(payload: CreateAttemptRequest, attempt_id: str) -> list[str]:
    if payload.item_ids is not None:
        if os.getenv("ASSESSMENT_ALLOW_FIXED_SELECTION") != "1":
            raise HTTPException(status_code=400, detail="item_ids not accepted")
        unknown = [i for i in payload.item_ids if i not in _ITEMS_BY_ID]
        if unknown or not payload.item_ids:
            raise HTTPException(status_code=400, detail="Unknown item id in fixed selection")
        return list(payload.item_ids)
    try:
        rng = random.Random(attempt_id)
        return select_items(_BANK_BY_SECTION, SELECTION_COUNTS, rng)
    except SelectionError:
        logger.exception("Item selection failed")
        raise HTTPException(status_code=500, detail="Question bank misconfigured")


@app.post("/api/attempts", response_model=CreateAttemptResponse)
def create_attempt(payload: CreateAttemptRequest, session: SessionDep):
    attempt = Attempt(name=payload.name.strip())
    attempt.item_ids = _resolve_selection(payload, attempt.id)
    selected_items = [_ITEMS_BY_ID[i] for i in attempt.item_ids]
    attempt.option_order = option_permutations(selected_items, random.Random(attempt.id + "opts"))
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return CreateAttemptResponse(attempt_id=attempt.id)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_attempts_api.py -v`
Expected: PASS (4 tests). Also run the full suite: `.venv/Scripts/python.exe -m pytest -v` → all green.

- [ ] **Step 5: Security review + commit**

Review: `item_ids` from the client is gated behind an env flag that is off by default and only set by the seed script; when off, the field is rejected outright. Fixed ids are validated against the bank whitelist. `random.Random(attempt_id)` seed is a uuid — not guessable in a way that matters (selection is not a security boundary). `SelectionError` detail is generic; real reason is logged only.

```bash
git add backend/main.py backend/tests/test_attempts_api.py
git commit -m "Run item selection on attempt creation; seed-only fixed-selection hook"
```

---

### Task 4: `GET /api/attempts/{id}/items` (scoped, shuffled, answer stripped); remove `GET /api/items`

**Files:**
- Modify: `backend/main.py` (`get_items` handler lines 84-86, `_ANSWER_KEY_FIELDS` usage)
- Modify: `backend/tests/test_attempts_api.py` (add cases)

**Interfaces:**
- Consumes: `Attempt.item_ids`, `Attempt.option_order`, `_ITEMS_BY_ID`, `_ANSWER_KEY_FIELDS`.
- Produces:
  - `GET /api/attempts/{attempt_id}/items` → `{"items": [...]}` where each item is the bank item minus `_ANSWER_KEY_FIELDS`, and for `type == "mcq"` the `options` list is reordered per `option_order[item_id]` (display order). Items are returned in `attempt.item_ids` order.
  - 404 if the attempt does not exist. 409 if `attempt.status != "in_progress"`.
  - `GET /api/items` is deleted.
  - Helper `_public_item(item: dict, permutation: list[int] | None) -> dict`.

- [ ] **Step 1: Write the failing tests (append to `test_attempts_api.py`)**

```python
def test_get_attempt_items_strips_answer_and_shuffles(client):
    attempt_id = client.post("/api/attempts", json={"name": "Ada"}).json()["attempt_id"]
    resp = client.get(f"/api/attempts/{attempt_id}/items")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 10
    for item in items:
        assert "answer" not in item
    with Session(client._engine) as session:
        attempt = session.get(Attempt, attempt_id)
    first_mcq = next(i for i in items if i["type"] == "mcq")
    perm = attempt.option_order[first_mcq["id"]]
    original = main._ITEMS_BY_ID[first_mcq["id"]]["options"]
    assert first_mcq["options"] == [original[idx] for idx in perm]


def test_get_attempt_items_404_for_unknown_attempt(client):
    assert client.get("/api/attempts/does-not-exist/items").status_code == 404


def test_get_attempt_items_409_after_submit(client):
    attempt_id = client.post("/api/attempts", json={"name": "Ada"}).json()["attempt_id"]
    with Session(client._engine) as session:
        attempt = session.get(Attempt, attempt_id)
        attempt.status = "done"
        session.add(attempt)
        session.commit()
    assert client.get(f"/api/attempts/{attempt_id}/items").status_code == 409


def test_old_items_endpoint_is_gone(client):
    assert client.get("/api/items").status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_attempts_api.py -v -k items`
Expected: FAIL — new route missing (404 on the scoped path in the shuffle test; `/api/items` still returns 200).

- [ ] **Step 3: Implement in `backend/main.py`**

Delete the `get_items` handler (lines 84-86, plus the temporary version added in Task 1 Step 7). Add:

```python
def _public_item(item: dict, permutation: list[int] | None) -> dict:
    public = {k: v for k, v in item.items() if k not in _ANSWER_KEY_FIELDS}
    if permutation is not None and "options" in public:
        public["options"] = [item["options"][idx] for idx in permutation]
    return public


@app.get("/api/attempts/{attempt_id}/items")
def get_attempt_items(attempt_id: str, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt is no longer accepting responses")
    return {
        "items": [
            _public_item(_ITEMS_BY_ID[item_id], attempt.option_order.get(item_id))
            for item_id in attempt.item_ids
        ]
    }
```

`_get_attempt_or_404` is defined lower in the file (line 103) — move it above this handler, or forward-reference is fine at call time since it's module-level. To keep it simple, move the `_get_attempt_or_404` definition to just below `_public_item`.

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_attempts_api.py -v`
Expected: PASS (all).

- [ ] **Step 5: Security review + commit**

Review: `answer` is stripped via `_public_item` for every item on the only path that serves items now. `status != in_progress` gate prevents item retrieval after submission. No IDOR beyond what already exists (attempt ids are uuids; the whole app is single-tenant by PRD §3).

```bash
git add backend/main.py backend/tests/test_attempts_api.py
git commit -m "Serve items per-attempt with shuffled options; remove global items endpoint"
```

---

### Task 5: `submit_response` — validate item against attempt, map shuffled letter to canonical

**Files:**
- Modify: `backend/main.py` (`submit_response` lines 110-132, `upload_audio` item check line 154)
- Create: `backend/tests/test_responses_api.py`

**Interfaces:**
- Consumes: `Attempt.item_ids`, `Attempt.option_order`, `canonical_letter`, `_ITEMS_BY_ID`.
- Produces:
  - `submit_response` rejects (`HTTP 400 "Item not in this attempt"`) any `item_id` not in `attempt.item_ids`.
  - For an MCQ item, the stored `Response.text` is the **canonical answer letter** (mapped from the client's display-position letter via `canonical_letter` + `attempt.option_order[item_id]`), so `objective.score_section` compares like-for-like against `item["answer"]`. Non-MCQ text is stored verbatim (unchanged).
  - `upload_audio` uses the same `item_id in attempt.item_ids` check instead of the global `_ITEM_IDS` set.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_responses_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import db
import main
from models import Attempt, Response


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)

    def _get_session():
        with Session(engine) as session:
            yield session

    main.app.dependency_overrides[main.get_session] = _get_session
    main._load_bank()
    with TestClient(main.app) as c:
        c._engine = engine
        yield c
    main.app.dependency_overrides.clear()


def _attempt_with(client, ids):
    import os
    os.environ["ASSESSMENT_ALLOW_FIXED_SELECTION"] = "1"
    try:
        return client.post("/api/attempts", json={"name": "T", "item_ids": ids}).json()["attempt_id"]
    finally:
        del os.environ["ASSESSMENT_ALLOW_FIXED_SELECTION"]


def test_submit_response_rejects_item_not_in_attempt(client):
    attempt_id = _attempt_with(client, ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"])
    # pick a grammar id that exists in the bank but is not in this fixed selection
    outside = next(
        i for i in main._ITEMS_BY_ID
        if i not in {"g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"}
    )
    resp = client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": outside, "text": "a"})
    assert resp.status_code == 400


def test_mcq_answer_stored_as_canonical_letter(client):
    attempt_id = _attempt_with(client, ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"])
    with Session(client._engine) as session:
        attempt = session.get(Attempt, attempt_id)
        perm = attempt.option_order["g1"]  # g1 canonical answer is "a" -> original index 0
    display_pos_of_correct = perm.index(0)  # where original option 0 now sits
    display_letter = ["a", "b", "c", "d"][display_pos_of_correct]
    client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": "g1", "text": display_letter})
    with Session(client._engine) as session:
        stored = session.exec(select(Response).where(Response.item_id == "g1")).first()
    assert stored.text == "a"  # canonical, regardless of shuffled display position


def test_writing_text_stored_verbatim(client):
    attempt_id = _attempt_with(client, ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"])
    essay = "Dear customer, I apologise for the delay."
    client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": "w1", "text": essay})
    with Session(client._engine) as session:
        stored = session.exec(select(Response).where(Response.item_id == "w1")).first()
    assert stored.text == essay
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_responses_api.py -v`
Expected: FAIL — item-not-in-attempt returns 200 (global whitelist still used); canonical-letter test fails (raw display letter stored).

- [ ] **Step 3: Implement in `backend/main.py`**

Replace `submit_response` (lines 110-132) with:

```python
@app.post("/api/attempts/{attempt_id}/response")
def submit_response(attempt_id: str, payload: SubmitResponseRequest, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt is no longer accepting responses")
    if payload.item_id not in attempt.item_ids:
        raise HTTPException(status_code=400, detail="Item not in this attempt")

    text = payload.text
    item = _ITEMS_BY_ID[payload.item_id]
    if item["type"] == "mcq":
        permutation = attempt.option_order.get(payload.item_id)
        given = text.strip().lower()
        if permutation is not None and given in {"a", "b", "c", "d", "e", "f"}[: len(permutation)]:
            text = canonical_letter(given, permutation)

    existing = session.exec(
        select(Response).where(
            Response.attempt_id == attempt_id,
            Response.item_id == payload.item_id,
        )
    ).first()

    if existing:
        existing.text = text
        session.add(existing)
    else:
        session.add(Response(attempt_id=attempt_id, item_id=payload.item_id, text=text))

    session.commit()
    return {"ok": True}
```

In `upload_audio` (line 154), replace `if item_id not in _ITEM_IDS:` with `if item_id not in attempt.item_ids:`. (`_ITEM_IDS` no longer exists — this is the last reference; confirm with `grep -n _ITEM_IDS backend/main.py` returning nothing after the edit.)

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_responses_api.py -v` → PASS.
Full suite: `.venv/Scripts/python.exe -m pytest -v` → all green.

- [ ] **Step 5: Security review + commit**

Review: item scope is now per-attempt (tighter than before). Candidate can only write responses for items actually in their test. `canonical_letter` guards on the letter being within range before mapping; an out-of-range or garbage MCQ value is stored as-is and simply scores wrong (no crash, no injection — value is a short string compared against the key). Writing/speaking text still hits the length cap (`Field(max_length=5000)`) and the judge-prompt injection defence from BUILD_LOG T2.10 is untouched.

```bash
git add backend/main.py backend/tests/test_responses_api.py
git commit -m "Scope responses to the attempt's items; store canonical MCQ answer letter"
```

---

### Task 6: Scope scoring to the attempt's selected items

**Files:**
- Modify: `backend/main.py` (`submit_attempt` lines 199-228)
- Modify: `backend/scoring/pipeline.py` (`run_scoring_pipeline` / `_run` — the `items_by_section` argument, lines 28-64)
- Create: `backend/tests/test_scoring_scope.py`

**Interfaces:**
- Consumes: `Attempt.item_ids`, `_ITEMS_BY_ID`.
- Produces:
  - `submit_attempt` builds `attempt_items_by_section: dict[str, list[dict]]` from `attempt.item_ids` (each looked up in `_ITEMS_BY_ID`, grouped by `section`) and passes THAT to both `score_section` and `run_scoring_pipeline` (instead of the module-global section map).
  - `run_scoring_pipeline(attempt_id, items_by_id, items_by_section)` signature is unchanged; callers now pass the attempt-scoped `items_by_section`. `items_by_id` stays the full `_ITEMS_BY_ID`.
  - `objective.score_section` is unchanged — it already accepts an explicit `items` list.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_scoring_scope.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import db
import main
from models import Attempt, Score


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(main, "run_scoring_pipeline", lambda *a, **k: None)  # skip Whisper/Ollama

    def _get_session():
        with Session(engine) as session:
            yield session

    main.app.dependency_overrides[main.get_session] = _get_session
    main._load_bank()
    with TestClient(main.app) as c:
        c._engine = engine
        yield c
    main.app.dependency_overrides.clear()


def test_grammar_score_total_reflects_attempt_not_whole_bank(client, monkeypatch):
    monkeypatch.setenv("ASSESSMENT_ALLOW_FIXED_SELECTION", "1")
    ids = ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"]
    attempt_id = client.post("/api/attempts", json={"name": "T", "item_ids": ids}).json()["attempt_id"]
    for item_id, letter in {"g1": "a", "g2": "c", "g3": "a", "g4": "b"}.items():
        client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": item_id, "text": letter})
    for item_id, letter in {"l1": "b", "l2": "b"}.items():
        client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": item_id, "text": letter})
    client.post(f"/api/attempts/{attempt_id}/submit")

    with Session(client._engine) as session:
        grammar = session.exec(
            select(Score).where(Score.attempt_id == attempt_id, Score.dimension == "grammar")
        ).first()
    assert grammar.evidence["total"] == 4  # the 4 grammar items in THIS attempt
    assert grammar.evidence["correct"] == 4
    assert grammar.band == 6
```

(Note: with the canonical 9-item bank of Task 1 the grammar count is 4; after Task 7 the bank is bigger but a fixed selection still yields exactly these 4. The test pins the fixed selection so it is stable across both.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_scoring_scope.py -v`
Expected: with the current code `submit_attempt` uses `_ITEMS_BY_SECTION` which no longer exists → `NameError`, or (if still referencing a global) `total` reflects the whole bank. Either way: FAIL.

- [ ] **Step 3: Implement**

In `backend/main.py`, replace `submit_attempt` (lines 199-228) with:

```python
@app.post("/api/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: str, background_tasks: BackgroundTasks, session: SessionDep):
    attempt = _get_attempt_or_404(session, attempt_id)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt already submitted")

    attempt_items_by_section: dict[str, list[dict]] = {}
    for item_id in attempt.item_ids:
        item = _ITEMS_BY_ID[item_id]
        attempt_items_by_section.setdefault(item["section"], []).append(item)

    responses = session.exec(select(Response).where(Response.attempt_id == attempt_id)).all()
    responses_by_item = {r.item_id: r.text for r in responses if r.text is not None}

    for dimension in ("grammar", "listening"):
        section_items = attempt_items_by_section.get(dimension, [])
        result = score_section(section_items, responses_by_item)
        session.add(
            Score(
                attempt_id=attempt_id,
                dimension=dimension,
                band=result["band"],
                evidence=result["evidence"],
            )
        )

    attempt.status = "scoring"
    session.add(attempt)
    session.commit()

    background_tasks.add_task(
        run_scoring_pipeline, attempt_id, _ITEMS_BY_ID, attempt_items_by_section
    )
    return {"ok": True}
```

`pipeline.py` needs no change — `_run` already reads `items_by_section.get("speaking", [])` / `.get("writing", [])`, which now contain only this attempt's items. Confirm there is no other reference to a module-global section map: `grep -n "_ITEMS_BY_SECTION" backend/` should return nothing.

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_scoring_scope.py -v` → PASS.
Full suite green.

- [ ] **Step 5: Security review + commit**

Review: scoring now iterates only the attempt's own items — no cross-attempt leakage. `responses_by_item` is keyed by item id and only the attempt's responses are queried. No new input surface.

```bash
git add backend/main.py backend/scoring/pipeline.py backend/tests/test_scoring_scope.py
git commit -m "Scope scoring to the attempt's selected items"
```

---

### Task 7: Author the question-bank content

**Files:**
- Modify: `backend/bank.json`
- Modify: `backend/tests/test_startup.py` (tighten count assertions)

**Interfaces:**
- Consumes: nothing new.
- Produces: `bank.json` with approximately — grammar **80** (`subskill` balanced ~20 each), writing **30**, speaking **12 read_aloud + 12 situational**, listening **2** (unchanged). All ids follow the Global Constraints conventions; `g1..g4/l1/l2/w1/s1/s2` retained. Every item has `time_limit_s` per the Global Constraints table.

- [ ] **Step 1: Draft grammar items (80)**

Write 80 grammar MCQs, 4 options each, `answer` one of `a|b|c|d` (vary the correct position — do not always make it `a`). Distribute `subskill` roughly evenly across `subject_verb`, `tense`, `preposition`, `vocab`. Keep the register consistent with the existing 4 (customer-support / workplace English). Ids `g5`..`g80` (g1-g4 already present). `time_limit_s: 40`.

Example shape:

```json
{ "id": "g5", "section": "grammar", "type": "mcq", "subskill": "subject_verb", "time_limit_s": 40,
  "prompt": "Neither the supervisor nor the agents ___ aware of the policy change.",
  "options": ["was", "were", "is", "has been"], "answer": "b" }
```

- [ ] **Step 2: Draft writing prompts (30)**

Ids `w2`..`w30`. Each `{ "id", "section": "writing", "type": "text", "time_limit_s": 180, "word_target": 100, "prompt": "..." }`. All customer-facing email / message scenarios that can be answered in ~100 words and exercise tone + task fulfilment (the judge scores `tone_appropriateness`). No `answer` field.

- [ ] **Step 3: Draft speaking items (12 + 12)**

Read-aloud ids `s3`..`s14`: `{ "type": "read_aloud", "time_limit_s": 30, "prep_s": 10, "reference_text": "<~40 words>" }`. Natural customer-support phrasing so WER is meaningful.
Situational ids `s15`..`s26`: `{ "type": "situational", "time_limit_s": 45, "prep_s": 20, "prompt": "<walk-through / explain / justify prompt>" }` — must elicit ≥60 words of continuous speech per demo PRD §4 constraint (ask to *explain / walk through / justify*, never *choose or state*).

- [ ] **Step 4: Validate the file**

Run: `cd backend && .venv/Scripts/python.exe -c "import json,collections; b=json.load(open('bank.json')); c=collections.Counter(i['section'] for i in b['items']); print(c); assert c['grammar']>=60 and c['writing']>=20 and c['speaking']>=16; ids=[i['id'] for i in b['items']]; assert len(ids)==len(set(ids)), 'dup ids'; assert all('time_limit_s' in i for i in b['items'])"`
Expected: prints the counter, no assertion error.

- [ ] **Step 5: Tighten and run startup tests**

In `backend/tests/test_startup.py` add:

```python
def test_bank_is_large_enough_for_variety():
    main._load_bank()
    assert len(main._BANK_BY_SECTION["grammar"]) >= 60
    assert len(main._BANK_BY_SECTION["writing"]) >= 20
    read_aloud = [i for i in main._BANK_BY_SECTION["speaking"] if i["type"] == "read_aloud"]
    situational = [i for i in main._BANK_BY_SECTION["speaking"] if i["type"] == "situational"]
    assert len(read_aloud) >= 8 and len(situational) >= 8


def test_no_mcq_always_has_answer_a():
    main._load_bank()
    answers = [i["answer"] for i in main._BANK_BY_SECTION["grammar"]]
    assert len(set(answers)) > 1  # correct option is not always the same letter
```

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_startup.py -v` → PASS.

- [ ] **Step 6: Security review + commit**

Review: content-only change; no code. Confirm no `answer` field leaked into any writing/speaking item, no secrets, no PII in prompts.

```bash
git add backend/bank.json backend/tests/test_startup.py
git commit -m "Expand question bank to ~120 items across grammar, writing, speaking"
```

---

### Task 8: Update seed scripts for the bank

**Files:**
- Modify: `backend/seed_attempts.py`
- Modify: `backend/seed_audio.ps1`
- Modify: `BUILD_LOG.md`

**Interfaces:**
- Consumes: `POST /api/attempts` fixed-selection hook (env `ASSESSMENT_ALLOW_FIXED_SELECTION=1` + `item_ids`), `GET /api/attempts/{id}/items`.
- Produces: seeded attempts run against a stable, known 9-item set (`g1 g2 g3 g4 l1 l2 w1 s1 s2`), so the hardcoded proficiency answer maps in `CANDIDATES` stay valid. Each seeded attempt also resolves the correct MCQ display letter from the served (shuffled) items before answering.

- [ ] **Step 1: Set the fixed selection when creating a seed attempt**

In `seed_attempts.py`, change `seed_one` so the create call sends the fixed id list and reads back the shuffled items to translate canonical answers to display letters:

```python
SEED_ITEM_IDS = ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"]


def seed_one(client: httpx.Client, candidate: dict) -> str:
    attempt_id = client.post(
        "/api/attempts", json={"name": candidate["name"], "item_ids": SEED_ITEM_IDS}
    ).json()["attempt_id"]

    served = {i["id"]: i for i in client.get(f"/api/attempts/{attempt_id}/items").json()["items"]}
    bank = {i["id"]: i for i in json.load(open(Path(__file__).parent / "bank.json"))["items"]}

    def display_letter(item_id: str, canonical: str) -> str:
        original = bank[item_id]["options"]
        target_text = original[["a", "b", "c", "d"].index(canonical)]
        shown = served[item_id]["options"]
        return ["a", "b", "c", "d"][shown.index(target_text)]

    for item_id, canonical in {**candidate["grammar"], **candidate["listening"]}.items():
        client.post(
            f"/api/attempts/{attempt_id}/response",
            json={"item_id": item_id, "text": display_letter(item_id, canonical)},
        )

    client.post(
        f"/api/attempts/{attempt_id}/response",
        json={"item_id": "w1", "text": candidate["writing"]},
    )

    for item_id, filename in (("s1", candidate["s1_audio"]), ("s2", candidate["s2_audio"])):
        path = AUDIO_DIR / filename
        with open(path, "rb") as f:
            client.post(
                f"/api/attempts/{attempt_id}/audio",
                data={"item_id": item_id},
                files={"file": (f"{item_id}.webm", f, "audio/webm")},
            )

    client.post(f"/api/attempts/{attempt_id}/submit")
    return attempt_id
```

Add `import json` at the top of `seed_attempts.py`.

- [ ] **Step 2: Document the env requirement in the script docstring**

Update the module docstring:

```python
"""Seeds 4 attempts at deliberately different proficiency levels through the
real scoring pipeline (T3.7). Requires the backend running on :8000 and
started with ASSESSMENT_ALLOW_FIXED_SELECTION=1 so the seed can pin a known
9-item set (g1..s2) against which the proficiency answer maps are defined.

Usage:
  ASSESSMENT_ALLOW_FIXED_SELECTION=1 .venv/Scripts/python -m uvicorn main:app   # terminal 1
  .venv/Scripts/python seed_attempts.py                                          # terminal 2
"""
```

- [ ] **Step 3: Check `seed_audio.ps1`**

Read `backend/seed_audio.ps1`. It only synthesises `.wav` files into `seed_audio/` — it does not reference item ids or the API. If so, no change is needed; note that in the commit body. If it does call the API with item ids, apply the same fixed-selection treatment.

- [ ] **Step 4: Manual verification**

```bash
cd backend
rm -f demo.db
ASSESSMENT_ALLOW_FIXED_SELECTION=1 .venv/Scripts/python.exe -m uvicorn main:app --port 8000 &
.venv/Scripts/python.exe seed_attempts.py
```
Expected: 4 lines `NAME: status=done cir=N`, then `Band spread: min=2 max=6` (or close — D2 requires ≥2 spread). Kill the server.

- [ ] **Step 5: Update `BUILD_LOG.md`**

Add a short dated section noting: bank.json replaces items.json; per-attempt random selection; seed script now pins a fixed selection via the env-gated hook; per-question + global timers; option shuffle; progress bar; resume-after-refresh. Update the "Item pool is 9 items" limitation line to reflect the new bank size.

- [ ] **Step 6: Security review + commit**

Review: seed script is a dev tool, not shipped in the request path. The env flag it depends on is off by default. No secrets.

```bash
git add backend/seed_attempts.py backend/seed_audio.ps1 BUILD_LOG.md
git commit -m "Update seed scripts to pin a fixed item selection against the bank"
```

---

### Task 9: Frontend test tooling + API client + begin-flow rewrite

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.js`
- Create: `frontend/src/test/setup.js`
- Modify: `frontend/src/api.js` (replace `getItems`, lines 10-12)
- Modify: `frontend/src/App.jsx` (`handleBegin`, lines 52-58)
- Create: `frontend/src/api.test.js`

**Interfaces:**
- Consumes: backend `POST /api/attempts`, `GET /api/attempts/{id}/items`.
- Produces:
  - `frontend/src/api.js` exports `getAttemptItems(attemptId)` → `GET /api/attempts/{attemptId}/items`; `getItems` is removed.
  - `App.jsx` `handleBegin(name)`: create the attempt first, then fetch that attempt's items, then set state and move to `check`.
  - `npm test` runs Vitest (`vitest run`), `npm run test:watch` runs `vitest`.

- [ ] **Step 1: Add dev dependencies**

```bash
cd frontend
npm install -D vitest@2.1.8 @testing-library/react@16.1.0 @testing-library/jest-dom@6.6.3 @testing-library/user-event@14.5.2 jsdom@25.0.1
```

Add to `package.json` `scripts`:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 2: Vitest config + setup**

`frontend/vitest.config.js`:

```js
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
  },
})
```

`frontend/src/test/setup.js`:

```js
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 3: Write the failing api test**

`frontend/src/api.test.js`:

```js
import { afterEach, expect, test, vi } from 'vitest'
import { createAttempt, getAttemptItems } from './api'

afterEach(() => vi.restoreAllMocks())

test('getAttemptItems calls the per-attempt items path', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ items: [] }),
  })
  await getAttemptItems('abc-123')
  expect(fetchMock).toHaveBeenCalledWith('/api/attempts/abc-123/items', undefined)
})

test('createAttempt posts the name', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ attempt_id: 'x' }),
  })
  await createAttempt('Ada')
  const [, opts] = fetchMock.mock.calls[0]
  expect(JSON.parse(opts.body)).toEqual({ name: 'Ada' })
})
```

- [ ] **Step 4: Run to verify failure**

Run: `cd frontend && npm test`
Expected: FAIL — `getAttemptItems` is not exported.

- [ ] **Step 5: Implement**

In `frontend/src/api.js`, replace `getItems` (lines 10-12):

```js
export function getAttemptItems(attemptId) {
  return request(`/api/attempts/${attemptId}/items`)
}
```

In `frontend/src/App.jsx`, update imports (line 2) to drop `getItems` and add `getAttemptItems`, and replace `handleBegin` (lines 52-58):

```js
const handleBegin = async (name) => {
  const { attempt_id } = await createAttempt(name)
  const { items: fetchedItems } = await getAttemptItems(attempt_id)
  setItems(fetchedItems)
  setAttemptId(attempt_id)
  setScreen('check')
}
```

- [ ] **Step 6: Run to verify pass + lint + build**

```bash
cd frontend
npm test
npm run lint
npm run build
```
Expected: tests PASS, lint clean, build succeeds.

- [ ] **Step 7: Security review + commit**

Review: no secrets. `attemptId` is interpolated into a URL path — it is a server-issued uuid echoed back; still, it flows only into a same-origin `/api/...` path, no injection surface. Dev dependencies only.

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.js frontend/src/test/ frontend/src/api.js frontend/src/App.jsx frontend/src/api.test.js
git commit -m "Add Vitest; fetch items per-attempt after creating the attempt"
```

---

### Task 10: Per-question timer — auto-save and advance on expiry, lock

**Files:**
- Modify: `frontend/src/screens/Test.jsx`
- Create: `frontend/src/screens/Test.test.jsx`

**Interfaces:**
- Consumes: `item.time_limit_s` on every non-speaking item (guaranteed by Global Constraints), `Timer` component.
- Produces:
  - Every non-speaking item renders a `<Timer>` (grammar and listening now have `time_limit_s`, so the existing `item.time_limit_s &&` guard now always passes for them).
  - On timer expiry: the current answer for that item (if any, from `answers[item.id]`) is sent via `submitResponse` (fire-and-forget — do not await before advancing), then the flow advances (`setIndex + 1`, or `onComplete()` on the last item).
  - Once left, an item is not returnable (there is already no "Back" control — this task keeps it that way and adds a regression test).

- [ ] **Step 1: Write the failing test**

`frontend/src/screens/Test.test.jsx`:

```js
import { render, screen, act } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import Test from './Test'

vi.mock('../api', () => ({
  submitResponse: vi.fn().mockResolvedValue({ ok: true }),
  uploadAudio: vi.fn().mockResolvedValue({ ok: true }),
}))
import { submitResponse } from '../api'

const items = [
  { id: 'g1', type: 'mcq', prompt: 'Q1', options: ['a', 'b', 'c', 'd'], time_limit_s: 2 },
  { id: 'g2', type: 'mcq', prompt: 'Q2', options: ['a', 'b', 'c', 'd'], time_limit_s: 2 },
]

beforeEach(() => vi.useFakeTimers())
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks() })

test('per-question timer expiry advances to the next item', async () => {
  render(<Test attemptId="a1" items={items} onComplete={vi.fn()} />)
  expect(screen.getByText('Q1')).toBeInTheDocument()
  await act(async () => { vi.advanceTimersByTime(2100) })
  expect(screen.getByText('Q2')).toBeInTheDocument()
})

test('timer expiry on the last item completes the test', async () => {
  const onComplete = vi.fn()
  render(<Test attemptId="a1" items={[items[0]]} onComplete={onComplete} />)
  await act(async () => { vi.advanceTimersByTime(2100) })
  expect(onComplete).toHaveBeenCalledTimes(1)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test src/screens/Test.test.jsx`
Expected: the first test may already pass (Timer + `onExpire={goNext}` exists for items with `time_limit_s`), but the answer-save-on-expiry behaviour and the grammar-item timer (grammar items in real data now have `time_limit_s`) need confirming. If both pass as-is, still add Step 3's explicit save and keep the tests as regressions. If the guard `item.time_limit_s` was blocking, they FAIL.

- [ ] **Step 3: Implement in `frontend/src/screens/Test.jsx`**

Change the expiry handler so the in-progress answer is persisted before advancing. Replace `goNext` and the `Timer` usage:

```js
const goNext = () => {
  setError(null)
  if (isLast) {
    onComplete()
  } else {
    setIndex((i) => i + 1)
  }
}

const handleTimerExpire = () => {
  const pending = answers[item.id]
  if (pending !== undefined && !isSpeaking) {
    // fire-and-forget: never block the advance on a slow save
    submitResponse(attemptId, item.id, pending).catch(() => {})
  }
  goNext()
}
```

And the header Timer:

```jsx
{!isSpeaking && item.time_limit_s && (
  <Timer seconds={item.time_limit_s} itemKey={item.id} onExpire={handleTimerExpire} />
)}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test` → PASS. `npm run lint` clean.

- [ ] **Step 5: Security review + commit**

Review: no new input surface; `submitResponse` already validated server-side (Task 5). Fire-and-forget catch swallows errors intentionally — the answer is re-sent on the next navigation via `handleAnswer` semantics for MCQ, and for the expiry-of-last-item case the value was already saved on selection.

```bash
git add frontend/src/screens/Test.jsx frontend/src/screens/Test.test.jsx
git commit -m "Save the in-progress answer when a question timer expires"
```

---

### Task 11: Global 12-minute test timer + Timer amber low-time state

**Files:**
- Modify: `frontend/src/screens/Test.jsx`
- Modify: `frontend/src/components/Timer.jsx`
- Modify: `frontend/src/screens/Test.test.jsx` (add cases)
- Create: `frontend/src/components/Timer.test.jsx`

**Interfaces:**
- Consumes: `Timer` component.
- Produces:
  - `Test.jsx` renders a second `Timer` in the header with `seconds={720}` and a fixed `itemKey="global"`; on its `onExpire` it calls `onComplete()` once (guard against double-fire with a ref).
  - `Timer.jsx` applies `text-amber-600` (replacing `text-gray-600`) when `remaining <= 10`, and adds `data-testid="timer"` stays; add `aria-live="polite"`.

- [ ] **Step 1: Write failing tests**

`frontend/src/components/Timer.test.jsx`:

```js
import { render, screen, act } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import Timer from './Timer'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

test('shows amber styling under 10 seconds remaining', async () => {
  render(<Timer seconds={12} itemKey="x" onExpire={vi.fn()} />)
  const el = screen.getByTestId('timer')
  expect(el.className).not.toContain('amber')
  await act(async () => { vi.advanceTimersByTime(3000) })
  expect(el.className).toContain('amber')
})

test('calls onExpire once when it reaches zero', async () => {
  const onExpire = vi.fn()
  render(<Timer seconds={2} itemKey="x" onExpire={onExpire} />)
  await act(async () => { vi.advanceTimersByTime(5000) })
  expect(onExpire).toHaveBeenCalledTimes(1)
})
```

Add to `Test.test.jsx`:

```js
test('global timer expiry completes the test', async () => {
  const onComplete = vi.fn()
  const longItems = [{ id: 'g1', type: 'mcq', prompt: 'Q1', options: ['a', 'b'], time_limit_s: 9999 }]
  render(<Test attemptId="a1" items={longItems} onComplete={onComplete} />)
  await act(async () => { vi.advanceTimersByTime(720_000 + 500) })
  expect(onComplete).toHaveBeenCalledTimes(1)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test`
Expected: FAIL — amber class absent; no global timer.

- [ ] **Step 3: Implement `Timer.jsx`**

```jsx
import { useEffect, useRef, useState } from 'react'

export default function Timer({ seconds, onExpire, itemKey }) {
  const [remaining, setRemaining] = useState(seconds)
  const onExpireRef = useRef(onExpire)
  onExpireRef.current = onExpire

  useEffect(() => {
    setRemaining(seconds)
    const start = Date.now()
    const interval = setInterval(() => {
      const left = seconds - Math.floor((Date.now() - start) / 1000)
      if (left <= 0) {
        setRemaining(0)
        clearInterval(interval)
        onExpireRef.current()
      } else {
        setRemaining(left)
      }
    }, 200)
    return () => clearInterval(interval)
    // itemKey forces the timer to restart when the current item changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seconds, itemKey])

  const low = remaining <= 10
  return (
    <div
      className={`text-sm font-mono tabular-nums ${low ? 'text-amber-600 font-semibold' : 'text-gray-600'}`}
      data-testid="timer"
      aria-live="polite"
    >
      {remaining}s
    </div>
  )
}
```

- [ ] **Step 4: Implement the global timer in `Test.jsx`**

Add near the top of the component:

```js
const GLOBAL_LIMIT_S = 720
const globalFiredRef = useRef(false)

const handleGlobalExpire = () => {
  if (globalFiredRef.current) return
  globalFiredRef.current = true
  onComplete()
}
```

(add `useRef` to the React import). In the header row, render both timers:

```jsx
<div className="flex items-center justify-between text-sm text-gray-500">
  <span>Item {index + 1} of {items.length}</span>
  <div className="flex items-center gap-4">
    <span className="text-gray-400">Test</span>
    <Timer seconds={GLOBAL_LIMIT_S} itemKey="global" onExpire={handleGlobalExpire} />
    {!isSpeaking && item.time_limit_s && (
      <Timer seconds={item.time_limit_s} itemKey={item.id} onExpire={handleTimerExpire} />
    )}
  </div>
</div>
```

- [ ] **Step 5: Run to verify pass**

Run: `cd frontend && npm test` → PASS. `npm run lint` clean. `npm run build` succeeds.

- [ ] **Step 6: Security review + commit**

Review: purely client-side UI/timing. The server does not trust the timer — `submit_attempt` scores whatever responses exist regardless of client timing. No new surface.

```bash
git add frontend/src/screens/Test.jsx frontend/src/components/Timer.jsx frontend/src/components/Timer.test.jsx frontend/src/screens/Test.test.jsx
git commit -m "Add global 12-minute test timer and amber low-time timer state"
```

---

### Task 12: Section-aware progress bar

**Files:**
- Create: `frontend/src/components/Progress.jsx`
- Create: `frontend/src/components/Progress.test.jsx`
- Modify: `frontend/src/screens/Test.jsx`

**Interfaces:**
- Consumes: the attempt's `items` array (each has `section`) and the current `index`.
- Produces:
  - `Progress.jsx` default export `Progress({ items, index })` — renders one chip per section in canonical order (`grammar`, `listening`, `writing`, `speaking`) that appears in `items`, labelled `Grammar`, `Listening`, `Writing`, `Speaking`. The chip for the current item's section also shows `n/total` (position within that section, 1-based) and is visually highlighted; sections fully behind the current index are marked done (checkmark or filled), sections ahead are muted.
  - Rendered in the `Test.jsx` header above the item body.

- [ ] **Step 1: Write failing tests**

`frontend/src/components/Progress.test.jsx`:

```js
import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import Progress from './Progress'

const items = [
  { id: 'g1', section: 'grammar' }, { id: 'g2', section: 'grammar' },
  { id: 'l1', section: 'listening' },
  { id: 'w1', section: 'writing' },
  { id: 's1', section: 'speaking' }, { id: 's2', section: 'speaking' },
]

test('shows all four section labels', () => {
  render(<Progress items={items} index={0} />)
  for (const label of ['Grammar', 'Listening', 'Writing', 'Speaking']) {
    expect(screen.getByText(new RegExp(label))).toBeInTheDocument()
  }
})

test('marks the current section with position within it', () => {
  render(<Progress items={items} index={1} />)
  expect(screen.getByText(/Grammar 2\/2/)).toBeInTheDocument()
})

test('current section is on the speaking chip when index is in speaking', () => {
  render(<Progress items={items} index={4} />)
  expect(screen.getByText(/Speaking 1\/2/)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test src/components/Progress.test.jsx`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `Progress.jsx`**

```jsx
const SECTION_ORDER = ['grammar', 'listening', 'writing', 'speaking']
const LABELS = { grammar: 'Grammar', listening: 'Listening', writing: 'Writing', speaking: 'Speaking' }

export default function Progress({ items, index }) {
  const currentSection = items[index]?.section
  const sections = SECTION_ORDER.filter((s) => items.some((it) => it.section === s))

  return (
    <ol className="flex flex-wrap items-center gap-2 text-xs" data-testid="progress">
      {sections.map((section) => {
        const inSection = items.filter((it) => it.section === section)
        const lastIdxOfSection = items.map((it) => it.section).lastIndexOf(section)
        const done = index > lastIdxOfSection
        const active = section === currentSection
        const posInSection = active
          ? items.slice(0, index + 1).filter((it) => it.section === section).length
          : null

        const classes = active
          ? 'bg-purple-600 text-white'
          : done
            ? 'bg-purple-100 text-purple-700'
            : 'bg-gray-100 text-gray-400'

        return (
          <li key={section} className={`rounded-full px-3 py-1 font-medium ${classes}`}>
            {done && !active ? '✓ ' : ''}
            {LABELS[section]}
            {active ? ` ${posInSection}/${inSection.length}` : ''}
          </li>
        )
      })}
    </ol>
  )
}
```

- [ ] **Step 4: Wire into `Test.jsx`**

Import `Progress` and render it just inside the outer `<div>`, above the existing header row:

```jsx
<Progress items={items} index={index} />
```

- [ ] **Step 5: Run to verify pass + lint + build**

Run: `cd frontend && npm test && npm run lint && npm run build` → all green.

- [ ] **Step 6: Security review + commit**

Review: presentational component, data already in the client. No user input, no new fetch.

```bash
git add frontend/src/components/Progress.jsx frontend/src/components/Progress.test.jsx frontend/src/screens/Test.jsx
git commit -m "Add section-aware progress bar to the test screen"
```

---

### Task 13: Resume after refresh

**Files:**
- Create: `frontend/src/session.js`
- Create: `frontend/src/session.test.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/screens/Test.jsx`

**Interfaces:**
- Consumes: `getAttemptItems` (Task 9), `localStorage`.
- Produces:
  - `frontend/src/session.js`:
    - `saveSession({ attemptId, index })` — writes `{ attemptId, index }` JSON to `localStorage` key `assessment.session`. Wrapped in try/catch (private-mode / disabled storage → no-op).
    - `loadSession()` — returns the parsed object or `null` (also `null` on parse error).
    - `clearSession()` — removes the key, try/catch.
  - `App.jsx`:
    - On mount (`useEffect`, once), if `loadSession()` returns a record, call `getAttemptItems(attemptId)`; on success set items + attemptId, set `screen = 'test'`, and pass the saved `index` as the test's starting index; on failure (404/409/network) call `clearSession()` and stay on `start`.
    - Clear the session when reaching `report`, and on a fresh `handleBegin`.
  - `Test.jsx`:
    - Accepts an optional `initialIndex = 0` prop; `useState(initialIndex)`.
    - Calls `saveSession({ attemptId, index })` in a `useEffect` on every `index` change.

- [ ] **Step 1: Write failing tests**

`frontend/src/session.test.js`:

```js
import { afterEach, expect, test } from 'vitest'
import { clearSession, loadSession, saveSession } from './session'

afterEach(() => localStorage.clear())

test('save then load round-trips', () => {
  saveSession({ attemptId: 'a1', index: 3 })
  expect(loadSession()).toEqual({ attemptId: 'a1', index: 3 })
})

test('loadSession returns null when nothing stored', () => {
  expect(loadSession()).toBeNull()
})

test('loadSession returns null on corrupt data', () => {
  localStorage.setItem('assessment.session', '{not json')
  expect(loadSession()).toBeNull()
})

test('clearSession removes the record', () => {
  saveSession({ attemptId: 'a1', index: 1 })
  clearSession()
  expect(loadSession()).toBeNull()
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test src/session.test.js`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `frontend/src/session.js`**

```js
const KEY = 'assessment.session'

export function saveSession(record) {
  try {
    localStorage.setItem(KEY, JSON.stringify(record))
  } catch {
    // storage unavailable (private mode / disabled) — resume is best-effort
  }
}

export function loadSession() {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed.attemptId !== 'string') return null
    return parsed
  } catch {
    return null
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // no-op
  }
}
```

- [ ] **Step 4: Write the failing App resume test**

`frontend/src/App.test.jsx`:

```js
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

vi.mock('./api', () => ({
  createAttempt: vi.fn(),
  getAttemptItems: vi.fn(),
  getReport: vi.fn(),
  pollReport: vi.fn(),
  submitAttempt: vi.fn(),
  submitResponse: vi.fn(),
  uploadAudio: vi.fn(),
  listAttempts: vi.fn(),
}))
import { getAttemptItems } from './api'
import App from './App'

afterEach(() => { localStorage.clear(); vi.clearAllMocks() })

test('resumes an in-progress attempt from localStorage', async () => {
  localStorage.setItem('assessment.session', JSON.stringify({ attemptId: 'a1', index: 1 }))
  getAttemptItems.mockResolvedValue({
    items: [
      { id: 'g1', type: 'mcq', prompt: 'Q1', options: ['a', 'b'], time_limit_s: 40 },
      { id: 'g2', type: 'mcq', prompt: 'Q2', options: ['a', 'b'], time_limit_s: 40 },
    ],
  })
  render(<App />)
  await waitFor(() => expect(screen.getByText('Q2')).toBeInTheDocument())
})

test('clears the session and stays on start when the attempt is gone', async () => {
  localStorage.setItem('assessment.session', JSON.stringify({ attemptId: 'dead', index: 0 }))
  getAttemptItems.mockRejectedValue(new Error('404'))
  render(<App />)
  await waitFor(() => expect(localStorage.getItem('assessment.session')).toBeNull())
})
```

- [ ] **Step 5: Run to verify failure**

Run: `cd frontend && npm test src/App.test.jsx`
Expected: FAIL — no resume logic; `App` renders `Start` regardless.

- [ ] **Step 6: Implement in `App.jsx`**

Add imports: `useEffect` from react, `{ clearSession, loadSession, saveSession }` from `./session`.

In `CandidateApp`, add a `initialIndex` state (default `0`) and a mount effect:

```js
const [initialIndex, setInitialIndex] = useState(0)

useEffect(() => {
  const saved = loadSession()
  if (!saved) return
  let cancelled = false
  getAttemptItems(saved.attemptId)
    .then(({ items: fetchedItems }) => {
      if (cancelled) return
      setItems(fetchedItems)
      setAttemptId(saved.attemptId)
      setInitialIndex(saved.index ?? 0)
      setScreen('test')
    })
    .catch(() => {
      if (!cancelled) clearSession()
    })
  return () => { cancelled = true }
}, [])
```

In `handleBegin`, call `clearSession()` before creating a new attempt. In `handleTestComplete`, after `setScreen('report')` on success, call `clearSession()`. Pass `initialIndex={initialIndex}` to `<Test>`.

- [ ] **Step 7: Implement in `Test.jsx`**

```js
export default function Test({ attemptId, items, onComplete, initialIndex = 0 }) {
  const [index, setIndex] = useState(initialIndex)
  // ...
  useEffect(() => {
    saveSession({ attemptId, index })
  }, [attemptId, index])
```

Add `useEffect` to the React import and `import { saveSession } from '../session'`.

- [ ] **Step 8: Run to verify pass + full check**

```bash
cd frontend
npm test
npm run lint
npm run build
```
Expected: all tests PASS, lint clean, build succeeds.

- [ ] **Step 9: Security review + commit**

Review: `localStorage` holds only a server-issued attempt uuid and an integer index — no PII, no answers, no secrets (answers already persist server-side per `Response` row). On resume, the server re-authorises via `GET /api/attempts/{id}/items` (404/409 → session cleared). A stale/forged `attemptId` in storage can at worst fetch a `409`/`404` and is discarded. `index` is used only as a local array offset; clamp it defensively: `Math.min(Math.max(0, saved.index ?? 0), fetchedItems.length - 1)`.

Apply that clamp in Step 6 before committing.

```bash
git add frontend/src/session.js frontend/src/session.test.js frontend/src/App.jsx frontend/src/App.test.jsx frontend/src/screens/Test.jsx
git commit -m "Resume an in-progress attempt after an accidental refresh"
```

---

### Task 14: End-to-end verification and docs

**Files:**
- Modify: `frontend/README.md` and/or `BUILD_LOG.md`
- Modify: `docs/superpowers/specs/2026-09-07-question-bank-and-timers-design.md` (mark Status: implemented)

**Interfaces:** none — verification only.

- [ ] **Step 1: Backend full suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Frontend full suite + lint + build**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all green.

- [ ] **Step 3: Manual end-to-end (candidate flow)**

```bash
# terminal 1
cd backend && .venv/Scripts/python.exe -m uvicorn main:app --port 8000
# terminal 2
cd frontend && npm run dev
```
In the browser:
1. Start → enter a name → Begin. Confirm the device check appears, then 10 items.
2. Confirm each grammar/listening item shows two timers (Test + item) and the item timer counts 40/60s.
3. Let one grammar item's timer expire → confirm auto-advance, and that reloading does not bring it back.
4. Refresh mid-test → confirm you land back on the same item with earlier MCQ answers still selected after re-selecting is NOT needed (answers were saved server-side; the radio reflects `answers` state which resets — acceptable, document it).
5. Finish → report renders.
6. Open a second attempt → confirm the grammar items and/or option order differ from the first attempt.

- [ ] **Step 4: Seed + recruiter check**

```bash
cd backend
rm -f demo.db
ASSESSMENT_ALLOW_FIXED_SELECTION=1 .venv/Scripts/python.exe -m uvicorn main:app --port 8000 &
.venv/Scripts/python.exe seed_attempts.py
```
Expected: 4 attempts reach `done`, band spread ≥ 2. Visit `/recruiter` → table lists them.

- [ ] **Step 5: Offline check (PRD D4)**

With the stack running, disable networking, complete a full attempt. Expected: no failure (all calls are same-origin + localhost).

- [ ] **Step 6: Update docs + commit**

Update `BUILD_LOG.md` with a dated "Day 4" section summarising the bank, timers, and flow features and the verification results above. Flip the spec's Status line to `implemented`.

```bash
git add BUILD_LOG.md frontend/README.md docs/superpowers/specs/2026-09-07-question-bank-and-timers-design.md
git commit -m "Document question bank + timer features; mark spec implemented"
```

---

## Self-Review

**Spec coverage:**
- §2 test shape / counts → Global Constraints + Task 1 (`SELECTION_COUNTS`) + Task 2 (`select_items`).
- §3 `bank.json` shape, `subskill`, `time_limit_s` → Task 1 (schema + 9 items) + Task 7 (content).
- §4 `selection.py` (`select_items`, `option_permutations`) → Task 2. `canonical_letter` added to the module (used Task 5).
- §5 `Attempt` columns → Task 1 Step 6.
- §6 endpoints: `POST /api/attempts` → Task 3; `GET /api/attempts/{id}/items` + remove `GET /api/items` → Task 4; `submit_response`/`upload_audio` validation + canonical mapping → Task 5; `submit_attempt` scoping → Task 6; startup load/validate → Task 1.
- §7 scoring scope → Task 6; `objective.py` unchanged (confirmed).
- §8 timers → Task 10 (per-question save+advance) + Task 11 (global + amber).
- §9 resume → Task 13.
- §10 progress bar → Task 12.
- §11 known limitations → recorded in Task 8 Step 5 / Task 14 Step 6 (BUILD_LOG).
- §12 testing → each task's tests + Task 14 manual passes.
- §13 files touched → matches the per-task Files blocks. Seed-only fixed-selection hook (`ASSESSMENT_ALLOW_FIXED_SELECTION`) is an addition beyond the spec, needed so seeded attempts keep their hardcoded proficiency answer maps; documented in Task 3 and Task 8.

**Placeholder scan:** no TBD/TODO; every code step has real code; tests are spelled out. Task 7 (content authoring) necessarily describes the *shape* of 120 items with examples rather than listing all 120 — this is content, not logic, and each item follows the given template and the Global Constraints; the validation step (Task 7 Step 4-5) is concrete.

**Type consistency:**
- `select_items(bank_by_section, counts, rng)` — same signature in Task 2 definition and Task 3 call.
- `option_permutations(items, rng)` returns `{item_id: [int]}` — consumed identically in Task 3 (persist) and Task 4 (`_public_item`) and Task 5 (`canonical_letter`).
- `canonical_letter(display_letter, permutation)` — Task 2 def, Task 5 call, both `(str, list[int]) -> str`.
- `getAttemptItems(attemptId)` — Task 9 def, Tasks 13 use — consistent.
- `Timer` props `{ seconds, onExpire, itemKey }` unchanged; `Test` gains `initialIndex` — set in Task 13 def and App call.
- `saveSession/loadSession/clearSession` — Task 13, consistent shape `{ attemptId, index }`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-07-question-bank-and-timers.md`. Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
