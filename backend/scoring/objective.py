def band_from_ratio(ratio: float) -> int:
    """Fixed-threshold mapping from percent-correct to a 1-6 band."""
    if ratio >= 1.0:
        return 6
    if ratio >= 0.75:
        return 5
    if ratio >= 0.5:
        return 4
    if ratio >= 0.25:
        return 3
    if ratio > 0.0:
        return 2
    return 1


def score_section(items: list[dict], responses_by_item: dict[str, str]) -> dict:
    """Answer-key comparison for a set of MCQ items. Returns band + evidence."""
    total = len(items)
    correct_ids = []
    incorrect_ids = []
    for item in items:
        given = (responses_by_item.get(item["id"]) or "").strip().lower()
        if given == item["answer"].strip().lower():
            correct_ids.append(item["id"])
        else:
            incorrect_ids.append(item["id"])

    ratio = len(correct_ids) / total if total else 0.0
    return {
        "band": band_from_ratio(ratio),
        "evidence": {
            "correct": len(correct_ids),
            "total": total,
            "correct_ids": correct_ids,
            "incorrect_ids": incorrect_ids,
        },
    }
