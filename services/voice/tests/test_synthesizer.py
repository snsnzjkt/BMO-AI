import io
import wave
import pytest
from unittest.mock import patch, MagicMock
import config
import src.synthesizer as synthesizer_module
from src.synthesizer import synthesize, SynthesisError


@pytest.fixture(autouse=True)
def reset_voice_cache():
    synthesizer_module._voice = None
    yield
    synthesizer_module._voice = None


@pytest.fixture(autouse=True)
def set_piper_config(monkeypatch):
    monkeypatch.setattr(config, 'PIPER_MODEL_PATH', '/fake/model.onnx')


def _make_fake_voice(sample_rate=22050):
    """Returns a mock PiperVoice whose synthesize_wav writes a minimal valid WAV."""
    def fake_synthesize_wav(text, wav_file, **kwargs):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b'\x00' * 200)

    mock_voice = MagicMock()
    mock_voice.synthesize_wav.side_effect = fake_synthesize_wav
    return mock_voice


def test_synthesize_returns_wav_bytes():
    mock_voice = _make_fake_voice()

    with patch('src.synthesizer.PiperVoice') as mock_pv:
        mock_pv.load.return_value = mock_voice
        result = synthesize('Hello Beemo!')

    assert isinstance(result, bytes)
    assert len(result) > 44  # more than just a WAV header
    mock_pv.load.assert_called_once_with('/fake/model.onnx')
    mock_voice.synthesize_wav.assert_called_once()


def test_synthesize_raises_on_voice_error():
    mock_voice = MagicMock()
    mock_voice.synthesize_wav.side_effect = RuntimeError('synthesis failed')

    with patch('src.synthesizer.PiperVoice') as mock_pv:
        mock_pv.load.return_value = mock_voice
        with pytest.raises(SynthesisError, match='synthesis failed'):
            synthesize('Hello!')


def test_synthesize_raises_when_model_load_fails():
    with patch('src.synthesizer.PiperVoice') as mock_pv:
        mock_pv.load.side_effect = RuntimeError('model not found')
        with pytest.raises(SynthesisError, match='model not found'):
            synthesize('Hello!')


def test_voice_is_loaded_once_and_cached():
    mock_voice = _make_fake_voice()

    with patch('src.synthesizer.PiperVoice') as mock_pv:
        mock_pv.load.return_value = mock_voice
        synthesize('First call')
        synthesize('Second call')

    mock_pv.load.assert_called_once()
