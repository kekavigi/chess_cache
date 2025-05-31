import fileinput
import os
from functools import partial
from io import StringIO
from time import sleep
# from tqdm import tqdm

from chess import Board
from chess.pgn import read_game

from chess_cache import AnalysisEngine

MAX_FULLMOVE = 6
MULTIPV = 1
TRUE_MULTIPV = True
MINIMAL_DEPTH = 34
WAIT_TIME = 20

# dapatkan daftar pgn; lalu sort
list_pgn = []
for line in fileinput.input():
    if line[0] == "1":
        list_pgn.append(line)
list_pgn.sort()


try:
    engine = AnalysisEngine(
        database_path="./data.sqlite",
        configs={
            "EvalFile": "nn-1c0000000000.nnue",
            "Threads": 4,
            "Hash": 2048,
            "MultiPV": MULTIPV,
        },
    )
    get_info = partial(engine.info, multipv=MULTIPV, true_multipv=TRUE_MULTIPV)

    I = len(list_pgn)
    for i, line in enumerate(list_pgn):

        # reverse analysis
        game = read_game(StringIO(line))
        assert game is not None

        board = Board()
        for move in game.mainline_moves():
            board.push(move)
            if board.fullmove_number > MAX_FULLMOVE:
                break

        #if board.move_stack[0].uci() != "e2e4":
        #    board = Board()  # .reset_board()
        #    continue

        while board.move_stack:
            depths = [_["depth"] for _ in get_info(board)]
            if len(depths) < MULTIPV or any(
                _ < MINIMAL_DEPTH for _ in depths
            ):
                os.system('clear')
                print(f"{i}/{I} ({100*i/I:.2f})", " ".join(_.uci() for _ in board.move_stack))
                engine.start(board)
                while True:
                    # sanity check jumlah multipv
                    sleep(WAIT_TIME)
                    depths = [_["depth"] for _ in get_info(board)]
                    print(depths)

                    if all(_ >= MINIMAL_DEPTH for _ in depths):
                        break
            board.pop()

except KeyboardInterrupt:
    print("\ninterrupted!")
finally:
    print("shutting down")
    engine.shutdown()
