import tomllib
from typing import Any


def load_config(filename) -> dict[str, Any]:
    try:
        with open(filename, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError:
        # TODO: what to do?
        raise
    else:
        return data
