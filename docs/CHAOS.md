# SurgeLine — CHAOS (diisi di P2)

> STUB. Model kegagalan target + oracle. Diisi & dikunci di P2.

Akan mendefinisikan (D3):
- 5% kegagalan deterministik berdasar seed + kunci record.
- 3 mode: HTTP 500 · respons lambat (sleep N dtk) · penolakan validasi.
- Proporsi tiap mode, cara mengaktifkan/menyetel via env target.
- **Oracle target**: skenario yang membuktikan tiap mode benar-benar muncul & reproducible,
  dijalankan lewat `make target-oracles` (server segar).
