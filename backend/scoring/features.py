import re

from scoring.asr import Word

PAUSE_THRESHOLD = 0.25  # seconds

_FILLERS = {"um", "uh", "erm", "hmm", "mm"}


def _is_filler(word: str) -> bool:
    return re.sub(r"[^a-z]", "", word.lower()) in _FILLERS


def extract_features(words: list[Word], total_duration: float) -> dict:
    """Fluency features per demo PRD §5.2, computed from Whisper word timestamps.

    `total_duration` is the audio clip's actual duration (from ffprobe), not
    just the span of detected words - silence before/after speech matters.
    """
    n_words = len(words)
    if n_words == 0 or total_duration <= 0:
        return {
            "speech_rate": 0.0,
            "articulation_rate": 0.0,
            "phonation_ratio": 0.0,
            "mean_length_of_run": 0.0,
            "pauses_per_100w": 0.0,
            "filled_pause_rate": 0.0,
        }

    speech_duration = sum(w.end - w.start for w in words)
    silence = max(total_duration - speech_duration, 0.0)

    pause_count = 0
    for prev, nxt in zip(words, words[1:]):
        if (nxt.start - prev.end) >= PAUSE_THRESHOLD:
            pause_count += 1

    filler_count = sum(1 for w in words if _is_filler(w.word))

    return {
        "speech_rate": n_words / total_duration * 60,
        "articulation_rate": (
            n_words / (total_duration - silence) * 60 if total_duration > silence else 0.0
        ),
        "phonation_ratio": (total_duration - silence) / total_duration,
        "mean_length_of_run": n_words / (pause_count + 1),
        "pauses_per_100w": pause_count / n_words * 100,
        "filled_pause_rate": filler_count / n_words * 100,
    }


def word_error_rate(reference_text: str, hypothesis_text: str) -> float:
    """Token-level Levenshtein distance / reference length, after normalising
    case and punctuation. 0.0 = identical, ~1.0 = completely different."""

    def normalize(text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        return text.split()

    ref = normalize(reference_text)
    hyp = normalize(hypothesis_text)
    if not ref:
        return 0.0 if not hyp else 1.0

    # Standard edit-distance DP over tokens.
    prev_row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        curr_row = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, start=1):
            cost = 0 if r == h else 1
            curr_row[j] = min(
                prev_row[j] + 1,       # deletion
                curr_row[j - 1] + 1,   # insertion
                prev_row[j - 1] + cost,  # substitution
            )
        prev_row = curr_row

    distance = prev_row[-1]
    return distance / len(ref)


def _band_speech_rate(sr: float) -> int:
    if sr >= 130:
        return 6
    if sr >= 110:
        return 5
    if sr >= 100:
        return 4
    if sr >= 90:
        return 3
    if sr > 0:
        return 2
    return 1


def _band_phonation_ratio(pr: float) -> int:
    if pr > 0.65:
        return 6
    if pr >= 0.58:
        return 5
    if pr >= 0.50:
        return 4
    if pr >= 0.42:
        return 3
    if pr > 0:
        return 2
    return 1


def _band_mean_length_of_run(mlr: float) -> int:
    if mlr > 7:
        return 6
    if mlr >= 5:
        return 5
    if mlr >= 4:
        return 4
    if mlr >= 3:
        return 3
    if mlr > 0:
        return 2
    return 1


def deterministic_fluency_band(features: dict) -> int:
    """Fluency band straight from the rubric's own thresholds - no LLM
    involved. Used for S1 (read-aloud), which the PRD scores via Whisper
    only (WER + fluency arithmetic), never the judge."""
    bands = [
        _band_speech_rate(features["speech_rate"]),
        _band_phonation_ratio(features["phonation_ratio"]),
        _band_mean_length_of_run(features["mean_length_of_run"]),
    ]
    return round(sum(bands) / len(bands))


def band_from_wer(wer: float) -> int:
    if wer <= 0.05:
        return 6
    if wer <= 0.15:
        return 5
    if wer <= 0.30:
        return 4
    if wer <= 0.50:
        return 3
    if wer <= 0.75:
        return 2
    return 1
