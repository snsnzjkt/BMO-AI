import pytest
from unittest.mock import patch, MagicMock
import subprocess
import config
from src.synthesizer import synthesize, SynthesisError


@pytest.fixture(autouse=True)
def set_piper_config(monkeypatch):
    monkeypatch.setattr(config, 'PIPER_BINARY', 'piper')
    monkeypatch.setattr(config, 'PIPER_MODEL_PATH', '/fake/model.onnx')


def test_synthesize_returns_wav_bytes():
    fake_wav = b'RIFF\x24\x00\x00\x00WAVEfmt '
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = fake_wav

    with patch('src.synthesizer.subprocess.run', return_value=mock_result) as mock_run:
        result = synthesize('Hello BMO!')

    assert result == fake_wav
    mock_run.assert_called_once_with(
        ['piper', '--model', '/fake/model.onnx'],
        input=b'Hello BMO!',
        capture_output=True,
    )


def test_synthesize_raises_on_nonzero_exit():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = b'model not found'

    with patch('src.synthesizer.subprocess.run', return_value=mock_result):
        with pytest.raises(SynthesisError, match='Piper exited with code 1'):
            synthesize('Hello!')


def test_synthesize_raises_when_piper_binary_missing():
    with patch('src.synthesizer.subprocess.run', side_effect=FileNotFoundError):
        with pytest.raises(SynthesisError, match='Piper binary not found'):
            synthesize('Hello!')
