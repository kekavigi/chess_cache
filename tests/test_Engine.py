import pytest
from chess import Board

from chess_cache.core import Engine


def create_engine(database_path: str) -> Engine:
    engine = Engine(engine_path="engine/stockfish", database_path=database_path)
    engine.set_options(
        {
            "EvalFile": "engine/nn-1c0000000000.nnue",
            "Threads": 4,
            "Hash": 1024,
        }
    )
    return engine


@pytest.fixture
def ae_file_empty(tmp_path):
    try:
        engine = create_engine(f"file:///{tmp_path}/test.sqlite")
        yield engine
    except:
        raise
    finally:
        engine.shutdown()


def test_sanity(ae_file_empty):
    engine = ae_file_empty

    # Engine yang digunakan adalah Stockfish
    # baca baris pertama yang muncul di stdout
    text = engine._std_read().strip()
    assert "Stockfish" in text

    # Kita berhasil membuat database kosong
    result = engine.db.sql.execute("SELECT count(fen) AS total FROM board").fetchone()
    assert result["total"] == 0


# @pytest.mark.skip(reason="slow")
def test_cache_is_working(ae_file_empty):
    engine = ae_file_empty
    fen = Board().fen()

    engine.put(fen, depth=10)
    engine.wait()

    result = engine.info(fen, only_best=True, max_depth=20)
    assert len(result) == 1
    assert result[0]["depth"] == 10

    # depth yang disinggah tidak berubah jika ada
    # analisa dengan depth yang lebih kecil
    engine.put(fen, depth=5)
    engine.wait()

    result = engine.info(fen, only_best=True, max_depth=20)
    assert len(result) == 1
    assert result[0]["depth"] == 10

    # tapi berubah jika depthnya lebih besar
    engine.put(fen, depth=15)
    engine.wait()
    result = engine.info(fen, only_best=True, max_depth=20)
    assert len(result) == 1
    assert result[0]["depth"] == 15
    # ini ngga bisa diprediksi, kecuali depth=infinite
    # dan given more time, biar move_stack-nya stabil
    # assert len(result[0]["pv"]) >= 15


def test_batch_analysis(ae_file_empty):
    engine = ae_file_empty
    fens = [
        "rnbqkb1r/pppppppp/7n/8/8/5P1N/PPPPP1PP/RNBQKB1R b KQkq - 2 2",
        "rnbqkbnr/ppppp1pp/5p2/8/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 0 2",
        "rnbqkbnr/pppp1ppp/8/4p3/7P/3P4/PPP1PPP1/RNBQKBNR b KQkq - 0 2",
        "rnbqkbnr/pp1ppppp/2p5/8/8/P2P4/1PP1PPPP/RNBQKBNR b KQkq - 0 2",
        "rnbqkbnr/ppppp1pp/5p2/8/1P6/4P3/P1PP1PPP/RNBQKBNR b KQkq - 0 2",
        "rnbqkbnr/ppppp1pp/8/5p2/8/1P5N/P1PPPPPP/RNBQKB1R b KQkq - 0 2",
        "rnbqkbnr/1ppppppp/p7/8/4P3/7N/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
        "rnbqkbnr/pppp1ppp/8/4p3/6P1/5N2/PPPPPP1P/RNBQKB1R b KQkq - 1 2",
        "rnbqkbnr/ppppppp1/8/7p/8/3PP3/PPP2PPP/RNBQKBNR b KQkq - 0 2",
    ]
    for fen in fens:
        engine.put(fen, depth=10)
    engine.wait()

    for fen in fens:
        result = engine.info(fen, only_best=True, max_depth=20)
        assert len(result) == 1
        assert result[0]["depth"] == 10


def test_insane_config_on_empty(ae_file_empty):
    engine = ae_file_empty
    fen = Board().fen()
    engine.put(fen, depth=10, config={"MultiPV": 20})
    engine.wait()

    result = engine.info(fen, only_best=False, max_depth=20)
    assert len(result) >= 20
    assert result[0]["depth"] >= 10


def test_checkmate(ae_file_empty):
    engine = ae_file_empty
    fen = "rnbqkbnr/1ppppp2/p6p/6p1/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq g6 0 4"
    engine.put(fen, depth=20)
    engine.wait()

    result = engine.info(fen, only_best=True, max_depth=1)
    assert result
    movestack = result[0]["pv"]
    assert len(movestack) == 1

    result = engine.info(fen, only_best=False, max_depth=1)
    assert result
    movestack = result[0]["pv"]
    assert len(movestack) == 1


# TODO: test wrong config or wrong input to chess engine
