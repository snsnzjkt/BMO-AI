import pytest
import numpy as np
from unittest.mock import patch, MagicMock
import src.transcriber as transcriber_module


@pytest.fixture(autouse=True)
def reset_cached_model():
    transcriber_module._model = None
    yield
    transcriber_module._model = None


def _make_mock_model(text):
    mock_segment = MagicMock()
    mock_segment.text = text
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())
    return mock_model


def test_transcribe_returns_stripped_text():
    mock_model = _make_mock_model('  Hello BMO!  ')

    with patch('src.transcriber.WhisperModel', return_value=mock_model):
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == 'Hello BMO!'
    _, kwargs = mock_model.transcribe.call_args
    assert kwargs.get('beam_size') == 5


def test_transcribe_returns_empty_string_on_silence():
    mock_model = _make_mock_model('   ')

    with patch('src.transcriber.WhisperModel', return_value=mock_model):
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == ''


def test_transcribe_returns_empty_string_on_transcription_exception():
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError('error')

    with patch('src.transcriber.WhisperModel', return_value=mock_model):
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == ''


def test_transcribe_returns_empty_string_when_model_load_fails():
    with patch('src.transcriber.WhisperModel', side_effect=RuntimeError('model not found')):
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == ''


def test_model_is_loaded_once_and_cached():
    mock_model = _make_mock_model('hi')

    with patch('src.transcriber.WhisperModel', return_value=mock_model) as mock_wm:
        audio = np.zeros(16000, dtype=np.float32)
        transcriber_module.transcribe(audio)
        transcriber_module.transcribe(audio)

    mock_wm.assert_called_once()
