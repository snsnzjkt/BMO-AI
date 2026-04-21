import numpy as np
import whisper
import config

_model = None


def _load_model():
    global _model
    if _model is None:
        _model = whisper.load_model(config.WHISPER_MODEL)
    return _model


def transcribe(audio_array: np.ndarray) -> str:
    try:
        model = _load_model()
        result = model.transcribe(audio_array, fp16=False)
        return result.get('text', '').strip()
    except Exception:
        return ''
