import sys
from contextlib import contextmanager
from datetime import datetime
from typing import no_type_check

from orjson import dumps

now = datetime.now


@no_type_check
@contextmanager
def log_traceback():
    # di lingkungan async; ngga bisa traceback sampai root

    # started = now()
    try:
        yield

    except Exception:
        # ended = now()

        # Tangkap exception dan traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()

        # start logging
        data = {
            # "started": started,
            # "elapsed": (ended - started).total_seconds(),
            "exception": exc_type.__name__,
            "message": exc_value.args[0] if exc_value.args else None,
            "tb": [],
        }
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

        with open(f"./logs/{now().isoformat()}.json", "wb") as f:
            f.write(dumps(data, default=repr))

        # re-raise
        raise
