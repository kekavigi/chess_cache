#!/home/user/.pyenv/shims/python

import atexit
import os
from heapq import heappop, heappush
from io import StringIO
from threading import Thread
from time import sleep

from chess import Board
from chess.pgn import read_game as read_pgn
from flask import Flask, g, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from chess_cache.core import STARTING_FEN, AnalysisEngine
from chess_cache.env import Env
from chess_cache.importer import extract_fens
from chess_cache.logger import get_logger

env = Env(".env")
logger = get_logger("flask")

FLASK_CONFIG = env.get("FLASK_CONFIG", {})
ENGINE_PATH = env.get("ENGINE_PATH", "stockfish")
DATABASE_URI = env.get("DATABASE_URI", ":memory:")
ANALYSIS_DEPTH = env.get("ANALYSIS_DEPTH", 35)

IMPORTER_PGN_DEPTH = env.get("IMPORTER_PGN_DEPTH", 50)
ENGINE_CONFIG_MAIN = env.get("ENGINE_CONFIG", {})
ENGINE_CONFIG_MISC = env.get("IMPORTER_ENGINE_CONFIG", ENGINE_CONFIG_MAIN)


class Queue:
    def __init__(self):
        "Memroses semua permintaan analisa posisi catur sesuai prioritasnya"

        self.engine = AnalysisEngine(ENGINE_PATH, DATABASE_URI, ENGINE_CONFIG_MAIN)
        self.heap = []
        self._quit = False
        self._thread = Thread(target=self._process, daemon=True)
        self._thread.start()

    def put(self, fen: str, priority: int = 0):
        heappush(self.heap, (-priority, fen))

    def _process(self):
        while not self._quit:
            if not self.heap:
                sleep(1)
                continue

            priority, fen = heappop(self.heap)
            analysis = self.engine.info(fen, only_best=True, max_depth=0)
            if analysis and analysis[0]["depth"] >= ANALYSIS_DEPTH:
                continue

            priority = -1 * priority
            logger.info("Menganalisa", extra={"fen": fen, "priority": priority})
            self.engine.start(
                fen,
                ANALYSIS_DEPTH,
                ENGINE_CONFIG_MAIN if priority > 0 else ENGINE_CONFIG_MISC,
            )
            self.engine.wait()

    def is_full(self, n: int = 10):
        heap, L = self.heap, len(self.heap)

        def count():
            # Hitung banyaknya non-background task di heap
            if i >= L or heap[i] == 0:
                return 0
            return 1 + count(2 * i + 1) + count(2 * i + 2)

        return count() >= n

    def shutdown(self):
        self.engine.stop()
        self._thread.join(timeout=3)
        self.engine.shutdown()
        logger.info("Nice")


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1000 * 1000

queue = Queue()
atexit.register(queue.shutdown)


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
    return {"analysis_queue": len(queue.heap)}


@app.get("/uv/info/<path:fen>")
def uv_get_info(fen):
    try:
        board = Board(fen)
    except ValueError:
        return {"status": "Invalid FEN", "info": fen}, 400

    try:
        results = queue.engine.info(board.epd(), max_depth=10)
        for info in results:
            board.set_fen(fen)
            movestack = info.pop("pv")
            info["pv"] = []
            for uci in movestack:
                san = board.san(board.parse_uci(uci))
                info["pv"].append(san)
                board.push_uci(uci)
    except:
        logger.exception("Something went wrong")
        raise

    return results


@app.post("/uv/upload_pgn")
def uv_parse_pgn():
    if "file" not in request.files:
        return {"status": "tidak ada file"}, 400

    file: flask.Request.files = request.files["file"]
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
            queue.put(fen)
        return {
            "status": "OK",
            "info": f"Berhasil mengekstrak {len(fens)} posisi",
        }, 200


@app.post("/uv/analysis")
def uv_process_analysis():
    data = request.get_json()
    if "pgn" not in data:
        return {"status": "invalid POST request", "info": "No pgn data"}, 400
    if queue.is_full():
        return {"status": "Too many requests"}, 429
    try:
        # TODO: raise exception on non-standard game
        game = read_pgn(StringIO(data["pgn"]))
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)
    except Exception:
        return {"status": "Invalid PGN", "info": data["pgn"]}, 400

    analysis = engine.info(fen, only_best=True, max_depth=0)
    if analysis and analysis[0]["depth"] > 35:
        return {
            "status": "Request denied.",
            "info": "cached data depth is deemed good enough.",
        }, 403

    queue.put(board.epd(), priority=100)
    return {"status": "OK"}, 200


if __name__ == "__main__":
    app.run(**FLASK_CONFIG)
