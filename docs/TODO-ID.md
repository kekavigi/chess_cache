# Todo

Ada beberapa hal yang ingin saya kembangkan:
* versi web dari *play_cli.py*
	* Undo dan reset
	* Popup on hover
	* Train with computer
* Buat metode penyinggahan?
	* TLRU/TRU/LRU menggunakan SQLite
* Optimasi kode
	1. Buat `decode_efen()`
	2. Buat test untuk starting pos, white-to-move dan black-to-move, berbagai castling, berbagai en-passant, kombinasinya. Gunakan fen di `lichess.sqlite` sebagai sanity check tambahan?
	3. Buat alternatif `chess.Board`, mungkin dengan ide dari [snakefish](https://github.com/cglouch/snakefish); karena `chess.Board` sangat lambat! 95% waktu di `Database.upsert()` digunakan oleh `board.fen()` dan `board.push_uci()`.
	4. Test test dan test! `perft` dll, gunakan data di `lichess.sqlite` sebagai sanity check tambahan? Pastikan cara kita signifikan lebih cepat daripada `chess.Board`.
	5. Update/integrasikan `encode_fen()` agar menggunakan alternatif kita, jika bisa; Pastikan cara kita signifikan lebih cepat daripada `chess.Board`.
	6. Update/integrasikan alternatif kita ke seluruh `core.py`

Lainnya:
* Unit test yang lebih banyak.
* Menggabungkan dua atau lebih database singgahan.
	* Jika nama mesin catur yang digunakan sama (misal `Stockfish`), dan satu database *strictly* berisi analisa oleh versi mesin yang lebih tinggi (sebut database ini sebagai *incoming*), ini seharusnya mudah: `INSERT INTO master SELECT incoming ... ON CONFLICT UPDATE ... WHERE excluded.depth >= master.depth`.
	* Jika hanya nama mesin catur yang sama? Jika nama mesin-mesin catur berbeda?
* Membuat antarmuka untuk melihat isi database singgahan dan mengelolanya (menjalankan `VACUUM`, menganalisa posisi secara manual, dsb.).
* Mengimport semua pgn game (suatu user atau semacamnya) dari Lichess/chess.com, untuk dianalisa.
* Dokumentasi yang lebih baik, berserta i18n.

Beberapa hal lainnya lagi, berserakan di kode-kode saya dan dapat ditemukan dengan menjalankan
```bash
grep -r --include="*.py" TODO .
```