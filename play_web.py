import atexit
import os
from io import StringIO

from chess import Board
from chess.pgn import read_game as read_pgn
from flask import Flask, Request, render_template, request, send_from_directory

from chess_cache import Engine, Env, get_logger, STARTING_FEN
from chess_cache.importer import extract_fens

env = Env(".env")
logger = get_logger("flask")

FLASK_CONFIG = env.get("FLASK_CONFIG", {})
ENGINE_PATH = env.get("ENGINE_PATH", "stockfish")
DATABASE_URI = env.get("DATABASE_URI", ":memory:")
ANALYSIS_DEPTH = env.get("ANALYSIS_DEPTH", 35)
MINIMAL_DEPTH = env.get("MINIMAL_DEPTH", 20)

IMPORTER_PGN_DEPTH = env.get("IMPORTER_PGN_DEPTH", 50)
ENGINE_CONFIG_MAIN = env.get("ENGINE_CONFIG", {})
ENGINE_CONFIG_MISC = env.get("IMPORTER_ENGINE_CONFIG", ENGINE_CONFIG_MAIN)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1000 * 1000

engine = Engine(ENGINE_PATH, DATABASE_URI, minimal_depth=MINIMAL_DEPTH)
engine.set_options(ENGINE_CONFIG_MAIN)
atexit.register(engine.shutdown)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.get("/train")
def train():
    return render_template("train.html", initial_fen=STARTING_FEN)


@app.get("/")
def explore():
    return render_template("explore.html", initial_fen=STARTING_FEN)


@app.get("/uv/stats")
def uv_stats():
    return {"analysis_queue": len(engine.heap)}


@app.get("/uv/info/<path:fen>")
def uv_get_info(fen):
    try:
        board = Board(fen)
    except ValueError:
        return {"status": "Invalid FEN", "info": fen}, 400

    try:
        results = engine.info(board.epd(), max_depth=10)
        for info in results:
            board.set_fen(fen)
            movestack = info.pop("pv")
            info["pv"] = []
            for uci in movestack:
                san = board.san(board.parse_uci(uci))
                info["pv"].append(san)
                board.push_uci(uci)
    except Exception as e:
        logger.exception(str(e))
        raise

    return results


@app.post("/uv/upload_pgn")
def uv_parse_pgn():
    if "file" not in request.files:
        return {"status": "tidak ada file"}, 400

    file: Request.files = request.files["file"]
    if file.filename == "":
        # If the user does not select a file, the browser
        # submits an empty file without a filename.
        return {"status": "tidak ada file"}, 400
    try:
        pgn = file.stream.read().decode("utf-8")
    except:
        logger.exception("unable to parse file")
        return {"status": "unable to parse file"}, 415
    else:
        fens = extract_fens(pgn, max_depth=IMPORTER_PGN_DEPTH)
        for fen in fens:
            engine.put(fen, ANALYSIS_DEPTH, config=ENGINE_CONFIG_MISC)
        return {
            "status": "OK",
            "info": f"Berhasil mengekstrak {len(fens)} posisi",
        }, 200


@app.post("/uv/analysis")
def uv_process_analysis():
    data = request.get_json()
    if "pgn" not in data:
        return {"status": "invalid POST request", "info": "No pgn data"}, 400
    if engine.is_full():
        return {"status": "Too many requests"}, 429
    try:
        # TODO: raise exception on non-standard game
        game = read_pgn(StringIO(data["pgn"]))
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)
    except Exception:
        return {"status": "Invalid PGN", "info": data["pgn"]}, 400

    fen = board.epd()
    analysis = engine.info(fen, only_best=True, max_depth=0)
    if analysis and analysis[0]["depth"] > 35:
        return {
            "status": "Request denied.",
            "info": "cached data depth is deemed good enough.",
        }, 403

    engine.put(fen, ANALYSIS_DEPTH, priority=100, config=ENGINE_CONFIG_MAIN)
    return {"status": "OK"}, 200


if __name__ == "__main__":
    app.run(**FLASK_CONFIG)
