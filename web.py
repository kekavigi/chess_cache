from contextlib import asynccontextmanager
from io import StringIO

from chess import Board
from chess.pgn import read_game as read_pgn
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from chess_cache import STARTING_FEN, Engine, env, get_logger
from chess_cache.importer import extract_fens

ENGINE_PATH = env.get("ENGINE_PATH", "stockfish")
DATABASE_URI = env.get("DATABASE_URI", ":memory:")
ANALYSIS_DEPTH = env.get("ANALYSIS_DEPTH", 35)
MINIMAL_DEPTH = env.get("MINIMAL_DEPTH", 20)

IMPORTER_PGN_DEPTH = env.get("IMPORTER_PGN_DEPTH", 50)
ENGINE_CONFIG_MAIN = env.get("ENGINE_CONFIG", {})
ENGINE_CONFIG_MISC = env.get("IMPORTER_ENGINE_CONFIG", ENGINE_CONFIG_MAIN)


engine = Engine(ENGINE_PATH, DATABASE_URI, minimal_depth=MINIMAL_DEPTH)
templates = Jinja2Templates(directory="templates")


@asynccontextmanager
async def lifespan(app: Starlette):
    # on start
    engine.set_options(ENGINE_CONFIG_MAIN)

    yield

    # on shutdown
    engine.shutdown()


async def stats(request: Request):
    return JSONResponse({"queue": engine.heap.qsize()})


async def evaluation(request: Request):
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


async def analyze(request: Request):
    if engine.is_full():
        return JSONResponse({"error": "Too many requests"}, 429)

    # TODO: handle DDoS untuk body/PGN berukuran besar
    body = await request.json()
    if "pgn" not in body or not body["pgn"]:
        return JSONResponse({"error": "Empty PGN"}, 400)
    try:
        game = read_pgn(StringIO(body["pgn"]))
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

    engine.put(fen, ANALYSIS_DEPTH, priority=100, config=ENGINE_CONFIG_MAIN)
    return JSONResponse({"status": "OK"})


async def parse_pgn(request: Request):
    async with request.form(max_files=1) as form:
        file = form.get("file")
        if not file:
            return JSONResponse({"error": "No file"}, 400)
        try:
            pgn = (await file.read()).decode("utf-8")
        except:
            return JSONResponse({"error": "unable to parse file"}, 415)

        fens = await run_in_threadpool(extract_fens, pgn, IMPORTER_PGN_DEPTH)
        for fen in fens:
            engine.put(fen, ANALYSIS_DEPTH, config=ENGINE_CONFIG_MISC)
        return JSONResponse({"status": "OK"})


async def t_chessboard(request: Request):
    return templates.TemplateResponse(
        request, "explore.html", context={"initial_fen": STARTING_FEN}
    )


routes = [
    Route("/stats", endpoint=stats),
    Route("/eval", endpoint=evaluation),
    Route("/analyze", endpoint=analyze, methods=["POST"]),
    Route("/upload_pgn", endpoint=parse_pgn, methods=["POST"]),
]

routes += [
    Route("/explore", endpoint=t_chessboard),
    Mount("/static", app=StaticFiles(directory="static"), name="static"),
]

app = Starlette(lifespan=lifespan, routes=routes)
