import json

import ollama
import pytest

import scoring.judge as judge

_WRITING = [{"item_id": "w1", "prompt": "Reply to the customer", "text": "Sorry for the delay."}]
_SPEAKING = [{
    "item_id": "s2", "prompt": "Explain the process", "transcript": "First you open the app",
    "features": {"speech_rate": 120.0, "phonation_ratio": 0.6, "mean_length_of_run": 6.0,
                 "pauses_per_100w": 3.0, "filled_pause_rate": 0.0},
}]

_VALID_JSON = json.dumps({
    "speaking": [{"item_id": "s2", "fluency": 4, "grammar": 4, "vocabulary": 4,
                  "task_fulfilment": 4, "justification": "ok"}],
    "writing": [{"item_id": "w1", "grammar": 4, "vocabulary": 4, "tone_appropriateness": 4,
                 "task_fulfilment": 4, "justification": "ok"}],
})


def test_prompt_lists_every_item_id_that_must_be_scored():
    prompt = judge.build_prompt(_WRITING, _SPEAKING)
    head = prompt.split("## Rubric")[0]
    assert "w1" in head and "s2" in head


def test_call_judge_disables_thinking(monkeypatch):
    seen = {}

    def fake_chat(**kwargs):
        seen.update(kwargs)
        return {"message": {"content": _VALID_JSON}}

    monkeypatch.setattr(judge.ollama, "chat", fake_chat)
    result = judge.call_judge("prompt")
    assert seen["think"] is False
    assert result.writing[0].item_id == "w1"


def test_call_judge_retries_without_think_on_older_server(monkeypatch):
    calls = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        if "think" in kwargs:
            raise ollama.ResponseError("unknown option: think", 400)
        return {"message": {"content": _VALID_JSON}}

    monkeypatch.setattr(judge.ollama, "chat", fake_chat)
    result = judge.call_judge("prompt")
    assert len(calls) == 2 and "think" not in calls[1]
    assert result.speaking[0].item_id == "s2"


def test_call_judge_does_not_mask_other_server_errors(monkeypatch):
    def fake_chat(**kwargs):
        raise ollama.ResponseError("model not found", 404)

    monkeypatch.setattr(judge.ollama, "chat", fake_chat)
    with pytest.raises(ollama.ResponseError):
        judge.call_judge("prompt")


def test_empty_content_is_a_validation_error_not_a_crash(monkeypatch):
    from pydantic import ValidationError

    monkeypatch.setattr(judge.ollama, "chat", lambda **k: {"message": {"content": ""}})
    with pytest.raises(ValidationError):
        judge.call_judge("prompt")
