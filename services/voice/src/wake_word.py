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
