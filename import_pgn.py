from chess.pgn import Game, read_game

from chess_cache.core import STARTING_FEN, AnalysisEngine
from chess_cache.env import Env
from chess_cache.logger import get_logger

env = Env()

ENGINE_PATH = env.get("ENGINE_PATH", "stockfish")
DATABASE_URI = env.get("DATABASE_URI", ":memory:")
ENGINE_CONFIG = env.get("ENGINE_CONFIG", {})
ANALYSIS_DEPTH = env.get("ANALYSIS_DEPTH", 35)
IMPORTER_PGN_DEPTH = env.get("IMPORTER_PGN_DEPTH", 8)

# overwrite
# ENGINE_CONFIG['MultiPV'] = 1
ENGINE_CONFIG["Thread"] = 4
ENGINE_CONFIG["Hash"] = 4096


def analyse_game(game: Game) -> None:
    if "Variant" not in game.headers or game.headers["Variant"] in ["Rapid"]:
        return

    board = game.board()
    if board.fen() != STARTING_FEN:
        return

    for move in list(game.mainline_moves())[:IMPORTER_PGN_DEPTH]:
        board.push(move)
    while board.move_stack:
        epd = board.epd()
        analysis = engine.info(epd, only_best=True, max_depth=0)
        if analysis and analysis[0]["depth"] < ANALYSIS_DEPTH:
            engine.start(epd, depth=ANALYSIS_DEPTH, config=ENGINE_CONFIG)
            engine.wait()
        board.pop()


if __name__ == "__main__":
    try:
        engine = AnalysisEngine(ENGINE_PATH, DATABASE_URI, ENGINE_CONFIG)
        logger = get_logger("importer")

        pgn_file = "lichess_kekavigi_2025-07-11.pgn"

        logger.info("Loading all games")
        games = []
        with open(pgn_file) as f:
            while True:
                game = read_game(f)
                if game is None:
                    break
                games.append(game)
        logger.info(f"{len(games)} games loaded")

        # PGN dari Lichess tersusun kronologis, terbaru di terakhir
        # mulai dari terbaru karena lebih mudah diingat dan lebih
        # dibutuhkan oleh user yang meng-import
        while games:
            game = games.pop()

            _h = game.headers
            _id = _h.get("GameId") or {_h.get("Event")}
            logger.info(f"Analysing game {_id}")
            analyse_game(game)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        engine.shutdown()
