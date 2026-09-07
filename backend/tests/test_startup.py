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
