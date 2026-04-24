import httpx
import config


def set_state(key: str) -> None:
    try:
        httpx.post(
            f'{config.BRAIN_URL}/state',
            json={'state': key},
            timeout=2.0,
        )
    except Exception:
        pass
