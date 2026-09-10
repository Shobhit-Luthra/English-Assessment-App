from scoring.asr import Word
from scoring.features import PAUSE_THRESHOLD, extract_features


def _words(timings: list[tuple[float, float]]) -> list[Word]:
    return [Word(word="word", start=s, end=e) for s, e in timings]


def test_features_are_nonzero_when_duration_and_words_present():
    words = _words([(0.2, 0.6), (0.8, 1.1), (1.3, 1.7), (2.0, 2.4)])
    features = extract_features(words, total_duration=2.3)
    # the whole point of the extraction - nothing may collapse to zero
    assert features["speech_rate"] > 0
    assert features["phonation_ratio"] > 0
    assert features["mean_length_of_run"] > 0
    assert features["articulation_rate"] > 0


def test_features_detect_pauses_between_words():
    words = _words([(0.0, 0.3), (1.0, 1.3), (2.0, 2.3)])
    features = extract_features(words, total_duration=2.3)
    assert features["pauses_per_100w"] > 0  # gaps exceed PAUSE_THRESHOLD


def test_zero_duration_guard_returns_all_zeros():
    words = _words([(0.0, 0.5), (0.6, 1.0)])
    assert extract_features(words, total_duration=0)["speech_rate"] == 0.0
    # missing word timestamps (empty list) also hit the guard
    assert extract_features([], total_duration=2.0)["phonation_ratio"] == 0.0


def test_pause_threshold_boundary():
    # a gap exactly at the threshold counts as a pause
    words = _words([(0.0, 0.3), (0.3 + PAUSE_THRESHOLD, 0.6 + PAUSE_THRESHOLD)])
    features = extract_features(words, total_duration=1.0)
    assert features["pauses_per_100w"] > 0