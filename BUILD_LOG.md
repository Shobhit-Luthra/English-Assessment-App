# Build Log

Tracks task completion against `03-build-plan.md`. One line per task once its acceptance criterion is verified.

## Day 0 — Pre-flight

- **Model choice:** Whisper `small` (CPU, int8) · Ollama `qwen2.5:3b-instruct`
- T0.1 — Ollama installed (winget, pre-existing), model pulled, terminal smoke test passed ("Hello! How can I assist you today?")
- T0.2 — Structured-output timing test: 1.70s (well under the 45s gate), valid JSON, sane bands
- T0.3 — Python 3.14.6 env + ffmpeg (winget) + faster-whisper smoke test passed: transcript correct, `words[0].start` returned a float
- T0.4 — Model choice recorded above
