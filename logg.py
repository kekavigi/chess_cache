import sys
from contextlib import contextmanager
from datetime import datetime
from json import dump as json_dump
from os import makedirs
from typing import Any, Iterator, Never

LOG_DIRECTORY = "./logs"
now = datetime.now

makedirs(LOG_DIRECTORY, exist_ok=True)


# TODO: turn off logging when testing


def representation(obj: Any) -> dict[str, Any] | str:
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    else:
        return repr(obj)


@contextmanager
def log_traceback(extra: Any = None) -> Iterator[Any]:
    # di lingkungan async; ngga bisa traceback sampai root

    # started = now()
    try:
        yield

    except Exception:
        # ended = now()

        # Tangkap exception dan traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        assert exc_type
        assert exc_value
        assert exc_traceback

        # start logging
        data: dict[str, Any] = {
            # "started": started,
            # "elapsed": (ended - started).total_seconds(),
            "exception": exc_type.__name__,
            "message": exc_value.args[0] if exc_value.args else None,
            "tb": [],
        }
        if extra is not None:
            data["extra"] = extra

        tb = exc_traceback.tb_next
        while tb:
            frame = tb.tb_frame
            local_vars = frame.f_locals
            info = {
                "function": frame.f_code.co_name,
                "line": tb.tb_lineno,
                "vars": {
                    f"{var_name}": value for var_name, value in local_vars.items()
                },
            }
            data["tb"].append(info)
            tb = tb.tb_next

        with open(f"{LOG_DIRECTORY}/{now().isoformat()}.json", "w") as f:
            json_dump(data, f, default=representation)

        # re-raise
        raise
