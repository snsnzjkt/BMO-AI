import pytest
import numpy as np
import sys
import os

# Ensure services/voice/ is on path for 'import main'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv('PIPER_MODEL_PATH', '/fake/model.onnx')
    monkeypatch.setenv('BRAIN_URL', 'http://localhost:3001')


def test_pipeline_runs_full_happy_path(mocker):
    """Wake word fires → record → transcribe → chat → synthesize → play → loop back."""
    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] > 1:
            raise KeyboardInterrupt
        return 'wake_word'

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello BMO!')
    mock_chat = mocker.patch('src.brain_client.chat', return_value='Hi there friend!')
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00\x01')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    import main
    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_chat.assert_called_once_with('Hello BMO!')
    mock_synthesize.assert_called_once_with('Hi there friend!')
    mock_play.assert_called_once_with(b'\x00\x01')


def test_pipeline_skips_when_transcription_is_empty(mocker):
    """Empty transcription → skip brain call, loop back immediately."""
    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] > 1:
            raise KeyboardInterrupt
        return 'ptt'

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='')
    mock_chat = mocker.patch('src.brain_client.chat')
    mocker.patch('main._validate')

    import main
    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_chat.assert_not_called()


def test_pipeline_plays_fallback_when_brain_unavailable(mocker):
    """BrainServiceError → synthesize + play the fallback message."""
    from src.brain_client import BrainServiceError

    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] > 1:
            raise KeyboardInterrupt
        return 'wake_word'

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.chat', side_effect=BrainServiceError('down'))
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    import main
    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_synthesize.assert_called_once_with(main.FALLBACK_MESSAGE)
    mock_play.assert_called_once_with(b'\x00')
