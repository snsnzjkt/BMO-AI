# Conversation Memory Implementation Design

## Overview

Add in-session conversation memory to Beemo's chat pipeline. Beemo will remember the last 10 turns of each conversation and forget everything when the pipeline restarts. No persistence to disk.

---

## Architecture

### `services/brain/src/services/ollamaClient.js`

Add a new `chat(model, messages)` function that calls Ollama's `/api/chat` endpoint. The `messages` argument is a fully assembled array including the system message as the first entry. The existing `generate()` function is kept for future use in RAG/vision pipelines.

Ollama `/api/chat` request body:
```json
{
  "model": "gemma3",
  "messages": [
    { "role": "system", "content": "<systemPrompt>" },
    { "role": "user", "content": "hello" },
    { "role": "assistant", "content": "hi there!" },
    { "role": "user", "content": "what's your name?" }
  ],
  "stream": false,
  "options": { "num_predict": 80, "temperature": 0.7 }
}
```

Response field: `data.message.content` (vs `data.response` from `/api/generate`).

### `services/brain/src/pipelines/chatPipeline.js`

Add a module-level `messages` array (in-memory, `[]` on startup). Each call to `runChatPipeline(text)` follows this flow:

```
1. system = loadSystemPrompt()
2. candidate = [...messages, { role: 'user', content: text }]
3. if candidate.length > 20 → candidate = candidate.slice(-20)
4. fullMessages = [{ role: 'system', content: system }, ...candidate]
5. response = await ollamaClient.chat(model, fullMessages)
6. messages = [...candidate, { role: 'assistant', content: response }]
7. return response
```

The user message is committed to `messages` only after a successful Ollama response (step 6). If `chat()` throws, `messages` is unchanged — the failed turn is not stored.

---

## Memory Cap

- `messages` stores only user/assistant turns (no system message)
- Maximum: 20 entries = 10 full turns (1 user + 1 assistant = 1 turn)
- Trimming: if `candidate.length > 20`, slice from the front — oldest turn dropped first
- System prompt is always prepended fresh from `loadSystemPrompt()` at call time

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Ollama non-ok status | `chat()` throws → route's existing 503 handler catches → fallback line plays → `messages` unchanged |
| Ollama unreachable | Same — throw propagates before any history mutation |
| History at 20 messages | Oldest 2 messages (1 turn) trimmed from `candidate` before call |
| Pipeline restart | `messages` resets to `[]` — Beemo starts fresh with no memory |

---

## Files Changed

| File | Change |
|---|---|
| `services/brain/src/services/ollamaClient.js` | Add `chat(model, messages)` using `/api/chat`; keep `generate()` |
| `services/brain/src/__tests__/ollamaClient.test.js` | Add tests for `chat()` |
| `services/brain/src/pipelines/chatPipeline.js` | Add `messages` array; switch to `ollamaClient.chat()`; implement cap logic |
| `services/brain/src/__tests__/chatPipeline.test.js` | Add tests for history accumulation, capping, error safety |

---

## What Does Not Change

- The `/chat` route (`src/routes/chat.js`) — unchanged
- The voice pipeline — unchanged
- The desktop UI — unchanged
- The `generate()` function — kept for future RAG/vision use
