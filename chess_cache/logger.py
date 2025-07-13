import logging
from time import strftime, gmtime
from json import dumps as json_dump
from typing import Any


class JSONFormatter(logging.Formatter):
    "A formatter for the standard logging module that converts a LogRecord into JSON"

    # https://gist.github.com/kdgregory/82cc3942311c1983a9e141a8ced1f5fd

    def __init__(self, **tags: Any):
        self.tags = tags

    def format(self, record: logging.LogRecord) -> str:
        result = {
            "ts": strftime("%Y-%m-%dT%H:%M:%S", gmtime(record.created))
            + f".{1000*(record.created % 1):.0f}Z",
            "logger": record.name,
            "level": record.levelname,
            "msg": record.msg % record.args,
        }

        if record.levelno >= logging.INFO:
            result.update({
                "pid": record.process,
                "thread": record.threadName,
                "loc": f"{record.filename}:{record.lineno}",
            })

        if "extra" in record.__dict__:
            result["extra"] = record.__dict__["extra"]

        if self.tags:
            result["tags"] = self.tags
        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            assert exc_type
            assert exc_traceback

            _result_tb = []
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
                _result_tb.append(info)
                tb = tb.tb_next

            result["exception"] = exc_type.__name__
            result["tb"] = _result_tb

        return json_dump(result, default=self._jsonify)

    def _jsonify(self, obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        else:
            return repr(obj)


class CustomLogger(logging.Logger):
    def makeRecord(
        self,
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: Any,
        args: Any,  # ugh
        exc_info: Any,  # ugh
        func: str | None = None,
        extra: Any = None,
        sinfo: str | None = None,
    ) -> logging.LogRecord:
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
