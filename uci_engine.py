from json import load as load_json
from logging import ERROR
from os import F_OK, X_OK
from os import access as os_access
from subprocess import PIPE, Popen
from threading import Thread

from chess import Board

from chess_cache.core import (
    STARTING_FEN,
    Database,
    Info,
    _parse_uci_info,
    _unparse_uci_info,
    logger_db,
    logger_engine,
)

logger_db.setLevel(ERROR)
logger_engine.setLevel(ERROR)


class UciEngine:
    """Menghasilkan singgahan hasil analisis mesin catur.

    Class ini sewajarnya hanya dieksekusi sebagai script, bukan untuk diimport.

    Attributes:
        db: Instance dari `Database`
        board: Instance dari `chess.Board`
        engine: Koneksi ke executable mesin catur
    """

    # cached uci engine, tepatnya :p

    def __init__(self, settings_path: str = "./settings.json"):
        """Menginisialisasi mesin catur dan database

        Args:
            settings_path: alamat dari berkas pengaturan.
                Saat ini pengaturan berisi informasi tentang alamat mesin
                catur dan alamat dari berkas database SQLite.
        """

        try:
            with open(settings_path) as f:
                settings = load_json(f)
        except Exception:
            logger_engine.warning("gagal membaca setting_path")
            settings = {}

        binary_path = settings.get("binary_path", "stockfish")
        if not os_access(binary_path, F_OK):
            msg = "Engine tidak ditemukan"
            logger_engine.error(msg)
            raise FileNotFoundError(msg)
        if not os_access(binary_path, X_OK):
            msg = "Engine tidak executable."
            logger_engine.error(msg)
            raise PermissionError(msg)
        self.engine = Popen(
            binary_path,
            stdin=PIPE,
            stdout=PIPE,
            universal_newlines=True,
            bufsize=1,
        )
        self.db = Database(settings.get("database_path", ":memory:"))
        self.fen = STARTING_FEN
        self._quit = False

        thread = Thread(target=self.parse_output)
        thread.start()

        try:
            logger_engine.info("Interaction started")
            self.parse_input()
        except Exception:
            logger_engine.exception("Something went wrong.")
            self._quit = True
        finally:
            logger_engine.info("Menghentikan UciEngine")

            self.db.close()

            self.engine.terminate()
            self._quit = True
            thread.join()
            logger_engine.info("Engine closed")

    def parse_input(self) -> None:
        "Memroses input pengguna agar hasil dari mesin catur dapat disinggah."

        assert self.engine.stdin is not None  # agar mypy senang
        std_write = self.engine.stdin.write

        while True:
            try:
                command = input().strip()
            except KeyboardInterrupt:
                break
            if not command:
                continue

            if command == "quit":
                self._quit = True
                break

            parts = command.split(maxsplit=2)
            if parts[0] == "position":
                try:
                    if len(parts) == 1:
                        # assume maksud adalah startpos
                        parts.append("startpos")

                    _, *final = parts[1:]
                    # _ akan berisi 'startpos' atau 'fen'

                    self.fen = ""
                    if final:
                        self.fen, *final = final[0].split("moves")
                        # harusnya .split(' moves') but eh whatever
                        # self.fen mungkin empty string, yang artinya STARTING_FEN
                        # atau posisi dalam notasi FEN. final selanjutnya berisi
                        # daftar moves, atau kosong
                    if not self.fen:
                        self.fen = STARTING_FEN

                    board = Board(self.fen)  # sekalian ngecek keabsahan FEN
                    if final:
                        # sesuaikan fen
                        for move in final[0].split(" "):
                            if not move:
                                continue
                            board.push_uci(move)
                        self.fen = board.fen()
                except:
                    raise ValueError("Invalid FEN or moves")

            std_write(f"{command}\n")

    def parse_output(self) -> None:
        "Memroses output dari mesin catur untuk disinggah dan ditampilkan."

        assert self.engine.stdout is not None  # agar mypy senang
        std_read = self.engine.stdout.readline

        # TODO: apakah perlu locking/sinkronisasi dengan parse_input
        # agar tidak ada race-condition: board sudah ganti, tapi
        # stdin dari stockfish masih refer to old position? atau itu
        # pratically tidak akan terjadi?

        try:
            while not self._quit:
                text = std_read().strip()
                if text == "":
                    continue

                cached: Info | None

                if (
                    (text[:4] == "info")
                    and ("score" in text)
                    and ("pv" in text)
                    and ("bound" not in text)
                ):
                    # baris info yang bisa disinggah
                    info = _parse_uci_info(text)
                    self.db.upsert(self.fen, info)
                    cached = self._cached_select(self.fen, info["multipv"])
                    assert cached is not None  # agar mypy senang
                    info.update(cached)
                    text = _unparse_uci_info(info)

                elif text[:8] == "bestmove":
                    # dapatkan bestmove dan ponder dari database

                    # TODO agak chaos kalau GUI ngirim "ponderhit" sedangkan
                    # ponder yang dicache beda dengan yang barusan dianalisis
                    # for simplicity sake, this part is commented, (extra
                    # logic is needed, too):
                    # if len(moves) == 2:
                    #     text = f"bestmove {moves[0]} ponder {moves[1]}"
                    # elif len(moves) == 1:
                    #     ...
                    # else, tampilkan apa yang diberikan mesin saja

                    cached = self._cached_select(self.fen, multipv=1)
                    if cached["pv"]:
                        text = f"bestmove {cached['pv'][0]}"

                print(text, flush=True)
        except:
            logger_engine.exception("Something went wrong.")
            raise

    def _cached_select(self, fen: str, multipv: int) -> Info:
        if multipv == 1:
            result = self.db.select(fen, only_best=True, max_depth=100)[0]

        else:
            # TODO: cache this part
            _tmp = self.db.select(fen, only_best=False, max_depth=100)
            if multipv <= len(_tmp):
                result = _tmp[multipv - 1]
            else:
                result = {}
        if "fen" in result:
            result.pop("fen")
        return result


if __name__ == "__main__":
    UciEngine(settings_path="./settings.json")
