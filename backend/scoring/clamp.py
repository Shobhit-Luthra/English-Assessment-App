from scoring.schemas import SpeakingScore


def apply_sanity_clamp(score: SpeakingScore, features: dict) -> SpeakingScore:
    """The JSON schema guarantees the response parses, not that the band is
    sensible - a small model can still emit a high fluency score against
    clearly halting acoustic features. Cap it when the features leave no
    room for doubt (demo PRD §5.4)."""
    if features["speech_rate"] < 90 and features["mean_length_of_run"] < 4:
        score.fluency = min(score.fluency, 3)
    return score
