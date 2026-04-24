import pytest
from unittest.mock import patch, MagicMock
import httpx
import config
from src.state_client import set_state


@pytest.fixture(autouse=True)
def set_brain_url(monkeypatch):
    monkeypatch.setattr(config, 'BRAIN_URL', 'http://localhost:3001')


def test_set_state_posts_correct_payload():
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch('src.state_client.httpx.post', return_value=mock_response) as mock_post:
        set_state('thinking')

    mock_post.assert_called_once_with(
        'http://localhost:3001/state',
        json={'state': 'thinking'},
        timeout=2.0,
    )


def test_set_state_silently_ignores_connect_error():
    with patch('src.state_client.httpx.post', side_effect=httpx.ConnectError('refused')):
        set_state('thinking')  # must not raise


def test_set_state_silently_ignores_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503
    with patch('src.state_client.httpx.post', side_effect=httpx.HTTPStatusError(
        '503', request=MagicMock(), response=mock_response
    )):
        set_state('thinking')  # must not raise


def test_set_state_silently_ignores_any_exception():
    with patch('src.state_client.httpx.post', side_effect=Exception('unexpected')):
        set_state('thinking')  # must not raise
