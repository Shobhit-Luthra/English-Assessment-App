from dataclasses import dataclass

from faster_whisper import WhisperModel

# Loaded once at import time - reloading per request costs ~1s and ~1GB RAM
# per call, which is slow enough to look broken.
_model = WhisperModel("small", device="cpu", compute_type="int8")


@dataclass
class Word:
    word: str
    start: float
    end: float


def transcribe(audio_path: str) -> tuple[str, list[Word]]:
    segments, _info = _model.transcribe(audio_path, word_timestamps=True)
    words: list[Word] = []
    parts: list[str] = []
    for segment in segments:
        parts.append(segment.text.strip())
        for w in segment.words or []:
            words.append(Word(word=w.word.strip(), start=w.start, end=w.end))
    return " ".join(parts), words
