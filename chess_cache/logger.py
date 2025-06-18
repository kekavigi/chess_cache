import logging
import time
from json import dumps as json_dump
from typing import Any, no_type_check

# TODO: turn off logging when testing


class JSONFormatter(logging.Formatter):
    "A formatter for the standard logging module that converts a LogRecord into JSON"

    # https://gist.github.com/kdgregory/82cc3942311c1983a9e141a8ced1f5fd

    def __init__(self, **tags: Any):
        self.tags = tags

    @no_type_check
    def format(self, record: logging.LogRecord):
        result = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + (".%03dZ" % (1000 * (record.created % 1))),
            "level": record.levelname,
            "logger": record.name,
            "message": record.msg % record.args,
            "processId": record.process,
            "thread": record.threadName,
            "locationInfo": {"fileName": record.filename, "lineNumber": record.lineno},
            "extra": record.__dict__.get("extra", None),
        }

        if self.tags:
            result["tags"] = self.tags
        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            result["exception"] = exc_type.__name__

            result["tb"] = []
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
                result["tb"].append(info)
                tb = tb.tb_next

        return json_dump(result, default=self._jsonify)

    def _jsonify(self, obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        else:
            return repr(obj)
