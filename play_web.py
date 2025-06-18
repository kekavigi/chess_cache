import os
from flask import Flask, request, send_from_directory, g, render_template
from chess import Board

from chess_cache.core import Database

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = Database("file:lichess.sqlite?mode=ro")
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


###


@app.get("/")
def index():
    return render_template('index.html')


@app.get("/info/<path:fen>")
def get_info(fen):
    db = get_db()
    try:
        board = Board(fen)  # TODO: optimalkan cara cek keabsahan FEN
    except ValueError:
        return {"status": "Invalid FEN", "info": fen}, 400
    else:
        return db.select(fen, max_depth=10)


if __name__ == "__main__":
    app.run(port=9900)
