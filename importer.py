"""
Mengubah dump analisa Lichess menjadi database SQLite
"""

import fileinput
import logging
import os
from itertools import batched, cycle
from json import loads
from multiprocessing import Pool

from chess_cache.core import MATE_SCORE, Database
from chess_cache.logger import JSONFormatter

MP = 2  # banyak multiprocess
DUMP_DIR = "./dump"
IMPORT_STT = """
    INSERT INTO master.board AS mas
    SELECT * FROM board AS mem WHERE TRUE
    ON CONFLICT (fen) DO UPDATE SET
        depth = excluded.depth,
        score = excluded.score,
        move  = excluded.move
    WHERE excluded.depth >= mas.depth
"""

path_to = lambda fname: os.path.join(DUMP_DIR, fname)

_handle_file = logging.FileHandler("logs/importer.jsonl")
_handle_file.setFormatter(JSONFormatter())
_handle_file.setLevel(logging.ERROR)

_handle_io = logging.StreamHandler()
_handle_io.setFormatter(
    logging.Formatter("\x1b[32m%(asctime)s\x1b[0m [%(process)s] %(message)s")
)

logger_imp = logging.Logger("importer")
logger_imp.addHandler(_handle_file)
logger_imp.addHandler(_handle_io)


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
        logger_imp.info("reading dumps")
        for line in fileinput.input(files=filenames):
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
                    except ValueError:
                        # bukan analisa posisi catur standar
                        continue

        # UPSERT isi database :memory: dengan berkas database
        logger_imp.info("upserting database")
        db.sql.execute(f"ATTACH DATABASE '{db_name}' AS master")
        db.sql.execute(IMPORT_STT)
        db.sql.execute('ANALYZE master')
        db.sql.execute("DETACH master")

        # Delete setelah upsert berhasil
        logger_imp.info("deleting dumps")
        for fname in filenames:
            os.remove(fname)

        logger_imp.info("process done")

    except:
        logger_imp.exception("processing failed")
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

    if "fish.exit" in os.listdir():
        os.remove("fish.exit")

    # untuk mempercepat proses import, gunakan multiprocess. Untuk menghindari
    # write lock, simpan analisa ke berkas SQLite berbeda (nanti digabung).
    # batched filenames bisa ditingkatkan, seperti lebih dari 500. SSD write
    # speed tetap menjadi bottleneck, karena kita dapat menalar perintah SQL
    # IMPORT_STT akan *jauh* lebih banyak melakukan INSERT ketimbang UPDATE
    # (signifikan terasa saat ukuran berkas database sudah dua digit gigabita).
    args = zip(cycle(db_names), batched(filenames, 250))
    with Pool(processes=MP) as pool:
        for _ in pool.imap_unordered(process, args):
            pass

    # untuk eksperimen saja
    # db_name, fname = db_names[0], filenames[0]
    # process((db_name, (fname,)))
