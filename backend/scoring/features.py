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
