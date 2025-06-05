import requests

from chess_cache import AnalysisEngine

URL = "https://test.kekavigi.xyz/cc"
AUTH_TOKEN = "test123"

engine = AnalysisEngine(
    engine_path="engine/stockfish",
    database_path=":memory:",
    configs={
        "EvalFile": "engine/nn-1c0000000000.nnue",
        "Threads": 4,
        "Hash": 1024,
    },
)


def main():
    req = requests.post(URL, json={"auth": AUTH_TOKEN})
    if req.status_code != 200:
        raise ConnectionRefusedError("wrong auth or server is died")

    while True:
        # get task
        print('requesting...')
        req = requests.get(URL)
        data = req.json()
        if not data or not data["fens"]:
            break  # nothing to do

        print('solving...')
        engine.start(data["fens"], depth=data["depth"], config=data["config"])
        engine.wait(delta=3)

        results = engine.db.to_json()
        engine.db.reset_db()

        print('uploading...')
        req = requests.post(URL, json={"auth": AUTH_TOKEN, "data": results})
        if req.status_code != 200:
            raise ConnectionRefusedError("something went wrong.")


main()
