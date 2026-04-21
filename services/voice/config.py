import os

BRAIN_URL = os.getenv('BRAIN_URL', 'http://localhost:3001')
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
PIPER_BINARY = os.getenv('PIPER_BINARY', 'piper')
PIPER_MODEL_PATH = os.getenv('PIPER_MODEL_PATH')
SILENCE_DURATION = float(os.getenv('SILENCE_DURATION', '1.5'))
SILENCE_THRESHOLD = float(os.getenv('SILENCE_THRESHOLD', '0.01'))
PTT_KEY = os.getenv('PTT_KEY', 'space')
WAKE_WORD_MODEL = os.getenv('WAKE_WORD_MODEL', 'alexa')
