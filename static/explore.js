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
        event.chessboard.setPosition(game.fen(), true).then(updateStatus())
    }
    return true
})

function promotePawn(event, turn, move) {
    board.showPromotionDialog(event.squareTo, turn, (result) => {
        if (result && result.piece) {
            move.promotion = result.piece.charAt(1)
            game.move(move)
            board.setPiece(result.square, result.piece, true).then(updateStatus())
        } else {
            promotePawn(event, turn, move);
        }
    });
}

function requestAnalysis() {
    var xhttp = new XMLHttpRequest();
    xhttp.open("PUT", "/analyze");
    xhttp.setRequestHeader("Content-Type", "application/json; charset=UTF-8")
    const body = JSON.stringify({ pgn: game.pgn(), });
    xhttp.send(body);
}

function formSubmit(event) {
  var url = "/upload_pgn";
  var request = new XMLHttpRequest();
  request.open('PUT', url, true);
  request.onload = function() {
    console.log('nice', request.responseText);
  };
  request.onerror = function() {
    console.log('ohno', request.responseText);
  };

  // create FormData from form that triggered event
  request.send(new FormData(event.target));
  event.preventDefault();
}

function updateStatus() {
    var fen = game.fen();
    document.getElementById('fen').innerHTML = fen;
    document.getElementById('pgn').innerHTML = game.pgn().split(']').pop();

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
document.getElementById("upload_pgn").addEventListener("submit", formSubmit);
