from pprint import pprint

from flask import Flask, request

from chess_cache import Database
from importer import Todo

app = Flask(__name__)
todo = Todo()
db = Database("data.sqlite")

TARGET_DEPTH = 24
AUTH_TOKENS = ["test123"]


@app.get("/")
def index():
    return "<p style='font-family:sans-serif'>Hello world</p>"


@app.get("/cc")
def get_fens():
    fens = []

    for fen in todo.random(10):
        info = db.select(fen)
        if info is None or info["depth"] < TARGET_DEPTH:
            fens.append(fen)

    return {"depth": TARGET_DEPTH, "fens": fens, "config": {}}


@app.post("/cc")
def get_results():
    data = request.get_json()
    if "auth" not in data or data["auth"] not in AUTH_TOKENS:
        return {"status": "failed auth"}, 403

    if "data" in data:
        results = data["data"]
        db.from_json(results)

    return {"status": "success"}, 200


if __name__ == "__main__":
    app.run(port=9900)
