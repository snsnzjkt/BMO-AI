# Conversation Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Beemo in-session conversation memory by switching the chat pipeline from Ollama's single-turn `/api/generate` to the multi-turn `/api/chat` endpoint, keeping the last 10 turns in memory.

**Architecture:** A new `chat(model, messages)` function is added to `ollamaClient.js` using Ollama's `/api/chat` endpoint. `chatPipeline.js` gains a module-level `messages` array that accumulates user/assistant turns (capped at 20 entries = 10 turns) and is prepended with the system prompt on every call. Failed Ollama calls do not mutate history.

**Tech Stack:** Node.js, Express, Ollama `/api/chat`, Jest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `services/brain/src/services/ollamaClient.js` | Modify | Add `chat(model, messages)` using `/api/chat`; keep `generate()` |
| `services/brain/src/__tests__/ollamaClient.test.js` | Modify | Add `describe` block for `chat()` |
| `services/brain/src/pipelines/chatPipeline.js` | Modify | Switch to `chat()`; add `messages` array with cap; export `_resetHistory` |
| `services/brain/src/__tests__/chatPipeline.test.js` | Modify | Update existing tests to use `chat` mock; add memory/capping/error-safety tests |

---

## Task 1: Add `chat()` to ollamaClient

**Files:**
- Modify: `services/brain/src/services/ollamaClient.js`
- Modify: `services/brain/src/__tests__/ollamaClient.test.js`

- [ ] **Step 1: Write failing tests for `chat()`**

Add a new `describe` block at the end of `services/brain/src/__tests__/ollamaClient.test.js` (after the existing `ollamaClient.generate` block). Add this import at the top of the file — change line 1 from:

```js
const { generate } = require('../services/ollamaClient');
```

to:

```js
const { generate, chat } = require('../services/ollamaClient');
```

Then append this `describe` block at the bottom of the file:

```js
describe('ollamaClient.chat', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
    delete global.fetch;
  });

  it('sends messages to /api/chat and returns message content', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: { content: 'Hello from Beemo!' } }),
    });

    const messages = [
      { role: 'system', content: 'You are Beemo.' },
      { role: 'user', content: 'hello' },
    ];

    const result = await chat('gemma3', messages);

    expect(result).toBe('Hello from Beemo!');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:11434/api/chat',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'gemma3',
          messages,
          stream: false,
          options: { num_predict: 80, temperature: 0.7 },
        }),
      })
    );
  });

  it('throws when Ollama returns a non-ok status', async () => {
    global.fetch.mockResolvedValue({ ok: false, status: 503 });
    await expect(chat('gemma3', [])).rejects.toThrow('Ollama request failed: 503');
  });

  it('throws when response is missing message.content', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: {} }),
    });
    await expect(chat('gemma3', [])).rejects.toThrow('missing "message.content"');
  });

  it('throws when fetch rejects (Ollama unreachable)', async () => {
    global.fetch.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(chat('gemma3', [])).rejects.toThrow('ECONNREFUSED');
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd services/brain && npx jest src/__tests__/ollamaClient.test.js --no-coverage
```

Expected: 4 existing tests PASS, 4 new `chat` tests FAIL with `chat is not a function`

- [ ] **Step 3: Implement `chat()` in ollamaClient.js**

Replace the full contents of `services/brain/src/services/ollamaClient.js` with:

```js
const BASE_URL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';

async function generate(model, prompt, system = '') {
  const response = await fetch(`${BASE_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, prompt, system, stream: false, options: { num_predict: 80, temperature: 0.7 } }),
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
    body: JSON.stringify({ model, messages, stream: false, options: { num_predict: 80, temperature: 0.7 } }),
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

module.exports = { generate, chat };
```

- [ ] **Step 4: Run tests to confirm all pass**

```bash
cd services/brain && npx jest src/__tests__/ollamaClient.test.js --no-coverage
```

Expected: 8 tests PASS (4 generate + 4 chat)

- [ ] **Step 5: Commit**

```bash
git add services/brain/src/services/ollamaClient.js services/brain/src/__tests__/ollamaClient.test.js
git commit -m "feat(brain): add ollamaClient.chat() using /api/chat for multi-turn conversations"
```

---

## Task 2: Rewrite chatPipeline with conversation memory

**Files:**
- Modify: `services/brain/src/pipelines/chatPipeline.js`
- Modify: `services/brain/src/__tests__/chatPipeline.test.js`

- [ ] **Step 1: Rewrite the test file**

Replace the full contents of `services/brain/src/__tests__/chatPipeline.test.js` with:

```js
jest.mock('../services/ollamaClient');

const { chat } = require('../services/ollamaClient');
const fs = require('fs');
const chatPipeline = require('../pipelines/chatPipeline');

describe('chatPipeline.runChatPipeline', () => {
  let readFileSyncSpy;

  beforeEach(() => {
    readFileSyncSpy = jest.spyOn(fs, 'readFileSync');
    chatPipeline._resetHistory();
    jest.resetAllMocks();
    readFileSyncSpy = jest.spyOn(fs, 'readFileSync');
  });

  afterEach(() => {
    readFileSyncSpy.mockRestore();
  });

  it('returns Ollama response using the system prompt from file', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockResolvedValue('Beep boop, hello friend!');

    const result = await chatPipeline.runChatPipeline('Hello!');

    expect(result).toBe('Beep boop, hello friend!');
    expect(chat).toHaveBeenCalledWith(
      expect.any(String),
      [
        { role: 'system', content: 'You are Beemo!' },
        { role: 'user', content: 'Hello!' },
      ]
    );
  });

  it('trims whitespace from the system prompt file content', async () => {
    readFileSyncSpy.mockReturnValue('   You are Beemo!   \n');
    chat.mockResolvedValue('Hi!');

    await chatPipeline.runChatPipeline('Hey');

    expect(chat).toHaveBeenCalledWith(
      expect.any(String),
      expect.arrayContaining([{ role: 'system', content: 'You are Beemo!' }])
    );
  });

  it('falls back to a default prompt when the system prompt file is unreadable', async () => {
    readFileSyncSpy.mockImplementation(() => { throw new Error('ENOENT'); });
    chat.mockResolvedValue('Hi there!');

    const result = await chatPipeline.runChatPipeline('Hello!');

    expect(result).toBe('Hi there!');
    expect(chat).toHaveBeenCalledWith(
      expect.any(String),
      expect.arrayContaining([
        { role: 'system', content: 'You are Beemo, a cheerful and playful AI assistant.' },
      ])
    );
  });

  it('propagates errors from chat without catching them', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockRejectedValue(new Error('ECONNREFUSED'));

    await expect(chatPipeline.runChatPipeline('Hello!')).rejects.toThrow('ECONNREFUSED');
  });

  it('accumulates conversation history across calls', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockResolvedValueOnce('Hi there!').mockResolvedValueOnce('Good, thanks!');

    await chatPipeline.runChatPipeline('Hello!');
    await chatPipeline.runChatPipeline('How are you?');

    expect(chat).toHaveBeenLastCalledWith(
      expect.any(String),
      [
        { role: 'system', content: 'You are Beemo!' },
        { role: 'user', content: 'Hello!' },
        { role: 'assistant', content: 'Hi there!' },
        { role: 'user', content: 'How are you?' },
      ]
    );
  });

  it('caps history at 20 messages by dropping the oldest when over limit', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockResolvedValue('ok');

    // 10 turns fills messages to 20 entries
    for (let i = 0; i < 10; i++) {
      await chatPipeline.runChatPipeline(`message ${i}`);
    }

    // 11th turn: candidate = 21, trimmed to 20, fullMessages = 21 (system + 20)
    await chatPipeline.runChatPipeline('message 10');

    const calledMessages = chat.mock.calls[chat.mock.calls.length - 1][1];
    expect(calledMessages.length).toBe(21); // system + 20 history entries
    expect(calledMessages[0].role).toBe('system');
    // oldest user turn ('message 0') must be gone
    expect(calledMessages.find(m => m.role === 'user' && m.content === 'message 0')).toBeUndefined();
    // newest user turn must be present
    expect(calledMessages[calledMessages.length - 1]).toEqual({ role: 'user', content: 'message 10' });
  });

  it('does not store history when chat throws', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockRejectedValueOnce(new Error('network error'));
    chat.mockResolvedValueOnce('success');

    await chatPipeline.runChatPipeline('failed message').catch(() => {});
    await chatPipeline.runChatPipeline('second message');

    // second call must not see the failed turn in history
    expect(chat).toHaveBeenLastCalledWith(
      expect.any(String),
      [
        { role: 'system', content: 'You are Beemo!' },
        { role: 'user', content: 'second message' },
      ]
    );
  });

  it('_resetHistory clears stored conversation', async () => {
    readFileSyncSpy.mockReturnValue('You are Beemo!');
    chat.mockResolvedValue('hi');

    await chatPipeline.runChatPipeline('hello');
    chatPipeline._resetHistory();

    chat.mockResolvedValue('fresh start');
    await chatPipeline.runChatPipeline('new message');

    expect(chat).toHaveBeenLastCalledWith(
      expect.any(String),
      [
        { role: 'system', content: 'You are Beemo!' },
        { role: 'user', content: 'new message' },
      ]
    );
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd services/brain && npx jest src/__tests__/chatPipeline.test.js --no-coverage
```

Expected: Most tests FAIL — `chat` mock is called but the pipeline still calls `generate`, and `_resetHistory` does not exist yet.

- [ ] **Step 3: Implement the new chatPipeline.js**

Replace the full contents of `services/brain/src/pipelines/chatPipeline.js` with:

```js
const path = require('path');
const fs = require('fs');
const { chat } = require('../services/ollamaClient');

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

async function runChatPipeline(text) {
  const system = loadSystemPrompt();
  const candidate = [...messages, { role: 'user', content: text }];
  const trimmed = candidate.length > MAX_HISTORY ? candidate.slice(-MAX_HISTORY) : candidate;
  const fullMessages = [{ role: 'system', content: system }, ...trimmed];

  const response = await chat(process.env.LLM_MODEL || 'gemma3', fullMessages);

  messages = [...trimmed, { role: 'assistant', content: response }];
  return response;
}

function _resetHistory() {
  messages = [];
}

module.exports = { runChatPipeline, _resetHistory };
```

- [ ] **Step 4: Run chatPipeline tests to confirm they pass**

```bash
cd services/brain && npx jest src/__tests__/chatPipeline.test.js --no-coverage
```

Expected: 8 tests PASS

- [ ] **Step 5: Run the full brain test suite**

```bash
cd services/brain && npx jest --no-coverage
```

Expected: All 35 tests PASS (32 existing + 3 new chat tests in ollamaClient — note: chatPipeline went from 4 to 8 tests)

- [ ] **Step 6: Commit**

```bash
git add services/brain/src/pipelines/chatPipeline.js services/brain/src/__tests__/chatPipeline.test.js
git commit -m "feat(brain): add conversation memory — 10-turn history via /api/chat"
```

---

## Self-Review

- [x] **Spec coverage:** `chat()` added to ollamaClient ✓, `messages` array with MAX_HISTORY=20 ✓, candidate pattern (no mutation before success) ✓, `_resetHistory` for test isolation ✓, system prompt prepended fresh each call ✓, failed calls don't pollute history ✓
- [x] **No placeholders:** All steps have complete code
- [x] **Type consistency:** `chat(model, messages)` signature matches across ollamaClient.js, test, and chatPipeline usage; `_resetHistory()` named consistently in implementation and tests
