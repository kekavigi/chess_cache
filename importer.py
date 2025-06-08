import fileinput
import os
from itertools import cycle
from multiprocessing import Pool
from random import shuffle

from chess import IllegalMoveError
from orjson import loads

from chess_cache import MATE_SCORE, Database
from logg import log_traceback

MP = 2
DUMP_DIR = "./dump"
path_to = lambda fname: os.path.join(DUMP_DIR, fname)


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
    db_part, fname = args

    fname = path_to(fname)
    db_path = f"lichess.sqlite.part{db_part}" 

    db = Database(db_path)
    try:
        db.sql.execute("ANALYZE")
        _process(db, fname)
        db.sql.execute("VACUUM")
        os.remove(fname)
    except:
        print(f"FAIL {fname}")
        raise
    else:
        print(f"DONE {fname}")
    finally:
        db.close()
    return fname


if __name__ == "__main__":
    filenames = os.listdir(DUMP_DIR)
    shuffle(filenames)

    args = zip(cycle(range(1, 10)), filenames)
    with Pool(processes=MP) as pool:
        for _ in pool.imap_unordered(process, args, chunksize=2):
            pass
