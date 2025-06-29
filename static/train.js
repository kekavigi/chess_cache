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

    getComputerResponse();
}

function getComputerResponse() {
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function () {
        if (this.readyState == 4 && this.status == 200) {
            var results = JSON.parse(xhttp.responseText);
            if (results.length == 0) {
                document.getElementById("info").innerHTML = 'no more moves in database!';
            }
            else {
                results = results.map(info => info['pv'][0])
                var random = Math.floor(Math.random() * Math.min(results.length, 5));
                game.move(results[random])
                updateStatus()
                setTimeout(function(){ board.position(game.fen()); }, 10);
            }
        }
    };
    xhttp.open("GET", "/uv/info/" + game.fen(), true);
    xhttp.send();
}

function onSnapEnd() {
    board.position(game.fen())
}

function takeBack() {
    game.undo();
    game.undo();
    board.position(game.fen());
    updateStatus();
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
                _html += "<b>" + info.depth + "</b> ";
                _html += "" + (info.score >= 0 ? '+' : '') + (info.score / 100).toFixed(2) + " ";
                _html += "<em>" + info.pv.map(item => `<span>${item}</span>`).join(' ') + "</em></li>";
            }
            document.getElementById("info").innerHTML = _html;
        }
    };
    xhttp.open("GET", "/uv/info/" + fen, true);
    xhttp.send();
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

document.getElementById("undo").addEventListener('click', () => { takeBack() });
