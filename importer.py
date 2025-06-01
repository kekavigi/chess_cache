import argparse
import fileinput
import os
import sqlite3
from functools import partial
from io import StringIO
from time import sleep
from typing import Any

from chess import Board, Move
from chess.pgn import read_game

from chess_cache import AnalysisEngine

MAX_FULLMOVE = 6
MINIMAL_DEPTH = 24


class Todo:
    def __init__(self, database: str = "eco.sqlite") -> None:

        def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d

        self.db = sqlite3.connect(
            database, check_same_thread=False, isolation_level=None
        )
        self.db.row_factory = dict_factory
        script = """
                PRAGMA journal_mode = wal;
                PRAGMA synchronous = normal;
                PRAGMA temp_store = memory;
                PRAGMA mmap_size = 30000000000;
                PRAGMA busy_timeout = 10000;

                PRAGMA wal_autocheckpoint;

                CREATE TABLE IF NOT EXISTS todo(
                    fen TEXT NOT NULL,
                    PRIMARY KEY (fen)
                    ) WITHOUT ROWID;
                """
        with self.db as conn:
            for stt in script.split(";"):
                conn.execute(stt)

        self._board = Board()

    def close(self) -> None:
        self.db.close()

    def push(self, move_stack: list[Move]):
        stt = "INSERT OR IGNORE INTO todo (fen) VALUES (?)"

        with self.db as conn:
            for move in move_stack:
                self._board.push(move)
                conn.execute(stt, (self._board.fen(),))
        self._board.reset()

    def pop(self) -> str | None:
        # TODO: ini menyedihkan karena kita tidak dapat mengoptimalkan
        # hash table (posisi yang diambil acak).
        result = self.db.execute(
            "SELECT fen FROM todo ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
        if not result:
            return None
        fen = result["fen"]
        with self.db as conn:
            conn.execute("DELETE FROM todo WHERE fen=?", (fen,))
        return fen


def stdin_to_todo(db: Todo):
    nl_count, text = 0, ""

    # https://gist.github.com/martinth/ed991fb8cdcac3dfadf7
    for line in fileinput.input(files=("-",)):
        if nl_count == 2:
            game = read_game(StringIO(text))
            eco = game.headers.get("ECO")
            # jika ada header eco, maka variant adalah standard
            # walau kita ngambil dari "standard rated games,"
            # saya ragu dengan PGN tanpa nilai ECO: apakah memang
            # standar? TODO: pastikan, agar kode berikut bisa
            # lebih singkat
            if eco and eco != "?":
                move_stack = list(game.mainline_moves())
                db.push(move_stack[: 2 * MAX_FULLMOVE])
            # reset
            nl_count, text = 0, ""
        else:
            text += line
            if line == "\n":
                nl_count += 1


def process_todo(db: Todo, engine: AnalysisEngine):
    board = Board()
    while True:
        fen = db.pop()
        if fen is None:
            break

        board.set_fen(fen)
        info = engine.info(board)
        if info and info[0]["depth"] >= MINIMAL_DEPTH:
            continue

        engine.start(board, depth=MINIMAL_DEPTH)
        sleep(1)
        while not engine._stop:
            sleep(1)
        os.system("clear")
        print(fen)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Importer",
        description="Mengumpulkan posisi catur yang perlu dianalisa",
    )
    parser.add_argument(
        "-a",
        "--add-first",
        action="store_true",
        help="Tambah posisi dari dump Lichess untuk dianalisa",
    )
    args = parser.parse_args()

    db = Todo()
    try:
        print('starting engine...')
        engine = AnalysisEngine(
            engine_path="engine/stockfish",
            database_path="data.sqlite",
            configs={
                "EvalFile": "engine/nn-1c0000000000.nnue",
                "Threads": 4,
                "Hash": 2048,
            },
        )

        if args.add_first:
            print("collecting...")
            stdin_to_todo(db)

        print("analyzing...")
        process_todo(db, engine)

    except KeyboardInterrupt:
        print("\ninterrupted!")

    finally:
        result = db.db.execute("SELECT COUNT(fen) AS total FROM todo").fetchone()
        print(result["total"])

        print("shutting down")
        engine.shutdown()
        db.close()
