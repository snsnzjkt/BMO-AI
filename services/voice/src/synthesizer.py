import subprocess
import config


class SynthesisError(Exception):
    pass


def synthesize(text: str) -> bytes:
    try:
        result = subprocess.run(
            [config.PIPER_BINARY, '--model', config.PIPER_MODEL_PATH],
            input=text.encode('utf-8'),
            capture_output=True,
        )
        if result.returncode != 0:
            raise SynthesisError(
                f'Piper exited with code {result.returncode}: {result.stderr.decode("utf-8", errors="replace")}'
            )
        return result.stdout
    except FileNotFoundError:
        raise SynthesisError(f'Piper binary not found: {config.PIPER_BINARY}')
