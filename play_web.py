#!/home/user/.pyenv/shims/python

import atexit
import os
from collections import deque
from io import StringIO
from threading import Thread
from time import sleep

from chess import Board
from chess.pgn import read_game as read_pgn
from flask import Flask, g, render_template, request, send_from_directory

from chess_cache.core import AnalysisEngine, STARTING_FEN
from chess_cache.env import Env

env = Env('.env')
FLASK_CONFIG = env.get('FLASK_CONFIG', {})
ENGINE_PATH = env.get('ENGINE_PATH', 'stockfish')
DATABASE_URI = env.get('DATABASE_URI', ':memory:')
ENGINE_CONFIG = env.get('ENGINE_CONFIG', {})
ANALYSIS_DEPTH = env.get('ANALYSIS_DEPTH', 35)


class AnalysisQueue:
    def __init__(self, qsize: int, engine: AnalysisEngine):
        self.q = deque(maxlen=qsize)
        self.engine = engine
        self.size = 0
        self.maxsize = qsize

        self._quit = False
        self.thread = Thread(target=self.process, daemon=True)
        self.thread.start()

    def process(self):
        while not self._quit:
            if len(self.q):
                fen = self.q.popleft()
                self.size -= 1
                engine.start(fen, ANALYSIS_DEPTH, config=ENGINE_CONFIG)
                self.engine.wait()
            else:
                sleep(1)

    def shutdown(self):
        self._quit = True
        self.thread.join()

    def add(self, fen: str):
        if fen not in self.q:
            self.q.append(fen)
            self.size += 1


app = Flask(__name__)
engine = AnalysisEngine(ENGINE_PATH, DATABASE_URI, ENGINE_CONFIG)

q_analysis = AnalysisQueue(qsize=64, engine=engine)
atexit.register(q_analysis.shutdown)

atexit.register(engine.shutdown)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.get("/train", defaults={"initial_fen": STARTING_FEN})
@app.get("/train/<path:initial_fen>")
def train(initial_fen: str):
    try:
        Board(initial_fen)
    except ValueError:
        initial_fen = STARTING_FEN
    return render_template("train.html", initial_fen=initial_fen)


@app.get("/", defaults={"initial_fen": STARTING_FEN})
@app.get("/<path:initial_fen>")
def explore(initial_fen: str):
    try:
        Board(initial_fen)
    except ValueError:
        initial_fen = STARTING_FEN
    return render_template("explore.html", initial_fen=initial_fen)


@app.get("/uv/stats")
def stats():
    return {"analysis_queue": list(q_analysis.q)}


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
        return {"status": "invalid POST request", "info": "No pgn data"}, 400

    if q_analysis.size == q_analysis.maxsize:
        return {"status": "Too many requests"}, 429

    try:
        # TODO: raise exception on non-standard game
        game = read_pgn(StringIO(data["pgn"]))
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)

    except Exception:
        return {"status": "Invalid PGN", "info": data["pgn"]}, 400

    else:
        # old_info = engine.info(fen, only_best=True, max_depth=0)
        # if old_info and old_info[0]["depth"] > 35:
        #     return {"status": "Request denied.", "info": "cached data depth is deemed good enough."}, 403

        q_analysis.add(board.epd())
        return {"status": "OK"}, 200


if __name__ == "__main__":
    app.run(**FLASK_CONFIG)
