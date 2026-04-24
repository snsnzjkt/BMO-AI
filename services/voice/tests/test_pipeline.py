import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main  # noqa: E402
from src.brain_client import BrainServiceError
from src.synthesizer import SynthesisError
from src.recorder import RecordingError
from src import state_client  # noqa: F401


@pytest.fixture(autouse=True)
def mock_set_state(mocker):
    return mocker.patch('src.state_client.set_state')


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv('PIPER_MODEL_PATH', '/fake/model.onnx')
    monkeypatch.setenv('BRAIN_URL', 'http://localhost:3001')


def _make_listen(n_calls=1, trigger='wake_word'):
    count = {'n': 0}
    def mock_listen():
        count['n'] += 1
        if count['n'] > n_calls:
            raise KeyboardInterrupt
        return trigger
    return mock_listen


def test_pipeline_runs_full_happy_path(mocker):
    """Wake word fires → record → transcribe → stream → synthesize → play → loop back."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello Beemo!')
    mock_stream = mocker.patch('src.brain_client.stream_chat', return_value=iter(['Hi there friend!']))
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00\x01')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_stream.assert_called_once_with('Hello Beemo!')
    mock_synthesize.assert_called_once_with('Hi there friend!')
    mock_play.assert_called_once_with(b'\x00\x01')


def test_pipeline_synthesizes_each_sentence_in_order(mocker):
    """Multiple sentences → each synthesized and played before reading the next."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello Beemo!')
    mocker.patch('src.brain_client.stream_chat', return_value=iter(['Hello!', 'How are you?']))
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    assert mock_synthesize.call_count == 2
    mock_synthesize.assert_any_call('Hello!')
    mock_synthesize.assert_any_call('How are you?')
    assert mock_play.call_count == 2


def test_pipeline_skips_when_transcription_is_empty(mocker):
    """Empty transcription → skip brain call, loop back immediately."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='ptt'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='')
    mock_stream = mocker.patch('src.brain_client.stream_chat')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_stream.assert_not_called()


def test_pipeline_plays_fallback_when_brain_unavailable(mocker):
    """BrainServiceError → synthesize + play the fallback message."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.stream_chat', side_effect=BrainServiceError('down'))
    mock_synthesize = mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mock_play = mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_synthesize.assert_called_once_with(main.FALLBACK_MESSAGE)
    mock_play.assert_called_once_with(b'\x00')


def test_pipeline_continues_when_synthesis_fails(mocker):
    """SynthesisError on one sentence → skip playback for that sentence, loop continues."""
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.stream_chat', return_value=iter(['Hi!']))
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
    mock_stream = mocker.patch('src.brain_client.stream_chat')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    mock_stream.assert_not_called()


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


def test_pipeline_emits_correct_state_transitions_on_happy_path(mocker, mock_set_state):
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello Beemo!')
    mocker.patch('src.brain_client.stream_chat', return_value=iter(['Hi there!']))
    mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert states == ['idle', 'listening', 'recording', 'transcribing', 'thinking', 'speaking', 'idle']


def test_pipeline_emits_fallback_state_when_brain_is_down(mocker, mock_set_state):
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='Hello!')
    mocker.patch('src.brain_client.stream_chat', side_effect=BrainServiceError('down'))
    mocker.patch('src.synthesizer.synthesize', return_value=b'\x00')
    mocker.patch('src.player.play')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert 'fallback' in states
    assert 'speaking' not in states


def test_pipeline_emits_error_state_when_recording_fails(mocker, mock_set_state):
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', side_effect=RecordingError('mic disconnected'))
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert 'error' in states


def test_pipeline_emits_silent_state_when_transcription_empty(mocker, mock_set_state):
    mocker.patch('src.wake_word.listen', side_effect=_make_listen(trigger='wake_word'))
    mocker.patch('src.recorder.record', return_value=np.zeros(16000, dtype=np.float32))
    mocker.patch('src.transcriber.transcribe', return_value='')
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert 'silent' in states


def test_pipeline_emits_error_state_when_wake_word_listener_fails(mocker, mock_set_state):
    call_count = {'n': 0}

    def mock_listen():
        call_count['n'] += 1
        if call_count['n'] == 1:
            raise RuntimeError('Listen timeout')
        raise KeyboardInterrupt

    mocker.patch('src.wake_word.listen', side_effect=mock_listen)
    mocker.patch('main._validate')

    with pytest.raises(KeyboardInterrupt):
        main.run_pipeline()

    states = [call.args[0] for call in mock_set_state.call_args_list]
    assert 'error' in states
