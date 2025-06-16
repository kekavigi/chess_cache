# Todo

Beberapa hal yang ingin dikembangkan:
* Unit test yang lebih banyak.
* Menggabungkan dua atau lebih database singgahan.
	* Jika nama mesin catur yang digunakan sama (misal `Stockfish`), dan satu database *strictly* berisi analisa oleh versi mesin yang lebih tinggi (sebut database ini sebagai *incoming*), ini seharusnya mudah: `INSERT INTO master SELECT incoming ... ON CONFLICT UPDATE ... WHERE excluded.depth >= master.depth`.
	* Jika hanya nama mesin catur yang sama? Jika nama mesin-mesin catur berbeda?
* Membuat antarmuka untuk melihat isi database singgahan dan mengelolanya (menjalankan `VACUUM`, menganalisa posisi secara manual, dsb.).
* Mengimport semua pgn game (suatu user atau semacamnya) dari Lichess/chess.com, untuk dianalisa.
* Menghapus kolom `multipv` dari table database, tanpa membuat peforma `UciEngine` menjadi lebih buruk.