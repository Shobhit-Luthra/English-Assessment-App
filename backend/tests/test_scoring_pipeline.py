"""Pipeline behaviour with Whisper and the judge stubbed out: every attempt
must end with every CIR component and a ``cir`` row, judge output is
validated against the attempt, and failures are categorised rather than
leaking exception text."""

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import scoring.pipeline as pipeline
from bank import get_all_items, load_bank
from models import Attempt, Response, Score
from scoring.asr import Word
from scoring.schemas import AttemptScores, SpeakingScore, WritingScore

ITEM_IDS = ["g1", "g2", "l1", "w1", "s1", "s2"]


def _items_by_section():
    items = get_all_items()
    by_section: dict[str, list[dict]] = {}
    for item_id in ITEM_IDS:
        by_section.setdefault(items[item_id]["section"], []).append(items[item_id])
    return by_section


def _judged(speaking_ids=("s2",), writing_ids=("w1",)):
    return AttemptScores(
        speaking=[
            SpeakingScore(item_id=i, fluency=5, grammar=4, vocabulary=4, task_fulfilment=5,
                          justification="ok")
            for i in speaking_ids
        ],
        writing=[
            WritingScore(item_id=i, grammar=4, vocabulary=5, tone_appropriateness=5,
                         task_fulfilment=4, justification="ok")
            for i in writing_ids
        ],
    )


@pytest.fixture
def engine(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(pipeline, "engine", eng)
    load_bank()
    return eng


@pytest.fixture
def stubs(monkeypatch):
    """Whisper returns a short fluent transcript; the judge returns a full
    result unless a test overrides it."""
    text = "thank you for calling our support line i understand how frustrating"
    words = [Word(word=w, start=i * 0.4, end=i * 0.4 + 0.3) for i, w in enumerate(text.split())]
    monkeypatch.setattr(pipeline, "transcribe", lambda path: (text, words, 4.0))
    monkeypatch.setattr(pipeline, "unload_model", lambda: None)
    calls = []

    def fake_judge(prompt):
        calls.append(prompt)
        return _judged()

    monkeypatch.setattr(pipeline, "call_judge", fake_judge)
    return calls


def _seed_attempt(engine, *, with_s1=True, with_s2=True, with_w1=True):
    with Session(engine) as s:
        attempt = Attempt(name="T", item_ids=ITEM_IDS, status="scoring")
        s.add(attempt)
        s.commit()
        s.refresh(attempt)
        # objective sections are scored synchronously at /submit, before the
        # pipeline runs, so they are always present when it starts
        s.add(Score(attempt_id=attempt.id, dimension="grammar", band=6, evidence={}))
        s.add(Score(attempt_id=attempt.id, dimension="listening", band=4, evidence={}))
        if with_s1:
            s.add(Response(attempt_id=attempt.id, item_id="s1", audio_path="audio/x/s1.webm",
                           duration_ms=4000))
        if with_s2:
            s.add(Response(attempt_id=attempt.id, item_id="s2", audio_path="audio/x/s2.webm",
                           duration_ms=4000))
        if with_w1:
            s.add(Response(attempt_id=attempt.id, item_id="w1", text="Dear customer, I am sorry."))
        s.commit()
        return attempt.id


def _run(engine, attempt_id):
    pipeline.run_scoring_pipeline(attempt_id, _items_by_section())
    with Session(engine) as s:
        attempt = s.get(Attempt, attempt_id)
        rows = s.exec(select(Score).where(Score.attempt_id == attempt_id)).all()
        return attempt.status, attempt.error, {r.dimension: r for r in rows}


def test_full_attempt_gets_cir_and_all_components(engine, stubs):
    status, error, scores = _run(engine, _seed_attempt(engine))
    assert status == "done" and error is None
    for dim in ("speaking_fluency_s1", "speaking_fluency_s2", "situational_task_fulfilment",
                "writing_tone", "speaking", "writing", "cir"):
        assert dim in scores, dim


def test_skipped_speaking_item_scores_band_one_and_cir_still_present(engine, stubs, monkeypatch):
    monkeypatch.setattr(pipeline, "call_judge", lambda p: _judged(speaking_ids=()))
    status, _, scores = _run(engine, _seed_attempt(engine, with_s2=False))
    assert status == "done"
    assert scores["speaking_fluency_s2"].band == 1
    assert scores["speaking_fluency_s2"].evidence["missing"] is True
    assert scores["situational_task_fulfilment"].band == 1
    assert "cir" in scores


def test_skipped_writing_item_scores_band_one_and_cir_still_present(engine, stubs, monkeypatch):
    monkeypatch.setattr(pipeline, "call_judge", lambda p: _judged(writing_ids=()))
    status, _, scores = _run(engine, _seed_attempt(engine, with_w1=False))
    assert status == "done"
    assert scores["writing_tone"].band == 1
    assert scores["writing_tone"].evidence["missing"] is True
    assert scores["writing"].band == 1
    assert "cir" in scores


def test_nothing_attempted_still_completes_with_cir(engine, stubs, monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "call_judge", lambda p: calls.append(p))
    status, _, scores = _run(
        engine, _seed_attempt(engine, with_s1=False, with_s2=False, with_w1=False)
    )
    assert status == "done"
    assert calls == []  # nothing to judge
    # 0.35*1 + 0.25*4 + 0.20*1 + 0.20*1 = 1.75 -> band 2
    assert scores["cir"].band == 2


def test_full_rubric_subscores_are_persisted(engine, stubs):
    _, _, scores = _run(engine, _seed_attempt(engine))
    assert scores["speaking_fluency_s2"].evidence["scores"] == {
        "fluency": 5, "grammar": 4, "vocabulary": 4, "task_fulfilment": 5}
    assert scores["writing_tone"].evidence["scores"] == {
        "grammar": 4, "vocabulary": 5, "tone_appropriateness": 5, "task_fulfilment": 4}
    assert scores["writing"].evidence["by_item"]["w1"] == pytest.approx(4.5)


def test_judge_item_not_in_attempt_is_ignored(engine, stubs, monkeypatch):
    monkeypatch.setattr(pipeline, "call_judge", lambda p: _judged(speaking_ids=("s2", "s99")))
    status, _, scores = _run(engine, _seed_attempt(engine))
    assert status == "done"
    assert "speaking_fluency_s99" not in scores


def test_judge_omitting_an_item_is_retried_once_for_that_item(engine, stubs, monkeypatch):
    prompts = []

    def flaky(prompt):
        prompts.append(prompt)
        # first call drops the writing item; the retry (writing only) returns it
        return _judged(writing_ids=()) if len(prompts) == 1 else _judged(speaking_ids=())

    monkeypatch.setattr(pipeline, "call_judge", flaky)
    status, _, scores = _run(engine, _seed_attempt(engine))
    assert status == "done"
    assert len(prompts) == 2
    retry_body = prompts[1].split("Responses to score")[1]
    assert "Writing item w1" in retry_body
    assert "Speaking item s2" not in retry_body
    assert scores["writing_tone"].band == 5


def test_retry_result_cannot_overwrite_scores_from_the_first_pass(engine, stubs, monkeypatch):
    prompts = []

    def flaky(prompt):
        prompts.append(prompt)
        if len(prompts) == 1:
            return _judged(writing_ids=())  # s2 scored (fluency 5), w1 omitted
        # retry was asked only about w1 but also emits an s2 entry with a different band
        retry = _judged()
        retry.speaking[0].fluency = 1
        return retry

    monkeypatch.setattr(pipeline, "call_judge", flaky)
    status, _, scores = _run(engine, _seed_attempt(engine))
    assert status == "done"
    assert scores["speaking_fluency_s2"].band == 5  # first-pass score kept


def test_judge_still_omitting_after_retry_is_invalid_output(engine, stubs, monkeypatch):
    monkeypatch.setattr(pipeline, "call_judge", lambda p: _judged(writing_ids=()))
    status, error, scores = _run(engine, _seed_attempt(engine))
    assert status == "error"
    assert error == "judge_invalid_output"
    assert "speaking_fluency_s1" in scores  # deterministic rows survive


@pytest.mark.parametrize("exc", [
    ConnectionError("Failed to connect to Ollama"),   # what ollama-python raises on refused
    pytest.param(None, id="ReadTimeout"),
    pytest.param("response", id="ResponseError"),
])
def test_judge_connection_failure_is_categorised_and_keeps_objective_rows(
    engine, stubs, monkeypatch, exc
):
    import httpx
    import ollama

    if exc is None:
        exc = httpx.ReadTimeout("timed out")
    elif exc == "response":
        exc = ollama.ResponseError("internal error", 500)

    def down(prompt):
        raise exc

    monkeypatch.setattr(pipeline, "call_judge", down)
    status, error, scores = _run(engine, _seed_attempt(engine))
    assert status == "error"
    assert error == "judge_unavailable"
    assert "grammar" in scores and "speaking_fluency_s1" in scores


def test_asr_failure_is_categorised(engine, stubs, monkeypatch):
    def boom(path):
        raise RuntimeError("ffmpeg not found: C:\\secret\\path")

    monkeypatch.setattr(pipeline, "transcribe", boom)
    status, error, _ = _run(engine, _seed_attempt(engine))
    assert status == "error"
    assert error == "asr_failed"


def test_missing_objective_component_is_an_error_not_a_silent_done(engine, stubs):
    attempt_id = _seed_attempt(engine)
    with Session(engine) as s:
        row = s.exec(select(Score).where(Score.attempt_id == attempt_id,
                                         Score.dimension == "listening")).one()
        s.delete(row)
        s.commit()
    status, error, scores = _run(engine, attempt_id)
    assert status == "error"
    assert error == "unknown"
    assert "cir" not in scores
