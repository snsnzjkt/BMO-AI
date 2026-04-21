import pytest
import numpy as np
import sys
import os

# conftest.py covers src.* — this insert is specifically for 'import main'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main  # noqa: E402 — must come after sys.path setup above
from src.brain_client import BrainServiceError
from src.synthesizer import SynthesisError
from src.recorder import RecordingError


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv('PIPER_MODEL_PATH', '/fake/model.onnx')
    monkeypatch.setenv('BRAIN_URL', 'http://localhost:3001')


def _make_listen(n_calls=1, trigger='wake_word'):
    """Returns a mock_listen that fires `trigger` on call 1, then KeyboardInterrupt."""
    count = {'n': 0}
    def mock_listen():
        count['n'] += 1
        if count['n'] > n_calls:
            raise KeyboardInterrupt
        return trigger
    return mock_listen


def test_pipeline_runs_full_happy_path(mocker):
    """Wake word fires → record → transcribe → chat → synthesize → play → loop back."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello BMO!')
    mock_chat = mocker.patch('src.brain_client.chat', return_value='Hi there friend!')
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00\x01')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_chat.assert_called_once_with('Hello BMO!')
    mock_synthesize.assert_called_once_with('Hi there friend!')
    mock_play.assert_called_once_with(b'\x00\x01')


def test_pipeline_skips_when_transcription_is_empty(mocker):
    """Empty transcription → skip brain call, loop back immediately."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='ptt'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='')
    mock_chat = mocker.patch('src.brain_client.chat')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_chat.assert_not_called()


def test_pipeline_plays_fallback_when_brain_unavailable(mocker):
    """BrainServiceError → synthesize + play the fallback message."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.chat', side_effect=BrainServiceError('down'))
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_synthesize.assert_called_once_with(main.FALLBACK_MESSAGE)
    mock_play.assert_called_once_with(b'\x00')


def test_pipeline_continues_when_synthesis_fails(mocker):
    """SynthesisError → log error, skip playback, loop continues."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.chat', return_value='Hi!')
    mocker.patch('src.synthesizer.synthesize', side_effect=SynthesisError('piper crashed'))
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_play.assert_not_called()


def test_pipeline_continues_when_recording_fails(mocker):
    """RecordingError → log error, loop continues to next wake word."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', side_effect=RecordingError('mic disconnected'))
    mock_chat = mocker.patch('src.brain_client.chat')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_chat.assert_not_called()


def test_pipeline_continues_when_listen_raises(mocker):
    """RuntimeError from wake_word.listen → log error, loop retries."""
    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] == 1:
            raise RuntimeError('Listen timeout')
        raise KeyboardInterrupt

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mock_record = mocker.patch('src.recorder.record')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_record.assert_not_called()
