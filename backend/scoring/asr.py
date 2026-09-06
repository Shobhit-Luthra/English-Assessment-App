import gc
from dataclasses import dataclass

from faster_whisper import WhisperModel

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel("small", device="cpu", compute_type="int8")
    return _model


def unload_model() -> None:
    """Release Whisper before the Ollama judge call - both compete for the
    same CPU/RAM, and running them concurrently causes swapping and
    multi-minute stalls (see demo PRD §5.4)."""
    global _model
    _model = None
    gc.collect()


@dataclass
class Word:
    word: str
    start: float
    end: float


def transcribe(audio_path: str) -> tuple[str, list[Word]]:
    model = _get_model()
    segments, _info = model.transcribe(audio_path, word_timestamps=True)
    words: list[Word] = []
    parts: list[str] = []
    for segment in segments:
        parts.append(segment.text.strip())
        for w in segment.words or []:
            words.append(Word(word=w.word.strip(), start=w.start, end=w.end))
    return " ".join(parts), words
