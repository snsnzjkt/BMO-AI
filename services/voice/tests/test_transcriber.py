import pytest
import numpy as np
from unittest.mock import patch, MagicMock
import src.transcriber as transcriber_module


@pytest.fixture(autouse=True)
def reset_cached_model():
    transcriber_module._model = None
    yield
    transcriber_module._model = None


def _make_mock_model(text_result):
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {'text': text_result}
    return mock_model


def test_transcribe_returns_stripped_text():
    mock_model = _make_mock_model('  Hello BMO!  ')

    with patch('src.transcriber.whisper') as mock_whisper:
        mock_whisper.load_model.return_value = mock_model
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == 'Hello BMO!'
    mock_model.transcribe.assert_called_once()


def test_transcribe_returns_empty_string_on_silence():
    mock_model = _make_mock_model('   ')

    with patch('src.transcriber.whisper') as mock_whisper:
        mock_whisper.load_model.return_value = mock_model
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == ''


def test_transcribe_returns_empty_string_on_exception():
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError('GPU error')

    with patch('src.transcriber.whisper') as mock_whisper:
        mock_whisper.load_model.return_value = mock_model
        result = transcriber_module.transcribe(np.zeros(16000, dtype=np.float32))

    assert result == ''


def test_model_is_loaded_once_and_cached():
    mock_model = _make_mock_model('hi')

    with patch('src.transcriber.whisper') as mock_whisper:
        mock_whisper.load_model.return_value = mock_model
        audio = np.zeros(16000, dtype=np.float32)
        transcriber_module.transcribe(audio)
        transcriber_module.transcribe(audio)

    mock_whisper.load_model.assert_called_once()
