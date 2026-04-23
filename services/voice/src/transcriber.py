import numpy as np
import logging
import config

_model = None
_whisper_import_error = None
_logged_import_error = False

try:
    from faster_whisper import WhisperModel
except Exception as exc:
    WhisperModel = None
    _whisper_import_error = exc


log = logging.getLogger(__name__)


def _load_model():
    global _logged_import_error
    global _model
    if _model is None:
        if WhisperModel is None:
            if not _logged_import_error:
                log.error('faster_whisper unavailable: %s', _whisper_import_error)
                _logged_import_error = True
            raise RuntimeError('Whisper model dependency is unavailable')
        _model = WhisperModel(config.WHISPER_MODEL, device='cpu', compute_type='int8')
    return _model


def transcribe(audio_array: np.ndarray) -> str:
    try:
        model = _load_model()
        segments, _ = model.transcribe(audio_array, beam_size=5)
        return ''.join(segment.text for segment in segments).strip()
    except Exception:
        return ''
