"""
Mengubah dump analisa Lichess menjadi database SQLite
"""

import os
from itertools import batched
from json import loads
from multiprocessing import Pool

from tqdm import tqdm


from chess_cache.core import MATE_SCORE, Database, Info
from chess_cache.logger import get_logger
from chess_cache.env import Env

env = Env(".env")

CPU_COUNT = env.get("IMPORTER_THREAD", 1)
BATCH_SIZE = env.get("IMPORTER_BATCH", 1)
DUMP_DIR = env.get("LICHESS_DUMP_DIR", "dump")
MAXIMUM_DEPTH = env.get("ANALYSIS_DEPTH", 35)
if MAXIMUM_DEPTH < 35:  # hardcoded agar tidak teledor
    MAXIMUM_DEPTH = 35

IMPORT_STT = """
    INSERT INTO master.board AS mas
            (fen, depth, score, move)
    SELECT   fen, depth, score, move
        FROM board AS mem
        WHERE TRUE
    ON CONFLICT (fen) DO
        UPDATE SET
            depth = excluded.depth,
            score = excluded.score,
            move  = excluded.move
        WHERE excluded.depth > mas.depth
"""


def process(filename: str) -> list[Info]:
    db = Database(":memory:")
    with open(filename) as f:
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
                    except ValueError:
                        # bukan analisa posisi catur standar
                        continue
    results = db.to_json()
    db.close()
    return results


def path_to(fname: str) -> str:
    return os.path.join(DUMP_DIR, fname)


if __name__ == "__main__":
    if "fish.exit" in os.listdir():
        os.remove("fish.exit")

    logger = get_logger("importer")

    FILENAMES = [path_to(_) for _ in os.listdir(DUMP_DIR)]

    for filenames in batched(FILENAMES, BATCH_SIZE):
        if "fish.exit" in os.listdir():
            logger.info("soft exit")
            break

        logger.info("reading dumps")
        db = Database(":memory:")
        with Pool(processes=CPU_COUNT) as pool:
            iter_ = pool.imap_unordered(process, filenames[::-1])
            for data in tqdm(iter_, total=BATCH_SIZE, ncols=0):
                db.from_json(data)

        # anggap sebagian besar data Lichess usang, sehingga kita
        # perlu menormalisasi analisa dengan depth > MAXIMUM_DEPTH
        # menjadi MAXIMUM_DEPTH - 2 (sehingga mudah untuk diupdate
        # oleh mesin catur)
        db.normalize_old_data(cutoff_score=MAXIMUM_DEPTH, new_score=MAXIMUM_DEPTH - 2)

        # UPSERT isi database :memory: dengan berkas database
        logger.info("upserting")
        db.sql.execute(f"ATTACH DATABASE 'lichess.sqlite' AS master")
        db.sql.execute(IMPORT_STT)

        logger.info("optimizing")
        db.sql.execute("ANALYZE master")
        db.sql.execute("DETACH master")
        db.close()

        # Delete setelah upsert berhasil
        logger.info("deleting dumps")
        for fname in filenames:
            os.remove(fname)

        logger.info("iteration complete")
