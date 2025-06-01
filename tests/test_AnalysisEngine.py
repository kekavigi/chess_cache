import pytest
from time import sleep
from chess import Board

from chess_cache import AnalysisEngine

@pytest.fixture
def create_empty_ae(tmp_path):
    engine = None
    try:
        engine = AnalysisEngine(
            engine_path="engine/stockfish",
            database_path=f"{tmp_path}/data.sqlite",
            configs={
                "EvalFile": "engine/nn-1c0000000000.nnue",
            },
        )
        yield engine
    except:
        raise
    finally:
        engine.shutdown()


@pytest.fixture
def create_copy_ae(tmp_path):
    # TODO: salin data.sqlite ke tmp
    # TODO: gunakan config di importer.py
    ...


def test_sanity(create_empty_ae):
    engine = create_empty_ae

    # Engine yang digunakan adalah Stockfish
    # baca baris pertama yang muncul di stdout
    text = engine._std_read().strip()
    assert "Stockfish" in text

    # Kita berhasil membuat database kosong
    result = engine.db.db.execute("SELECT count(fen) AS total FROM board").fetchone()
    assert result["total"] == 0


def test_cache_is_working(create_empty_ae):
    engine = create_empty_ae
    board = Board()

    engine.start(board, depth=10)
    sleep(3)
    result = engine.info(board)
    assert len(result) == 1
    assert result[0]["depth"] == 10

    # depth yang disinggah tidak berubah jika ada
    # analisa dengan depth yang lebih kecil
    engine.start(board, depth=5)
    sleep(3)
    result = engine.info(board)
    assert len(result) == 1
    assert result[0]["depth"] == 10

    # tapi berubah jika depthnya lebih besar
    engine.start(board, depth=15)
    sleep(3)
    result = engine.info(board, with_move=True)
    assert len(result) == 1
    assert result[0]["depth"] == 15
    assert len(result[0]["pv"]) >= 15


# TODO: test kasus checkmate
# TODO: dengan create_copy_ae, check true_multipv
