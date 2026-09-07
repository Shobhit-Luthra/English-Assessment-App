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
