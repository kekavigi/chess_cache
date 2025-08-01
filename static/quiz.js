import { Chess } from './libs/chess.js';
import { Chessboard, INPUT_EVENT_TYPE } from "./cb/Chessboard.js"
import { PromotionDialog } from "./cb/extensions/promotion-dialog/PromotionDialog.js"
import { Markers } from "./cb/extensions/markers/Markers.js"

var data = {};
var counter = 0;
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

        updateStatus()

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

function newQuiz() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            data = JSON.parse(xhttp.responseText);
            game = new Chess(data.fen)
            board.setPosition(data.fen)
            board.setOrientation(game.turn())

            document.getElementById('fen').innerHTML = data.fen;
            console.log(data)
        }
    };
    xhttp.open("POST", "/get_quiz?min=100&max=300", true);
    xhttp.send();
};

function updateStatus() {
    counter += 1
    console.log('solved', counter)
    newQuiz()
}

newQuiz()