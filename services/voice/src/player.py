import io
import logging
import wave
import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

_SAMPLE_WIDTH_DTYPE = {1: np.int8, 2: np.int16, 4: np.int32}


def play(wav_bytes: bytes) -> None:
    if not wav_bytes:
        log.warning('player.play() called with empty bytes, skipping')
        return
    try:
        with wave.open(io.BytesIO(wav_bytes)) as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        dtype = _SAMPLE_WIDTH_DTYPE.get(sample_width)
        if dtype is None:
            log.error('Unsupported WAV sample width: %d bytes', sample_width)
            return

        divisor = float(1 << (8 * sample_width - 1))
        audio = np.frombuffer(raw, dtype=dtype).astype(np.float32) / divisor
        if n_channels > 1:
            audio = audio.reshape(-1, n_channels)

        log.debug('Playing %.1fs of audio at %dHz', n_frames / sample_rate, sample_rate)
        sd.play(audio, sample_rate)
        sd.wait()
        log.debug('Playback complete')
    except wave.Error as e:
        log.error('Invalid WAV data: %s', e)
    except sd.PortAudioError as e:
        log.error('Audio playback hardware error: %s', e)
