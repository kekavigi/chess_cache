import argparse
import fileinput
import re
import sqlite3
from time import sleep
from typing import Any

from chess import Board
from tqdm import tqdm

from chess_cache import AnalysisEngine

MAX_FULLMOVE = 4
MINIMAL_DEPTH = 24

# Hapus semua komentar, gerakan non-mainline, angka, dan notasi
RE_PGN_NON_MOVE = re.compile(r"\{.*?\}|\(.*?\)|\d+\.+|\+|\!|\?")


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
                    fmn INTEGER NOT NULL, -- fullmove number
                    PRIMARY KEY (fen, fmn)
                    ) WITHOUT ROWID;
                """
        with self.db as conn:
            for stt in script.split(";"):
                conn.execute(stt)

        self._board = Board()

    def close(self) -> None:
        self.db.close()

    def insert(self, move_stack: list[str]):
        stt = "INSERT OR IGNORE INTO todo (fen, fmn) VALUES (?, ?)"

        try:
            with self.db as conn:
                for move in move_stack:
                    self._board.push_san(move)
                    conn.execute(stt, (self._board.fen(), self._board.fullmove_number))
        except:
            print(move_stack)
            raise
        self._board.reset()

    def random(self, limit: int = 1) -> list[str]:
        # TODO: ini menyedihkan karena kita tidak dapat mengoptimalkan
        # hash table (posisi yang diambil acak).
        assert isinstance(limit, int)
        results = self.db.execute(
            f"SELECT fen FROM todo ORDER BY fmn ASC, RANDOM() LIMIT {limit}"
        ).fetchall()
        return [_["fen"] for _ in results]

    def delete(self, fen: str):
        with self.db as conn:
            conn.execute("DELETE FROM todo WHERE fen=?", (fen,))

    def pop(self, board: Board | None = None) -> str | None:
        results = self.random()
        if not results:
            return None
        fen = results[0]
        self.delete(fen)
        return fen


def stdin_to_todo(db: Todo):
    # https://gist.github.com/martinth/ed991fb8cdcac3dfadf7
    for line in tqdm(fileinput.input(files=("-",)), ncols=0):

        # pastikan permainan dimulai dari awal
        if line[:3] == "1. ":
            # tidak menggunakan chess.pgn.read_game, karena kita cuma butuh
            # mainline move. Cara 'manual' ini mempercepat dari 7k iter/s
            # menjadi 21.5k iter/s.
            moves = RE_PGN_NON_MOVE.sub("", line).split()
            moves = moves[: min(len(moves) - 1, 2 * MAX_FULLMOVE)]
            db.insert(moves)


def process_todo(db: Todo, engine: AnalysisEngine):
    while True:
        fen = db.pop()
        if fen is None:
            break

        info = engine.info(fen)
        if info and info[0]["depth"] >= MINIMAL_DEPTH:
            continue

        engine.start(fen, depth=MINIMAL_DEPTH)
        sleep(1)
        while not engine._stop:
            sleep(0.5)
        # os.system("clear")
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
    engine = None
    try:
        if args.add_first:
            print("collecting...")
            stdin_to_todo(db)

        print("starting engine...")
        engine = AnalysisEngine(
            engine_path="engine/stockfish",
            database_path="data.sqlite",
            configs={
                "EvalFile": "engine/nn-1c0000000000.nnue",
                "Threads": 4,
                # "Hash": 1024,
            },
        )

        print("analyzing...")
        process_todo(db, engine)

    except KeyboardInterrupt:
        print("\ninterrupted!")

    finally:
        print("shutting down")
        db.db.execute("VACUUM")
        db.close()
        if engine:
            # just-in-case Ctrl+C saat collecting
            engine.shutdown()
