# BMO Voice Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/services/voice` Python service that listens for a wake word (or push-to-talk), transcribes speech with Whisper, sends text to the Brain service, synthesizes a TTS response via Piper, and plays it back through the speakers.

**Architecture:** Modular pipeline — each stage is an independent module (`wake_word`, `recorder`, `transcriber`, `brain_client`, `synthesizer`, `player`) orchestrated by a thin `main.py`. Hardware-bound modules (wake word, recorder, player) are not unit-tested; logic-bound modules (brain client, synthesizer, transcriber) follow TDD with mocks.

**Tech Stack:** Python 3.10+, openai-whisper, openwakeword, sounddevice, httpx, keyboard, Piper (binary), pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `services/voice/requirements.txt` | Create | Python package dependencies |
| `services/voice/config.py` | Create | All env var reads in one place |
| `services/voice/src/__init__.py` | Create | Makes `src` a package |
| `services/voice/tests/__init__.py` | Create | Makes `tests` a package |
| `services/voice/tests/conftest.py` | Create | sys.path setup for pytest |
| `services/voice/src/brain_client.py` | Create | httpx POST to brain service, `BrainServiceError` |
| `services/voice/tests/test_brain_client.py` | Create | Unit tests for brain_client |
| `services/voice/src/synthesizer.py` | Create | Piper subprocess → WAV bytes, `SynthesisError` |
| `services/voice/tests/test_synthesizer.py` | Create | Unit tests for synthesizer |
| `services/voice/src/transcriber.py` | Create | Whisper base STT, lazy model load |
| `services/voice/tests/test_transcriber.py` | Create | Unit tests for transcriber |
| `services/voice/src/player.py` | Create | sounddevice WAV playback (no unit tests) |
| `services/voice/src/recorder.py` | Create | sounddevice mic recording until silence (no unit tests) |
| `services/voice/src/wake_word.py` | Create | OpenWakeWord + PTT threading (no unit tests) |
| `services/voice/main.py` | Create | Orchestrator: startup validation + pipeline loop |
| `services/voice/tests/test_pipeline.py` | Create | Integration test for pipeline call sequence |

---

## Task 1: Project setup — requirements.txt, config.py, package structure

**Files:**
- Create: `services/voice/requirements.txt`
- Create: `services/voice/config.py`
- Create: `services/voice/src/__init__.py`
- Create: `services/voice/tests/__init__.py`
- Create: `services/voice/tests/conftest.py`

- [ ] **Step 1: Create directories**

```bash
cd services/voice
mkdir -p src tests
```

- [ ] **Step 2: Write requirements.txt**

Create `services/voice/requirements.txt`:

```
openai-whisper
openwakeword
sounddevice
numpy
httpx
keyboard
pytest
pytest-mock
```

- [ ] **Step 3: Write config.py**

Create `services/voice/config.py`:

```python
import os

BRAIN_URL = os.getenv('BRAIN_URL', 'http://localhost:3001')
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
PIPER_BINARY = os.getenv('PIPER_BINARY', 'piper')
PIPER_MODEL_PATH = os.getenv('PIPER_MODEL_PATH')
SILENCE_DURATION = float(os.getenv('SILENCE_DURATION', '1.5'))
SILENCE_THRESHOLD = float(os.getenv('SILENCE_THRESHOLD', '0.01'))
PTT_KEY = os.getenv('PTT_KEY', 'space')
WAKE_WORD_MODEL = os.getenv('WAKE_WORD_MODEL', 'alexa')
```

No `sys.exit` here — validation happens in `main._validate()` at startup.

- [ ] **Step 4: Write src/__init__.py**

Create `services/voice/src/__init__.py` — empty file:

```python
```

- [ ] **Step 5: Write tests/__init__.py**

Create `services/voice/tests/__init__.py` — empty file:

```python
```

- [ ] **Step 6: Write tests/conftest.py**

Create `services/voice/tests/conftest.py`:

```python
import sys
import os

# Add services/voice/ to sys.path so 'config' and 'src.*' are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
```

- [ ] **Step 7: Install dependencies**

```bash
cd services/voice
pip install -r requirements.txt
```

Expected: packages install without errors. Piper is NOT in requirements.txt — it's a standalone binary installed separately.

- [ ] **Step 8: Verify pytest is available**

```bash
pytest --version
```

Expected: prints `pytest X.Y.Z`.

- [ ] **Step 9: Commit**

```bash
cd ../..
git add services/voice/requirements.txt services/voice/config.py \
        services/voice/src/__init__.py services/voice/tests/__init__.py \
        services/voice/tests/conftest.py
git commit -m "chore(voice): set up project structure, config, and requirements"
```

---

## Task 2: brain_client.py — TDD

**Files:**
- Create: `services/voice/src/brain_client.py`
- Create: `services/voice/tests/test_brain_client.py`

- [ ] **Step 1: Write the failing tests**

Create `services/voice/tests/test_brain_client.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import httpx


@pytest.fixture(autouse=True)
def set_brain_url(monkeypatch):
    monkeypatch.setenv('BRAIN_URL', 'http://localhost:3001')


def test_chat_returns_text_on_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {'text': 'Hello from BMO!'}
    mock_response.raise_for_status.return_value = None

    with patch('httpx.post', return_value=mock_response) as mock_post:
        from src.brain_client import chat
        result = chat('Hello!')

    assert result == 'Hello from BMO!'
    mock_post.assert_called_once_with(
        'http://localhost:3001/chat',
        json={'text': 'Hello!'},
        timeout=30.0,
    )


def test_chat_raises_brain_service_error_on_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503

    with patch('httpx.post') as mock_post:
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            '503 error', request=MagicMock(), response=mock_response
        )
        from src.brain_client import chat, BrainServiceError
        with pytest.raises(BrainServiceError, match='503'):
            chat('Hello!')


def test_chat_raises_brain_service_error_on_connection_failure():
    with patch('httpx.post', side_effect=httpx.ConnectError('Connection refused')):
        from src.brain_client import chat, BrainServiceError
        with pytest.raises(BrainServiceError, match='unreachable'):
            chat('Hello!')
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd services/voice
pytest tests/test_brain_client.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'src.brain_client'`

- [ ] **Step 3: Implement brain_client.py**

Create `services/voice/src/brain_client.py`:

```python
import httpx
import config


class BrainServiceError(Exception):
    pass


def chat(text: str) -> str:
    try:
        response = httpx.post(
            f'{config.BRAIN_URL}/chat',
            json={'text': text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()['text']
    except httpx.HTTPStatusError as e:
        raise BrainServiceError(
            f'Brain service returned {e.response.status_code}'
        ) from e
    except httpx.RequestError as e:
        raise BrainServiceError(f'Brain service unreachable: {e}') from e
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_brain_client.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add services/voice/src/brain_client.py services/voice/tests/test_brain_client.py
git commit -m "feat(voice): add brain_client with httpx POST and error handling"
```

---

## Task 3: synthesizer.py — TDD

**Files:**
- Create: `services/voice/src/synthesizer.py`
- Create: `services/voice/tests/test_synthesizer.py`

- [ ] **Step 1: Write the failing tests**

Create `services/voice/tests/test_synthesizer.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import subprocess


@pytest.fixture(autouse=True)
def set_piper_config(monkeypatch):
    monkeypatch.setenv('PIPER_BINARY', 'piper')
    monkeypatch.setenv('PIPER_MODEL_PATH', '/fake/model.onnx')


def test_synthesize_returns_wav_bytes():
    fake_wav = b'RIFF\x24\x00\x00\x00WAVEfmt '
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = fake_wav

    with patch('subprocess.run', return_value=mock_result) as mock_run:
        from src.synthesizer import synthesize
        result = synthesize('Hello BMO!')

    assert result == fake_wav
    mock_run.assert_called_once_with(
        ['piper', '--model', '/fake/model.onnx'],
        input=b'Hello BMO!',
        capture_output=True,
    )


def test_synthesize_raises_on_nonzero_exit():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = b'model not found'

    with patch('subprocess.run', return_value=mock_result):
        from src.synthesizer import synthesize, SynthesisError
        with pytest.raises(SynthesisError, match='Piper exited with code 1'):
            synthesize('Hello!')


def test_synthesize_raises_when_piper_binary_missing():
    with patch('subprocess.run', side_effect=FileNotFoundError):
        from src.synthesizer import synthesize, SynthesisError
        with pytest.raises(SynthesisError, match='Piper binary not found'):
            synthesize('Hello!')
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd services/voice
pytest tests/test_synthesizer.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'src.synthesizer'`

- [ ] **Step 3: Implement synthesizer.py**

Create `services/voice/src/synthesizer.py`:

```python
import subprocess
import config


class SynthesisError(Exception):
    pass


def synthesize(text: str) -> bytes:
    try:
        result = subprocess.run(
            [config.PIPER_BINARY, '--model', config.PIPER_MODEL_PATH],
            input=text.encode('utf-8'),
            capture_output=True,
        )
        if result.returncode != 0:
            raise SynthesisError(
                f'Piper exited with code {result.returncode}: {result.stderr.decode()}'
            )
        return result.stdout
    except FileNotFoundError:
        raise SynthesisError(f'Piper binary not found: {config.PIPER_BINARY}')
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_synthesizer.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add services/voice/src/synthesizer.py services/voice/tests/test_synthesizer.py
git commit -m "feat(voice): add Piper synthesizer with subprocess wrapper and error handling"
```

---

## Task 4: transcriber.py — TDD

**Files:**
- Create: `services/voice/src/transcriber.py`
- Create: `services/voice/tests/test_transcriber.py`

- [ ] **Step 1: Write the failing tests**

Create `services/voice/tests/test_transcriber.py`:

```python
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
import src.transcriber as transcriber_module


@pytest.fixture(autouse=True)
def reset_cached_model():
    transcriber_module._model = None
    yield
    transcriber_module._model = None


def _make_mock_model(text_result):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {'text': text_result}
    return mock_model


def test_transcribe_returns_stripped_text():
    mock_model = _make_mock_model('  Hello BMO!  ')

    with patch('src.transcriber.whisper') as mock_whisper:
        mock_whisper.load_model.return_value = mock_model
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == 'Hello BMO!'
    mock_model.transcribe.assert_called_once()


def test_transcribe_returns_empty_string_on_silence():
    mock_model = _make_mock_model('   ')

    with patch('src.transcriber.whisper') as mock_whisper:
        mock_whisper.load_model.return_value = mock_model
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == ''


def test_transcribe_returns_empty_string_on_exception():
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError('GPU error')

    with patch('src.transcriber.whisper') as mock_whisper:
        mock_whisper.load_model.return_value = mock_model
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == ''


def test_model_is_loaded_once_and_cached():
    mock_model = _make_mock_model('hi')

    with patch('src.transcriber.whisper') as mock_whisper:
        mock_whisper.load_model.return_value = mock_model
        audio = np.zeros(16000, dtype=np.float32)
        transcriber_module.transcribe(audio)
        transcriber_module.transcribe(audio)

    mock_whisper.load_model.assert_called_once()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd services/voice
pytest tests/test_transcriber.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'src.transcriber'`

- [ ] **Step 3: Implement transcriber.py**

Create `services/voice/src/transcriber.py`:

```python
import numpy as np
import whisper
import config

_model = None


def _load_model():
    global _model
    if _model is None:
        _model = whisper.load_model(config.WHISPER_MODEL)
    return _model


def transcribe(audio_array: np.ndarray) -> str:
    model = _load_model()
    try:
        result = model.transcribe(audio_array, fp16=False)
        return result.get('text', '').strip()
    except Exception:
        return ''
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_transcriber.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add services/voice/src/transcriber.py services/voice/tests/test_transcriber.py
git commit -m "feat(voice): add Whisper transcriber with lazy model loading and tests"
```

---

## Task 5: player.py — implementation (no unit tests)

**Files:**
- Create: `services/voice/src/player.py`

- [ ] **Step 1: Implement player.py**

Create `services/voice/src/player.py`:

```python
import io
import wave
import numpy as np
import sounddevice as sd


def play(wav_bytes: bytes) -> None:
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels)

    sd.play(audio, sample_rate)
    sd.wait()
```

- [ ] **Step 2: Commit**

```bash
cd ../..
git add services/voice/src/player.py
git commit -m "feat(voice): add sounddevice audio player"
```

---

## Task 6: recorder.py — implementation (no unit tests)

**Files:**
- Create: `services/voice/src/recorder.py`

- [ ] **Step 1: Implement recorder.py**

Create `services/voice/src/recorder.py`:

```python
import numpy as np
import sounddevice as sd
import config

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1  # 100ms per chunk


def record() -> np.ndarray:
    buffer = []
    silence_chunks = 0
    silence_limit = int(config.SILENCE_DURATION / CHUNK_DURATION)
    chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
        while True:
            chunk, _ = stream.read(chunk_samples)
            buffer.append(chunk)
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            if rms < config.SILENCE_THRESHOLD:
                silence_chunks += 1
                if silence_chunks >= silence_limit:
                    break
            else:
                silence_chunks = 0

    return np.concatenate(buffer, axis=0).flatten()
```

- [ ] **Step 2: Commit**

```bash
cd ../..
git add services/voice/src/recorder.py
git commit -m "feat(voice): add mic recorder with silence detection"
```

---

## Task 7: wake_word.py — implementation (no unit tests)

**Files:**
- Create: `services/voice/src/wake_word.py`

- [ ] **Step 1: Implement wake_word.py**

Create `services/voice/src/wake_word.py`:

```python
import queue
import threading
import numpy as np
import sounddevice as sd
import keyboard
from openwakeword.model import Model
import config

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # ~80ms, recommended chunk size for OpenWakeWord


def listen() -> str:
    """Block until wake word detected or PTT key pressed.

    Returns 'wake_word' or 'ptt'.
    """
    result_queue: queue.Queue[str] = queue.Queue(maxsize=1)
    stop_event = threading.Event()

    def _wake_word_thread() -> None:
        oww = Model(wakeword_models=[config.WAKE_WORD_MODEL], inference_framework='onnx')
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16') as stream:
            while not stop_event.is_set():
                chunk, _ = stream.read(CHUNK_SAMPLES)
                scores = oww.predict(chunk.flatten())
                for score in scores.values():
                    if score > 0.5 and result_queue.empty():
                        result_queue.put('wake_word')
                        return

    def _ptt_handler() -> None:
        if result_queue.empty():
            result_queue.put('ptt')

    wake_thread = threading.Thread(target=_wake_word_thread, daemon=True)
    keyboard.add_hotkey(config.PTT_KEY, _ptt_handler)
    wake_thread.start()

    result = result_queue.get()
    stop_event.set()
    keyboard.remove_all_hotkeys()
    return result
```

**Note:** On Linux, the `keyboard` library requires root privileges or `uinput` access. On Windows, it works without elevated permissions.

- [ ] **Step 2: Commit**

```bash
cd ../..
git add services/voice/src/wake_word.py
git commit -m "feat(voice): add wake word listener with OpenWakeWord and PTT fallback"
```

---

## Task 8: main.py + pipeline integration test — TDD

**Files:**
- Create: `services/voice/main.py`
- Create: `services/voice/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing pipeline test**

Create `services/voice/tests/test_pipeline.py`:

```python
import pytest
import numpy as np
import sys
import os

# Ensure services/voice/ is on path for 'import main'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv('PIPER_MODEL_PATH', '/fake/model.onnx')
    monkeypatch.setenv('BRAIN_URL', 'http://localhost:3001')


def test_pipeline_runs_full_happy_path(mocker):
    """Wake word fires → record → transcribe → chat → synthesize → play → loop back."""
    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] > 1:
            raise KeyboardInterrupt
        return 'wake_word'

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello BMO!')
    mock_chat = mocker.patch('src.brain_client.chat', return_value='Hi there friend!')
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00\x01')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    import main
    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_chat.assert_called_once_with('Hello BMO!')
    mock_synthesize.assert_called_once_with('Hi there friend!')
    mock_play.assert_called_once_with(b'\x00\x01')


def test_pipeline_skips_when_transcription_is_empty(mocker):
    """Empty transcription → skip brain call, loop back immediately."""
    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] > 1:
            raise KeyboardInterrupt
        return 'ptt'

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='')
    mock_chat = mocker.patch('src.brain_client.chat')
    mocker.patch('main._validate')

    import main
    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_chat.assert_not_called()


def test_pipeline_plays_fallback_when_brain_unavailable(mocker):
    """BrainServiceError → synthesize + play the fallback message."""
    from src.brain_client import BrainServiceError

    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] > 1:
            raise KeyboardInterrupt
        return 'wake_word'

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.chat', side_effect=BrainServiceError('down'))
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    import main
    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_synthesize.assert_called_once_with(main.FALLBACK_MESSAGE)
    mock_play.assert_called_once_with(b'\x00')
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd services/voice
pytest tests/test_pipeline.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Implement main.py**

Create `services/voice/main.py`:

```python
import sys
import os
import shutil
import logging

sys.path.insert(0, os.path.dirname(__file__))

import config
from src import wake_word, recorder, transcriber, brain_client, synthesizer, player

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

FALLBACK_MESSAGE = "BMO's brain is sleeping... please try again later!"


def _validate() -> None:
    if config.PIPER_MODEL_PATH is None:
        sys.exit('ERROR: PIPER_MODEL_PATH environment variable is required.')
    if shutil.which(config.PIPER_BINARY) is None:
        sys.exit(f'ERROR: Piper binary not found: {config.PIPER_BINARY}')
    try:
        import sounddevice as sd
        sd.query_devices(kind='input')
    except Exception as e:
        sys.exit(f'ERROR: Microphone not available: {e}')
    log.info('Startup checks passed.')


def run_pipeline() -> None:
    _validate()
    log.info('BMO is ready! Listening for wake word or press [%s]...', config.PTT_KEY)

    while True:
        trigger = wake_word.listen()
        log.info('Triggered by: %s', trigger)

        audio = recorder.record()
        text = transcriber.transcribe(audio)

        if not text:
            log.info('No speech detected, continuing...')
            continue

        log.info('You said: %s', text)

        try:
            response_text = brain_client.chat(text)
        except brain_client.BrainServiceError as e:
            log.error('Brain service error: %s', e)
            response_text = FALLBACK_MESSAGE

        log.info('BMO says: %s', response_text)

        try:
            audio_bytes = synthesizer.synthesize(response_text)
            player.play(audio_bytes)
        except synthesizer.SynthesisError as e:
            log.error('Synthesis error: %s', e)

        log.info('Listening for wake word or press [%s]...', config.PTT_KEY)


if __name__ == '__main__':
    run_pipeline()
```

- [ ] **Step 4: Run pipeline tests — verify they pass**

```bash
cd services/voice
pytest tests/test_pipeline.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Run the full test suite**

```bash
pytest --tb=short
```

Expected: `10 passed` (3 brain_client + 3 synthesizer + 4 transcriber = 10; pipeline = 3 → total 13 passed).

- [ ] **Step 6: Commit**

```bash
cd ../..
git add services/voice/main.py services/voice/tests/test_pipeline.py
git commit -m "feat(voice): add pipeline orchestrator with startup validation and full test coverage"
```

---

## Done

Phase 2 of the Voice service is complete. The service:
- Listens for wake word (`WAKE_WORD_MODEL`, default `alexa`) OR PTT key (`PTT_KEY`, default `space`)
- Records mic audio until `SILENCE_DURATION` seconds of silence
- Transcribes via Whisper `base` model (cached in memory)
- Sends text to Brain service (`POST /chat`) and receives response
- Synthesizes response via Piper TTS subprocess
- Plays WAV audio through speakers via sounddevice
- Plays fallback message if Brain service is unreachable

**To run:**
```bash
cd services/voice
export PIPER_MODEL_PATH=/path/to/en_US-lessac-medium.onnx
python main.py
```

**Next phase:** Add intent routing (Phase 3) or camera + vision (Phase 4).
