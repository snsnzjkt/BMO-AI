import sys
import os
import shutil
import logging
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

import config
from src import wake_word, recorder, transcriber, brain_client, synthesizer, player, state_client

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
        state_client.set_state('idle')
        try:
            trigger = wake_word.listen()
            log.info('Triggered by: %s', trigger)
        except RuntimeError as e:
            log.error('Wake word listener error: %s — retrying...', e)
            state_client.set_state('error')
            continue

        state_client.set_state('listening')

        try:
            state_client.set_state('recording')
            audio = recorder.record()
        except recorder.RecordingError as e:
            log.error('Recording failed: %s — retrying...', e)
            state_client.set_state('error')
            continue

        state_client.set_state('transcribing')
        text = transcriber.transcribe(audio)

        if not text:
            log.info('No speech detected, continuing...')
            state_client.set_state('silent')
            continue

        log.info('You said: %s', text)

        state_client.set_state('thinking')
        try:
            first = True
            for sentence in brain_client.stream_chat(text):
                if first:
                    state_client.set_state('speaking')
                    first = False
                log.info('Beemo says: %s', sentence)
                try:
                    audio_bytes = synthesizer.synthesize(sentence)
                    player.play(audio_bytes)
                except synthesizer.SynthesisError as e:
                    log.error('Synthesis error for sentence: %s', e)
        except brain_client.BrainServiceError as e:
            log.error('Brain service error: %s', e)
            state_client.set_state('fallback')
            log.info('Beemo says: %s', FALLBACK_MESSAGE)
            try:
                audio_bytes = synthesizer.synthesize(FALLBACK_MESSAGE)
                player.play(audio_bytes)
            except synthesizer.SynthesisError as e:
                log.error('Synthesis error: %s', e)

        log.info('Listening for wake word or press [%s]...', config.PTT_KEY)


if __name__ == '__main__':
    run_pipeline()
