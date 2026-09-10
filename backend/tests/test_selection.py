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
