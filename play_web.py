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

from chess_cache.core import AnalysisEngine
from chess_cache.env import load_config

CONFIG = load_config("config.shared.toml")


class AnalysisQueue:
    def __init__(self, qsize: int, engine: AnalysisEngine, max_depth: int):
        self.q = deque(maxlen=qsize)
        self.engine = engine
        self.depth = max_depth
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
                print(fen)
                engine.start(fen, depth=35, config=CONFIG["engine"]["config"])
                self.engine.wait()
            else:
                sleep(1)

    def shutdown(self):
        self._quit = True
        self.thread.join()

    def add(self, fen: str):
        self.q.append(fen)
        self.size += 1


app = Flask(__name__)
engine = AnalysisEngine(**CONFIG["engine"])

q_analysis = AnalysisQueue(qsize=64, engine=engine, max_depth=35)
atexit.register(q_analysis.shutdown)

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

@app.get("/explore")
def explore():
    return render_template("explore.html")


@app.get("/info/<path:fen>")
def get_info(fen):
    try:
        board = Board(fen)  # TODO: optimalkan cara cek keabsahan FEN
    except ValueError:
        return {"status": "Invalid FEN", "info": fen}, 400
    else:
        return engine.info(fen, max_depth=10)

@app.get('/stats')
def stats():
    return {
        'analysis_queue' : list(q_analysis.q)
    }


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
    try:
        board = Board()  # assume standard game position
        game = read_pgn(StringIO(data["pgn"]))
        for move in game.mainline_moves():
            board.push(move)
    except Exception:
        return {"status": "Invalid PGN", "info": data['pgn']}, 400
    else:
        # old_info = engine.info(fen, only_best=True, max_depth=0)
        # if old_info and old_info[0]["depth"] > 35:
        #     return {"status": "Request denied.", "info": "cached data depth is deemed good enough."}, 403
        if q_analysis.size == q_analysis.maxsize:
            return {"status": "Too many requests"}, 429
        q_analysis.add(board.epd())

        return {"status": "OK"}, 200


if __name__ == "__main__":
    app.run(**CONFIG["play_web"].get("flask", {}))
