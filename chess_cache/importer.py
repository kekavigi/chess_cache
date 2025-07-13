from chess import Board
from chess.pgn import Game, read_game

from .core import STARTING_FEN, AnalysisEngine
from .logger import get_logger

logger = get_logger("importer")


def pgn_to_fens(path: str, max_depth: int) -> list[str]:
    logger.info(f"Membaca PGN '{path}'")

    boards = []
    with open(path) as f:
        while True:
            game = read_game(f)
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
    logger.info(f"Berhasil memuat {len(boards)} permainan varian standar")

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

    logger.info(f"Berhasil mengekstrak {count_fen} posisi")
    return [k for (k, v) in sorted(fens.items(), key=lambda tup: tup[1])]


if __name__ == "__main__":
    from .env import Env

    env = Env()

    ENGINE_PATH = env.get("ENGINE_PATH", "stockfish")
    DATABASE_URI = env.get("DATABASE_URI", ":memory:")
    ENGINE_CONFIG = env.get("IMPORTER_ENGINE_CONFIG", {"Thread": 4, "Hash": 1024})
    ANALYSIS_DEPTH = env.get("ANALYSIS_DEPTH", 35)
    IMPORTER_PGN_DEPTH = env.get("IMPORTER_PGN_DEPTH", 8)

    pgn_file = "lichess_kekavigi_2025-07-11.pgn"
    fens = pgn_to_fens(pgn_file, max_depth=IMPORTER_PGN_DEPTH)

    try:
        engine = AnalysisEngine(ENGINE_PATH, DATABASE_URI, ENGINE_CONFIG)
        while fens:
            epd = fens.pop()
            analysis = engine.info(epd, only_best=True, max_depth=0)
            if analysis and analysis[0]["depth"] < ANALYSIS_DEPTH:
                engine.start(epd, depth=ANALYSIS_DEPTH, config=ENGINE_CONFIG)
                engine.wait()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        engine.shutdown()
