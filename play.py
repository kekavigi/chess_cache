import itertools
import re
import readline
from random import choice
from time import sleep
from typing import Any, TextIO

from chess import AmbiguousMoveError, Board, IllegalMoveError, InvalidMoveError
from rich import box, get_console, print
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.prompt import InvalidResponse, PromptBase, PromptType
from rich.table import Table
from rich.text import Text

from chess_cache import AnalysisEngine, Info

RE_COLORIZE = re.compile(r"([kqrnbp])")
PROG_CHOICE = ["", "SPOIL", "UNDO"]

BOOK_MOVE = 2
MULTIPV_USER = 3
MULTIPV_ENGINE = 7
MINIMAL_USER_DEPTH = 24
SCORE_CUTOFF = 100  # cp


class UserInput(PromptBase):
    response_type = str

    def __init__(
        self, *, console: Console | None = None, board_ref: Board | None = None
    ) -> None:
        self.console = console or get_console()
        self.prompt = Text.from_markup("input", style="prompt")
        self.password = False
        self.choices = PROG_CHOICE
        self.case_sensitive = True
        self.show_default = False
        self.show_choices = False
        self.board_ref = board_ref

    @classmethod
    def ask(
        cls,
        *,
        console: Console | None = None,
        board_ref: Board | None = None,
        default: Any = ...,
        stream: TextIO | None = None,
    ) -> Any:
        _prompt = cls(console=console, board_ref=board_ref)
        return _prompt(default=default, stream=stream)

    def process_response(self, value: str) -> PromptType:
        assert self.board_ref is not None

        value = value.strip()
        try:
            return_value: PromptType = self.response_type(value)
        except ValueError:
            raise InvalidResponse(self.validate_error_message)

        # apakah input berupa command?
        if value in self.choices:
            return return_value

        # apakah input berupa SAN?
        try:
            self.board_ref.parse_san(value)
        except (InvalidMoveError, IllegalMoveError, AmbiguousMoveError):
            raise InvalidResponse("[prompt.invalid]Invalid move, try again.")
        else:
            return return_value


def fetch(
    engine: AnalysisEngine, board: Board, cutoff: int | None = None
) -> list[Info]:
    # hanya hasilkan uci, score, depth yang bagus

    multipv = MULTIPV_USER if cutoff is not None else MULTIPV_ENGINE
    suggests = engine.info(board, multipv=multipv, true_multipv=False)
    if cutoff is None or not suggests:
        return suggests

    results: list[Info] = []
    tail = suggests[0]["score"]
    for info in suggests:
        if abs(info["score"] - tail) > cutoff:
            break  # cutoff, jangan sertakan pv ini
        tail = info["score"]
        results.append(info)
    return results


def request(engine: AnalysisEngine, board: Board, is_user: bool) -> None:
    depths = [info["depth"] for info in fetch(engine, board)]

    if is_user:  # and (not depths or min(depths) < MINIMAL_USER_DEPTH):
        engine.start(board, config={"MultiPV": MULTIPV_USER})
    elif not is_user:
        engine.start(board, config={"MultiPV": MULTIPV_ENGINE})


def display_board(board: Board) -> Panel:
    text = RE_COLORIZE.sub(r"[red]\1[/red]", board.__str__())
    return Panel.fit(text, title="board")


def display_movestack(board: Board) -> Panel:
    movestack = ""
    b = Board()
    for i, plies in enumerate(itertools.batched(board.move_stack, 2), start=1):
        white_, *black_ = plies
        white = b.san_and_push(white_)
        black = b.san_and_push(black_[0]) if black_ else ""  # type: str

        movestack += f"[bright_black]{i}[/bright_black]. {white} [red]{black}[/red] "
    return Panel(movestack, title="move stack")


def display_analysis_status(board: Board) -> Panel:
    suggests = fetch(engine, board)
    depths = [info["depth"] for info in suggests]
    scores = [f"{info['score']/100:+.2f}" for info in suggests]
    text = f"Info at depth {', '.join(str(_) for _ in depths)}, "
    text += f"each with score {', '.join(scores)}."
    return Panel.fit(text, title="status")


def display_suggestions(board: Board) -> Table:
    table = Table(title="suggestions", safe_box=True, box=box.ROUNDED)
    table.add_column("move", justify="center")
    table.add_column("score", justify="center")
    table.add_column("depth", justify="center")

    for info in fetch(engine, board, cutoff=SCORE_CUTOFF):
        san = board.san(board.parse_uci(info["pv"][0]))

        table.add_row(
            san,
            f"{info['score']/100:+.2f}",
            f"{info["depth"]}",
        )
    return table


def new_screen() -> tuple[Console, Layout]:
    layout = Layout()
    layout.split_row(
        Layout(name="board"),
        Layout(name="info"),
        Layout(name="suggests"),
    )
    layout["info"].split_column(
        Layout(name="status"),
        Layout(name="movestack"),
    )
    layout["board"].size = 19
    layout["info"].size = 120
    layout["info"]["status"].size = 3

    console = Console(height=10)
    return console, layout


def update_layout(layout: Layout, board: Board) -> None:
    layout["board"].update(display_board(board))
    layout["info"]["status"].update(display_analysis_status(board))
    layout["info"]["movestack"].update(display_movestack(board))
    layout["suggests"].update(display_suggestions(board))


console, layout = new_screen()
board = Board()
try:
    print("starting...")
    engine = AnalysisEngine(
        engine_path="engine/stockfish",
        database_path="data.sqlite",
        configs={
            "EvalFile": "engine/nn-1c0000000000.nnue",
            "Threads": 2,
            "Hash": 2048,
        },
    )

    while True:
        # user-to-move; as white
        request(engine, board, is_user=True)
        cmd_undo = False
        cmd_spoil = False
        feedback = ""

        while True:
            update_layout(layout, board)
            layout["suggests"].visible = cmd_spoil

            console.clear()
            console.print(layout)
            if feedback:
                print(feedback)

            suggests = fetch(engine, board, cutoff=SCORE_CUTOFF)
            _depths = [info["depth"] for info in suggests]

            user_input = UserInput.ask(board_ref=board)
            if user_input == "":
                cmd_spoil = False
                continue
            elif user_input == "SPOIL":
                cmd_spoil = True
                continue
            elif any(_ < MINIMAL_USER_DEPTH for _ in _depths):
                print("waiting for suggestions first.")
                sleep(1)
                continue
            elif user_input == "UNDO":
                board.pop()  # black
                board.pop()  # white
                cmd_undo = True
                break
            else:
                move = board.parse_san(user_input)

            # skip suggesting move in opening phase
            if board.fullmove_number <= BOOK_MOVE:
                break

            # update suggestion and check optimality
            suggests = fetch(engine, board, cutoff=SCORE_CUTOFF)
            moves = [info["pv"][0] for info in suggests]
            if move.uci() not in moves:
                feedback = "your move isn't optimal, try again"
                continue

            # nice move :)
            break

        cmd_spoil = False
        if cmd_undo:
            continue

        board.push(move)
        if board.is_checkmate():
            break

        # engine-to-move; as black
        print("calculating...")
        request(engine, board, is_user=False)
        possibles: list[str] = []
        while not possibles:
            sleep(3)
            possibles = [info["pv"][0] for info in fetch(engine, board)]
        board.push_uci(choice(possibles))
        if board.is_checkmate():
            break

except KeyboardInterrupt:
    print("\ninterrupted!")

finally:
    print("shutting down")
    engine.shutdown()
