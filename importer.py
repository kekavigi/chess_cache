import fileinput
import os
from itertools import batched, cycle
from json import loads
from multiprocessing import Pool
from random import shuffle

from chess import IllegalMoveError

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
                    except (IllegalMoveError, KeyError):
                        # analisa ini bukan catur standar
                        continue


def process(args):
    db_name, filenames = args

    if "fish.exit" in os.listdir():
        return

    db = Database(":memory:")
    try:
        _len = len(filenames)
        for e, fname in enumerate(filenames, start=1):
            print(f"starting ({e}/{_len}) {fname}")
            _process(db, fname)

        print("start joining")
        db.sql.execute(f"ATTACH DATABASE '{db_name}' AS master")
        db.sql.execute(IMPORT_STT)
        db.sql.execute("DETACH master")

        print("start deleting")
        for fname in filenames:
            os.remove(fname)

        print("done")

    except:
        print(f"FAIL {filenames}")
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
    filenames = [path_to(_) for _ in os.listdir(DUMP_DIR)]
    shuffle(filenames)

    args = zip(cycle(db_names), batched(filenames, 100))
    with Pool(processes=MP) as pool:
        for _ in pool.imap_unordered(process, args):
            pass

    # db_name, fname = db_names[0], filenames[0]
    # process((db_name, (fname,)))
