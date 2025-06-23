#!/home/user/.pyenv/shims/python

import atexit
import os
from io import StringIO

from chess import AmbiguousMoveError, Board, IllegalMoveError, InvalidMoveError
from chess.pgn import read_game as read_pgn
from flask import Flask, g, render_template, request, send_from_directory

from chess_cache.core import AnalysisEngine
from chess_cache.env import load_config


CONFIG = load_config("config.shared.toml")

app = Flask(__name__)
engine = AnalysisEngine(**CONFIG["engine"])

atexit.register(engine.shutdown)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/info/<path:fen>")
def get_info(fen):
    try:
        board = Board(fen)  # TODO: optimalkan cara cek keabsahan FEN
    except ValueError:
        return {"status": "Invalid FEN", "info": fen}, 400
    else:
        return engine.info(fen, max_depth=10)


@app.get("/uv/info/<path:fen>")
def uv_get_info(fen):
    try:
        board = Board(fen)
    except ValueError:
        return {"status": "Invalid FEN", "info": fen}, 400
    else:
        results = engine.info(board.epd(), max_depth=10)
        for info in results:
            board.set_fen(fen)
            movestack = info.pop("pv")
            info["pv"] = []
            for uci in movestack:
                san = board.san(board.parse_uci(uci))
                info["pv"].append(san)
                board.push_uci(uci)
        return results


@app.post("/uv/analysis")
def uv_process_analysis():
    data = request.get_json()
    if "pgn" not in data:
        return {"status": "invalid POST request", "info": "No PGN data"}, 400

    try:
        game = read_pgn(StringIO(data["pgn"]))
        board = Board()  # assume standard game
        for move in game.mainline_moves():
            board.push(move)
        fen = board.epd()
    except (ValueError, InvalidMoveError, IllegalMoveError, AmbiguousMoveError):
        return {"status": "Invalid PGN for standard chess game", "info": pgn}, 400
    else:
        old_info = engine.info(fen, only_best=True, max_depth=0)
        if old_info and old_info[0]["depth"] > 35:
            return {"status": "Request denied."}, 403

        engine.start(fen, 35)
        return {"status": "OK"}, 200


if __name__ == "__main__":
    app.run(**CONFIG["play_web"].get("flask", {}))
