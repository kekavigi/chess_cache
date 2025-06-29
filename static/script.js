import { Chess } from './libs/chess.js';

var board = null
var game = null

function onDragStart(source, piece, position, orientation) {
    // do not pick up pieces if the game is over
    if (game.isGameOver()) return false

    // only pick up pieces for the side to move
    if ((game.turn() === 'w' && piece.search(/^b/) !== -1) ||
        (game.turn() === 'b' && piece.search(/^w/) !== -1)) {
        return false
    }
}

function onDrop(source, target) {
    // see if the move is legal
    var promotion = 'q';
    try {
        game.move({ from: source, to: target, promotion: promotion })
    } catch (error) {
        return 'snapback'
    }
    game.undo()

    var qualified = (target[1] === '1' || target[1] === '8') && game.get(source).type === 'p';
    if (qualified) promotion = prompt('promote to?', 'q');
    game.move({ from: source, to: target, promotion: promotion })

    updateStatus()
}

// update the board position after the piece snap
// for castling, en passant, pawn promotion
function onSnapEnd() {
    board.position(game.fen())
}

function takeBack() {
    game.undo();
    board.position(game.fen());
    updateStatus();
}

function requestAnalysis() {
    var xhttp = new XMLHttpRequest();
    xhttp.open("POST", "/uv/analysis");
    xhttp.setRequestHeader("Content-Type", "application/json; charset=UTF-8")
    const body = JSON.stringify({
        pgn: game.pgn(),
    });
    xhttp.send(body);
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
            for (var info of results) {
                _html += "<li>";
                _html += "<b>depth " + info.depth + "</b> ";
                _html += "score " + (info.score >= 0 ? '+' : '') + (info.score / 100).toFixed(2) + " ";
                _html += "<em>moves: " + info.pv.map(item => `<span>${item}</span>`).join(' ') + "</em></li>";
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

var config = {
    pieceTheme: '/static/img/chesspieces/wikipedia/{piece}.png',
    draggable: true,
    position: initial_fen,
    onDragStart: onDragStart,
    onDrop: onDrop,
    onSnapEnd: onSnapEnd
};

board = Chessboard('myBoard', config);
game = new Chess(initial_fen);

updateStatus();

document.getElementById("flip").addEventListener('click', () => { board.flip() });
document.getElementById("undo").addEventListener('click', () => { takeBack() });
document.getElementById("analyze").addEventListener('click', () => { requestAnalysis() });
document.getElementById("refresh").addEventListener('click', () => { updateStatus() });
