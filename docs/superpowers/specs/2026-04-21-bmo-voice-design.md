# BMO Voice Service — Design Spec

**Date:** 2026-04-21
**Phase:** 2 — Voice pipeline (wake word + STT + brain + TTS + playback)
**Scope:** `/services/voice` Python service only

---

## Overview

The Voice service is the audio I/O layer for the BMO assistant. It continuously listens for a wake word (or push-to-talk key), records the user's speech, transcribes it via Whisper, sends the text to the Brain service, synthesizes the response via Piper TTS, and plays it back through the speakers — then loops back to listening.

This spec covers Phase 2: a fully working local voice pipeline. The Brain service (`POST /chat`) from Phase 1 is the only external dependency.

---

## Folder Structure

```
services/voice/
├── main.py                  # Entry point — orchestrates the pipeline loop
├── requirements.txt         # Python dependencies
├── config.py                # All config read from env vars in one place
└── src/
    ├── wake_word.py         # OpenWakeWord detection + PTT key fallback
    ├── recorder.py          # Mic recording until silence
    ├── transcriber.py       # Whisper base STT
    ├── brain_client.py      # HTTP client → POST /chat on brain service
    ├── synthesizer.py       # Piper TTS subprocess → WAV bytes
    └── player.py            # sounddevice audio playback
```

Each module has one responsibility. Hardware-bound modules (`wake_word`, `recorder`, `player`) are not unit-tested; logic-bound modules (`transcriber`, `brain_client`, `synthesizer`) are fully tested with mocks.

---

## Data Flow

```
main.py loop (runs forever):
  │
  ├─1─► wake_word.listen()
  │       blocks until "hey BMO" detected OR PTT key (spacebar) pressed
  │
  ├─2─► recorder.record()
  │       captures mic audio until 1.5s of silence
  │       returns numpy audio array
  │
  ├─3─► transcriber.transcribe(audio)
  │       Whisper base → text string
  │       if empty → skip, back to step 1
  │
  ├─4─► brain_client.chat(text)
  │       POST {BRAIN_URL}/chat  { "text": text }
  │       returns response text string
  │       if error → synthesize + play fallback message, back to step 1
  │
  ├─5─► synthesizer.synthesize(response_text)
  │       Piper subprocess → WAV bytes
  │
  ├─6─► player.play(audio_bytes)
  │       sounddevice → default output device
  │
  └─────► back to step 1
```

---

## Component Details

### `config.py`

Reads all configuration from environment variables at import time. All other modules import from `config` — no env reads outside this file.

| Env var | Default | Purpose |
|---|---|---|
| `BRAIN_URL` | `http://localhost:3001` | Brain service base URL |
| `WHISPER_MODEL` | `base` | Whisper model size (tiny/base/small) |
| `PIPER_BINARY` | `piper` | Path or name of Piper executable |
| `PIPER_MODEL_PATH` | *(required)* | Absolute path to `.onnx` Piper voice model |
| `SILENCE_DURATION` | `1.5` | Seconds of silence that ends a recording |
| `SILENCE_THRESHOLD` | `0.01` | RMS amplitude below which audio is silence |
| `PTT_KEY` | `space` | Keyboard key for push-to-talk |

`PIPER_MODEL_PATH` must be set — the service fails fast on startup if missing.

### `wake_word.py`

Runs OpenWakeWord on a streaming microphone buffer. Simultaneously listens for the PTT key via the `keyboard` library. Whichever event fires first (wake word detection or key press) unblocks the caller and returns a string: `'wake_word'` or `'ptt'`. The other listener is cancelled.

### `recorder.py`

Records from the default microphone using `sounddevice`. Appends audio chunks to a buffer. Stops when the RMS amplitude of incoming chunks stays below `SILENCE_THRESHOLD` for `SILENCE_DURATION` seconds. Returns the buffer as a numpy float32 array at 16kHz (Whisper's required sample rate).

### `transcriber.py`

Loads the Whisper `base` model once at module import time (cached in memory for the process lifetime). Exposes `transcribe(audio_array: np.ndarray) -> str`. Returns an empty string if Whisper produces no meaningful output (silence, noise). Does not raise — returns empty string on failure.

### `brain_client.py`

Thin `httpx` client. Exposes `chat(text: str) -> str`. POSTs `{"text": text}` to `{BRAIN_URL}/chat`. Returns the `text` field from the JSON response. Raises `BrainServiceError` on non-2xx responses or connection errors, allowing `main.py` to handle gracefully.

### `synthesizer.py`

Invokes the Piper binary as a subprocess. Pipes the response text to stdin, captures WAV bytes from stdout. Exposes `synthesize(text: str) -> bytes`. Raises `SynthesisError` if the subprocess exits non-zero.

### `player.py`

Decodes WAV bytes using the `wave` standard library module, then plays through the default output device via `sounddevice.play()` + `sounddevice.wait()` (blocking playback). Exposes `play(wav_bytes: bytes) -> None`.

### `main.py`

Thin orchestrator. On startup: validates config, loads Whisper model (via import), checks Piper binary exists, checks microphone is available. Then enters the pipeline loop described in the Data Flow section above. Catches `BrainServiceError` and plays a fallback TTS message before looping.

---

## Error Handling

| Condition | Behavior |
|---|---|
| Whisper returns empty string | Skip silently, loop back to wake word |
| Brain service unreachable | Synthesize + play `"BMO's brain is sleeping..."`, loop back |
| Piper binary not found at startup | `sys.exit(1)` with clear error message |
| Microphone not available at startup | `sys.exit(1)` with clear error message |
| `PIPER_MODEL_PATH` not set | `sys.exit(1)` with clear error message |
| PTT and wake word fire simultaneously | First event wins; other listener cancelled |
| Piper subprocess exits non-zero | Log error, skip playback, loop back |

---

## Dependencies (`requirements.txt`)

```
openWakeWord
whisper
sounddevice
numpy
httpx
keyboard
```

Piper is a standalone binary — not a Python package. It must be installed separately and available on `PATH` (or set via `PIPER_BINARY` env var).

---

## Testing

Hardware-bound modules (`wake_word.py`, `recorder.py`, `player.py`) are tested manually — they require a microphone and speakers.

Logic-bound modules have unit tests:

| Test file | What it tests |
|---|---|
| `tests/test_transcriber.py` | Mock Whisper model; assert text returned, empty string on silence |
| `tests/test_brain_client.py` | Mock `httpx`; assert correct POST body, error handling on 503/timeout |
| `tests/test_synthesizer.py` | Mock Piper subprocess; assert WAV bytes returned, error on non-zero exit |
| `tests/test_pipeline.py` | Mock all 6 modules; assert correct call sequence in `main.py` |

Test runner: `pytest`.

---

## Out of Scope (Phase 2)

- Wake word training / custom model
- Multi-language STT
- Voice activity detection (VAD) beyond silence threshold
- Streaming TTS (sentence-by-sentence)
- WebSocket audio streaming to Electron UI
- Conversation history passed to brain service
