import fileinput
import os
from itertools import cycle
from multiprocessing import Pool
from random import shuffle

from chess import IllegalMoveError
from orjson import loads
from tqdm import tqdm

from chess_cache import MATE_SCORE, Database
from logg import log_traceback

MP = 2
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


def _process(db, fname):
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

                # urutkan untuk dapat multipv; upsert
                data.sort(key=lambda d: d["score"], reverse=True)
                for i, info in enumerate(data, start=1):
                    info["multipv"] = i
                    try:
                        db.upsert(info["fen"], info)
                    except IllegalMoveError:
                        # analisa ini bukan catur standar
                        continue


def process(args):
    db_name, fname = args
    fname = path_to(fname)

    db = Database(":memory:")
    try:
        _process(db, fname)
        db.sql.execute(f"ATTACH DATABASE '{db_name}' AS master")
        db.sql.execute(IMPORT_STT)
        db.sql.execute("DETACH master")
        os.remove(fname)
    except:
        print(f"FAIL {fname}")
        raise
    finally:
        db.close()
    return fname


if __name__ == "__main__":
    db_names = [
        "lichess.sqlite",
        "lichess.sqlite.part1",
        "lichess.sqlite.part2",
        "lichess.sqlite.part3",
    ][:MP]
    filenames = os.listdir(DUMP_DIR)
    # shuffle(filenames)

    args = zip(cycle(db_names), filenames)
    with Pool(processes=MP) as pool:
        for _ in tqdm(
            pool.imap_unordered(process, args),
            total=len(filenames),
            ncols=0,
        ):
            pass

    # db_part, fname = 1, filenames[0]
    # process((db_part, fname))
