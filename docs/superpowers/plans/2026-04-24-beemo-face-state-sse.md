# Beemo Face State SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire 10 SVG face states into the desktop UI by adding an SSE state channel to the brain service and calling it from the voice pipeline on every step transition.

**Architecture:** The brain service gains a `/state` route — `POST /state` lets the Python pipeline push the current state, `GET /state/stream` pushes it to the browser via SSE. The desktop replaces its CSS face divs with a single `<img>` that swaps src on each SSE event.

**Tech Stack:** Node.js/Express (brain service), Python/httpx (voice pipeline), vanilla JS EventSource API (desktop UI), Jest/supertest (brain tests), pytest/pytest-mock (pipeline tests)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `services/brain/src/state.js` | Create | In-memory state store + SSE client list |
| `services/brain/src/routes/state.js` | Create | `POST /state` + `GET /state/stream` |
| `services/brain/src/__tests__/state.test.js` | Create | Unit tests for state store |
| `services/brain/src/__tests__/state.route.test.js` | Create | Route tests for POST + SSE |
| `services/brain/index.js` | Modify | Mount `/state` route |
| `services/voice/src/state_client.py` | Create | Fire-and-forget `set_state(key)` |
| `services/voice/tests/test_state_client.py` | Create | Tests for state_client |
| `services/voice/main.py` | Modify | Add `set_state` calls at each pipeline step |
| `services/voice/tests/test_pipeline.py` | Modify | Mock state_client + add state-transition test |
| `apps/desktop/index.html` | Modify | Replace face divs with `<img>`, add SSE script |
| `apps/desktop/styles.css` | Modify | Remove face CSS, add `#face-svg` rule |

---

## Task 1: Brain service — state store

**Files:**
- Create: `services/brain/src/state.js`
- Create: `services/brain/src/__tests__/state.test.js`

- [ ] **Step 1: Write the failing tests**

Create `services/brain/src/__tests__/state.test.js`:

```js
describe('state store', () => {
  let state;

  beforeEach(() => {
    jest.resetModules();
    state = require('../state');
  });

  it('starts with idle as current state', () => {
    expect(state.currentState).toBe('idle');
  });

  it('setState updates currentState', () => {
    state.setState('thinking');
    expect(state.currentState).toBe('thinking');
  });

  it('setState broadcasts to all clients', () => {
    const write1 = jest.fn();
    const write2 = jest.fn();
    state.clients.push({ write: write1 }, { write: write2 });
    state.setState('recording');
    expect(write1).toHaveBeenCalledWith('data: {"state":"recording"}\n\n');
    expect(write2).toHaveBeenCalledWith('data: {"state":"recording"}\n\n');
  });

  it('setState with no clients does not throw', () => {
    expect(() => state.setState('speaking')).not.toThrow();
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd services/brain && npx jest src/__tests__/state.test.js --no-coverage
```

Expected: FAIL with `Cannot find module '../state'`

- [ ] **Step 3: Implement the state store**

Create `services/brain/src/state.js`:

```js
const store = {
  currentState: 'idle',
  clients: [],
  setState(key) {
    this.currentState = key;
    const message = `data: ${JSON.stringify({ state: key })}\n\n`;
    this.clients.forEach(res => res.write(message));
  },
};

module.exports = store;
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd services/brain && npx jest src/__tests__/state.test.js --no-coverage
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add services/brain/src/state.js services/brain/src/__tests__/state.test.js
git commit -m "feat(brain): add in-memory state store with SSE broadcast"
```

---

## Task 2: Brain service — state route

**Files:**
- Create: `services/brain/src/routes/state.js`
- Create: `services/brain/src/__tests__/state.route.test.js`

- [ ] **Step 1: Write the failing tests**

Create `services/brain/src/__tests__/state.route.test.js`:

```js
const http = require('http');
const request = require('supertest');
const express = require('express');

describe('state route', () => {
  let app, state, stateRoute;

  beforeEach(() => {
    jest.resetModules();
    state = require('../state');
    stateRoute = require('../routes/state');
    app = express();
    app.use(express.json());
    app.use('/state', stateRoute);
  });

  describe('POST /state', () => {
    it('returns 204 and updates currentState', async () => {
      const res = await request(app).post('/state').send({ state: 'thinking' });
      expect(res.status).toBe(204);
      expect(state.currentState).toBe('thinking');
    });

    it('returns 400 when state field is missing', async () => {
      const res = await request(app).post('/state').send({});
      expect(res.status).toBe(400);
    });

    it('returns 400 when state is not a string', async () => {
      const res = await request(app).post('/state').send({ state: 42 });
      expect(res.status).toBe(400);
    });
  });

  describe('GET /state/stream', () => {
    it('sets SSE headers and sends current state immediately', (done) => {
      const server = app.listen(0, () => {
        const { port } = server.address();
        let data = '';
        const req = http.get(`http://localhost:${port}/state/stream`, (res) => {
          expect(res.headers['content-type']).toMatch('text/event-stream');
          expect(res.headers['cache-control']).toBe('no-cache');
          expect(res.headers['connection']).toBe('keep-alive');
          res.on('data', (chunk) => {
            data += chunk.toString();
            if (data.includes('\n\n')) {
              expect(data).toContain('data: {"state":"idle"}');
              req.destroy();
              server.close(done);
            }
          });
        });
      });
    });

    it('removes client from clients array on connection close', (done) => {
      const server = app.listen(0, () => {
        const { port } = server.address();
        const req = http.get(`http://localhost:${port}/state/stream`, () => {
          expect(state.clients.length).toBe(1);
          req.destroy();
          setTimeout(() => {
            expect(state.clients.length).toBe(0);
            server.close(done);
          }, 50);
        });
      });
    });
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd services/brain && npx jest src/__tests__/state.route.test.js --no-coverage
```

Expected: FAIL with `Cannot find module '../routes/state'`

- [ ] **Step 3: Implement the state route**

Create `services/brain/src/routes/state.js`:

```js
const { Router } = require('express');
const store = require('../state');

const router = Router();

router.post('/', (req, res) => {
  const { state } = req.body ?? {};
  if (!state || typeof state !== 'string') {
    return res.status(400).json({ error: 'state must be a non-empty string' });
  }
  store.setState(state);
  res.sendStatus(204);
});

router.get('/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.flushHeaders();

  res.write(`data: ${JSON.stringify({ state: store.currentState })}\n\n`);
  store.clients.push(res);

  req.on('close', () => {
    const i = store.clients.indexOf(res);
    if (i !== -1) store.clients.splice(i, 1);
  });
});

module.exports = router;
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd services/brain && npx jest src/__tests__/state.route.test.js --no-coverage
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add services/brain/src/routes/state.js services/brain/src/__tests__/state.route.test.js
git commit -m "feat(brain): add POST /state and GET /state/stream SSE route"
```

---

## Task 3: Wire state route into brain service

**Files:**
- Modify: `services/brain/index.js`

- [ ] **Step 1: Mount the state route**

In `services/brain/index.js`, add the require and `app.use` for the state route. The file currently ends at line 33. Add after line 5 (`const ragRoute = ...`):

```js
const stateRoute = require('./src/routes/state');
```

And after line 23 (`app.use('/rag', ragRoute);`):

```js
app.use('/state', stateRoute);
```

Full updated `services/brain/index.js`:

```js
require('dotenv').config();
const express = require('express');

const chatRoute = require('./src/routes/chat');
const visionRoute = require('./src/routes/vision');
const ragRoute = require('./src/routes/rag');
const stateRoute = require('./src/routes/state');

const app = express();
const PORT = process.env.PORT || 3001;

app.use(express.json());

app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    console.log(`${req.method} ${req.path} ${res.statusCode} — ${Date.now() - start}ms`);
  });
  next();
});

app.get('/health', (req, res) => res.json({ status: 'ok', service: 'brain' }));

app.use('/chat', chatRoute);
app.use('/vision', visionRoute);
app.use('/rag', ragRoute);
app.use('/state', stateRoute);

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Beemo Brain service running on port ${PORT} 🎮`);
  });
}

module.exports = app;
```

- [ ] **Step 2: Run the full brain test suite**

```bash
cd services/brain && npx jest --no-coverage
```

Expected: All existing tests pass + new state tests pass

- [ ] **Step 3: Commit**

```bash
git add services/brain/index.js
git commit -m "feat(brain): mount /state route"
```

---

## Task 4: Voice pipeline — state client

**Files:**
- Create: `services/voice/src/state_client.py`
- Create: `services/voice/tests/test_state_client.py`

- [ ] **Step 1: Write the failing tests**

Create `services/voice/tests/test_state_client.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import httpx
import config
from src.state_client import set_state


@pytest.fixture(autouse=True)
def set_brain_url(monkeypatch):
    monkeypatch.setattr(config, 'BRAIN_URL', 'http://localhost:3001')


def test_set_state_posts_correct_payload():
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch('src.state_client.httpx.post', return_value=mock_response) as mock_post:
        set_state('thinking')

    mock_post.assert_called_once_with(
        'http://localhost:3001/state',
        json={'state': 'thinking'},
        timeout=2.0,
    )


def test_set_state_silently_ignores_connect_error():
    with patch('src.state_client.httpx.post', side_effect=httpx.ConnectError('refused')):
        set_state('thinking')  # must not raise


def test_set_state_silently_ignores_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503
    with patch('src.state_client.httpx.post') as mock_post:
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            '503', request=MagicMock(), response=mock_response
        )
        set_state('thinking')  # must not raise


def test_set_state_silently_ignores_any_exception():
    with patch('src.state_client.httpx.post', side_effect=Exception('unexpected')):
        set_state('thinking')  # must not raise
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd services/voice && python -m pytest tests/test_state_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.state_client'`

- [ ] **Step 3: Implement the state client**

Create `services/voice/src/state_client.py`:

```python
import httpx
import config


def set_state(key: str) -> None:
    try:
        httpx.post(
            f'{config.BRAIN_URL}/state',
            json={'state': key},
            timeout=2.0,
        )
    except Exception:
        pass
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd services/voice && python -m pytest tests/test_state_client.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add services/voice/src/state_client.py services/voice/tests/test_state_client.py
git commit -m "feat(voice): add state_client with silent fire-and-forget set_state"
```

---

## Task 5: Voice pipeline — wire state calls into main.py

**Files:**
- Modify: `services/voice/main.py`
- Modify: `services/voice/tests/test_pipeline.py`

- [ ] **Step 1: Add autouse mock + state-transition test to test_pipeline.py**

In `services/voice/tests/test_pipeline.py`, add after the existing imports:

```python
from src import state_client  # noqa: F401 — imported so mocker can patch it
```

Add this fixture immediately before the first `def test_` function:

```python
@pytest.fixture(autouse=True)
def mock_set_state(mocker):
    return mocker.patch('src.state_client.set_state')
```

Add this test at the end of the file:

```python
def test_pipeline_emits_correct_state_transitions_on_happy_path(mocker, mock_set_state):
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello Beemo!')
    mocker.patch('src.brain_client.chat', return_value='Hi there!')
    mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert states == ['idle', 'listening', 'recording', 'transcribing', 'thinking', 'speaking', 'idle']


def test_pipeline_emits_fallback_state_when_brain_is_down(mocker, mock_set_state):
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.chat', side_effect=BrainServiceError('down'))
    mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert 'fallback' in states
    assert 'speaking' not in states


def test_pipeline_emits_error_state_when_recording_fails(mocker, mock_set_state):
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', side_effect=RecordingError('mic disconnected'))
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert 'error' in states


def test_pipeline_emits_silent_state_when_transcription_empty(mocker, mock_set_state):
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert 'silent' in states
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
cd services/voice && python -m pytest tests/test_pipeline.py::test_pipeline_emits_correct_state_transitions_on_happy_path -v
```

Expected: FAIL (state_client.set_state is not called yet — `main.py` hasn't been modified)

- [ ] **Step 3: Update main.py with state calls**

Replace the contents of `services/voice/main.py` with:

```python
import sys
import os
import shutil
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

import config
from src import wake_word, recorder, transcriber, brain_client, synthesizer, player, state_client

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

FALLBACK_MESSAGE = "Beemo's brain is sleeping... please try again later!"


def _validate() -> None:
    if config.PIPER_MODEL_PATH is None:
        sys.exit('ERROR: PIPER_MODEL_PATH environment variable is required.')
    piper_found = shutil.which(config.PIPER_BINARY) or os.path.isfile(config.PIPER_BINARY)
    if not piper_found:
        sys.exit(f'ERROR: Piper binary not found: {config.PIPER_BINARY}')
    try:
        import sounddevice as sd
        sd.query_devices(kind='input')
    except Exception as e:
        sys.exit(f'ERROR: Microphone not available: {e}')
    log.info('Startup checks passed.')


def run_pipeline() -> None:
    _validate()
    log.info('Beemo is ready! Listening for wake word or press [%s]...', config.PTT_KEY)

    while True:
        state_client.set_state('idle')
        try:
            trigger = wake_word.listen()
            log.info('Triggered by: %s', trigger)
        except RuntimeError as e:
            log.error('Wake word listener error: %s — retrying...', e)
            state_client.set_state('error')
            continue

        state_client.set_state('listening')

        try:
            state_client.set_state('recording')
            audio = recorder.record()
        except recorder.RecordingError as e:
            log.error('Recording failed: %s — retrying...', e)
            state_client.set_state('error')
            continue

        state_client.set_state('transcribing')
        text = transcriber.transcribe(audio)

        if not text:
            log.info('No speech detected, continuing...')
            state_client.set_state('silent')
            continue

        log.info('You said: %s', text)

        state_client.set_state('thinking')
        try:
            response_text = brain_client.chat(text)
            speak_state = 'speaking'
        except brain_client.BrainServiceError as e:
            log.error('Brain service error: %s', e)
            speak_state = 'fallback'
            response_text = FALLBACK_MESSAGE

        log.info('Beemo says: %s', response_text)

        state_client.set_state(speak_state)
        try:
            audio_bytes = synthesizer.synthesize(response_text)
            player.play(audio_bytes)
        except synthesizer.SynthesisError as e:
            log.error('Synthesis error: %s', e)

        log.info('Listening for wake word or press [%s]...', config.PTT_KEY)


if __name__ == '__main__':
    run_pipeline()
```

- [ ] **Step 4: Run the full pipeline test suite**

```bash
cd services/voice && python -m pytest tests/test_pipeline.py -v
```

Expected: All tests pass (existing 6 + new 4 = 10 tests)

- [ ] **Step 5: Commit**

```bash
git add services/voice/main.py services/voice/tests/test_pipeline.py
git commit -m "feat(voice): emit state transitions throughout pipeline"
```

---

## Task 6: Desktop UI — face image + SSE script + CSS

**Files:**
- Modify: `apps/desktop/index.html`
- Modify: `apps/desktop/styles.css`

- [ ] **Step 1: Replace index.html**

Replace `apps/desktop/index.html` with:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>BMO Desktop</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <div class="container">
      <div class="face">
        <img id="face-svg" src="states/Idle or listening.svg" alt="Beemo face" />
      </div>
      <div class="controls">
        <div class="CD"></div>
        <button class="blue-btn power-btn" type="button" aria-label="Toggle monochrome mode">
          <span class="power-icon" aria-hidden="true"></span>
        </button>
        <div class="yellow-btn">
          <span class="yellow-btn2"></span>
        </div>
        <div class="triangle">
          <span class="outline"></span>
          <span class="outline2"></span>
          <span class="outline3"></span>
        </div>
        <div class="green-btn"></div>
        <div class="blue-line"></div>
        <div class="red-btn"></div>
      </div>
    </div>
    <script>
      const STATE_FACES = {
        idle:         'states/Idle or listening.svg',
        listening:    'states/listening.svg',
        recording:    'states/recording or transcribing.svg',
        transcribing: 'states/recording or transcribing.svg',
        thinking:     'states/thinking or brain_request.svg',
        speaking:     ['states/speaking or playing_response.svg', 'states/speaking or playing_response (1).svg'],
        silent:       'states/silent_skip when transcription is empty.svg',
        error:        'states/error_recovering when something fails but the loop continues.svg',
        fallback:     'states/fallback_speaking when the brain is down and it plays the fallback line.svg',
        off:          'states/powered off.svg',
      };

      const faceSvg = document.getElementById('face-svg');
      const powerButton = document.querySelector('.power-btn');
      const container = document.querySelector('.container');

      let speakingInterval = null;
      let isPoweredOff = false;
      let es = null;

      function setFace(state) {
        clearInterval(speakingInterval);
        speakingInterval = null;
        const src = STATE_FACES[state];
        if (!src) return;
        if (Array.isArray(src)) {
          let frame = 0;
          faceSvg.src = src[0];
          speakingInterval = setInterval(() => {
            frame = (frame + 1) % src.length;
            faceSvg.src = src[frame];
          }, 500);
        } else {
          faceSvg.src = src;
        }
      }

      function connectSse() {
        if (es) es.close();
        es = new EventSource('http://localhost:3001/state/stream');
        es.onmessage = (event) => {
          if (isPoweredOff) return;
          const { state } = JSON.parse(event.data);
          setFace(state);
        };
      }

      powerButton.addEventListener('click', () => {
        container.classList.toggle('is-monochrome');
        isPoweredOff = container.classList.contains('is-monochrome');
        if (isPoweredOff) {
          setFace('off');
        } else {
          connectSse();
        }
      });

      connectSse();
    </script>
  </body>
</html>
```

- [ ] **Step 2: Update styles.css**

Replace `apps/desktop/styles.css` with:

```css
.body,
body {
  margin: 0;
  min-height: 100vh;
  background: #000;
  position: relative;
  overflow: auto;
}

body.is-monochrome {
  filter: grayscale(1);
}

body::before {
  content: "";
  position: fixed;
  inset: 0;
  background: url("./Adventure Time.jpg") center center / cover no-repeat;
  filter: blur(2px);
  transform: scale(1.08);
  z-index: 0;
}

.container {
  height: 16.875rem;
  width: 12.5rem;
  background-color: #43a899;
  position: absolute;
  margin: auto;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  border: black solid 0.2rem;
  border-radius: 0.4rem;
  transform: scale(2.5);
  transform-origin: center;
  z-index: 1;
}

.container.is-monochrome {
  filter: grayscale(1);
}

.face {
  height: 6.25rem;
  width: 9.375rem;
  margin-left: 1.5rem;
  margin-top: 1rem;
  border: black solid 1px;
  border-radius: 0.4rem;
  background-color: #8fecbf;
  overflow: hidden;
}

#face-svg {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: fill;
}

.CD {
  height: 0.625rem;
  width: 5.625rem;
  background-color: #072821;
  margin-top: 1rem;
  margin-left: 1.4rem;
}

.blue-btn {
  height: 0.6875rem;
  width: 0.6875rem;
  background-color: #00009c;
  border: black solid 1px;
  border-radius: 5rem;
  margin-top: -0.7rem;
  margin-left: 10rem;
}

.power-btn {
  appearance: none;
  -webkit-appearance: none;
  padding: 0;
  cursor: pointer;
  display: grid;
  place-items: center;
  position: relative;
}

.power-btn:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}

.power-icon {
  width: 0.22rem;
  height: 0.22rem;
  border: 0.8px solid #fff;
  border-radius: 50%;
  position: relative;
}

.power-icon::before {
  content: "";
  position: absolute;
  width: 0.075rem;
  height: 0.18rem;
  background: #fff;
  top: -0.11rem;
  left: 50%;
  transform: translateX(-50%);
  border-radius: 999px;
}

.yellow-btn {
  background-color: #fdd050;
  height: 3.75rem;
  position: relative;
  width: 1.25rem;
  left: 3.8rem;
  top: 1rem;
  border: black solid 1px;
}

.yellow-btn2 {
  height: 1.25rem;
  width: 1.3125rem;
  background-color: #fdd050;
  position: absolute;
  left: 1.2rem;
  bottom: 1.3rem;
  border-top: black solid 1px;
  border-right: black solid 1px;
  border-bottom: black solid 1px;
  border-left: #fdd050 solid 1px;
}

.yellow-btn2::after {
  content: "";
  height: 1.25rem;
  background-color: #fdd050;
  position: relative;
  display: block;
  left: -2.5rem;
  border-top: black solid 1px;
  border-left: black solid 1px;
  border-bottom: black solid 1px;
  border-right: #fdd050 solid 1px;
}

.triangle {
  width: 0;
  height: 0;
  border-left: 13px solid transparent;
  border-right: 13px solid transparent;
  border-bottom: 23px solid #48c2cf;
  top: -1.7rem;
  left: 8rem;
  position: relative;
}

.outline {
  border-bottom: solid black 1px;
  width: 1.5625rem;
  position: absolute;
  top: 1.4rem;
  left: -0.8rem;
}

.outline2 {
  border-bottom: solid black 1px;
  width: 1.625rem;
  position: absolute;
  top: 0.7rem;
  left: -1.2rem;
  transform: rotate(120deg);
}

.outline3 {
  border-bottom: solid black 1px;
  width: 1.625rem;
  position: absolute;
  top: 0.7rem;
  left: -0.4rem;
  transform: rotate(61deg);
}

.green-btn {
  height: 0.75rem;
  width: 0.75rem;
  background-color: #4dc07b;
  border: black solid 1px;
  border-radius: 5rem;
  top: 12rem;
  left: 10.3rem;
  position: absolute;
}

.red-btn {
  height: 1.5625rem;
  width: 1.5625rem;
  background-color: #e70e16;
  border: black solid 1px;
  border-radius: 5rem;
  top: -1.6rem;
  left: 8.9rem;
  position: relative;
}

.blue-line {
  height: 0.25rem;
  width: 1.625rem;
  background-color: #00009c;
  border: black solid 1px;
  border-radius: 5rem;
  left: 2.5rem;
  bottom: -0.8rem;
  position: relative;
}

.blue-line::after {
  content: "";
  height: 0.25rem;
  width: 1.625rem;
  background-color: #00009c;
  border: black solid 1px;
  border-radius: 5rem;
  left: 2.5rem;
  bottom: -0.1rem;
  position: absolute;
}
```

- [ ] **Step 3: Open the UI and manually verify face displays**

Open `apps/desktop/index.html` directly in a browser. The face box should show the idle face (two arc eyes + smile). Check browser console for errors — expect one benign `EventSource` connection error if the brain service is not running (this is fine; the face defaults to idle).

- [ ] **Step 4: Start the brain service and verify SSE connection**

```bash
cd services/brain && node index.js
```

In a second terminal:
```bash
curl -N http://localhost:3001/state/stream
```

Expected output: `data: {"state":"idle"}` followed by a held-open connection.

Refresh the desktop page — the face should show idle. Open browser DevTools → Network → filter by `state/stream` → confirm it shows as a pending SSE connection.

- [ ] **Step 5: Manually test a state transition**

```bash
curl -X POST http://localhost:3001/state -H "Content-Type: application/json" -d "{\"state\": \"thinking\"}"
```

Expected: the face in the browser immediately switches to the thinking face (small eyes + furrowed brows + frown).

Try each state key to verify all 10 SVGs display correctly:
```bash
for STATE in idle listening recording transcribing thinking speaking silent error fallback off; do
  curl -s -X POST http://localhost:3001/state -H "Content-Type: application/json" -d "{\"state\": \"$STATE\"}"
  echo "Set: $STATE — check browser"
  read -p "Press enter to continue..."
done
```

- [ ] **Step 6: Verify power button behaviour**

Click the power button — container should go grayscale AND face should show the X-eyes powered-off SVG. Click again — face should return to current pipeline state (idle if brain is running).

- [ ] **Step 7: Commit**

```bash
git add apps/desktop/index.html apps/desktop/styles.css
git commit -m "feat(ui): replace CSS face with SVG state images driven by SSE"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All 10 state keys mapped, all 3 services touched, SSE push model, CORS header, speaking animation, power button, silent error swallowing — all covered.
- [x] **No placeholders:** Every step has complete code.
- [x] **Type consistency:** `store.setState` / `store.clients` / `store.currentState` used consistently across state.js, state route, and state route tests. `set_state` in Python always takes a `str`.
- [x] **`speak_state` variable:** Used in `main.py` to choose between `'speaking'` and `'fallback'` — passed to a single `state_client.set_state(speak_state)` call, not two separate branches.
- [x] **Existing pipeline tests:** Protected by `autouse` `mock_set_state` fixture — no existing test needs modification beyond adding the fixture.
