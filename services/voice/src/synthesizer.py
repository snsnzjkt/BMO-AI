import io
import logging
import wave
import config
from piper import PiperVoice

log = logging.getLogger(__name__)

_voice = None


class SynthesisError(Exception):
    pass


def _get_voice():
    global _voice
    if _voice is None:
        log.info('Loading Piper voice model: %s', config.PIPER_MODEL_PATH)
        _voice = PiperVoice.load(config.PIPER_MODEL_PATH)
    return _voice


def synthesize(text: str) -> bytes:
    try:
        voice = _get_voice()
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            voice.synthesize_wav(text, wav_file)  # set_wav_format=True by default
        return wav_io.getvalue()
    except Exception as e:
        raise SynthesisError(f'Piper synthesis failed: {e}') from e
