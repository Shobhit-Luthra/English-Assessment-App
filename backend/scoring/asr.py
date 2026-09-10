import gc
from dataclasses import dataclass

from faster_whisper import WhisperModel

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel("small", device="cpu", compute_type="int8")
    return _model


def warm_up() -> None:
    """Instantiate the Whisper model at startup so the one-time weight
    download (the "small" model is ~460 MB) is paid before the first real
    submit, not while a candidate waits on the scoring screen."""
    _get_model()


def unload_model() -> None:
    """Release Whisper before the judge call - a local Ollama judge competes
    for the same CPU/RAM, and running both concurrently causes swapping and
    multi-minute stalls (see demo PRD §5.4)."""
    global _model
    _model = None
    gc.collect()


@dataclass
class Word:
    word: str
    start: float
    end: float


def transcribe(audio_path: str) -> tuple[str, list[Word], float]:
    """Transcribe audio, returning the transcript, word-level timestamps and
    the clip duration decoded by Whisper (seconds). The duration is a fallback
    source: ffmpeg/ffprobe is not guaranteed on every machine, and the fluent
    features need a non-zero total duration or they all collapse to zero."""
    model = _get_model()
    segments, info = model.transcribe(audio_path, word_timestamps=True)
    words: list[Word] = []
    parts: list[str] = []
    for segment in segments:
        parts.append(segment.text.strip())
        for w in segment.words or []:
            words.append(Word(word=w.word.strip(), start=w.start, end=w.end))
    return " ".join(parts), words, float(info.duration or 0.0)
