"""Question bank loading and access.

The bank is loaded once at startup into in-memory structures shared by all
attempt endpoints. Exposed as module-level accessors so handlers never depend
on each other's globals.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
BANK_PATH = BASE_DIR / "bank.json"
AUDIO_DIR = BASE_DIR / "audio"

SELECTION_COUNTS: dict[str, int] = {
    "grammar": 5,
    "listening": 2,
    "writing": 1,
    "speaking": 2,
}

_ITEMS_BY_ID: dict[str, dict] = {}
_BANK_BY_SECTION: dict[str, list[dict]] = {}


def load_bank() -> None:
    """Load bank.json and validate it can satisfy a full test shape."""
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


def get_item(item_id: str) -> dict | None:
    return _ITEMS_BY_ID.get(item_id)


def get_bank_by_section() -> dict[str, list[dict]]:
    return _BANK_BY_SECTION


def get_all_items() -> dict[str, dict]:
    return _ITEMS_BY_ID