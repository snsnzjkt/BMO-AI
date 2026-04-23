import sys
import os
import shutil
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

import config
from src import wake_word, recorder, transcriber, brain_client, synthesizer, player

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

FALLBACK_MESSAGE = "Beemo's brain is sleeping... please try again later!"


def _validate() -> None:
    if config.PIPER_MODEL_PATH is None:
        sys.exit('ERROR: PIPER_MODEL_PATH environment variable is required.')
    piper_found = shutil.which(config.PIPER_BINARY) or os.path.isfile(config.PIPER_BINARY)
    if not piper_found:
        sys.exit(f'ERROR: Piper binary not found: {config.PIPER_BINARY}')
    try:
        import sounddevice as sd
        sd.query_devices(kind='input')
    except Exception as e:
        sys.exit(f'ERROR: Microphone not available: {e}')
    log.info('Startup checks passed.')


def run_pipeline() -> None:
    _validate()
    log.info('Beemo is ready! Listening for wake word or press [%s]...', config.PTT_KEY)

    while True:
        try:
            trigger = wake_word.listen()
            log.info('Triggered by: %s', trigger)
        except RuntimeError as e:
            log.error('Wake word listener error: %s — retrying...', e)
            continue

        try:
            audio = recorder.record()
        except recorder.RecordingError as e:
            log.error('Recording failed: %s — retrying...', e)
            continue

        text = transcriber.transcribe(audio)

        if not text:
            log.info('No speech detected, continuing...')
            continue

        log.info('You said: %s', text)

        try:
            response_text = brain_client.chat(text)
        except brain_client.BrainServiceError as e:
            log.error('Brain service error: %s', e)
            response_text = FALLBACK_MESSAGE

        log.info('Beemo says: %s', response_text)

        try:
            audio_bytes = synthesizer.synthesize(response_text)
            player.play(audio_bytes)
        except synthesizer.SynthesisError as e:
            log.error('Synthesis error: %s', e)

        log.info('Listening for wake word or press [%s]...', config.PTT_KEY)


if __name__ == '__main__':
    run_pipeline()
