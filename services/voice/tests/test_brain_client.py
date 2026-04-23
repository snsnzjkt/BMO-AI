import pytest
from unittest.mock import patch, MagicMock
import httpx
import config
from src.brain_client import chat, BrainServiceError


@pytest.fixture(autouse=True)
def set_brain_url(monkeypatch):
    monkeypatch.setattr(config, 'BRAIN_URL', 'http://localhost:3001')


def test_chat_returns_text_on_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {'text': 'Hello from Beemo!'}
    mock_response.raise_for_status.return_value = None

    with patch('src.brain_client.httpx.post', return_value=mock_response) as mock_post:
        result = chat('Hello!')

    assert result == 'Hello from Beemo!'
    mock_post.assert_called_once_with(
        'http://localhost:3001/chat',
        json={'text': 'Hello!'},
        timeout=30.0,
    )


def test_chat_raises_brain_service_error_on_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503

    with patch('src.brain_client.httpx.post') as mock_post:
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            '503 error', request=MagicMock(), response=mock_response
        )
        with pytest.raises(BrainServiceError, match='503'):
            chat('Hello!')


def test_chat_raises_brain_service_error_on_connection_failure():
    with patch('src.brain_client.httpx.post', side_effect=httpx.ConnectError('Connection refused')):
        with pytest.raises(BrainServiceError, match='unreachable'):
            chat('Hello!')
