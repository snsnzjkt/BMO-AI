# Sentence-Level Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Beemo start speaking after the first sentence by streaming tokens from Ollama, splitting them into sentences in the brain service, and synthesizing + playing each sentence in the voice pipeline as it arrives.

**Architecture:** A new `chatStream()` async generator in `ollamaClient.js` calls Ollama's `/api/chat` with `stream: true` and yields tokens. `streamChatPipeline()` in `chatPipeline.js` accumulates tokens into sentences and yields them one at a time while updating conversation history at the end. A new `POST /chat/stream` route sends sentences as NDJSON. The Python voice pipeline's `stream_chat()` reads the NDJSON stream and `main.py` synthesizes and plays each sentence before reading the next.

**Tech Stack:** Node.js/Express, Ollama `/api/chat` streaming, NDJSON, Python/httpx streaming, Piper TTS

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `services/brain/src/services/ollamaClient.js` | Modify | Add `chatStream(model, messages)` async generator |
| `services/brain/src/__tests__/ollamaClient.test.js` | Modify | Add tests for `chatStream()` |
| `services/brain/src/pipelines/chatPipeline.js` | Modify | Add `streamChatPipeline(text)` async generator |
| `services/brain/src/__tests__/chatPipeline.test.js` | Modify | Add tests for `streamChatPipeline()` |
| `services/brain/src/routes/chat.js` | Modify | Add `POST /chat/stream` NDJSON handler |
| `services/brain/src/__tests__/chat.test.js` | Modify | Add tests for `/chat/stream` |
| `services/voice/src/brain_client.py` | Modify | Add `stream_chat(text)` generator |
| `services/voice/tests/test_brain_client.py` | Modify | Add tests for `stream_chat()` |
| `services/voice/main.py` | Modify | Replace single chat+synthesize+play with per-sentence loop |
| `services/voice/tests/test_pipeline.py` | Modify | Update to mock `stream_chat`, add streaming path tests |

---

## Task 1: Add `chatStream()` to ollamaClient

**Files:**
- Modify: `services/brain/src/services/ollamaClient.js`
- Modify: `services/brain/src/__tests__/ollamaClient.test.js`

- [ ] **Step 1: Write failing tests for `chatStream()`**

Add `chatStream` to the import on line 1 of `services/brain/src/__tests__/ollamaClient.test.js`:

```js
const { generate, chat, chatStream } = require('../services/ollamaClient');
```

Append this `describe` block at the end of the file:

```js
describe('ollamaClient.chatStream', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
    delete global.fetch;
  });

  function makeReader(lines) {
    const encoder = new TextEncoder();
    const chunks = lines.map(l => encoder.encode(l + '\n'));
    let i = 0;
    return {
      read: jest.fn().mockImplementation(async () => {
        if (i < chunks.length) return { done: false, value: chunks[i++] };
        return { done: true, value: undefined };
      }),
    };
  }

  it('yields token content from Ollama streaming response', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      body: {
        getReader: () => makeReader([
          JSON.stringify({ message: { content: 'Hello' }, done: false }),
          JSON.stringify({ message: { content: ' world' }, done: false }),
          JSON.stringify({ message: { content: '' }, done: true }),
        ]),
      },
    });

    const tokens = [];
    for await (const token of chatStream('gemma3', [])) {
      tokens.push(token);
    }

    expect(tokens).toEqual(['Hello', ' world']);
  });

  it('stops yielding at done:true even if more lines follow', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      body: {
        getReader: () => makeReader([
          JSON.stringify({ message: { content: 'Hi' }, done: false }),
          JSON.stringify({ message: { content: '' }, done: true }),
          JSON.stringify({ message: { content: 'after done' }, done: false }),
        ]),
      },
    });

    const tokens = [];
    for await (const token of chatStream('gemma3', [])) {
      tokens.push(token);
    }

    expect(tokens).toEqual(['Hi']);
  });

  it('throws when Ollama returns a non-ok status', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 503 });

    const gen = chatStream('gemma3', []);
    await expect(gen.next()).rejects.toThrow('Ollama request failed: 503');
  });

  it('calls /api/chat with stream:true and shared options', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      body: { getReader: () => makeReader([JSON.stringify({ message: { content: '' }, done: true })]) },
    });

    const msgs = [{ role: 'user', content: 'hi' }];
    for await (const _ of chatStream('gemma3', msgs)) { /* drain */ }

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:11434/api/chat',
      expect.objectContaining({
        body: JSON.stringify({
          model: 'gemma3',
          messages: msgs,
          stream: true,
          options: { num_predict: 80, temperature: 0.7 },
        }),
      })
    );
  });
});
```

- [ ] **Step 2: Run tests to confirm the new ones fail**

```bash
cd services/brain && npx jest src/__tests__/ollamaClient.test.js --no-coverage
```

Expected: 9 existing tests PASS, 4 new `chatStream` tests FAIL with `chatStream is not a function`

- [ ] **Step 3: Implement `chatStream()` in ollamaClient.js**

Replace the full file with:

```js
const BASE_URL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
const GENERATION_OPTIONS = { num_predict: 80, temperature: 0.7 };

async function generate(model, prompt, system = '') {
  const response = await fetch(`${BASE_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, prompt, system, stream: false, options: GENERATION_OPTIONS }),
  });

  if (!response.ok) {
    throw new Error(`Ollama request failed: ${response.status}`);
  }

  const data = await response.json();
  if (data.response === undefined) {
    throw new Error('Ollama response missing "response" field');
  }
  return data.response;
}

async function chat(model, messages) {
  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages, stream: false, options: GENERATION_OPTIONS }),
  });

  if (!response.ok) {
    throw new Error(`Ollama request failed: ${response.status}`);
  }

  const data = await response.json();
  if (!data.message?.content) {
    throw new Error('Ollama response missing "message.content" field');
  }
  return data.message.content;
}

async function* chatStream(model, messages) {
  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages, stream: true, options: GENERATION_OPTIONS }),
  });

  if (!response.ok) {
    throw new Error(`Ollama request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let lineBuffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    lineBuffer += decoder.decode(value, { stream: true });
    const lines = lineBuffer.split('\n');
    lineBuffer = lines.pop();
    for (const line of lines) {
      if (!line.trim()) continue;
      const data = JSON.parse(line);
      if (data.message?.content) yield data.message.content;
      if (data.done) return;
    }
  }
}

module.exports = { generate, chat, chatStream };
```

- [ ] **Step 4: Run tests to confirm all pass**

```bash
cd services/brain && npx jest src/__tests__/ollamaClient.test.js --no-coverage
```

Expected: 13 tests PASS (9 existing + 4 new chatStream)

- [ ] **Step 5: Commit**

```bash
git add services/brain/src/services/ollamaClient.js services/brain/src/__tests__/ollamaClient.test.js
git commit -m "feat(brain): add chatStream() async generator for Ollama token streaming"
```

---

## Task 2: Add `streamChatPipeline()` to chatPipeline

**Files:**
- Modify: `services/brain/src/pipelines/chatPipeline.js`
- Modify: `services/brain/src/__tests__/chatPipeline.test.js`

- [ ] **Step 1: Add streamChatPipeline tests to chatPipeline.test.js**

Append this `describe` block at the end of `services/brain/src/__tests__/chatPipeline.test.js` (after the existing `runChatPipeline` describe block closes):

```js
describe('chatPipeline.streamChatPipeline', () => {
  let chatStream, streamChatPipeline, chatPipelineModule, readFileSyncSpy;

  beforeEach(() => {
    jest.resetModules();
    jest.mock('../services/ollamaClient');
    readFileSyncSpy = jest.spyOn(require('fs'), 'readFileSync').mockReturnValue('You are Beemo!');
    chatPipelineModule = require('../pipelines/chatPipeline');
    streamChatPipeline = chatPipelineModule.streamChatPipeline;
    ({ chatStream } = require('../services/ollamaClient'));
    chatPipelineModule._resetHistory();
  });

  afterEach(() => {
    readFileSyncSpy.mockRestore();
  });

  it('yields sentences split on punctuation boundaries', async () => {
    chatStream.mockImplementation(async function* () {
      yield 'Hello ';
      yield 'world! ';
      yield 'How are you?';
    });

    const sentences = [];
    for await (const s of streamChatPipeline('hi')) {
      sentences.push(s);
    }

    expect(sentences).toEqual(['Hello world!', 'How are you?']);
  });

  it('yields trailing text without punctuation at end of stream', async () => {
    chatStream.mockImplementation(async function* () {
      yield 'Hello';
      yield ' world';
    });

    const sentences = [];
    for await (const s of streamChatPipeline('hi')) {
      sentences.push(s);
    }

    expect(sentences).toEqual(['Hello world']);
  });

  it('updates conversation history with full response after generator exhausted', async () => {
    chatStream
      .mockImplementationOnce(async function* () {
        yield 'Hello! ';
        yield 'How are you?';
      })
      .mockImplementationOnce(async function* () {
        yield 'Great!';
      });

    for await (const _ of streamChatPipeline('hi')) { /* exhaust */ }
    for await (const _ of streamChatPipeline('thanks')) { /* exhaust */ }

    const secondCallMessages = chatStream.mock.calls[1][1];
    expect(secondCallMessages).toContainEqual({ role: 'user', content: 'hi' });
    expect(secondCallMessages).toContainEqual({ role: 'assistant', content: 'Hello! How are you?' });
  });

  it('does not update history when chatStream throws', async () => {
    chatStream
      .mockImplementationOnce(async function* () {
        throw new Error('Ollama down');
      })
      .mockImplementationOnce(async function* () {
        yield 'Hi!';
      });

    const drain = async () => {
      for await (const _ of streamChatPipeline('first')) { /* exhaust */ }
    };
    await expect(drain()).rejects.toThrow('Ollama down');

    for await (const _ of streamChatPipeline('second')) { /* exhaust */ }

    const secondCallMessages = chatStream.mock.calls[1][1];
    // history should only contain 'second', not 'first'
    expect(secondCallMessages.filter(m => m.role === 'user')).toHaveLength(1);
    expect(secondCallMessages).toContainEqual({ role: 'user', content: 'second' });
  });

  it('propagates errors from chatStream to the caller', async () => {
    chatStream.mockImplementation(async function* () {
      throw new Error('connection refused');
    });

    const drain = async () => {
      for await (const _ of streamChatPipeline('hi')) { /* exhaust */ }
    };
    await expect(drain()).rejects.toThrow('connection refused');
  });
});
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
cd services/brain && npx jest src/__tests__/chatPipeline.test.js --no-coverage
```

Expected: 8 existing tests PASS, 5 new `streamChatPipeline` tests FAIL with `streamChatPipeline is not a function`

- [ ] **Step 3: Implement `streamChatPipeline()` in chatPipeline.js**

Replace the full file with:

```js
const path = require('path');
const fs = require('fs');
const { chat, chatStream } = require('../services/ollamaClient');

const SYSTEM_PROMPT_PATH = path.resolve(
  __dirname,
  '../../../../packages/prompts/systemPrompt.txt'
);

const FALLBACK_PROMPT = 'You are Beemo, a cheerful and playful AI assistant.';
const MAX_HISTORY = 20;

let messages = [];

function loadSystemPrompt() {
  try {
    return fs.readFileSync(SYSTEM_PROMPT_PATH, 'utf8').trim();
  } catch {
    return FALLBACK_PROMPT;
  }
}

const SYSTEM_PROMPT = loadSystemPrompt();

async function runChatPipeline(text) {
  const candidate = [...messages, { role: 'user', content: text }];
  const trimmed = candidate.length > MAX_HISTORY ? candidate.slice(-MAX_HISTORY) : candidate;
  const fullMessages = [{ role: 'system', content: SYSTEM_PROMPT }, ...trimmed];

  const response = await chat(process.env.LLM_MODEL || 'gemma3', fullMessages);

  messages = [...trimmed, { role: 'assistant', content: response }];
  return response;
}

async function* streamChatPipeline(text) {
  const candidate = [...messages, { role: 'user', content: text }];
  const trimmed = candidate.length > MAX_HISTORY ? candidate.slice(-MAX_HISTORY) : candidate;
  const fullMessages = [{ role: 'system', content: SYSTEM_PROMPT }, ...trimmed];

  let tokenBuffer = '';
  const sentences = [];

  for await (const token of chatStream(process.env.LLM_MODEL || 'gemma3', fullMessages)) {
    tokenBuffer += token;
    const match = tokenBuffer.match(/^(.*?[.!?])\s+([\s\S]*)$/);
    if (match) {
      const sentence = match[1].trim();
      sentences.push(sentence);
      tokenBuffer = match[2];
      yield sentence;
    }
  }

  if (tokenBuffer.trim()) {
    sentences.push(tokenBuffer.trim());
    yield tokenBuffer.trim();
  }

  if (sentences.length > 0) {
    const fullResponse = sentences.join(' ');
    messages = [...trimmed, { role: 'assistant', content: fullResponse }];
  }
}

function _resetHistory() {
  messages = [];
}

module.exports = { runChatPipeline, streamChatPipeline, _resetHistory };
```

- [ ] **Step 4: Run the full chatPipeline test suite**

```bash
cd services/brain && npx jest src/__tests__/chatPipeline.test.js --no-coverage
```

Expected: 13 tests PASS (8 existing + 5 new)

- [ ] **Step 5: Run the full brain test suite**

```bash
cd services/brain && npx jest --no-coverage
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/brain/src/pipelines/chatPipeline.js services/brain/src/__tests__/chatPipeline.test.js
git commit -m "feat(brain): add streamChatPipeline() — sentence-splitting async generator"
```

---

## Task 3: Add `POST /chat/stream` route

**Files:**
- Modify: `services/brain/src/routes/chat.js`
- Modify: `services/brain/src/__tests__/chat.test.js`

- [ ] **Step 1: Add streaming route tests to chat.test.js**

In `services/brain/src/__tests__/chat.test.js`, update the top of the file to also import `streamChatPipeline`:

```js
const { runChatPipeline, streamChatPipeline } = require('../pipelines/chatPipeline');
```

Then append this `describe` block at the end of the file (after the existing `POST /chat` describe block closes):

```js
describe('POST /chat/stream', () => {
  let consoleErrorSpy;

  beforeEach(() => {
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    jest.resetAllMocks();
  });

  it('returns 400 when text field is missing', async () => {
    const res = await request(app).post('/chat/stream').send({});
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Beemo needs something to think about!');
  });

  it('returns 400 when text is empty string', async () => {
    const res = await request(app).post('/chat/stream').send({ text: '   ' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Beemo needs something to think about!');
  });

  it('streams sentences as NDJSON and ends with done:true', async () => {
    streamChatPipeline.mockImplementation(async function* () {
      yield 'Hello!';
      yield 'How are you?';
    });

    const res = await request(app)
      .post('/chat/stream')
      .send({ text: 'Hi there' })
      .buffer(true)
      .parse((res, fn) => {
        let data = '';
        res.on('data', chunk => { data += chunk.toString(); });
        res.on('end', () => fn(null, data));
      });

    const lines = res.body.split('\n').filter(Boolean).map(JSON.parse);
    expect(lines).toEqual([
      { sentence: 'Hello!' },
      { sentence: 'How are you?' },
      { done: true },
    ]);
  });

  it('returns 503 JSON when streamChatPipeline throws before first write', async () => {
    streamChatPipeline.mockImplementation(async function* () {
      throw new Error('Ollama down');
      yield; // make it an async generator
    });

    const res = await request(app)
      .post('/chat/stream')
      .send({ text: 'Hi' });

    expect(res.status).toBe(503);
    expect(res.body.error).toBe("Beemo's brain is sleeping... try again!");
    expect(consoleErrorSpy).toHaveBeenCalledWith('[chat/stream] pipeline error:', expect.any(Error));
  });
});
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
cd services/brain && npx jest src/__tests__/chat.test.js --no-coverage
```

Expected: Existing 5 tests PASS, 4 new streaming tests FAIL (route does not exist yet)

- [ ] **Step 3: Implement the `/chat/stream` route in chat.js**

Replace the full file with:

```js
const { Router } = require('express');
const { classifyIntent } = require('../services/intentRouter');
const { runChatPipeline, streamChatPipeline } = require('../pipelines/chatPipeline');

const router = Router();

const PIPELINES = {
  chat: runChatPipeline,
};

router.post('/', async (req, res) => {
  const { text } = req.body ?? {};

  if (!text || typeof text !== 'string' || text.trim() === '') {
    return res.status(400).json({ error: 'Beemo needs something to think about!' });
  }

  try {
    const intent = await classifyIntent(text);
    const pipeline = PIPELINES[intent] ?? runChatPipeline;
    const responseText = await pipeline(text);
    res.json({ text: responseText, intent, model: process.env.LLM_MODEL || 'gemma3' });
  } catch (err) {
    console.error('[chat route] pipeline error:', err);
    res.status(503).json({ error: "Beemo's brain is sleeping... try again!" });
  }
});

router.post('/stream', async (req, res) => {
  const { text } = req.body ?? {};

  if (!text || typeof text !== 'string' || text.trim() === '') {
    return res.status(400).json({ error: 'Beemo needs something to think about!' });
  }

  res.setHeader('Content-Type', 'application/x-ndjson');
  res.setHeader('Transfer-Encoding', 'chunked');

  try {
    for await (const sentence of streamChatPipeline(text)) {
      res.write(JSON.stringify({ sentence }) + '\n');
    }
    res.write(JSON.stringify({ done: true }) + '\n');
  } catch (err) {
    console.error('[chat/stream] pipeline error:', err);
    if (!res.headersSent) {
      return res.status(503).json({ error: "Beemo's brain is sleeping... try again!" });
    }
    res.write(JSON.stringify({ error: "Beemo's brain is sleeping... try again!" }) + '\n');
  }
  res.end();
});

module.exports = router;
```

- [ ] **Step 4: Run the full brain test suite**

```bash
cd services/brain && npx jest --no-coverage
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/brain/src/routes/chat.js services/brain/src/__tests__/chat.test.js
git commit -m "feat(brain): add POST /chat/stream NDJSON streaming endpoint"
```

---

## Task 4: Add `stream_chat()` to brain_client.py

**Files:**
- Modify: `services/voice/src/brain_client.py`
- Modify: `services/voice/tests/test_brain_client.py`

- [ ] **Step 1: Write failing tests for `stream_chat()`**

Append to `services/voice/tests/test_brain_client.py`:

```python
import json
from src.brain_client import stream_chat


def _make_stream_mock(lines, status_code=200):
    """Returns a context manager mock whose iter_lines() yields the given strings."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.raise_for_status.return_value = None
    mock_response.iter_lines.return_value = iter(lines)
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response
    mock_cm.__exit__.return_value = False
    return mock_cm


def test_stream_chat_yields_sentences():
    lines = [
        json.dumps({'sentence': 'Hello world!'}),
        json.dumps({'sentence': 'How are you?'}),
        json.dumps({'done': True}),
    ]
    with patch('src.brain_client.httpx.stream', return_value=_make_stream_mock(lines)) as mock_stream:
        sentences = list(stream_chat('Hello!'))

    assert sentences == ['Hello world!', 'How are you?']
    mock_stream.assert_called_once_with(
        'POST',
        'http://localhost:3001/chat/stream',
        json={'text': 'Hello!'},
        timeout=60.0,
    )


def test_stream_chat_stops_at_done():
    lines = [
        json.dumps({'sentence': 'Hi!'}),
        json.dumps({'done': True}),
        json.dumps({'sentence': 'Should not appear'}),
    ]
    with patch('src.brain_client.httpx.stream', return_value=_make_stream_mock(lines)):
        sentences = list(stream_chat('Hello!'))

    assert sentences == ['Hi!']


def test_stream_chat_raises_brain_service_error_on_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        '503', request=MagicMock(), response=mock_response
    )
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response
    mock_cm.__exit__.return_value = False

    with patch('src.brain_client.httpx.stream', return_value=mock_cm):
        with pytest.raises(BrainServiceError, match='503'):
            list(stream_chat('Hello!'))


def test_stream_chat_raises_brain_service_error_on_connection_failure():
    with patch('src.brain_client.httpx.stream', side_effect=httpx.ConnectError('refused')):
        with pytest.raises(BrainServiceError, match='unreachable'):
            list(stream_chat('Hello!'))


def test_stream_chat_skips_empty_lines():
    lines = [
        '',
        json.dumps({'sentence': 'Hello!'}),
        '',
        json.dumps({'done': True}),
    ]
    with patch('src.brain_client.httpx.stream', return_value=_make_stream_mock(lines)):
        sentences = list(stream_chat('Hello!'))

    assert sentences == ['Hello!']
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
cd services/voice && python -m pytest tests/test_brain_client.py -v
```

Expected: 3 existing tests PASS, 5 new `stream_chat` tests FAIL with `ImportError` or `AttributeError`

- [ ] **Step 3: Implement `stream_chat()` in brain_client.py**

Replace the full file with:

```python
import json
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


def stream_chat(text: str):
    try:
        with httpx.stream(
            'POST',
            f'{config.BRAIN_URL}/chat/stream',
            json={'text': text},
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get('done'):
                    return
                if 'sentence' in data:
                    yield data['sentence']
    except httpx.HTTPStatusError as e:
        raise BrainServiceError(
            f'Brain service returned {e.response.status_code}'
        ) from e
    except httpx.RequestError as e:
        raise BrainServiceError(f'Brain service unreachable: {e}') from e
```

- [ ] **Step 4: Run all brain_client tests**

```bash
cd services/voice && python -m pytest tests/test_brain_client.py -v
```

Expected: 8 tests PASS (3 existing + 5 new)

- [ ] **Step 5: Commit**

```bash
git add services/voice/src/brain_client.py services/voice/tests/test_brain_client.py
git commit -m "feat(voice): add stream_chat() generator for NDJSON sentence streaming"
```

---

## Task 5: Update main.py with per-sentence loop

**Files:**
- Modify: `services/voice/main.py`
- Modify: `services/voice/tests/test_pipeline.py`

- [ ] **Step 1: Update test_pipeline.py**

Replace the full contents of `services/voice/tests/test_pipeline.py` with:

```python
import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main  # noqa: E402
from src.brain_client import BrainServiceError
from src.synthesizer import SynthesisError
from src.recorder import RecordingError
from src import state_client  # noqa: F401


@pytest.fixture(autouse=True)
def mock_set_state(mocker):
    return mocker.patch('src.state_client.set_state')


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv('PIPER_MODEL_PATH', '/fake/model.onnx')
    monkeypatch.setenv('BRAIN_URL', 'http://localhost:3001')


def _make_listen(n_calls=1, trigger='wake_word'):
    count = {'n': 0}
    def mock_listen():
        count['n'] += 1
        if count['n'] > n_calls:
            raise KeyboardInterrupt
        return trigger
    return mock_listen


def test_pipeline_runs_full_happy_path(mocker):
    """Wake word fires → record → transcribe → stream → synthesize → play → loop back."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello Beemo!')
    mock_stream = mocker.patch('src.brain_client.stream_chat', return_value=iter(['Hi there friend!']))
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00\x01')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_stream.assert_called_once_with('Hello Beemo!')
    mock_synthesize.assert_called_once_with('Hi there friend!')
    mock_play.assert_called_once_with(b'\x00\x01')


def test_pipeline_synthesizes_each_sentence_in_order(mocker):
    """Multiple sentences → each synthesized and played before reading the next."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello Beemo!')
    mocker.patch('src.brain_client.stream_chat', return_value=iter(['Hello!', 'How are you?']))
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    assert mock_synthesize.call_count == 2
    mock_synthesize.assert_any_call('Hello!')
    mock_synthesize.assert_any_call('How are you?')
    assert mock_play.call_count == 2


def test_pipeline_skips_when_transcription_is_empty(mocker):
    """Empty transcription → skip brain call, loop back immediately."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='ptt'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='')
    mock_stream = mocker.patch('src.brain_client.stream_chat')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_stream.assert_not_called()


def test_pipeline_plays_fallback_when_brain_unavailable(mocker):
    """BrainServiceError → synthesize + play the fallback message."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.stream_chat', side_effect=BrainServiceError('down'))
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_synthesize.assert_called_once_with(main.FALLBACK_MESSAGE)
    mock_play.assert_called_once_with(b'\x00')


def test_pipeline_continues_when_synthesis_fails(mocker):
    """SynthesisError on one sentence → skip playback for that sentence, loop continues."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.stream_chat', return_value=iter(['Hi!']))
    mocker.patch('src.synthesizer.synthesize', side_effect=SynthesisError('piper crashed'))
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_play.assert_not_called()


def test_pipeline_continues_when_recording_fails(mocker):
    """RecordingError → log error, loop continues to next wake word."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', side_effect=RecordingError('mic disconnected'))
    mock_stream = mocker.patch('src.brain_client.stream_chat')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_stream.assert_not_called()


def test_pipeline_continues_when_listen_raises(mocker):
    """RuntimeError from wake_word.listen → log error, loop retries."""
    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] == 1:
            raise RuntimeError('Listen timeout')
        raise KeyboardInterrupt

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mock_record = mocker.patch('src.recorder.record')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_record.assert_not_called()


def test_pipeline_emits_correct_state_transitions_on_happy_path(mocker, mock_set_state):
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello Beemo!')
    mocker.patch('src.brain_client.stream_chat', return_value=iter(['Hi there!']))
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
    mocker.patch('src.brain_client.stream_chat', side_effect=BrainServiceError('down'))
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


def test_pipeline_emits_error_state_when_wake_word_listener_fails(mocker, mock_set_state):
    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] == 1:
            raise RuntimeError('Listen timeout')
        raise KeyboardInterrupt

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert 'error' in states
```

- [ ] **Step 2: Run tests to confirm failing ones fail**

```bash
cd services/voice && python -m pytest tests/test_pipeline.py::test_pipeline_runs_full_happy_path tests/test_pipeline.py::test_pipeline_synthesizes_each_sentence_in_order -v
```

Expected: Both FAIL — `main.py` still calls `brain_client.chat()`, not `stream_chat()`

- [ ] **Step 3: Implement the per-sentence loop in main.py**

Replace the full file with:

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
            first = True
            for sentence in brain_client.stream_chat(text):
                if first:
                    state_client.set_state('speaking')
                    first = False
                log.info('Beemo says: %s', sentence)
                try:
                    audio_bytes = synthesizer.synthesize(sentence)
                    player.play(audio_bytes)
                except synthesizer.SynthesisError as e:
                    log.error('Synthesis error for sentence: %s', e)
        except brain_client.BrainServiceError as e:
            log.error('Brain service error: %s', e)
            state_client.set_state('fallback')
            log.info('Beemo says: %s', FALLBACK_MESSAGE)
            try:
                audio_bytes = synthesizer.synthesize(FALLBACK_MESSAGE)
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

Expected: All 13 tests PASS (12 updated + 1 new `test_pipeline_synthesizes_each_sentence_in_order`)

- [ ] **Step 5: Run the full voice test suite**

```bash
cd services/voice && python -m pytest -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/voice/main.py services/voice/tests/test_pipeline.py
git commit -m "feat(voice): switch to per-sentence streaming playback via stream_chat()"
```

---

## Self-Review

- [x] **Spec coverage:** `chatStream()` with `stream:true` ✓, sentence splitting regex in `streamChatPipeline` ✓, trailing text without punctuation ✓, history update after exhaustion ✓, `POST /chat/stream` NDJSON ✓, `{"done":true}` terminator ✓, `stream_chat()` Python generator ✓, per-sentence loop in `main.py` ✓, `first` flag for `speaking` state ✓, fallback path unchanged ✓, backward compat (`POST /chat` and `brain_client.chat()` untouched) ✓
- [x] **No placeholders:** All steps have complete code
- [x] **Type consistency:** `chatStream` exported from `ollamaClient` and imported in `chatPipeline`; `streamChatPipeline` exported from `chatPipeline` and imported in `chat.js`; `stream_chat` in `brain_client.py` called as `brain_client.stream_chat(text)` in `main.py`; `BrainServiceError` raised by `stream_chat` and caught in `main.py` — all consistent
