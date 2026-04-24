import logging
import queue
import threading
import numpy as np
import sounddevice as sd
import keyboard
from openwakeword.model import Model
import config

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280  # ~80ms, recommended chunk size for OpenWakeWord
LISTEN_TIMEOUT = 300.0  # 5-minute absolute timeout on waiting for a trigger

_oww_model: Model | None = None


def _get_model() -> Model:
    global _oww_model
    if _oww_model is None:
        log.debug('Loading OpenWakeWord model: %s', config.WAKE_WORD_MODEL)
        _oww_model = Model(wakeword_models=[config.WAKE_WORD_MODEL], inference_framework='onnx')
    return _oww_model


def listen() -> str:
    """Block until wake word detected or PTT key pressed.

    Returns 'wake_word' or 'ptt'. Raises RuntimeError if the wake-word
    thread fails (e.g. hardware or model error).
    """
    result_queue: queue.Queue[str] = queue.Queue(maxsize=1)
    stop_event = threading.Event()

    def _wake_word_thread() -> None:
        try:
            oww = _get_model()
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16') as stream:
                while not stop_event.is_set():
                    chunk, _ = stream.read(CHUNK_SAMPLES)
                    # scores is dict[model_name, float]
                    scores = oww.predict(chunk.flatten())
                    for score in scores.values():
                        if score > 0.5 and result_queue.empty():
                            log.debug('Wake word detected (score=%.2f)', score)
                            result_queue.put('wake_word')
                            return
        except Exception as e:
            log.error('Wake word thread failed: %s', e)
            if result_queue.empty():
                result_queue.put('error')

    hotkey = keyboard.add_hotkey(config.PTT_KEY, lambda: result_queue.put('ptt') if result_queue.empty() else None)

    if config.WAKE_WORD_MODEL:
        wake_thread = threading.Thread(target=_wake_word_thread, daemon=True)
        wake_thread.start()
    else:
        log.info('No wake word model configured — PTT only (press [%s])', config.PTT_KEY)
        wake_thread = None

    try:
        result = result_queue.get(timeout=LISTEN_TIMEOUT)
    except queue.Empty:
        log.warning('Listen timeout after %.0fs, restarting listener', LISTEN_TIMEOUT)
        result = 'timeout'
    finally:
        stop_event.set()
        keyboard.remove_hotkey(hotkey)
        if wake_thread:
            wake_thread.join(timeout=1.0)

    if result == 'error':
        raise RuntimeError('Wake word detection failed — check hardware and model config')

    if result == 'timeout':
        raise RuntimeError(f'Listen timeout after {LISTEN_TIMEOUT:.0f}s — no trigger received')

    log.info('Triggered by: %s', result)
    return result
