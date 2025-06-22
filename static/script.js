var board = null
var game = new Chess()
var $fen = $('#fen')
var $pgn = $('#pgn')

function onDragStart(source, piece, position, orientation) {
    // do not pick up pieces if the game is over
    if (game.game_over()) return false

    // only pick up pieces for the side to move
    if ((game.turn() === 'w' && piece.search(/^b/) !== -1) ||
        (game.turn() === 'b' && piece.search(/^w/) !== -1)) {
        return false
    }
}

function onDrop(source, target) {
    // see if the move is legal
    var promotion = 'q';
    var check = game.move({ from: source, to: target, promotion: promotion })
    if (check === null) return 'snapback'
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
        fen: game.fen(),
    });
    xhttp.send(body);
}

function updateStatus() {
    var fen = game.fen();

    $fen.html(fen)
    $pgn.html(game.pgn())

    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var results = JSON.parse(xhttp.responseText);
            var _html = "<ol>";
            for (var info of results) {
                _html += "<li>";
                _html += "<b>depth " + info.depth + "</b> ";
                _html += "score " + (info.score >= 0 ? '+' : '') + (info.score / 100).toFixed(2) + " ";
                _html += "<em>moves: " + info.pv.map(item => `<span>${item}</span>`).join(' ') + "</em></li>";
            }
            _html += '</ol>'
            document.getElementById("info").innerHTML = _html;
        }
    };
    xhttp.open("GET", "/uv/info/" + fen, true);
    xhttp.send();
}

var config = {
    pieceTheme: 'static/img/chesspieces/wikipedia/{piece}.png',
    draggable: true,
    position: 'start',
    onDragStart: onDragStart,
    onDrop: onDrop,
    onSnapEnd: onSnapEnd
}
board = Chessboard('myBoard', config)

updateStatus()