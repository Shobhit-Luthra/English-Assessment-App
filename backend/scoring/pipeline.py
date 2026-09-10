import logging
from pathlib import Path

from sqlmodel import Session, select

from db import engine
from models import Attempt, Response, Score
from scoring.asr import transcribe, unload_model
from scoring.clamp import apply_sanity_clamp
from scoring.features import band_from_wer, deterministic_fluency_band, extract_features, word_error_rate
from scoring.judge import build_prompt, call_judge

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


def run_scoring_pipeline(
    attempt_id: str, items_by_id: dict[str, dict], items_by_section: dict[str, list[dict]]
) -> None:
    """Runs after /submit, via BackgroundTasks. Strictly sequential: all
    transcription happens before Whisper is released, which happens before
    the single judge call - Whisper and the local Ollama judge contend for the
    same CPU/RAM (demo PRD §5.4)."""
    with Session(engine) as session:
        attempt = session.get(Attempt, attempt_id)
        if attempt is None:
            return
        try:
            _run(session, attempt, items_by_id, items_by_section)
            attempt.status = "done"
            session.add(attempt)
            session.commit()
        except Exception as e:  # noqa: BLE001 - pipeline must never leave an attempt stuck
            logger.exception("Scoring pipeline failed for attempt %s", attempt_id)
            session.rollback()
            attempt = session.get(Attempt, attempt_id)
            attempt.status = "error"
            attempt.error = str(e)[:2000]
            session.add(attempt)
            session.commit()


def _run(
    session: Session,
    attempt: Attempt,
    items_by_id: dict[str, dict],
    items_by_section: dict[str, list[dict]],
) -> None:
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
        transcript, words, clip_duration = transcribe(str(audio_path))
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

    judged = None
    if writing_entries or speaking_entries:
        prompt = build_prompt(writing_entries, speaking_entries)
        judged = call_judge(prompt)

    fluency_bands: list[int] = []

    # Composite section evidence: every judged sub-skill averaged into a single
    # 1-6 band per speaking/writing item, then averaged across items. These are
    # stored so recruiter-facing metrics reflect the full rubric instead of a
    # single dimension (fluency only / tone only).
    judged_speaking: list[float] = []
    judged_writing: list[float] = []

    # S1: deterministic, Whisper-only (WER + fluency arithmetic, no LLM).
    for item in speaking_items:
        if item["type"] != "read_aloud" or item["id"] not in transcripts:
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

    # S2 (and any other situational item): judged + clamped.
    if judged:
        for s in judged.speaking:
            feats = features_by_item.get(s.item_id)
            if feats:
                apply_sanity_clamp(s, feats)
            fluency_bands.append(s.fluency)
            judged_speaking.append(
                (s.fluency + s.grammar + s.vocabulary + s.task_fulfilment) / 4
            )
            session.add(
                Score(
                    attempt_id=attempt_id,
                    dimension=f"speaking_fluency_{s.item_id}",
                    band=s.fluency,
                    evidence={
                        "item_id": s.item_id,
                        "transcript": transcripts.get(s.item_id),
                        "features": features_by_item.get(s.item_id),
                        "justification": s.justification,
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

        for w in judged.writing:
            judged_writing.append(
                (w.grammar + w.vocabulary + w.tone_appropriateness + w.task_fulfilment) / 4
            )
            session.add(
                Score(
                    attempt_id=attempt_id,
                    dimension="writing_tone",
                    band=w.tone_appropriateness,
                    evidence={"item_id": w.item_id, "justification": w.justification},
                )
            )

    if judged_speaking:
        session.add(
            Score(
                attempt_id=attempt_id,
                dimension="speaking",
                band=round(sum(judged_speaking) / len(judged_speaking)),
                evidence={"components": judged_speaking},
            )
        )
    if judged_writing:
        session.add(
            Score(
                attempt_id=attempt_id,
                dimension="writing",
                band=round(sum(judged_writing) / len(judged_writing)),
                evidence={"components": judged_writing},
            )
        )

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
    if all(v is not None for v in components.values()):
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
