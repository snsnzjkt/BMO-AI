# Sentence-Level Streaming Design

## Overview

Reduce Beemo's response latency by streaming tokens from Ollama, splitting them into sentences, and synthesizing + playing each sentence as it completes — so Beemo starts speaking after the first sentence rather than waiting for the full response.

Synthesis is **sequential**: play sentence 1, then synthesize and play sentence 2, and so on. No parallelism.

---

## Architecture

Five files change. Nothing else is touched.

| File | Change |
|---|---|
| `services/brain/src/services/ollamaClient.js` | Add `chatStream(model, messages)` async generator using Ollama `/api/chat` with `stream: true` |
| `services/brain/src/pipelines/chatPipeline.js` | Add `streamChatPipeline(text)` async generator that splits tokens into sentences and updates history after completion |
| `services/brain/src/routes/chat.js` | Add `POST /chat/stream` NDJSON handler; existing `POST /chat` unchanged |
| `services/voice/src/brain_client.py` | Add `stream_chat(text)` generator using `httpx.stream()` |
| `services/voice/main.py` | Replace single synthesize+play block with per-sentence loop |

---

## Brain Service

### `ollamaClient.js` — `chatStream(model, messages)`

Calls Ollama `/api/chat` with `stream: true`. Reads the response body using the Fetch streaming API (`response.body.getReader()`), decodes NDJSON line by line, and yields each non-empty `data.message.content` token string. Returns (stops yielding) when `data.done` is `true`.

```js
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
```

Throws if Ollama returns a non-ok status before streaming begins. Mid-stream errors propagate as thrown exceptions from the `for await` loop in the caller.

---

### `chatPipeline.js` — `streamChatPipeline(text)`

Async generator alongside the existing `runChatPipeline`. Shares the same module-level `messages` array and `MAX_HISTORY` cap.

**Sentence splitting:** accumulates tokens into a buffer. After each token, tests the buffer against `/^(.*?[.!?])\s+([\s\S]*)$/`. On match, yields the sentence (match group 1, trimmed) and carries the remainder (match group 2) forward. After the token stream ends, yields any remaining buffer content if non-empty.

**History update:** assembles the full response by joining all yielded sentences with a space, then writes to `messages` after the last `yield` — only if the generator completes naturally. Disconnections mid-stream do not update history for that turn.

```js
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
```

---

### `routes/chat.js` — `POST /chat/stream`

Added alongside the existing `POST /` handler. Validates input, sets `Content-Type: application/x-ndjson`, iterates `streamChatPipeline`, writes each sentence as `{"sentence":"..."}\n`, and writes `{"done":true}\n` on completion.

If `streamChatPipeline` throws before any write: responds with `503`. If it throws after headers are sent: writes `{"error":"..."}\n` and ends the response.

The existing `POST /` handler and all intent-routing logic are **unchanged**.

---

## Voice Pipeline

### `src/brain_client.py` — `stream_chat(text)`

Generator function. Opens an `httpx` streaming POST to `{BRAIN_URL}/chat/stream`, reads lines one at a time via `response.iter_lines()`, parses each as JSON, yields `data['sentence']`, and stops on `data.get('done')`. Raises `BrainServiceError` on non-ok HTTP status or connection failure.

```python
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
        raise BrainServiceError(f'Brain service returned {e.response.status_code}') from e
    except httpx.RequestError as e:
        raise BrainServiceError(f'Brain service unreachable: {e}') from e
```

The existing `chat(text)` function is **unchanged**.

---

### `main.py` — per-sentence loop

The `thinking` → `speaking`/`fallback` block is replaced:

```python
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
    response_text = FALLBACK_MESSAGE
    log.info('Beemo says: %s', response_text)
    try:
        audio_bytes = synthesizer.synthesize(response_text)
        player.play(audio_bytes)
    except synthesizer.SynthesisError as e:
        log.error('Synthesis error: %s', e)
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Ollama unreachable / non-ok before first token | `chatStream` throws → `BrainServiceError` → `fallback` state → fallback line plays |
| Ollama drops connection mid-stream | `httpx` raises mid-iteration → loop exits, partial sentences already played, no fallback |
| Empty sentence after splitting | Skipped — guarded by `if buffer.trim()` |
| Synthesis fails on one sentence | `SynthesisError` caught per-sentence, logged, skipped — loop continues |
| Response produces zero sentences | Generator yields nothing → history not updated → state stays `thinking` → loop top resets to `idle` |

---

## State Transitions

```
set_state('thinking')       ← before stream_chat() starts
first sentence arrives  →   set_state('speaking')
... per-sentence play ...
loop top                →   set_state('idle')

BrainServiceError       →   set_state('fallback') → play fallback → loop top → set_state('idle')
```

---

## Backward Compatibility

- `POST /chat` — unchanged
- `brain_client.chat()` — unchanged
- `runChatPipeline()` — unchanged
- All existing tests — unchanged
- `_resetHistory()` — resets history for both `runChatPipeline` and `streamChatPipeline` (shared `messages` array)
