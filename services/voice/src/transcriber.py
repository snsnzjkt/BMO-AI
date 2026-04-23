import numpy as np
from faster_whisper import WhisperModel
import config

_model = None


def _load_model():
    global _model
    if _model is None:
        _model = WhisperModel(config.WHISPER_MODEL, device='cpu', compute_type='int8')
    return _model


def transcribe(audio_array: np.ndarray) -> str:
    try:
        model = _load_model()
        segments, _ = model.transcribe(audio_array, beam_size=5)
        return ''.join(segment.text for segment in segments).strip()
    except Exception:
        return ''
