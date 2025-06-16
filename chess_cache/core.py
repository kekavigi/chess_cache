"""
Menggabungkan kemampuan mesin catur dengan database hasil analisa posisi.
"""

# MIT License Copyright (c) 2025 Agapitus Keyka Vigiliant
# MIT License Copyright (c) 2020 Tomasz Sobczyk
# GNU GPLv3 (C) 2012-2021 Niklas Fiekas <niklas.fiekas@backscattering.de>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# Spesifikasi protokol UCI: https://wbec-ridderkerk.nl/html/UCIProtocol.html

import logging
import sqlite3
from base64 import b85decode, b85encode
from functools import lru_cache
from itertools import product
from re import compile as regex_compile
from subprocess import PIPE, Popen
from threading import Thread
from time import sleep
from typing import Any

from chess import Board, IllegalMoveError

from .logger import JSONFormatter

# TODO: tidak usah gunakan module chess, kita kurang lebih hanya butuh atribut
# berikut: fen, set_fen, push_uci, dan copy. Ide, buat representasi papan
# dalam bentuk bitboard. Empat atribut tersebut seharusnya mudah dibuat, dan
# itu juga akan meringkas kode di encode_fen()

# TODO: ketika Ctrl+C di AnalysisEngine, akan muncul "Exception ignored in" yang
# saya tidak tahu cara mengatasinya. Kode berikut akan mensuppress pesan tersebut
# https://stackoverflow.com/questions/16314321/suppressing-printout-of-exception-ignored-message-in-python-3
# https://stackoverflow.com/questions/24169893/how-to-prevent-exception-ignored-in-module-threading-from-while-settin
# import sys
# sys.unraisablehook = lambda unraisable: None

_handle_db = logging.FileHandler("logs/database.jsonl")
_handle_db.setFormatter(JSONFormatter())
logger_db = logging.Logger("database")
logger_db.addHandler(_handle_db)

_handle_engine = logging.FileHandler("logs/engine.jsonl")
_handle_engine.setFormatter(JSONFormatter())
logger_engine = logging.Logger("engine")
logger_engine.addHandler(_handle_engine)
logger_engine.setLevel(logging.WARNING)


Info = dict[str, Any]
Config = dict[str, str | int]

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MATE_SCORE = 2**12

UCI_REGEX = regex_compile(r"^[a-h][1-8][a-h][1-8][pnbrqk]?|[PNBRQK]@[a-h][1-8]|0000\Z")
CHESS_FILE = {c: [8 * r + f for r in range(8)] for f, c in enumerate("abcdefgh")}
PIECE_MAP_ENCODE = {
    "P": (1, True),
    "N": (2, True),
    "B": (3, True),
    "R": (4, True),
    "Q": (5, True),
    "K": (6, True),
    "p": (1, False),
    "n": (2, False),
    "b": (3, False),
    "r": (4, False),
    "q": (5, False),
    "k": (6, False),
}


def uci_int_mapping() -> tuple[dict[str, int], dict[int, str]]:
    possibles = (
        [(0, y) for y in range(-7, 8)]
        + [(x, 0) for x in range(-7, 8)]
        + [(d, d) for d in range(-7, 8)]
        + [(d, -d) for d in range(-7, 8)]
        + list(product(range(-2, 3), range(-2, 3)))
    )
    possibles = set(possibles) - {(0, 0)}  # type: ignore[assignment]

    file = " abcdefgh"
    total = []
    for x, y, (dx, dy) in product(range(1, 9), range(1, 9), possibles):
        i, j = x + dx, y + dy
        if (0 < i < 9) and (0 < j < 9):
            _uci = f"{file[x]}{y}{file[i]}{j}"
            total.append(_uci)
            if j == 1 or j == 8:
                for promotion in "rbnq":
                    total.append(_uci + promotion)
    total.sort()

    uci2num = {_uci: i for i, _uci in enumerate(total)}
    num2uci = {i: _uci for i, _uci in enumerate(total)}
    return uci2num, num2uci


UCI_TO_NUM, NUM_TO_UCI = uci_int_mapping()


@lru_cache(maxsize=4096)
def encode_fen(fen: str) -> bytes:
    # Didasarkan oleh kode oleh Tomasz Sobczyk
    # https://github.com/official-stockfiPiecesh/nnue-pytorch/blob/master/lib/nnue_training_data_formats.h#L4615

    # Proses ini sebenarnya reversible, tetapi untuk masalah ini proses decode
    # tidak dibutuhkan. Kode bisa diringkas dengan membuat fungsi sebagai
    # atribut dari Board, dan daripada menggunakan self.fen().split(), ambil
    # informasi dari self.castling_xfen(), self.ep_square(), self.piece_type_at()
    # dan sebagainya. Cuma masalahnya, cukup fucked up untuk me-LRUCache-nya.

    splitted = fen.split()

    # ubah fen ke piece map; "sepadan" dengan chess.Board().piece_map()
    _i = 63
    piece_map = {}
    for _ in "/".join(_[::-1] for _ in splitted[0].split("/")):
        if _ == "/":
            continue
        elif _ in "12345678":
            _i -= int(_)
        else:
            piece_map[_i] = PIECE_MAP_ENCODE[_]
            _i -= 1

    turn_is_black = splitted[1] == "b"
    castling_right = splitted[2]
    _ep = splitted[3]
    ep_file = CHESS_FILE[_ep[0]] if _ep != "-" else []

    # enkode semua piece di papan
    nibble, occupancy, bitcount = 0, 0, 64
    for square in range(64):
        if square not in piece_map:
            occupancy = occupancy << 1 | 0
            continue

        occupancy = occupancy << 1 | 1
        bitcount += 4
        ptype, pcolor = piece_map[square]
        ptype = 2 * ptype - 1

        if ptype == 1:
            if _ep and square in ep_file:
                nibble = nibble << 4 | 12
            else:
                nibble = nibble << 4 | ptype - pcolor
        elif ptype == 7:
            if square == 0 and "Q" in castling_right:
                nibble = nibble << 4 | 13
            elif square == 7 and "K" in castling_right:
                nibble = nibble << 4 | 13
            elif square == 56 and "q" in castling_right:
                nibble = nibble << 4 | 14
            elif square == 63 and "k" in castling_right:
                nibble = nibble << 4 | 14
            else:
                nibble = nibble << 4 | ptype - pcolor
        elif ptype == 11:
            if turn_is_black and not pcolor:
                nibble = nibble << 4 | 15
            else:
                nibble = nibble << 4 | ptype - pcolor
        else:
            nibble = nibble << 4 | ptype - pcolor

    num = nibble << 64 | occupancy
    # ubah ke BLOB, num terlalu besar untuk SQLite
    bitcount = (bitcount + 7) // 8  # == ceil(log2(num))
    return num.to_bytes(bitcount)


def _parse_uci_info(text_info: str) -> Info:
    # modifikasi dari kode chess.engine._parse_uci_info
    # oleh Niklas Fiekas <niklas.fiekas@backscattering.de>

    info: Info = {}
    tokens = text_info.split(" ")
    try:
        while tokens:
            parameter = tokens.pop(0)

            if parameter == "string":
                info["string"] = " ".join(tokens)
                break
            elif parameter in [
                "depth",
                "seldepth",
                "nodes",
                "multipv",
                "currmovenumber",
                "hashfull",
                "nps",
                "tbhits",
                "cpuload",
            ]:
                info[parameter] = int(tokens.pop(0))
            elif parameter == "time":
                info["time"] = int(tokens.pop(0))
            elif parameter == "ebf":
                info["ebf"] = float(tokens.pop(0))
            elif parameter == "score":
                kind = tokens.pop(0)
                value = int(tokens.pop(0))
                if tokens and tokens[0] in ["lowerbound", "upperbound"]:
                    info[tokens.pop(0)] = True
                if kind == "cp":
                    info["score"] = value
                elif kind == "mate":
                    if value > 0:
                        info["score"] = MATE_SCORE - value
                    else:
                        info["score"] = -MATE_SCORE - value
                else:
                    raise Exception("Unknown score kind")
            elif parameter == "currmove":
                info["currmove"] = tokens.pop(0)
            elif parameter == "currline":
                if "currline" not in info:
                    info["currline"] = {}

                cpunr = int(tokens.pop(0))
                currline: list[str] = []
                info["currline"][cpunr] = currline

                while tokens and UCI_REGEX.match(tokens[0]):
                    currline.append(tokens.pop(0))
            elif parameter == "refutation":
                if "refutation" not in info:
                    info["refutation"] = {}

                refuted = tokens.pop(0)
                refuted_by: list[str] = []
                info["refutation"][refuted] = refuted_by

                while tokens and UCI_REGEX.match(tokens[0]):
                    refuted_by.append(tokens.pop(0))
            elif parameter == "pv":
                pv: list[str] = []
                info["pv"] = pv
                while tokens and UCI_REGEX.match(tokens[0]):
                    pv.append(tokens.pop(0))
            elif parameter == "wdl":
                info["wdl"] = (
                    int(tokens.pop(0)),
                    int(tokens.pop(0)),
                    int(tokens.pop(0)),
                )
    except (ValueError, IndexError):
        raise ValueError("Exception when parsing info")
    return info


def _unparse_uci_info(info: Info) -> str:
    text = ["info"]
    for k, v in info.items():
        text.append(k)
        if k == "pv":
            text.extend(info["pv"])
        elif k == "score":
            if v > MATE_SCORE - 100:
                text.append(f"mate {MATE_SCORE - v}")
            elif v < 100 - MATE_SCORE:
                text.append(f"mate {-MATE_SCORE - v}")
            else:
                text.append(f"cp {v}")
        else:
            text.append(str(v))
    return " ".join(text)


class Database:
    """Database singgahan hasil analisis mesin catur.

    Attributes:
        db: koneksi ke database SQLite
    """

    def __init__(self, uri: str = ":memory:") -> None:
        """Membuat koneksi ke database dengan URI `database`.

        Membuat instance `sqlite3.Connection`, yang dapat diakses oleh
        sembarang thread, dan tanpa BEGIN implisit. Akses langsung ke atribut
        `db` untuk tujuan _write_ disarankan menggunakan _with statement_.

        Karena posisi catur yang disinggah banyak, database dibuat
        sekecil mungkin dan hanya menyinggah informasi "fen", "multipv",
        "depth", "score", dan "move". Tidak ada ROWID. PRIMARY KEY adalah
        komposit nilai ("fen", "multipv"). Menggunakan mode jurnal WAL
        dengan AUTOCHECKPOINT.

        Kolom `fen` berisi posisi catur dalam notasi FEN yang terenkode.
        Kolom `move` berisi langkah bidak dalam notasi UCI yang terenkode.

        Args:
            uri: URI lokasi database.
        """

        def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d

        self.sql = sqlite3.connect(uri, check_same_thread=False, isolation_level=None)
        self.sql.row_factory = dict_factory
        script = """
                PRAGMA journal_mode = wal;
                PRAGMA synchronous = off;
                PRAGMA temp_store = memory;
                PRAGMA mmap_size = 30000000000;
                PRAGMA busy_timeout = 10000;

                PRAGMA wal_autocheckpoint;

                CREATE TABLE IF NOT EXISTS board(
                    fen         BLOB    NOT NULL,
                    multipv     INTEGER NOT NULL,
                    depth       INTEGER NOT NULL,
                    score       INTEGER NOT NULL,
                    move        INTEGER,
                    PRIMARY KEY (fen, multipv)
                    ) WITHOUT ROWID;
                """
        # PRAGMA cache_size = -4096000;

        # https://stackoverflow.com/questions/15856976/transactions-with-python-sqlite3
        # sederhananya, jangan pakai executescript()
        with self.sql as conn:
            for stt in script.split(";"):
                conn.execute(stt)

        cur = self.sql.execute(
            'SELECT file FROM pragma_database_list WHERE name="main"'
        )
        self._is_memory = not cur.fetchone()["file"]

    def close(self) -> None:
        "Menutup koneksi ke database."
        # self.sql.execute('VACUUM')
        self.sql.close()

    def select(
        self,
        fen: str,
        multipv: int = 1,
        with_move: bool = False,
    ) -> Info | None:
        """Mendapatkan info dari suatu posisi catur.

        Args:
            fen: Posisi catur dalam notasi FEN.
            multipv: Urutan principal move yang ingin dicari.
            with_move: Pilihan untuk menyertakan daftar bestmove.
        """

        stt = """
            SELECT multipv, depth, score, move
            FROM board WHERE fen=? AND multipv=?
        """
        efen = encode_fen(fen)
        info = self.sql.execute(stt, (efen, multipv)).fetchone()  # type: Info | None
        if not info:
            return None

        # dapatkan rangkaian balasan
        pv = NUM_TO_UCI.get(info.pop("move"))
        info["pv"] = [pv] if pv is not None else []
        if pv is not None and with_move:
            stt = "SELECT move FROM board WHERE fen=? AND multipv=1"
            board = Board(fen)
            depth = info["depth"] - 1

            try:
                while depth > 0:
                    # dapatkan next best move
                    board.push_uci(pv)  # type: ignore[arg-type]

                    efen = encode_fen(board.fen())
                    result = self.sql.execute(stt, (efen,)).fetchone()
                    if not result:
                        break
                    pv = NUM_TO_UCI.get(result["move"])
                    info["pv"].append(pv)
                    depth -= 1
            except:
                # TODO: database bermasalah, tapi dengan mengabaikannya
                # akan heal sendiri, kenapa? apakah iya memang heal?
                # race condition dengan upsert di UciEngine.parse_output?
                logger_db.warning("Something fishy happening", exc_info=True)
                pass

        return info

    def upsert(self, fen: str, info: Info) -> None:
        """Menyimpan atau memperbarui info dari suatu posisi catur.

        Lebih tepatnya, `UPSERT OR IGNORE INTO` dari semua move `pv` di info.
        Kondisi IGNORE terjadi ketika move yang sudah ada di database memiliki
        nilai `depth` yang lebih besar, atau ada child yang pernah dianalisis
        dan memiliki data yang lebih baik daripada hasil ekstrapolasi info.

        Args:
            fen: Posisi catur dalam notasi FEN.
            multipv: Urutan principal move yang ingin dicari.
            with_move: Pilihan untuk menyertakan daftar bestmove.
        """

        stt = """
            INSERT INTO board (fen, multipv, depth, score, move)
            VALUES (:fen, :multipv, :depth, :score, :move)
            ON CONFLICT (fen, multipv) DO UPDATE SET
                depth = excluded.depth,
                score = excluded.score,
                move  = excluded.move
        """
        board = Board(fen)
        info_ = info.copy()
        # info_ akan digunakan sebagai "taksiran" hasil analisis mesin catur
        # untuk semua move di info['pv'], dengan beberapa penyesuaian

        try:
            with self.sql as conn:
                for num, move in enumerate(info_["pv"]):

                    # loop sampai nol
                    if info_["depth"] == 0:
                        break

                    fen = board.fen()

                    # bandingkan dengan hasil singgahan
                    old_info = self.select(fen, info_["multipv"])
                    if old_info and old_info["depth"] > info_["depth"]:
                        # hentikan menyinggah karena posisi ini pernah dianalisis
                        # dan depthnya lebih besar daripada depth hasil taksiran
                        break
                    elif old_info and old_info["depth"] == info_["depth"] and num != 0:
                        # hentikan menyinggah karena posisi ini pernah dianalisis
                        # walau depthnya sama, posisi ini lebih baik karena yang
                        # kita miliki hanyalah taksiran/ekstrapolasi
                        break

                    # untuk iterasi pertama; induk
                    info_["fen"] = encode_fen(fen)
                    info_["move"] = UCI_TO_NUM[move]
                    conn.execute(stt, info_)

                    # untuk semua iterasi berikutnya; keturunannya
                    board.push_uci(move)
                    info_["multipv"] = 1  # walau multipv induk mungkin !=1
                    info_["score"] *= -1  # ubah sudut pandang score
                    info_["depth"] -= 1  # kurangi depth

        except (IllegalMoveError, KeyError):
            # aman untuk mengasumsikan daftar move di pv bukan
            # rangkaian gerakan catur standar. Jadi analisa ini
            # bukan posisi standar, sehingga tidak usah di upsert

            # TODO: buat custom error
            raise ValueError("Data tidak sahih atau bukan permainan catur standar")

        except:
            logger_db.exception("Something went wrong.", extra={"extra": info_})
            raise

        return

    def to_json(self) -> list[Info]:
        cur = self.sql.execute("SELECT * FROM board")
        results = []
        for row in cur.fetchall():
            row["fen"] = b85encode(row["fen"]).decode("utf-8")
            results.append(row)
        return results

    def from_json(self, json: list[Info]) -> None:
        stt = """
            INSERT INTO board (fen, multipv, depth, score, move)
            VALUES (:fen, :multipv, :depth, :score, :move)
            ON CONFLICT (fen, multipv) DO UPDATE SET
                depth = excluded.depth,
                score = excluded.score,
                move  = excluded.move
            WHERE excluded.depth >= depth
        """
        with self.sql as conn:
            for row_ in json:
                row = row_.copy()
                row["fen"] = b85decode(row["fen"])
                conn.execute(stt, row)

    def reset_db(self) -> None:
        if not self._is_memory:
            # too dangerous
            raise RuntimeError

        with self.sql as conn:
            conn.execute("DELETE FROM board")
            conn.execute("VACUUM")


class AnalysisEngine:
    """Mesin catur dengan database singgahan analisa posisi.

    Attributes:
        db: Instance dari `Database`.
    """

    def __init__(
        self,
        engine_path: str = "./stockfish",
        database_path: str = ":memory:",
        configs: Config = {},
    ):
        """Menginisialisasi mesin catur dan database.

        Args:
            engine_path: Alamat dari mesin catur.
            database_path: Alamat dari berkas database SQLite.
            configs: Dict berisi UCI setoptions untuk dikirim ke
                mesin catur.
        """

        # TODO: try except engine exist

        self.db = Database(database_path)
        self._engine = Popen(
            engine_path,
            stdin=PIPE,
            stdout=PIPE,
            universal_newlines=True,
            bufsize=1,
        )
        self._thread: Thread | None = None

        assert self._engine.stdin is not None
        assert self._engine.stdout is not None
        # def debug_write(text):
        #     print(text, end='')
        #     self._engine.stdin.write(text)
        # def debug_read():
        #     text = self._engine.stdout.readline()
        #     print(text, end='')
        #     return text
        # self._std_write = debug_write
        # self._std_read = debug_read
        self._std_write = self._engine.stdin.write
        self._std_read = self._engine.stdout.readline

        self._std_write("uci\n")
        self._set_options(configs)
        self._stop = False

    def _set_options(self, configs: Config) -> None:
        for name, value in configs.items():
            self._std_write(f"setoption name {name} value {value}\n")

    def stop(self, timeout: float = 1) -> None:
        """Menghentikan proses analisa oleh mesin catur.

        Disarankan untuk menetapkan `timeout` bernilai positif
        karena dapat terjadi race-condition: mesin masih menghasilkan analisa
        posisi lawas, sedangkan class mengharapkan analisa posisi baru.

        Args:
            timeout: lama waktu maksimum untuk menunggu sinkronisasi
                komunikasi dengan mesin catur.
        """
        if self._thread and self._thread.is_alive():
            self._stop = True
            self._std_write("stop\n")
            self._thread.join(timeout)
        self._stop = False

    def wait(self, delta: float = 1) -> None:
        while not self._stop:
            sleep(delta)

    def start(
        self, fen: str | list[str], depth: int | None = None, config: Config = {}
    ) -> None:
        """Memulai analisa posisi catur oleh mesin catur.

        Config yang disertakan disini akan menimpa config yang ditetapkan
        di __init__(), jika ada.

        Args:
            fen: (Daftar) posisi catur dalam notasi FEN.
            depth: Nilai `depth` yang ingin dicari.
            configs: Dict berisi UCI setoptions untuk dikirim ke mesin catur.
        """

        self.stop()
        fens = [fen] if isinstance(fen, str) else fen

        if len(fens) > 1 and depth is None:
            # sanity-check biar ngga infinite loop
            raise ValueError("Depth harus ada untuk analisa banyak FEN")

        def process() -> None:
            try:
                self._set_options(config)

                for fen in fens:
                    self._std_write(f"position fen {fen}\n")

                    # "flush" sampai dapat `readyok`
                    _ = ""
                    self._std_write("isready\n")
                    while _ != "readyok" and not self._stop:
                        _ = self._std_read().strip()

                    if depth is not None and depth > 0:
                        self._std_write(f"go depth {depth}\n")
                    else:
                        self._std_write("go infinite\n")

                    # proses output dari engine
                    while True:
                        if self._stop:
                            self._std_write("stop\n")

                        text = self._std_read().strip()
                        if "bestmove" in text:
                            break
                        if (
                            ("score" not in text)
                            or ("pv" not in text)
                            or ("bound" in text)
                            or text[:4] != "info"
                        ):
                            continue

                        info = _parse_uci_info(text)
                        self.db.upsert(fen, info)

                # untuk thread lain tahu bahwa proses sudah berhenti
                self._stop = True
            except BrokenPipeError:
                pass
            except:
                logger_engine.exception("Something went wrong.")
                raise

        self._thread = Thread(target=process)
        self._thread.daemon = True
        self._thread.start()

    def info(
        self,
        fen: str,
        multipv: int = 1,
        true_multipv: bool = True,
        with_move: bool = False,
    ) -> list[Info]:
        """Mendapatkan singgahan hasil analisa posisi catur.

        Args:
            fen: Posisi catur dalam notasi FEN.
            multipv: Urutan principal move yang ingin dicari.
            true_multipv: Pilihan untuk hanya menggunakan info MultiPV yang
                dihasilkan oleh mesin catur.
            with_move: Pilihan untuk menyertakan daftar bestmove.
        """

        if true_multipv:
            # pada dasarnya, "SELECT * FROM board WHERE fen=fen AND multipv=pv";
            # dengan pv berada di rentang [1, multipv]
            results = []
            for pv in range(multipv):
                info = self.db.select(
                    fen,
                    multipv=pv + 1,
                    with_move=with_move,
                )
                if info:
                    results.append(info)
        else:
            # pada dasarnya, "SELECT * FROM board WHERE fen=fen AND multipv=1";
            # dengan fen adalah semua anak yang mungkin dari posisi saat ini
            board = Board(fen)
            results = []
            for move in board.legal_moves:
                board.push(move)
                info = self.db.select(board.fen(), multipv=1, with_move=with_move)
                if info:
                    info["score"] *= -1
                    info["depth"] += 1
                    info["pv"].insert(0, move.uci())
                    results.append(info)
                board.pop()

            # sort
            results.sort(key=lambda d: (d["depth"], d["score"]), reverse=True)
            for pv, info in enumerate(results, start=1):
                info["multipv"] = pv

            # limit
            results = results[:multipv]

        return results

    def shutdown(self) -> None:
        "Menghentikan mesin catur dan database."

        # self.stop()
        self.db.close()
        self._engine.terminate()
