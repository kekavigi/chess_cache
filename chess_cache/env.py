import ast
import os
from configparser import UNNAMED_SECTION, ConfigParser
from typing import Any


class Env:
    def __init__(self, filename: str = ".env") -> None:
        cp = ConfigParser(allow_unnamed_section=True)
        cp.read(filename)
        self.cp = cp[UNNAMED_SECTION]

    def get(self, varname: str, default: Any = None) -> Any:
        val = os.environ.get(varname)
        if val is None:
            val = self.cp.get(varname)
        if val is None:
            return default

        # '123456' -> 123456
        # '"{'key':'value}"' -> "{'key':'value'}"
        if isinstance(val, str):
            try:
                val = ast.literal_eval(val)
            except (SyntaxError, ValueError):
                pass

        # "{'key':'value}" -> {'key':'value'}
        if isinstance(val, str):
            try:
                val = ast.literal_eval(val)
            except (SyntaxError, ValueError):
                pass

        return val
