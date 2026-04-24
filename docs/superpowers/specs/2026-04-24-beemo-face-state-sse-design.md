# Beemo Face State — SSE Design

## Overview

Wire the 10 SVG face states in `apps/desktop/states/` to the live voice pipeline by adding a Server-Sent Events (SSE) state channel to the brain service. The desktop UI holds an SSE connection open and swaps the face SVG whenever the pipeline advances to a new step.

---

## State Map

| Pipeline moment | State key | SVG file |
|---|---|---|
| Top of loop, `wake_word.listen()` running | `idle` | `Idle or listening.svg` |
| Wake word detected, before `recorder.record()` | `listening` | `listening.svg` |
| `recorder.record()` running | `recording` | `recording or transcribing.svg` |
| `transcriber.transcribe()` running | `transcribing` | `recording or transcribing.svg` |
| `brain_client.chat()` running | `thinking` | `thinking or brain_request.svg` |
| `synthesizer.synthesize()` + `player.play()` running | `speaking` | alternates between `speaking or playing_response.svg` and `speaking or playing_response (1).svg` at 500ms |
| Transcription returned empty string | `silent` | `silent_skip when transcription is empty.svg` |
| `RecordingError` or wake word `RuntimeError` caught | `error` | `error_recovering when something fails but the loop continues.svg` |
| `BrainServiceError` caught, playing fallback line | `fallback` | `fallback_speaking when the brain is down and it plays the fallback line.svg` |
| Power button pressed in UI | `off` | `powered off.svg` |

---

## Architecture

### Brain service — `services/brain/`

**`src/state.js`** — in-memory state store

- Exports `currentState` (string, default `'idle'`)
- Exports `clients` (array of active SSE `res` objects)
- Exports `setState(key)` — updates `currentState`, writes `data: {"state":"<key>"}\n\n` to every client in `clients`

**`src/routes/state.js`** — two endpoints

- `POST /state` — reads `{ state }` from request body, calls `setState(key)`, responds `204`
- `GET /state/stream` — sets SSE headers (`Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`), pushes client into `clients`, immediately sends current state, removes client from array on connection close

**`index.js`** — mount `stateRoute` at `/state`

---

### Voice pipeline — `services/voice/`

**`src/state_client.py`** — single public function

```python
def set_state(key: str) -> None:
```

- Fire-and-forget `POST http://localhost:3001/state` with `{"state": key}`
- Uses `httpx` (already a dependency) with a short timeout (2s)
- Catches all exceptions silently — a UI update must never crash the pipeline

**`main.py`** — call `set_state` before each step

```
set_state('idle')        ← top of loop, before wake_word.listen()
set_state('listening')   ← after wake word detected
set_state('recording')   ← before recorder.record()
set_state('transcribing')← before transcriber.transcribe()
set_state('thinking')    ← before brain_client.chat()
set_state('speaking')    ← before synthesizer.synthesize() + player.play()
set_state('silent')      ← when text is empty, before continue
set_state('error')       ← in RecordingError / RuntimeError handlers, before continue
set_state('fallback')    ← after BrainServiceError, before playing fallback
```

---

### Desktop UI — `apps/desktop/`

**`index.html`**

- Replace the `.face` child divs (`.eyes`, `.mouth`, etc.) with `<img id="face-svg" src="states/Idle or listening.svg">`
- Add `EventSource` script:
  - Connects to `http://localhost:3001/state/stream`
  - On each message: looks up state key in a map, sets `faceSvg.src`
  - While `is-monochrome` is active (power off), ignores SSE events
  - On `onerror`: browser auto-reconnects; on reconnect the brain immediately resends current state
- Power button handler: sets `faceSvg.src` to `powered off.svg` on toggle-off; on toggle-on, re-enables SSE handling (current state arrives automatically on next event)

**`styles.css`**

- Remove `.eyes`, `.eyes:after`, `.mouth`, `.teeth`, `.tounge` rules
- Add `#face-svg` rule: `width: 100%; height: 100%; display: block; object-fit: fill;`

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Brain service down when pipeline calls `POST /state` | `state_client.py` swallows exception; pipeline continues |
| Brain service restarts mid-session | SSE drops; `EventSource` auto-reconnects; brain sends current state immediately on reconnect |
| Desktop opens before pipeline starts | SSE connects, brain sends `idle` immediately |
| Power toggled off | UI switches to `powered off.svg` locally; SSE events ignored until toggled back on |
| Speaking animation | JS `setInterval` at 500ms alternates between the two speaking SVGs while state is `speaking`; cleared when state changes |

---

## Files Changed

| File | Change |
|---|---|
| `services/brain/src/state.js` | new |
| `services/brain/src/routes/state.js` | new |
| `services/brain/index.js` | mount `/state` route |
| `services/voice/src/state_client.py` | new |
| `services/voice/main.py` | add `set_state` calls |
| `apps/desktop/index.html` | replace face divs, add SSE script |
| `apps/desktop/styles.css` | remove face CSS, add `#face-svg` rule |
