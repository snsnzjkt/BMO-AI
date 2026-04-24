import json
import pytest
from unittest.mock import patch, MagicMock
import httpx
import config
from src.brain_client import chat, BrainServiceError, stream_chat


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


def _make_stream_mock(lines, status_code=200):
    """Returns a context manager mock whose iter_lines() yields the given strings."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.raise_for_status.return_value = None
    mock_response.iter_lines.return_value = iter(lines)
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response
    mock_cm.__exit__.return_value = False
    return mock_cm


def test_stream_chat_yields_sentences():
    lines = [
        json.dumps({'sentence': 'Hello world!'}),
        json.dumps({'sentence': 'How are you?'}),
        json.dumps({'done': True}),
    ]
    with patch('src.brain_client.httpx.stream', return_value=_make_stream_mock(lines)) as mock_stream:
        sentences = list(stream_chat('Hello!'))

    assert sentences == ['Hello world!', 'How are you?']
    mock_stream.assert_called_once_with(
        'POST',
        'http://localhost:3001/chat/stream',
        json={'text': 'Hello!'},
        timeout=60.0,
    )


def test_stream_chat_stops_at_done():
    lines = [
        json.dumps({'sentence': 'Hi!'}),
        json.dumps({'done': True}),
        json.dumps({'sentence': 'Should not appear'}),
    ]
    with patch('src.brain_client.httpx.stream', return_value=_make_stream_mock(lines)):
        sentences = list(stream_chat('Hello!'))

    assert sentences == ['Hi!']


def test_stream_chat_raises_brain_service_error_on_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        '503', request=MagicMock(), response=mock_response
    )
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_response
    mock_cm.__exit__.return_value = False

    with patch('src.brain_client.httpx.stream', return_value=mock_cm):
        with pytest.raises(BrainServiceError, match='503'):
            list(stream_chat('Hello!'))


def test_stream_chat_raises_brain_service_error_on_connection_failure():
    with patch('src.brain_client.httpx.stream', side_effect=httpx.ConnectError('refused')):
        with pytest.raises(BrainServiceError, match='unreachable'):
            list(stream_chat('Hello!'))


def test_stream_chat_skips_empty_lines():
    lines = [
        '',
        json.dumps({'sentence': 'Hello!'}),
        '',
        json.dumps({'done': True}),
    ]
    with patch('src.brain_client.httpx.stream', return_value=_make_stream_mock(lines)):
        sentences = list(stream_chat('Hello!'))

    assert sentences == ['Hello!']
