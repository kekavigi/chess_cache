from io import StringIO

from chess import Board
from chess.pgn import Game, read_game

from .core import STARTING_FEN, Engine
from .logger import get_logger

logger = get_logger("importer")


def extract_fens(pgn: str, max_depth: int) -> list[str]:
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


if __name__ == "__main__":
    from .env import Env

    env = Env()

    ENGINE_PATH = env.get("ENGINE_PATH", "stockfish")
    DATABASE_URI = env.get("DATABASE_URI", ":memory:")
    ENGINE_CONFIG = env.get("IMPORTER_ENGINE_CONFIG", {"Thread": 4, "Hash": 1024})
    ANALYSIS_DEPTH = env.get("ANALYSIS_DEPTH", 35)
    MINIMAL_DEPTH = env.get("MINIMAL_DEPTH", 20)
    IMPORTER_PGN_DEPTH = env.get("IMPORTER_PGN_DEPTH", 8)

    pgn_file = "kekavigi.pgn"
    with open(pgn_file) as f:
        fens = extract_fens(f.read(), max_depth=IMPORTER_PGN_DEPTH)

    try:
        engine = Engine(ENGINE_PATH, DATABASE_URI)
        engine.set_options(ENGINE_CONFIG)
        while fens:
            engine.put(fens.pop(), ANALYSIS_DEPTH)
        engine.wait()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        engine.shutdown()
