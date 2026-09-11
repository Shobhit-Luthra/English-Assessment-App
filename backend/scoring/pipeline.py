import logging
from pathlib import Path

import httpx
import ollama
from pydantic import ValidationError
from sqlmodel import Session, select

from db import engine
from models import Attempt, Response, Score
from scoring.asr import transcribe, unload_model
from scoring.clamp import apply_sanity_clamp
from scoring.features import band_from_wer, deterministic_fluency_band, extract_features, word_error_rate
from scoring.judge import build_prompt, call_judge
from scoring.schemas import AttemptScores, SpeakingScore, WritingScore

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent

# CIR = 0.35*speaking_fluency + 0.25*listening + 0.20*writing_tone + 0.20*situational_task_fulfilment
# (demo PRD §5.5). speaking_fluency is the average of S1 (deterministic) and
# S2 (judged+clamped) - both are "speaking fluency" evidence.
CIR_WEIGHTS = {
    "speaking_fluency": 0.35,
    "listening": 0.25,
    "writing_tone": 0.20,
    "situational_task_fulfilment": 0.20,
}

# Stored in ``attempt.error`` and returned by /report. Short categories, never
# exception text: the message can name file paths, hosts and model internals.
ERROR_JUDGE_UNAVAILABLE = "judge_unavailable"
ERROR_JUDGE_INVALID = "judge_invalid_output"
ERROR_ASR_FAILED = "asr_failed"
ERROR_INTERRUPTED = "interrupted"
ERROR_UNKNOWN = "unknown"

ERROR_MESSAGES = {
    ERROR_JUDGE_UNAVAILABLE: "The scoring engine was unavailable. A recruiter can re-run scoring.",
    ERROR_JUDGE_INVALID: "The scoring engine returned an unusable result. A recruiter can re-run scoring.",
    ERROR_ASR_FAILED: "The recording could not be transcribed. A recruiter can re-run scoring.",
    ERROR_INTERRUPTED: "Scoring was interrupted by a server restart. A recruiter can re-run scoring.",
    ERROR_UNKNOWN: "Scoring failed unexpectedly. A recruiter can re-run scoring.",
}


class AsrError(Exception):
    """Whisper (or the audio decode in front of it) failed for one clip."""


class JudgeIncompleteError(Exception):
    """The judge did not return a score for every item, even after a retry."""


def run_scoring_pipeline(attempt_id: str, items_by_section: dict[str, list[dict]]) -> None:
    """Runs after /submit, via BackgroundTasks. Strictly sequential: all
    transcription happens before Whisper is released, which happens before
    the single judge call - Whisper and the local Ollama judge contend for the
    same CPU/RAM (demo PRD §5.4)."""
    with Session(engine) as session:
        attempt = session.get(Attempt, attempt_id)
        if attempt is None:
            return
        try:
            _run(session, attempt, items_by_section)
            attempt.status = "done"
            attempt.error = None
            session.add(attempt)
            session.commit()
        except Exception as e:  # noqa: BLE001 - pipeline must never leave an attempt stuck
            logger.exception("Scoring pipeline failed for attempt %s", attempt_id)
            session.rollback()
            attempt = session.get(Attempt, attempt_id)
            attempt.status = "error"
            attempt.error = _categorise(e)
            session.add(attempt)
            session.commit()


def fail_interrupted_attempts(session: Session) -> int:
    """Called at startup. A BackgroundTasks pipeline dies with the process, so
    any attempt still in ``scoring`` can never finish on its own; mark it
    ``error`` so it shows up as failed and can be re-scored."""
    stuck = session.exec(select(Attempt).where(Attempt.status == "scoring")).all()
    for attempt in stuck:
        attempt.status = "error"
        attempt.error = ERROR_INTERRUPTED
        session.add(attempt)
    session.commit()
    if stuck:
        logger.warning("marked %d attempt(s) left in 'scoring' by a restart as error", len(stuck))
    return len(stuck)


def _categorise(exc: Exception) -> str:
    if isinstance(exc, AsrError):
        return ERROR_ASR_FAILED
    if isinstance(exc, (ollama.ResponseError, httpx.HTTPError, ConnectionError)):
        return ERROR_JUDGE_UNAVAILABLE
    if isinstance(exc, (ValidationError, JudgeIncompleteError, ValueError)):
        return ERROR_JUDGE_INVALID
    return ERROR_UNKNOWN


def _judge(writing_entries: list[dict], speaking_entries: list[dict]) -> AttemptScores:
    """One judge call, validated against the items we asked about. Unknown
    item ids are dropped (a small model can invent one); missing items get a
    single targeted retry, then the attempt fails as invalid output rather
    than finishing with a silent gap."""
    expected_writing = {e["item_id"] for e in writing_entries}
    expected_speaking = {e["item_id"] for e in speaking_entries}
    if not expected_writing and not expected_speaking:
        return AttemptScores(speaking=[], writing=[])

    def _valid(
        result: AttemptScores, allowed_speaking: set[str], allowed_writing: set[str]
    ) -> tuple[dict[str, SpeakingScore], dict[str, WritingScore]]:
        speaking = {}
        for s in result.speaking:
            if s.item_id in allowed_speaking:
                speaking[s.item_id] = s
            else:
                logger.warning("judge returned unexpected speaking item id %r; ignored", s.item_id)
        writing = {}
        for w in result.writing:
            if w.item_id in allowed_writing:
                writing[w.item_id] = w
            else:
                logger.warning("judge returned unexpected writing item id %r; ignored", w.item_id)
        return speaking, writing

    speaking, writing = _valid(
        call_judge(build_prompt(writing_entries, speaking_entries)),
        expected_speaking, expected_writing,
    )

    missing_w = [e for e in writing_entries if e["item_id"] not in writing]
    missing_s = [e for e in speaking_entries if e["item_id"] not in speaking]
    if missing_w or missing_s:
        logger.warning(
            "judge omitted items (writing=%s, speaking=%s); retrying for those only",
            [e["item_id"] for e in missing_w], [e["item_id"] for e in missing_s],
        )
        # The retry only saw the missing items, so only those may come back
        # from it - a score it emits for an item it was not shown must not
        # replace the first pass.
        retry_s, retry_w = _valid(
            call_judge(build_prompt(missing_w, missing_s)),
            {e["item_id"] for e in missing_s}, {e["item_id"] for e in missing_w},
        )
        speaking.update(retry_s)
        writing.update(retry_w)
        still = [e["item_id"] for e in writing_entries + speaking_entries
                 if e["item_id"] not in writing and e["item_id"] not in speaking]
        if still:
            raise JudgeIncompleteError(f"judge omitted items after retry: {still}")

    return AttemptScores(speaking=list(speaking.values()), writing=list(writing.values()))


def _run(session: Session, attempt: Attempt, items_by_section: dict[str, list[dict]]) -> None:
    attempt_id = attempt.id
    responses = session.exec(select(Response).where(Response.attempt_id == attempt_id)).all()
    responses_by_item = {r.item_id: r for r in responses}

    speaking_items = items_by_section.get("speaking", [])
    writing_items = items_by_section.get("writing", [])

    transcripts: dict[str, str] = {}
    features_by_item: dict[str, dict] = {}
    wer_by_item: dict[str, float] = {}

    for item in speaking_items:
        resp = responses_by_item.get(item["id"])
        if not resp or not resp.audio_path:
            continue
        audio_path = BASE_DIR / resp.audio_path
        try:
            transcript, words, clip_duration = transcribe(str(audio_path))
        except Exception as e:  # noqa: BLE001 - any decode/model failure is "asr failed"
            raise AsrError(str(e)) from e
        transcripts[item["id"]] = transcript
        # ffprobe duration is preferred (it includes silence before/after the
        # detected speech); fall back to Whisper's decoded duration when ffprobe
        # is missing so the fluency features never collapse to zero.
        duration_s = (resp.duration_ms or 0) / 1000
        if duration_s <= 0:
            duration_s = clip_duration
        features_by_item[item["id"]] = extract_features(words, duration_s)
        if item["type"] == "read_aloud":
            wer_by_item[item["id"]] = word_error_rate(item["reference_text"], transcript)

    unload_model()  # release before the judge call - see module docstring

    fluency_bands: list[int] = []

    # S1: deterministic, Whisper-only (WER + fluency arithmetic, no LLM). A
    # skipped read-aloud scores band 1 so the attempt still gets every CIR
    # component - a missing row would silently drop the overall score.
    for item in speaking_items:
        if item["type"] != "read_aloud":
            continue
        if item["id"] not in transcripts:
            fluency_bands.append(1)
            session.add(_missing_row(attempt_id, f"speaking_fluency_{item['id']}", item["id"]))
            continue
        feats = features_by_item[item["id"]]
        wer = wer_by_item.get(item["id"], 1.0)
        band = round((deterministic_fluency_band(feats) + band_from_wer(wer)) / 2)
        fluency_bands.append(band)
        session.add(
            Score(
                attempt_id=attempt_id,
                dimension=f"speaking_fluency_{item['id']}",
                band=band,
                evidence={
                    "item_id": item["id"],
                    "transcript": transcripts[item["id"]],
                    "features": feats,
                    "wer": wer,
                },
            )
        )

    # Everything computed so far survives a judge failure: commit before the
    # network call so a re-score only has to redo the judged part.
    session.commit()

    writing_entries = [
        {"item_id": item["id"], "prompt": item["prompt"], "text": responses_by_item[item["id"]].text}
        for item in writing_items
        if item["id"] in responses_by_item and responses_by_item[item["id"]].text
    ]
    speaking_entries = [
        {
            "item_id": item["id"],
            "prompt": item.get("prompt", ""),
            "transcript": transcripts[item["id"]],
            "features": features_by_item[item["id"]],
        }
        for item in speaking_items
        if item["type"] == "situational" and item["id"] in transcripts
    ]

    judged = _judge(writing_entries, speaking_entries)
    judged_speaking_by_id = {s.item_id: s for s in judged.speaking}
    judged_writing_by_id = {w.item_id: w for w in judged.writing}

    # Composite section evidence: every judged sub-skill averaged into a single
    # 1-6 band per speaking/writing item, then averaged across items. These are
    # stored so recruiter-facing metrics reflect the full rubric instead of a
    # single dimension (fluency only / tone only).
    speaking_by_item: dict[str, float] = {}
    writing_by_item: dict[str, float] = {}

    # S2 (and any other situational item): judged + clamped, or band 1 if the
    # candidate never recorded it.
    for item in speaking_items:
        if item["type"] != "situational":
            continue
        s = judged_speaking_by_id.get(item["id"])
        if s is None:
            fluency_bands.append(1)
            speaking_by_item[item["id"]] = 1.0
            session.add(_missing_row(attempt_id, f"speaking_fluency_{item['id']}", item["id"]))
            session.add(_missing_row(attempt_id, "situational_task_fulfilment", item["id"]))
            continue
        feats = features_by_item.get(s.item_id)
        if feats:
            apply_sanity_clamp(s, feats)
        fluency_bands.append(s.fluency)
        subscores = {
            "fluency": s.fluency,
            "grammar": s.grammar,
            "vocabulary": s.vocabulary,
            "task_fulfilment": s.task_fulfilment,
        }
        speaking_by_item[s.item_id] = sum(subscores.values()) / len(subscores)
        session.add(
            Score(
                attempt_id=attempt_id,
                dimension=f"speaking_fluency_{s.item_id}",
                band=s.fluency,
                evidence={
                    "item_id": s.item_id,
                    "transcript": transcripts.get(s.item_id),
                    "features": feats,
                    "justification": s.justification,
                    "scores": subscores,
                },
            )
        )
        session.add(
            Score(
                attempt_id=attempt_id,
                dimension="situational_task_fulfilment",
                band=s.task_fulfilment,
                evidence={"item_id": s.item_id, "justification": s.justification},
            )
        )

    for item in writing_items:
        w = judged_writing_by_id.get(item["id"])
        if w is None:
            writing_by_item[item["id"]] = 1.0
            session.add(_missing_row(attempt_id, "writing_tone", item["id"]))
            continue
        subscores = {
            "grammar": w.grammar,
            "vocabulary": w.vocabulary,
            "tone_appropriateness": w.tone_appropriateness,
            "task_fulfilment": w.task_fulfilment,
        }
        writing_by_item[w.item_id] = sum(subscores.values()) / len(subscores)
        session.add(
            Score(
                attempt_id=attempt_id,
                dimension="writing_tone",
                band=w.tone_appropriateness,
                evidence={"item_id": w.item_id, "justification": w.justification, "scores": subscores},
            )
        )

    if speaking_by_item:
        session.add(_composite_row(attempt_id, "speaking", speaking_by_item))
    if writing_by_item:
        session.add(_composite_row(attempt_id, "writing", writing_by_item))

    session.commit()

    # CIR: average any per-item components (e.g. two speaking_fluency_* rows)
    # into single per-dimension values, then apply the weighted formula.
    all_scores = session.exec(select(Score).where(Score.attempt_id == attempt_id)).all()
    bands_by_dim: dict[str, list[int]] = {}
    for row in all_scores:
        dim = "speaking_fluency" if row.dimension.startswith("speaking_fluency_") else row.dimension
        bands_by_dim.setdefault(dim, []).append(row.band)

    components = {
        dim: (sum(vals) / len(vals) if (vals := bands_by_dim.get(dim)) else None) for dim in CIR_WEIGHTS
    }
    absent = [dim for dim, value in components.items() if value is None]
    if absent:
        # Every component is written above or at /submit; reaching here means a
        # bug or a partially-written attempt. Fail loudly rather than mark the
        # attempt done with no overall score.
        raise RuntimeError(f"CIR components missing for attempt {attempt_id}: {absent}")
    cir = sum(CIR_WEIGHTS[d] * components[d] for d in CIR_WEIGHTS)
    session.add(
        Score(
            attempt_id=attempt_id,
            dimension="cir",
            band=round(cir),
            evidence={"raw": cir, "components": components},
        )
    )
    session.commit()


def _missing_row(attempt_id: str, dimension: str, item_id: str) -> Score:
    return Score(
        attempt_id=attempt_id, dimension=dimension, band=1,
        evidence={"item_id": item_id, "missing": True},
    )


def _composite_row(attempt_id: str, dimension: str, by_item: dict[str, float]) -> Score:
    values = list(by_item.values())
    return Score(
        attempt_id=attempt_id,
        dimension=dimension,
        band=round(sum(values) / len(values)),
        evidence={"components": values, "by_item": by_item},
    )
