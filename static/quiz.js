import { Chess } from './libs/chess.js';
import { Chessboard, INPUT_EVENT_TYPE } from "./cb/Chessboard.js"
import { PromotionDialog } from "./cb/extensions/promotion-dialog/PromotionDialog.js"
import { Markers } from "./cb/extensions/markers/Markers.js"

var data = {};
var game = new Chess();
var board = new Chessboard(document.getElementById("myBoard"), {
    position: data.fen,
    assetsUrl: "/static/cb/assets/",
    style: { pieces: { file: "pieces/standard.svg" } },
    extensions: [{ class: PromotionDialog }, { class: Markers }]
})

board.enableMoveInput((event) => {
    if (event.type === INPUT_EVENT_TYPE.validateMoveInput) {
        var move = { from: event.squareFrom, to: event.squareTo, promotion: 'q' }
        try { game.move(move) }
        catch (error) { return false }

        var ispromo = event.squareTo.charAt(1) == '1' || event.squareTo.charAt(1) == 8
        var ispawn = event.piece.charAt(1) === "p"
        if (ispromo && ispawn) {
            game.undo()
            promotePawn(event, game.turn(), move);
        }

        var solution = data.answers[0]
        var submitted = move.from + move.to + (solution.length == 4 ? '' : move.promotion)
        if (submitted != solution) {
            game.undo()
            return false
        }

        new_quiz()

    } else if (event.type === INPUT_EVENT_TYPE.moveInputFinished) {
        event.chessboard.setPosition(game.fen(), true)
    }
    return true
})

function promotePawn(event, turn, move) {
    board.showPromotionDialog(event.squareTo, turn, (result) => {
        if (result && result.piece) {
            move.promotion = result.piece.charAt(1)
            game.move(move)
            board.setPiece(result.square, result.piece, true)
        } else {
            promotePawn(event, turn, move);
        }
    });
}

function new_quiz() {
    var xhttp = new XMLHttpRequest();
    var score_min = document.getElementById('minima').value
    var score_max = document.getElementById('maxima').value

    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            data = JSON.parse(xhttp.responseText);
            game = new Chess(data.fen)
            board.setPosition(data.fen)
            board.setOrientation(game.turn())

            document.getElementById('fen').innerHTML = data.fen;
            console.log(data.answers)

            get_analysis(data.fen);
        }
    };
    xhttp.open("POST", "/get_quiz?min=" + score_min + "&max=" + score_max, true);
    xhttp.send();
};

function get_analysis(fen) {
    // info multipv
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var results = JSON.parse(xhttp.responseText);
            var _html = "";
            for (var info of results.pvs) {
                _html += "<li>";
                _html += "<b title='depth'>" + info.depth + "</b> ";
                _html += "<span title='score'>" + (info.score >= 0 ? '+' : '') + (info.score / 100).toFixed(2) + "</span> ";
                _html += "<em title='pv'>" + info.pv.map(item => `<span>${item}</span>`).join(' ') + "</em></li>";
            }
            document.getElementById("info").innerHTML = _html;
        }
    };
    xhttp.open("GET", "/eval?notation=san&fen=" + encodeURIComponent(fen), true);
    xhttp.send();
}

function formSubmit(event) {
    // TODO: handle invalid input
    event.preventDefault();
    new_quiz()
}

new_quiz()
document.getElementById("config").addEventListener("submit", formSubmit);
