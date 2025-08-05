import asyncio
from contextlib import asynccontextmanager
from io import StringIO
from typing import AsyncIterator

from chess import Board
from chess.pgn import read_game as read_pgn
from starlette.applications import Starlette
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from chess_cache import STARTING_FEN, Engine
from chess_cache.core import decode_fen
from chess_cache.env import (
    ANALYSIS_DEPTH,
    DATABASE_URI,
    ENGINE_BASE_CONFIG,
    ENGINE_MAIN_CONFIG,
    ENGINE_PATH,
    IMPORTER_PGN_DEPTH,
    MINIMAL_DEPTH,
)
from chess_cache.importer import extract_fens

ENGINE_CONFIG = ENGINE_BASE_CONFIG.copy()
ENGINE_CONFIG.update(ENGINE_MAIN_CONFIG)

engine = Engine(ENGINE_PATH, DATABASE_URI, minimal_depth=MINIMAL_DEPTH)
templates = Jinja2Templates(directory="templates")


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    # on start
    engine.set_options(ENGINE_CONFIG)

    yield None

    # on shutdown
    engine.shutdown()


async def stats(request: Request) -> JSONResponse:
    "Menghasilkan statistik mengenai program"

    return JSONResponse({"queue": engine.heap.qsize()})


async def evaluation(request: Request) -> JSONResponse:
    "Menghasilkan analisa suatu posisi"

    fen = request.query_params.get("fen")
    if not fen:
        return JSONResponse({"error": "Empty FEN"}, 400)
    try:
        board = Board(fen)
    except ValueError:
        return JSONResponse({"error": "Invalid FEN", "info": fen}, 400)

    results = engine.info(board.epd(), max_depth=10)
    notation = request.query_params.get("notation", "uci")
    if notation == "san":
        for info in results:
            board.set_fen(fen)
            movestack = info.pop("pv")
            info["pv"] = []
            for uci in movestack:
                san = board.san(board.parse_uci(uci))
                info["pv"].append(san)
                board.push_uci(uci)
    return JSONResponse({"fen": fen, "pvs": results})


async def analyze(request: Request) -> JSONResponse:
    "Menganalisa posisi yang direpresentasikan dengan notasi PGN"

    if engine.is_full():
        return JSONResponse({"error": "Too many requests"}, 429)

    # TODO: handle DDoS untuk body/PGN berukuran besar
    body = await request.json()
    if "pgn" not in body or not body["pgn"]:
        return JSONResponse({"error": "Empty PGN"}, 400)
    try:
        game = read_pgn(StringIO(body["pgn"]))
        assert game is not None
    except Exception:
        return JSONResponse({"error": "Failed parsing PGN"}, 400)

    board = game.board()
    if board.fen() != STARTING_FEN:
        return JSONResponse(
            {
                "error": "The game is assumed to be non-standard",
                "info": "Invalid starting position",
            },
            400,
        )
    try:
        for move in game.mainline_moves():
            board.push(move)
    except Exception:
        return JSONResponse(
            {
                "error": "The game is assumed to be non-standard",
                "info": "Invalid move stack",
            },
            400,
        )

    fen = board.epd()
    analysis = engine.info(fen, only_best=True, max_depth=0)
    if analysis and analysis[0]["depth"] > 35:
        return JSONResponse(
            {
                "error": "Request denied",
                "info": "cached data depth is deemed good enough.",
            },
            403,
        )

    engine.put(fen, ANALYSIS_DEPTH, priority=100)
    return JSONResponse({"status": "OK"})


async def parse_pgn(request: Request) -> JSONResponse:
    "Menganalisa semua posisi yang memenuhi syarat di berkas PGN"

    async with request.form(max_files=1) as form:
        file = form.get("file")
        if not isinstance(file, UploadFile):
            return JSONResponse({"error": "No file"}, 400)
        try:
            pgn = (await file.read()).decode("utf-8")
        except:
            return JSONResponse({"error": "unable to parse file"}, 415)

        fens = await asyncio.to_thread(extract_fens, pgn, IMPORTER_PGN_DEPTH)
        for fen in fens:
            engine.put(fen, ANALYSIS_DEPTH)
        return JSONResponse({"status": "OK"})


async def get_quiz(request: Request) -> JSONResponse:
    "Menghasilkan suatu posisi catur acak dan daftar solusi terbaiknya"

    try:
        _depth = 35
        _min = int(request.query_params.get("min", 100))
        _max = int(request.query_params.get("max", 300))
        assert _min < _max
    except (AssertionError, ValueError):
        return JSONResponse({"error": "Invalid query param(s) usage"}, 400)
    else:
        _fen = engine.db.sql.execute(
            """
            SELECT fen FROM board
            WHERE depth=:depth AND score >= :min AND score <= :max
            ORDER BY RANDOM() LIMIT 1
            """,
            {"min": _min, "max": _max, "depth": _depth},
        ).fetchone()

    if not _fen:
        # no eligible fen
        return JSONResponse({})

    fen = decode_fen(_fen["fen"])
    answers = [engine.info(fen, only_best=True)[0]["pv"][0]]
    # TODO: urus kasus ada beberapa PV bagus
    # TODO: urus kasus PV punya depth yang berbeda-beda

    return JSONResponse({"fen": fen, "answers": answers})


async def t_chessboard(request: Request):
    return templates.TemplateResponse(
        request, "explore.html", context={"initial_fen": STARTING_FEN}
    )


async def t_quiz(request: Request):
    # TODO: bikin token; simpan dalam bentuk db sqlite cache TTL 1 menit or bust.
    return templates.TemplateResponse(request, "quiz.html")


routes = [
    Route("/stats", endpoint=stats),
    Route("/eval", endpoint=evaluation),
    Route("/analyze", endpoint=analyze, methods=["PUT"]),
    Route("/upload_pgn", endpoint=parse_pgn, methods=["PUT"]),
    Route("/get_quiz", endpoint=get_quiz, methods=["POST"]),
    Route("/explore", endpoint=t_chessboard),
    Route("/quiz", endpoint=t_quiz),
    Mount("/static", app=StaticFiles(directory="static"), name="static"),
]

app = Starlette(lifespan=lifespan, routes=routes)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
