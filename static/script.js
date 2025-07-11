import { Chess } from './libs/chess.js';
import { Chessboard, INPUT_EVENT_TYPE } from "./cb/Chessboard.js"
import { PromotionDialog } from "./cb/extensions/promotion-dialog/PromotionDialog.js"
import { Markers } from "./cb/extensions/markers/Markers.js"

var game = new Chess(initial_fen)
var board = new Chessboard(document.getElementById("myBoard"), {
    position: initial_fen,
    assetsUrl: "/static/cb/assets/",
    style: { pieces: { file: "pieces/standard.svg" } },
    extensions: [{ class: PromotionDialog }, { class: Markers }]
})
board.enableMoveInput((event) => {
    console.log(event)
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

    } else if (event.type === INPUT_EVENT_TYPE.moveInputFinished) {
        updateStatus();
        console.log('updated!')
    }
    return true
})

function promotePawn(event, turn, move) {
    board.showPromotionDialog(event.squareTo, turn, (result) => {
        if (result && result.piece) {
            move.promotion = result.piece.charAt(1)
            game.move(move)

            board.setPiece(result.square, result.piece, true).then( () => {updateStatus()} )

        } else {
            promotePawn(event, turn, move);
        }
    });
}

function requestAnalysis() {
    var xhttp = new XMLHttpRequest();
    xhttp.open("POST", "/uv/analysis");
    xhttp.setRequestHeader("Content-Type", "application/json; charset=UTF-8")
    const body = JSON.stringify({ pgn: game.pgn(), });
    xhttp.send(body);
}

function updateStatus() {
    var fen = game.fen();
    console.log(fen)

    document.getElementById('fen').innerHTML = fen;
    document.getElementById('pgn').innerHTML = game.pgn().split(']').pop();

    // info multipv
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var results = JSON.parse(xhttp.responseText);
            var _html = "";
            for (var info of results) {
                _html += "<li>";
                _html += "<b title='depth'>" + info.depth + "</b> ";
                _html += "<span title='score'>" + (info.score >= 0 ? '+' : '') + (info.score / 100).toFixed(2) + "</span> ";
                _html += "<em title='pv'>" + info.pv.map(item => `<span>${item}</span>`).join(' ') + "</em></li>";
            }
            document.getElementById("info").innerHTML = _html;
        }
    };
    xhttp.open("GET", "/uv/info/" + fen, true);
    xhttp.send();

    // antrian analisa
    var xhttp_q = new XMLHttpRequest();
    xhttp_q.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var results = JSON.parse(xhttp_q.responseText);
            var _html = "";
            for (var fen of results['analysis_queue']) {
                _html += "<li>" + fen;
            }
            document.getElementById("queue").innerHTML = _html;
        }
    };
    xhttp_q.open("GET", "/uv/stats", true);
    xhttp_q.send();

}

updateStatus();

document.getElementById("flip").addEventListener('click', () => {
    board.setOrientation(board.getOrientation() === 'w' ? 'b' : 'w')
});
document.getElementById("undo").addEventListener('click', () => { 
    game.undo();
    board.setPosition(game.fen());
    updateStatus();
});
document.getElementById("analyze").addEventListener('click', () => { requestAnalysis() });
document.getElementById("refresh").addEventListener('click', () => { updateStatus() });