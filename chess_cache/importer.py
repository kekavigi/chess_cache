from io import StringIO
from json import loads

from chess.pgn import read_game

from .core import MATE_SCORE, STARTING_FEN, Database, Engine
from .logger import get_logger

logger = get_logger("importer")


def extract_fens(pgn: str, max_depth: int) -> list[str]:
    """
    Mencatat semua FEN unik sampai kedalaman max_depth di teks PGN

    Args:
        pgn: Teks PGN.
        max_depth: kedalaman maksimum proses ekstraksi.
    """

    _pgn = StringIO(pgn)
    boards = []
    while True:
        game = read_game(_pgn)
        if game is None:
            break

        # hanya sertakan varian standar
        if game.headers.get("Variant") not in ["Rapid", "Standard"]:
            continue
        board = game.board()
        if game.board().fen() != STARTING_FEN:
            continue
        try:
            # pastikan semua move valid dari sudut
            # pandang permainan varian standar
            for move in list(game.mainline_moves()):
                board.push(move)
        except:
            continue

        boards.append(board)

    fens, count_fen = {}, 0
    for board in boards:
        _over = len(board.move_stack) - max_depth
        for _ in range(max(_over, 0)):
            board.pop()

        while board.move_stack:
            epd = board.epd()
            if epd not in fens:
                count_fen += 1
                fens[epd] = count_fen
            board.pop()

    return [k for (k, v) in sorted(fens.items(), key=lambda tup: tup[1])]


def extract_dump(
    filename: str,
    minimal_depth: int = 1,
    maximum_depth: int = 100,
) -> Database:
    """
    Mengekstrak berkas JSON dump Lichess.

    Dump Lichess akan diekstraksi ke memori utama, sehingga
    ada baiknya ukuran berkas dibatasi.

    Args:
        pgn: Teks PGN.
        max_depth: kedalaman maksimum proses ekstraksi.
    """

    db = Database(":memory:", minimal_depth=minimal_depth)

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

    # anggap sebagian besar data Lichess usang, sehingga kita
    # perlu menormalisasi analisa dengan depth > maximum_depth
    # menjadi maximum_depth - 2 (sehingga mudah untuk diupdate
    # oleh mesin catur nantinya)
    db.normalize_old_data(cutoff_score=maximum_depth, new_score=maximum_depth - 2)

    return db


# import os
# from itertools import batched
# from multiprocessing import Pool
# from tqdm import tqdm

# CPU_COUNT = env.get("IMPORTER_THREAD", 1)
# BATCH_SIZE = env.get("IMPORTER_BATCH", 1)
# DUMP_DIR = env.get("LICHESS_DUMP_DIR", "dump")
# MAXIMUM_DEPTH = env.get("ANALYSIS_DEPTH", 35)

# IMPORT_STT = """
#     INSERT INTO master.board AS mas
#             (fen, depth, score, move)
#     SELECT   fen, depth, score, move
#         FROM board AS mem
#         WHERE TRUE
#     ON CONFLICT (fen) DO
#         UPDATE SET
#             depth = excluded.depth,
#             score = excluded.score,
#             move  = excluded.move
#         WHERE excluded.depth > mas.depth
# """


# if __name__ == "__main__":
#     if "fish.exit" in os.listdir():
#         os.remove("fish.exit")

#     FILENAMES = [os.path.join(DUMP_DIR, _) for _ in os.listdir(DUMP_DIR)]

#     for filenames in batched(FILENAMES, BATCH_SIZE):
#         if "fish.exit" in os.listdir():
#             logger.info("soft exit")
#             break

#         logger.info("reading dumps")
#         db = Database(":memory:")
#         with Pool(processes=CPU_COUNT) as pool:
#             iter_ = pool.imap_unordered(process, filenames[::-1])
#             for data in tqdm(iter_, total=BATCH_SIZE, ncols=0):
#                 db.from_json(data)

#         # UPSERT isi database :memory: dengan berkas database
#         logger.info("upserting")
#         db.sql.execute(f"ATTACH DATABASE 'lichess.sqlite' AS master")
#         db.sql.execute(IMPORT_STT)

#         logger.info("optimizing")
#         db.sql.execute("ANALYZE master")
#         db.sql.execute("DETACH master")
#         db.close()

#         # Delete setelah upsert berhasil
#         logger.info("deleting dumps")
#         for fname in filenames:
#             os.remove(fname)

#         logger.info("iteration complete")


if __name__ == "__main__":
    import argparse
    import pathlib

    from .env import (
        ANALYSIS_DEPTH,
        DATABASE_URI,
        ENGINE_BASE_CONFIG,
        ENGINE_MAIN_CONFIG,
        ENGINE_PATH,
        IMPORTER_PGN_DEPTH,
        MINIMAL_DEPTH,
    )

    ENGINE_CONFIG = ENGINE_BASE_CONFIG.copy()
    ENGINE_CONFIG.update(ENGINE_MAIN_CONFIG)

    parser = argparse.ArgumentParser(prog="importer")
    parser.add_argument("--pgn", type=pathlib.Path)
    args = parser.parse_args()

    with args.pgn.open("r") as f:
        fens = extract_fens(f.read(), max_depth=IMPORTER_PGN_DEPTH)

    engine = Engine(ENGINE_PATH, DATABASE_URI)
    try:
        engine.set_options(ENGINE_CONFIG)
        while fens:
            engine.put(fens.pop(), ANALYSIS_DEPTH)
        engine.wait()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        engine.shutdown()
