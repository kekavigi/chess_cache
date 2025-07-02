import logging
import time
from json import dumps as json_dump
from typing import Any, no_type_check


class JSONFormatter(logging.Formatter):
    "A formatter for the standard logging module that converts a LogRecord into JSON"

    # https://gist.github.com/kdgregory/82cc3942311c1983a9e141a8ced1f5fd

    def __init__(self, **tags: Any):
        self.tags = tags

    @no_type_check
    def format(self, record: logging.LogRecord):
        result = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + (".%03dZ" % (1000 * (record.created % 1))),
            "logger": record.name,
            "level": record.levelname,
            "message": record.msg % record.args,
            "processId": record.process,
            "thread": record.threadName,
            "location": f"{record.filename}:{record.lineno}",
        }

        if "extra" in record.__dict__:
            result["extra"] = record.__dict__["extra"]

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


class CustomLogger(logging.Logger):
    def makeRecord(
        self,
        name,
        level,
        fn,
        lno,
        msg,
        args,
        exc_info,
        func=None,
        extra=None,
        sinfo=None,
    ):
        rv = logging.LogRecord(name, level, fn, lno, msg, args, exc_info, func, sinfo)
        if extra is not None:
            for key in extra:
                if (key in ["message", "asctime"]) or (key in rv.__dict__):
                    raise KeyError("Attempt to overwrite %r in LogRecord" % key)
            rv.__dict__["extra"] = extra
        return rv


logging.setLoggerClass(CustomLogger)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    sh = logging.StreamHandler()
    sh.setFormatter(JSONFormatter())
    logger.addHandler(sh)

    return logger
