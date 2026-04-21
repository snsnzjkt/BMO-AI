import logging
import numpy as np
import sounddevice as sd
import config

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1  # 100ms per chunk
MAX_DURATION = 30.0   # seconds — prevents infinite loop in noisy environments


class RecordingError(Exception):
    pass


def record() -> np.ndarray:
    buffer = []
    silence_chunks = 0
    silence_limit = int(config.SILENCE_DURATION / CHUNK_DURATION)
    chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION)
    max_chunks = int(MAX_DURATION / CHUNK_DURATION)

    log.debug('Recording started (silence threshold=%.3f, limit=%.1fs)',
              config.SILENCE_THRESHOLD, config.SILENCE_DURATION)
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
            while True:
                chunk, _ = stream.read(chunk_samples)
                buffer.append(chunk)
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                if rms < config.SILENCE_THRESHOLD:
                    silence_chunks += 1
                    if silence_chunks >= silence_limit:
                        log.debug('Silence detected, stopping recording')
                        break
                else:
                    silence_chunks = 0
                if len(buffer) >= max_chunks:
                    log.warning('Max recording duration (%.0fs) reached, stopping early', MAX_DURATION)
                    break
    except sd.PortAudioError as e:
        log.error('Microphone hardware error: %s', e)
        raise RecordingError(f'Microphone unavailable: {e}') from e

    audio = np.concatenate(buffer, axis=0).flatten()
    log.debug('Recorded %.2fs of audio (%d samples)', len(audio) / SAMPLE_RATE, len(audio))
    return audio
