import json
import httpx
import config


class BrainServiceError(Exception):
    pass


def chat(text: str) -> str:
    try:
        response = httpx.post(
            f'{config.BRAIN_URL}/chat',
            json={'text': text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()['text']
    except httpx.HTTPStatusError as e:
        raise BrainServiceError(
            f'Brain service returned {e.response.status_code}'
        ) from e
    except httpx.RequestError as e:
        raise BrainServiceError(f'Brain service unreachable: {e}') from e


def stream_chat(text: str):
    try:
        with httpx.stream(
            'POST',
            f'{config.BRAIN_URL}/chat/stream',
            json={'text': text},
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get('done'):
                    return
                if 'sentence' in data:
                    yield data['sentence']
    except httpx.HTTPStatusError as e:
        raise BrainServiceError(
            f'Brain service returned {e.response.status_code}'
        ) from e
    except httpx.RequestError as e:
        raise BrainServiceError(f'Brain service unreachable: {e}') from e
