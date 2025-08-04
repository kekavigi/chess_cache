import ast
import os
from typing import Any

from backports.configparser import UNNAMED_SECTION, ConfigParser

from .logger import get_logger

logger = get_logger("env")


class Env:
    def __init__(self, filename: str = ".env") -> None:
        cp = ConfigParser(allow_unnamed_section=True)
        cp.read(filename)
        self.cp = cp[UNNAMED_SECTION]

    def get(self, varname: str, default: Any = None) -> Any:
        if varname in os.environ:
            logger.debug(f"Menggunakan '{varname}' dari os.environ")
            val = os.environ[varname]
        elif varname in self.cp:
            logger.debug(f"Menggunakan '{varname}' dari berkas enviroment")
            val = self.cp[varname]
        else:
            logger.debug(f"Menggunakan nilai default dari '{varname}'")
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


env = Env(".env")

DATABASE_URI = env.get("DATABASE_URI", "temporary.sqlite")

ENGINE_PATH = env.get("ENGINE_PATH", "stockfish")
ENGINE_BASE_CONFIG = env.get("ENGINE_BASE_CONFIG", {})
ENGINE_MAIN_CONFIG = env.get("ENGINE_MAIN_CONFIG", {})
ENGINE_IMPORT_CONFIG = env.get("ENGINE_IMPORT_CONFIG", ENGINE_MAIN_CONFIG)

ANALYSIS_DEPTH = env.get("MAXIMAL_DEPTH", 35)
MINIMAL_DEPTH = env.get("MINIMAL_DEPTH", 20)
IMPORTER_PGN_DEPTH = env.get("IMPORTER_PGN_DEPTH", 50)
