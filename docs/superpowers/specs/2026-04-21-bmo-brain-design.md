# BMO Brain Service — Design Spec

**Date:** 2026-04-21
**Phase:** 1 — Basic chat via Ollama
**Scope:** `/services/brain` Node.js backend only

---

## Overview

The Brain service is the AI orchestration layer for the BMO assistant. It accepts text input, classifies the intent using Gemma 3, routes to the appropriate pipeline, and returns a text response with metadata.

This spec covers Phase 1: a working chat endpoint with LLM-based intent routing. Later phases add pipelines for RAG, vision, and camera without changing the core structure.

---

## Folder Structure

```
services/brain/
├── index.js                  # Express server, mounts routes
├── package.json
└── src/
    ├── routes/
    │   ├── chat.js           # POST /chat
    │   ├── vision.js         # POST /vision  (501 stub)
    │   └── rag.js            # POST /rag     (501 stub)
    ├── services/
    │   ├── ollamaClient.js   # fetch wrapper around Ollama HTTP API
    │   └── intentRouter.js   # LLM-based intent classification via Gemma
    └── pipelines/
        └── chatPipeline.js   # input → Gemma → text response
```

Each future phase adds one new pipeline file and one route — nothing else changes.

---

## API Contract

### `POST /chat`

**Request:**
```json
{ "text": "string" }
```

**Response:**
```json
{
  "text": "string",
  "intent": "chat | rag | vision | camera | web",
  "model": "gemma3"
}
```

### `POST /vision`
Returns `501 Not Implemented` (stub for Phase 4).

### `POST /rag`
Returns `501 Not Implemented` (stub for Phase 5).

---

## Data Flow

```
POST /chat  { text }
  │
  ├─► intentRouter  →  Gemma classifies intent (one word: chat | rag | vision | camera | web)
  │
  ├─► chatPipeline  →  BMO system prompt + user text → Gemma → response text
  │   (future: ragPipeline, visionPipeline, etc.)
  │
  └─► { text, intent, model }
```

---

## Component Details

### `ollamaClient.js`

- Thin `fetch` wrapper to Ollama's HTTP API (`/api/generate`)
- Exported function: `generate(model, prompt, system)` → `string`
- Uses `stream: false` for full response at once
- Base URL: `OLLAMA_BASE_URL` env var, defaults to `http://localhost:11434`

### `intentRouter.js`

- Calls `ollamaClient.generate()` with a strict classification prompt
- Prompt instructs Gemma to reply with exactly one word from the allowed set
- Strips whitespace, lowercases, validates against `['chat', 'rag', 'vision', 'camera', 'web']`
- Falls back to `chat` if response is unrecognized

### `chatPipeline.js`

- Reads BMO system prompt from `packages/prompts/systemPrompt.txt`
- Calls `ollamaClient.generate()` with system prompt + user text
- Returns response string

### `index.js`

- Express server on port `3001` (configurable via `PORT` env var)
- JSON body parsing middleware
- Request logger (method + path + duration)
- Mounts all three routes

---

## Error Handling

| Condition | HTTP | Response body |
|---|---|---|
| Missing or empty `text` | 400 | `{ "error": "BMO needs something to think about!" }` |
| Ollama unreachable | 503 | `{ "error": "BMO's brain is sleeping... try again!" }` |
| Unknown intent | — | Falls back to `chat` pipeline silently |

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `PORT` | `3001` | Express listen port |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `LLM_MODEL` | `gemma3` | Model used for chat + intent |

---

## Out of Scope (Phase 1)

- RAG retrieval and vector DB
- Vision / Moondream integration
- Camera capture
- Voice pipeline (Whisper / Piper)
- Authentication
- Conversation history / memory
