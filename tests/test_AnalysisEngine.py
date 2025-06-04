import os
from shutil import copyfile
from time import sleep

import pytest
from chess import Board

from chess_cache import AnalysisEngine


def create_engine(database_path: str) -> AnalysisEngine:
    return AnalysisEngine(
        engine_path="engine/stockfish",
        database_path=database_path,
        configs={
            "EvalFile": "engine/nn-1c0000000000.nnue",
            "Threads": 4,
            "Hash": 1024,
        },
    )


@pytest.fixture
def ae_file_empty(tmp_path):
    try:
        engine = create_engine(f"{tmp_path}/test.sqlite")
        yield engine
    except:
        raise
    finally:
        engine.shutdown()


@pytest.fixture
def ae_file_full(tmp_path):
    try:
        copyfile("data.sqlite", f"{tmp_path}/test.sqlite")
        engine = create_engine(f"{tmp_path}/test.sqlite")
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

    engine.start(fen, depth=10)
    sleep(2)
    result = engine.info(fen)
    assert len(result) == 1
    assert result[0]["depth"] == 10

    # depth yang disinggah tidak berubah jika ada
    # analisa dengan depth yang lebih kecil
    engine.start(fen, depth=5)
    sleep(2)
    result = engine.info(fen)
    assert len(result) == 1
    assert result[0]["depth"] == 10

    # tapi berubah jika depthnya lebih besar
    engine.start(fen, depth=15)
    sleep(2)
    result = engine.info(fen, with_move=True)
    assert len(result) == 1
    assert result[0]["depth"] == 15
    # ini ngga bisa diprediksi, kecuali depth=infinite
    # dan given more time, biar move_stack-nya stabil
    # assert len(result[0]["pv"]) >= 15


# TODO: test kasus checkmate
# TODO: dengan create_copy_ae, check true_multipv
