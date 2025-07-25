import os
from shutil import copyfile
from time import sleep

import pytest
from chess import Board

from chess_cache.core import STARTING_FEN, Database, Engine
from chess_cache.env import Env

env = Env()


@pytest.fixture
def db_file(tmp_path):
    try:
        db = Database(f"file:///{tmp_path}/test.sqlite")
        yield db
    except:
        raise
    else:
        db.close()


@pytest.fixture
def db_memory_empty():
    try:
        db = Database(":memory:")
        yield db
    except:
        raise
    else:
        db.close()


@pytest.fixture
def db_memory_full(db_memory_empty):
    test_db = db_memory_empty
    stt = """
        INSERT INTO board (fen, depth, score, move)
        VALUES (:fen, :depth, :score, :move)
    """
    try:
        true_db = Database("lichess.sqlite")
        with test_db.sql as conn:
            for row in true_db.sql.execute("SELECT * FROM board LIMIT 10").fetchall():
                conn.execute(stt, row)
    except:
        raise
    else:
        true_db.close()

    return test_db


def test_sanity(db_file, db_memory_full):
    print(
        db_file.sql.execute(
            'SELECT file FROM pragma_database_list WHERE name="main"'
        ).fetchone()
    )

    assert db_file._is_memory == False
    assert db_memory_full._is_memory == True


def test_sanity2(db_memory_empty):
    db = db_memory_empty
    info = {"multipv": 1, "depth": 100, "score": 42, "move": ["d2d4", "e7e5", "h8h8"]}
    with pytest.raises(ValueError):
        db.upsert(STARTING_FEN, info)
    result = db.sql.execute("SELECT COUNT(*) AS total FROM board").fetchone()
    assert result["total"] == 0


def test_to_json(db_memory_full):
    db = db_memory_full
    cur = db.sql.execute("SELECT COUNT(*) AS total FROM board")
    total = cur.fetchone()["total"]

    data = db.to_json()
    assert len(data) == total


def test_from_json(db_memory_empty, db_memory_full):
    db_empty = db_memory_empty
    db_full = db_memory_full

    data_from = db_full.to_json()
    db_empty.from_json(data_from)
    data_dest = db_empty.to_json()
    assert data_from == data_dest

    data_from[0]["depth"] = 0
    db_empty.from_json(data_from)
    assert db_empty.to_json() == data_dest

    data_from[0]["depth"] = 100
    db_empty.from_json(data_from)
    assert db_empty.to_json() != data_dest


def test_reset_db(db_file, db_memory_full):
    with pytest.raises(RuntimeError):
        db_file.reset_db()

    db_memory_full.reset_db()
    cur = db_memory_full.sql.execute("SELECT COUNT(*) AS total FROM board")
    assert cur.fetchone()["total"] == 0


def test_normalize_old_data():
    try:
        ae = Engine(engine_path=env.get("ENGINE_PATH"), database_path=":memory:")

        DEPTH = 20
        ae.put(STARTING_FEN, DEPTH)
        ae.wait()

        results = ae.db.sql.execute("SELECT depth FROM board").fetchall()
        results = set(_["depth"] for _ in results)
        assert results == set(range(1, DEPTH + 1))

        ae.db.normalize_old_data(cutoff_score=15, new_score=13)

        results = ae.db.sql.execute("SELECT depth FROM board").fetchall()
        results = set(_["depth"] for _ in results)
        assert results == set(range(1, 15 + 1))

    finally:
        ae.shutdown()


def test_minimal_depth():
    try:
        DEPTH = 20
        MINIMAL_DEPTH = 10

        ae = Engine(
            engine_path=env.get("ENGINE_PATH"),
            database_path=":memory:",
            database_configs={"minimal_depth": 10},
        )
        ae.put(STARTING_FEN, DEPTH)
        ae.wait()

        results = ae.db.sql.execute("SELECT depth FROM board").fetchall()
        results = set(_["depth"] for _ in results)
        assert results == set(range(MINIMAL_DEPTH, DEPTH + 1))

    finally:
        ae.shutdown()


# TODO: simultaneous upsert from different thread
