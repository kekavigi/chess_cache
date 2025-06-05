# chess_cache

Ini adalah proyek saya menggabungkan mesin catur seperti Stockfish, dengan database yang menyinggah hasil analisa posisi, agar lebih efektif saat digunakan. Sebagai contoh alasan saya membuat ini: ketika Anda menggunakan antarmuka GUI seperti Nibbler atau EnCroissant, pernahkah Anda menghabiskan waktu lama menganalisa suatu posisi, lalu secara tidak sengaja menganalisa posisi lain (misal karena *mouse-slip*)? Malang sekali, waktu yang Anda habiskan terbuang percuma karena analisa yang Anda tunggu hilang, dan perlu diulang dari awal lagi. Contoh lain, Anda telah menghabiskan waktu menganalisa posisi di suatu program, tetapi tidak ada cara mudah menggunakan analisa Anda di program lain, *ugh*. Selain dua hal itu, saya juga penasaran, ingin membuat database yang berisi analisa semua posisi catur permainan standar; sesuatu yang tidak realistis, tapi apa salahnya mencoba? Saya juga ingin menggunakan proyek ini sebagai tempat berlatih menjadi developer yang baik.

Beberapa hal yang ingin dikembangkan:
* Unit test yang lebih banyak.
* Menggabungkan dua atau lebih database singgahan. Jika nama dan versi mesin catur yang digunakan sama (misal `Stockfish 17.1`), Ini seharusnya mudah: pilih `(multipv, fen)` dengan `depth` tertinggi di semua database (jika ada), untuk semua `(multipv, fen)`.
* Membuat antarmuka untuk melihat isi database singgahan dan mengelolanya (menjalankan `VACUUM`, menganalisis posisi secara manual, dsb.).

## Usaha terkait

* [github.com/r2dev2/ChessData](https://github.com/r2dev2/ChessData). *This is an in progress dataset which contains millions of positions with stockfish evaluations. Please help contribute evaluations of the positions to the repo. So far, we have 12958035 evaluations.* Di [dataset Kaggle terkait](https://www.kaggle.com/datasets/ronakbadhe/chess-evaluations), "This is the file which contains the positions and evaluations. The positions are given in FEN form and the evaluations are in centi-pawns and are generated from Stockfish 11 at depth 22.".

