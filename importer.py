"""
Mengubah dump analisa Lichess menjadi database SQLite
"""

import fileinput
import os
from itertools import batched, cycle
from json import loads
from multiprocessing import Pool
from random import shuffle

from chess import IllegalMoveError

from chess_cache import MATE_SCORE, Database
from logg import log_traceback

MP = 2  # banyak multiprocess
DUMP_DIR = "./dump"
path_to = lambda fname: os.path.join(DUMP_DIR, fname)

IMPORT_STT = """
    INSERT INTO master.board AS mas
    SELECT * FROM board AS mem WHERE TRUE
    ON CONFLICT (fen, multipv) DO UPDATE SET
        depth = excluded.depth,
        score = excluded.score,
        move  = excluded.move
    WHERE excluded.depth >= mas.depth
"""


def _process(db: Database, fname: str) -> None:
    "Memparse berkas JSONL Lichess dan menyimpannya ke database."

    with log_traceback(), fileinput.input(files=(fname,)) as f:
        for line in f:
            raw = loads(line)

            for eval in raw["evals"]:
                data = []

                # tambahkan data eval
                for pv in eval["pvs"]:
                    if "cp" in pv:
                        score = pv["cp"]
                    else:
                        value = pv["mate"]
                        if value > 0:
                            score = MATE_SCORE - value
                        else:
                            score = -MATE_SCORE - value
                    data.append(
                        {
                            "fen": raw["fen"],
                            "depth": eval["depth"],
                            "score": score,
                            "pv": pv["line"].split(" "),
                        }
                    )

                # urutkan untuk dapat multipv; lalu upsert
                data.sort(key=lambda d: d["score"], reverse=True)
                for i, info in enumerate(data, start=1):
                    info["multipv"] = i
                    try:
                        db.upsert(info["fen"], info)
                    except (IllegalMoveError, KeyError):
                        # aman untuk mengasumsikan daftar move di pv bukan
                        # rangkaian gerakan catur standar. Jadi analisa ini
                        # bukan posisi standar, sehingga tidak usah di upsert
                        continue


def process(args) -> None:
    db_name, filenames = args

    # meniru fishtest-nya Stockfish: tidak melakukan proses import
    # jika ada berkas `fish.exit` di working dir. Lebih baik daripada
    # user mengirim KeyboardInterrupt saat program berjalan
    if "fish.exit" in os.listdir():
        return

    # gunakan memory untuk menyimpan sementara hasil import analisa catur.
    # Cara ini jauh lebih cepat karena UPSERT terjadi di RAM bukan di SSD,
    # dan tanpa peningkatan berarti pada penggunaan RAM
    db = Database(":memory:")
    try:

        # dump Lichess di-praproses dengan `zstdcat dump.jsonl.zstd | split`
        # Dari observasi didapati kita dapat memroses banyak berkas hasil
        # split tanpa peningkatan berarti pada penggunaan RAM
        _len = len(filenames)
        for e, fname in enumerate(filenames, start=1):
            print(f"starting ({e}/{_len}) {fname}")
            _process(db, fname)

        # UPSERT isi database :memory: dengan berkas database
        print("start joining")
        db.sql.execute(f"ATTACH DATABASE '{db_name}' AS master")
        db.sql.execute(IMPORT_STT)
        db.sql.execute("DETACH master")

        # Delete setelah upsert berhasil
        print("start deleting")
        for fname in filenames:
            os.remove(fname)

        print("done")

    except:
        print(f"FAIL {filenames}")
        raise
    finally:
        db.close()
    return


if __name__ == "__main__":
    db_names = [
        "lichess.sqlite",
        "lichess.sqlite.part1",
        "lichess.sqlite.part2",
        "lichess.sqlite.part3",
    ][:MP]
    filenames = [path_to(_) for _ in os.listdir(DUMP_DIR)]
    shuffle(filenames)  # opsional; selera pribadi

    # untuk mempercepat proses import, gunakan multiprocess. Untuk menghindari
    # write lock, simpan analisa ke berkas SQLite berbeda (nanti digabung).
    # batched filenames bisa ditingkatkan, seperti lebih dari 500. SSD write
    # speed tetap menjadi bottleneck, karena kita dapat menalar perintah SQL
    # IMPORT_STT akan *jauh* lebih banyak melakukan INSERT ketimbang UPDATE
    # (signifikan terasa saat ukuran berkas database sudah dua digit gigabita).
    args = zip(cycle(db_names), batched(filenames, 100))
    with Pool(processes=MP) as pool:
        for _ in pool.imap_unordered(process, args):
            pass

    # untuk eksperimen saja
    # db_name, fname = db_names[0], filenames[0]
    # process((db_name, (fname,)))
