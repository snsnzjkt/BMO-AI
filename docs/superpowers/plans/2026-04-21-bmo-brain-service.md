# BMO Brain Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/services/brain` Node.js Express service that accepts text input, classifies intent via Gemma 3, runs the chat pipeline, and returns a structured response.

**Architecture:** Service-layer pattern — routes are thin, each pipeline is a single file, and shared Ollama access goes through one client module. Each future phase (RAG, Vision) adds one pipeline file and one route without touching existing code.

**Tech Stack:** Node.js 18+, Express 4, Jest 29, Supertest, Ollama HTTP API (local), Gemma 3

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `services/brain/package.json` | Modify | Dependencies, scripts, Jest config |
| `services/brain/.env.example` | Create | Document env vars |
| `packages/prompts/systemPrompt.txt` | Modify | BMO personality system prompt |
| `services/brain/src/services/ollamaClient.js` | Create | `fetch` wrapper for Ollama `/api/generate` |
| `services/brain/src/__tests__/ollamaClient.test.js` | Create | Unit tests for Ollama client |
| `services/brain/src/services/intentRouter.js` | Create | LLM-based intent classification |
| `services/brain/src/__tests__/intentRouter.test.js` | Create | Unit tests for intent router |
| `services/brain/src/pipelines/chatPipeline.js` | Create | Chat pipeline: text → Gemma → response |
| `services/brain/src/__tests__/chatPipeline.test.js` | Create | Unit tests for chat pipeline |
| `services/brain/src/routes/vision.js` | Create | 501 stub for POST /vision |
| `services/brain/src/routes/rag.js` | Create | 501 stub for POST /rag |
| `services/brain/src/routes/chat.js` | Create | POST /chat route handler |
| `services/brain/src/__tests__/chat.test.js` | Create | Integration tests for /chat route |
| `services/brain/index.js` | Modify | Express server entry point |

---

## Task 1: Configure package.json and project structure

**Files:**
- Modify: `services/brain/package.json`
- Create: `services/brain/.env.example`

- [ ] **Step 1: Write package.json**

```json
{
  "name": "@bmo/brain",
  "version": "0.1.0",
  "description": "BMO AI brain service — LLM orchestration via Ollama",
  "main": "index.js",
  "engines": { "node": ">=18" },
  "scripts": {
    "start": "node index.js",
    "dev": "node --watch index.js",
    "test": "jest"
  },
  "dependencies": {
    "dotenv": "^16.4.5",
    "express": "^4.18.2"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "supertest": "^6.3.4"
  },
  "jest": {
    "testEnvironment": "node"
  }
}
```

- [ ] **Step 2: Create .env.example**

Create `services/brain/.env.example` with:

```
PORT=3001
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=gemma3
```

- [ ] **Step 3: Create directory structure and install dependencies**

```bash
cd services/brain
mkdir -p src/services src/pipelines src/routes src/__tests__
npm install
```

Expected output ends with: `added N packages` and no errors.

- [ ] **Step 4: Verify Jest is available**

```bash
npx jest --version
```

Expected: prints a version like `29.x.x`.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add services/brain/package.json services/brain/.env.example services/brain/package-lock.json
git commit -m "chore(brain): configure package.json, jest, and project structure"
```

---

## Task 2: Write BMO system prompt

**Files:**
- Modify: `packages/prompts/systemPrompt.txt`

- [ ] **Step 1: Write the BMO personality prompt**

Replace the contents of `packages/prompts/systemPrompt.txt` with:

```
You are BMO, a small, cheerful game console and AI companion from the land of Ooo.
You are playful, warm, and a little quirky. You speak in simple, friendly sentences.
You occasionally refer to yourself as "BMO". Keep your answers short and kind.
You love helping your friends and always try to see the bright side of things.
```

- [ ] **Step 2: Commit**

```bash
git add packages/prompts/systemPrompt.txt
git commit -m "chore(prompts): write BMO personality system prompt"
```

---

## Task 3: ollamaClient — TDD

**Files:**
- Create: `services/brain/src/services/ollamaClient.js`
- Create: `services/brain/src/__tests__/ollamaClient.test.js`

- [ ] **Step 1: Write the failing test**

Create `services/brain/src/__tests__/ollamaClient.test.js`:

```js
const { generate } = require('../services/ollamaClient');

describe('ollamaClient.generate', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it('sends a POST request to Ollama and returns response text', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'Hello from BMO!' }),
    });

    const result = await generate('gemma3', 'say hello', 'you are BMO');

    expect(result).toBe('Hello from BMO!');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:11434/api/generate',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'gemma3',
          prompt: 'say hello',
          system: 'you are BMO',
          stream: false,
        }),
      })
    );
  });

  it('defaults system to empty string when omitted', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'ok' }),
    });

    await generate('gemma3', 'hello');

    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({ model: 'gemma3', prompt: 'hello', system: '', stream: false }),
      })
    );
  });

  it('throws when Ollama returns a non-ok HTTP status', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 500 });

    await expect(generate('gemma3', 'hello')).rejects.toThrow(
      'Ollama request failed: 500'
    );
  });

  it('throws when fetch rejects (Ollama unreachable)', async () => {
    global.fetch.mockRejectedValue(new Error('ECONNREFUSED'));

    await expect(generate('gemma3', 'hello')).rejects.toThrow('ECONNREFUSED');
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd services/brain
npx jest src/__tests__/ollamaClient.test.js --no-coverage
```

Expected: `FAIL` with `Cannot find module '../services/ollamaClient'`.

- [ ] **Step 3: Implement ollamaClient.js**

Create `services/brain/src/services/ollamaClient.js`:

```js
const BASE_URL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';

async function generate(model, prompt, system = '') {
  const response = await fetch(`${BASE_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, prompt, system, stream: false }),
  });

  if (!response.ok) {
    throw new Error(`Ollama request failed: ${response.status}`);
  }

  const data = await response.json();
  return data.response;
}

module.exports = { generate };
```

- [ ] **Step 4: Run test — verify it passes**

```bash
npx jest src/__tests__/ollamaClient.test.js --no-coverage
```

Expected: `PASS` — 4 tests passing.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add services/brain/src/services/ollamaClient.js services/brain/src/__tests__/ollamaClient.test.js
git commit -m "feat(brain): add ollamaClient with fetch wrapper and tests"
```

---

## Task 4: intentRouter — TDD

**Files:**
- Create: `services/brain/src/services/intentRouter.js`
- Create: `services/brain/src/__tests__/intentRouter.test.js`

- [ ] **Step 1: Write the failing test**

Create `services/brain/src/__tests__/intentRouter.test.js`:

```js
jest.mock('../services/ollamaClient');

const { generate } = require('../services/ollamaClient');
const { classifyIntent } = require('../services/intentRouter');

describe('intentRouter.classifyIntent', () => {
  afterEach(() => jest.resetAllMocks());

  it('returns intent when Gemma responds with a valid label', async () => {
    generate.mockResolvedValue('vision');
    const intent = await classifyIntent('what do you see in this image?');
    expect(intent).toBe('vision');
  });

  it('strips whitespace and lowercases before validating', async () => {
    generate.mockResolvedValue('  RAG  \n');
    const intent = await classifyIntent('search my notes for recipes');
    expect(intent).toBe('rag');
  });

  it('falls back to chat for unrecognized Gemma responses', async () => {
    generate.mockResolvedValue('something completely unexpected');
    const intent = await classifyIntent('hello there');
    expect(intent).toBe('chat');
  });

  it('passes a prompt that contains the user text', async () => {
    generate.mockResolvedValue('chat');
    await classifyIntent('tell me a joke');
    const calledPrompt = generate.mock.calls[0][1];
    expect(calledPrompt).toContain('tell me a joke');
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd services/brain
npx jest src/__tests__/intentRouter.test.js --no-coverage
```

Expected: `FAIL` with `Cannot find module '../services/intentRouter'`.

- [ ] **Step 3: Implement intentRouter.js**

Create `services/brain/src/services/intentRouter.js`:

```js
const { generate } = require('./ollamaClient');

const VALID_INTENTS = ['chat', 'rag', 'vision', 'camera', 'web'];

function buildClassificationPrompt(text) {
  return (
    `Classify the following message into exactly one of: chat, rag, vision, camera, web.\n` +
    `Reply with only that single word — no punctuation, no explanation.\n\n` +
    `Message: "${text}"`
  );
}

async function classifyIntent(text) {
  const raw = await generate(
    process.env.LLM_MODEL || 'gemma3',
    buildClassificationPrompt(text),
    ''
  );
  const intent = raw.trim().toLowerCase();
  return VALID_INTENTS.includes(intent) ? intent : 'chat';
}

module.exports = { classifyIntent };
```

- [ ] **Step 4: Run test — verify it passes**

```bash
npx jest src/__tests__/intentRouter.test.js --no-coverage
```

Expected: `PASS` — 4 tests passing.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add services/brain/src/services/intentRouter.js services/brain/src/__tests__/intentRouter.test.js
git commit -m "feat(brain): add LLM-based intent router with Gemma and tests"
```

---

## Task 5: chatPipeline — TDD

**Files:**
- Create: `services/brain/src/pipelines/chatPipeline.js`
- Create: `services/brain/src/__tests__/chatPipeline.test.js`

- [ ] **Step 1: Write the failing test**

Create `services/brain/src/__tests__/chatPipeline.test.js`:

```js
jest.mock('../services/ollamaClient');
jest.mock('fs');

const { generate } = require('../services/ollamaClient');
const fs = require('fs');
const { runChatPipeline } = require('../pipelines/chatPipeline');

describe('chatPipeline.runChatPipeline', () => {
  afterEach(() => jest.resetAllMocks());

  it('returns Gemma response using the system prompt from file', async () => {
    fs.readFileSync.mockReturnValue('You are BMO!');
    generate.mockResolvedValue('Beep boop, hello friend!');

    const result = await runChatPipeline('Hello!');

    expect(result).toBe('Beep boop, hello friend!');
    expect(generate).toHaveBeenCalledWith(
      expect.any(String),
      'Hello!',
      'You are BMO!'
    );
  });

  it('trims whitespace from the system prompt file content', async () => {
    fs.readFileSync.mockReturnValue('   You are BMO!   \n');
    generate.mockResolvedValue('Hi!');

    await runChatPipeline('Hey');

    expect(generate).toHaveBeenCalledWith(expect.any(String), 'Hey', 'You are BMO!');
  });

  it('falls back to a default prompt when the system prompt file is unreadable', async () => {
    fs.readFileSync.mockImplementation(() => { throw new Error('ENOENT'); });
    generate.mockResolvedValue('Hi there!');

    const result = await runChatPipeline('Hello!');

    expect(result).toBe('Hi there!');
    expect(generate).toHaveBeenCalledWith(
      expect.any(String),
      'Hello!',
      'You are BMO, a cheerful and playful AI assistant.'
    );
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd services/brain
npx jest src/__tests__/chatPipeline.test.js --no-coverage
```

Expected: `FAIL` with `Cannot find module '../pipelines/chatPipeline'`.

- [ ] **Step 3: Implement chatPipeline.js**

Create `services/brain/src/pipelines/chatPipeline.js`:

```js
const path = require('path');
const fs = require('fs');
const { generate } = require('../services/ollamaClient');

const SYSTEM_PROMPT_PATH = path.resolve(
  __dirname,
  '../../../packages/prompts/systemPrompt.txt'
);

const FALLBACK_PROMPT = 'You are BMO, a cheerful and playful AI assistant.';

function loadSystemPrompt() {
  try {
    return fs.readFileSync(SYSTEM_PROMPT_PATH, 'utf8').trim();
  } catch {
    return FALLBACK_PROMPT;
  }
}

async function runChatPipeline(text) {
  const system = loadSystemPrompt();
  return generate(process.env.LLM_MODEL || 'gemma3', text, system);
}

module.exports = { runChatPipeline };
```

- [ ] **Step 4: Run test — verify it passes**

```bash
npx jest src/__tests__/chatPipeline.test.js --no-coverage
```

Expected: `PASS` — 3 tests passing.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add services/brain/src/pipelines/chatPipeline.js services/brain/src/__tests__/chatPipeline.test.js
git commit -m "feat(brain): add chat pipeline that injects BMO system prompt"
```

---

## Task 6: Stub routes for vision and rag

**Files:**
- Create: `services/brain/src/routes/vision.js`
- Create: `services/brain/src/routes/rag.js`
- Create: `services/brain/src/__tests__/stubs.test.js`

- [ ] **Step 1: Write the failing tests**

Create `services/brain/src/__tests__/stubs.test.js`:

```js
const request = require('supertest');
const express = require('express');
const visionRoute = require('../routes/vision');
const ragRoute = require('../routes/rag');

const app = express();
app.use(express.json());
app.use('/vision', visionRoute);
app.use('/rag', ragRoute);

describe('Stub routes', () => {
  it('POST /vision returns 501', async () => {
    const res = await request(app).post('/vision').send({});
    expect(res.status).toBe(501);
    expect(res.body).toHaveProperty('error');
  });

  it('POST /rag returns 501', async () => {
    const res = await request(app).post('/rag').send({});
    expect(res.status).toBe(501);
    expect(res.body).toHaveProperty('error');
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd services/brain
npx jest src/__tests__/stubs.test.js --no-coverage
```

Expected: `FAIL` with `Cannot find module '../routes/vision'`.

- [ ] **Step 3: Implement vision.js**

Create `services/brain/src/routes/vision.js`:

```js
const { Router } = require('express');

const router = Router();

router.post('/', (req, res) => {
  res.status(501).json({ error: 'Vision pipeline not yet implemented (Phase 4).' });
});

module.exports = router;
```

- [ ] **Step 4: Implement rag.js**

Create `services/brain/src/routes/rag.js`:

```js
const { Router } = require('express');

const router = Router();

router.post('/', (req, res) => {
  res.status(501).json({ error: 'RAG pipeline not yet implemented (Phase 5).' });
});

module.exports = router;
```

- [ ] **Step 5: Run test — verify it passes**

```bash
npx jest src/__tests__/stubs.test.js --no-coverage
```

Expected: `PASS` — 2 tests passing.

- [ ] **Step 6: Commit**

```bash
cd ../..
git add services/brain/src/routes/vision.js services/brain/src/routes/rag.js services/brain/src/__tests__/stubs.test.js
git commit -m "feat(brain): add 501 stub routes for vision and rag"
```

---

## Task 7: chat route — TDD

**Files:**
- Create: `services/brain/src/routes/chat.js`
- Create: `services/brain/src/__tests__/chat.test.js`

- [ ] **Step 1: Write the failing test**

Create `services/brain/src/__tests__/chat.test.js`:

```js
jest.mock('../services/intentRouter');
jest.mock('../pipelines/chatPipeline');

const { classifyIntent } = require('../services/intentRouter');
const { runChatPipeline } = require('../pipelines/chatPipeline');
const request = require('supertest');
const express = require('express');
const chatRoute = require('../routes/chat');

const app = express();
app.use(express.json());
app.use('/chat', chatRoute);

describe('POST /chat', () => {
  afterEach(() => jest.resetAllMocks());

  it('returns 400 when text field is missing', async () => {
    const res = await request(app).post('/chat').send({});
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('BMO needs something to think about!');
  });

  it('returns 400 when text is an empty string', async () => {
    const res = await request(app).post('/chat').send({ text: '   ' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('BMO needs something to think about!');
  });

  it('returns text, intent, and model on success', async () => {
    classifyIntent.mockResolvedValue('chat');
    runChatPipeline.mockResolvedValue('Beep boop! I am BMO.');

    const res = await request(app).post('/chat').send({ text: 'Hello BMO!' });

    expect(res.status).toBe(200);
    expect(res.body).toEqual({
      text: 'Beep boop! I am BMO.',
      intent: 'chat',
      model: 'gemma3',
    });
  });

  it('returns 503 when intentRouter throws (Ollama unreachable)', async () => {
    classifyIntent.mockRejectedValue(new Error('ECONNREFUSED'));

    const res = await request(app).post('/chat').send({ text: 'Hello' });

    expect(res.status).toBe(503);
    expect(res.body.error).toBe("BMO's brain is sleeping... try again!");
  });

  it('returns 503 when chatPipeline throws', async () => {
    classifyIntent.mockResolvedValue('chat');
    runChatPipeline.mockRejectedValue(new Error('timeout'));

    const res = await request(app).post('/chat').send({ text: 'Hello' });

    expect(res.status).toBe(503);
    expect(res.body.error).toBe("BMO's brain is sleeping... try again!");
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd services/brain
npx jest src/__tests__/chat.test.js --no-coverage
```

Expected: `FAIL` with `Cannot find module '../routes/chat'`.

- [ ] **Step 3: Implement chat.js**

Create `services/brain/src/routes/chat.js`:

```js
const { Router } = require('express');
const { classifyIntent } = require('../services/intentRouter');
const { runChatPipeline } = require('../pipelines/chatPipeline');

const router = Router();

router.post('/', async (req, res) => {
  const { text } = req.body;

  if (!text || typeof text !== 'string' || text.trim() === '') {
    return res.status(400).json({ error: 'BMO needs something to think about!' });
  }

  try {
    const intent = await classifyIntent(text);
    const responseText = await runChatPipeline(text);
    res.json({ text: responseText, intent, model: process.env.LLM_MODEL || 'gemma3' });
  } catch {
    res.status(503).json({ error: "BMO's brain is sleeping... try again!" });
  }
});

module.exports = router;
```

- [ ] **Step 4: Run test — verify it passes**

```bash
npx jest src/__tests__/chat.test.js --no-coverage
```

Expected: `PASS` — 5 tests passing.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add services/brain/src/routes/chat.js services/brain/src/__tests__/chat.test.js
git commit -m "feat(brain): add POST /chat route with intent routing and error handling"
```

---

## Task 8: Express server entry point + smoke test

**Files:**
- Modify: `services/brain/index.js`

- [ ] **Step 1: Implement index.js**

Replace `services/brain/index.js` contents with:

```js
require('dotenv').config();
const express = require('express');

const chatRoute = require('./src/routes/chat');
const visionRoute = require('./src/routes/vision');
const ragRoute = require('./src/routes/rag');

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

app.listen(PORT, () => {
  console.log(`BMO Brain service running on port ${PORT} 🎮`);
});

module.exports = app;
```

- [ ] **Step 2: Run the full test suite**

```bash
cd services/brain
npx jest --no-coverage
```

Expected: all tests pass. Output ends with something like:
```
Test Suites: 4 passed, 4 total
Tests:       14 passed, 14 total
```

- [ ] **Step 3: Start the server and verify the health endpoint**

Ensure Ollama is running locally (`ollama serve`), then in a terminal:

```bash
node index.js
```

In a second terminal:

```bash
curl http://localhost:3001/health
```

Expected response:
```json
{ "status": "ok", "service": "brain" }
```

- [ ] **Step 4: Smoke-test the chat endpoint**

```bash
curl -s -X POST http://localhost:3001/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello BMO! What is 2 + 2?"}' | jq .
```

Expected response shape (text will vary):
```json
{
  "text": "BMO says it is 4! Simple math is fun!",
  "intent": "chat",
  "model": "gemma3"
}
```

- [ ] **Step 5: Verify stub routes return 501**

```bash
curl -s -X POST http://localhost:3001/vision -H "Content-Type: application/json" -d '{}' | jq .
curl -s -X POST http://localhost:3001/rag -H "Content-Type: application/json" -d '{}' | jq .
```

Expected: both return `{ "error": "... not yet implemented ..." }` with HTTP 501.

- [ ] **Step 6: Commit**

```bash
cd ../..
git add services/brain/index.js
git commit -m "feat(brain): add Express server entry point with request logging and health endpoint"
```

---

## Done

Phase 1 of the Brain service is complete. The service:
- Accepts `POST /chat` with `{ text }` input
- Classifies intent via Gemma 3 (LLM-based)
- Runs the chat pipeline with BMO personality
- Returns `{ text, intent, model }`
- Returns meaningful 400/503 errors
- Has stubs ready for Phase 4 (vision) and Phase 5 (RAG)

**Next phase:** Add voice pipeline (Whisper STT + Piper TTS) in `/services/voice`.
