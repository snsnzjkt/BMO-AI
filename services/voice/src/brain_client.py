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
