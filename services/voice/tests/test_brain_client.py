import pytest
from unittest.mock import patch, MagicMock
import httpx


@pytest.fixture(autouse=True)
def set_brain_url(monkeypatch):
    monkeypatch.setenv('BRAIN_URL', 'http://localhost:3001')


def test_chat_returns_text_on_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {'text': 'Hello from BMO!'}
    mock_response.raise_for_status.return_value = None

    with patch('httpx.post', return_value=mock_response) as mock_post:
        from src.brain_client import chat
        result = chat('Hello!')

    assert result == 'Hello from BMO!'
    mock_post.assert_called_once_with(
        'http://localhost:3001/chat',
        json={'text': 'Hello!'},
        timeout=30.0,
    )


def test_chat_raises_brain_service_error_on_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503

    with patch('httpx.post') as mock_post:
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            '503 error', request=MagicMock(), response=mock_response
        )
        from src.brain_client import chat, BrainServiceError
        with pytest.raises(BrainServiceError, match='503'):
            chat('Hello!')


def test_chat_raises_brain_service_error_on_connection_failure():
    with patch('httpx.post', side_effect=httpx.ConnectError('Connection refused')):
        from src.brain_client import chat, BrainServiceError
        with pytest.raises(BrainServiceError, match='unreachable'):
            chat('Hello!')
