import numpy as np
import sounddevice as sd
import config

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1  # 100ms per chunk


def record() -> np.ndarray:
    buffer = []
    silence_chunks = 0
    silence_limit = int(config.SILENCE_DURATION / CHUNK_DURATION)
    chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
        while True:
            chunk, _ = stream.read(chunk_samples)
            buffer.append(chunk)
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            if rms < config.SILENCE_THRESHOLD:
                silence_chunks += 1
                if silence_chunks >= silence_limit:
                    break
            else:
                silence_chunks = 0

    return np.concatenate(buffer, axis=0).flatten()
