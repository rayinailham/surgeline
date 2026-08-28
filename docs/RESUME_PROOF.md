# SurgeLine — Bukti Crash-Recovery P9

**Tanggal:** 2026-08-28

**Run:** `p09-crash-proof`

**Target:** container milik project `surgeline-target`, `http://127.0.0.1:8110`

**Chaos:** ON — rate `0.05`, seed `1337`, delay `2.0` detik

**Antrean:** 3.000 record sintetis, SQLite WAL, 4 worker Playwright Chromium

## Persiapan

```text
$ docker compose up -d
 Container surgeline-target Running

$ curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8110/health
200

$ wc -l data/p09-input-3000.csv
3001 data/p09-input-3000.csv

$ uv run --no-sync python src/load.py --input data/p09-input-3000.csv --run p09-crash-proof
dibaca=3000 dimasukkan=3000 duplikat_ditolak=0
```

## Kill paksa dan resume

Setiap runner dijalankan sebagai process group sendiri. `kill -9` diarahkan hanya ke
process group runner tersebut agar runner dan empat child worker benar-benar mati seperti
putus daya proses; tidak ada service atau container lain yang disentuh.

```text
$ setsid uv run --no-sync python src/run.py --run p09-crash-proof --workers 4 ...
$ sleep 15; kill -9 -- -231590
kill#1 pid=231590 ok=423 claimed=4

$ setsid uv run --no-sync python src/run.py --run p09-crash-proof --workers 4 ...
$ sleep 15; kill -9 -- -232283
kill#2 pid=232283 ok=804 claimed=8
```

`804 > 423 > 0`: resume kedua maju dari state SQLite yang sama, bukan mengulang dari nol.
Empat klaim per kill tertinggal sebagai yatim. Mereka sengaja tidak direbut sebelum lease
120 detik berakhir (D8).

## Resume sampai terminal

Pass resume pertama memproses 2.367 percobaan dalam 108,306 detik. Saat pass itu selesai,
empat klaim dari kill kedua belum melewati lease sehingga hasil antara masih jujur mencatat:

```text
workers=4 processed=2367 elapsed=108.306s throughput=21.85 job/s return_codes=[0, 0, 0, 0]

--- status akhir sementara ---
claimed|4
dead|49
failed|44
ok|2903

--- pending+claimed ---
4
```

Setelah lease kedaluwarsa, startup runner berikutnya menyapu empat klaim itu dan
menuntaskannya:

```text
--- umur claimed (detik) ---
4|143.4|144.6

worker=w-1 ok=1 retryable=0 timeout=0 permanent=0 dead=0
worker=w-3 ok=1 retryable=0 timeout=0 permanent=0 dead=0
worker=w-4 ok=1 retryable=0 timeout=0 permanent=0 dead=0
worker=w-2 ok=1 retryable=0 timeout=0 permanent=0 dead=0
workers=4 processed=8 elapsed=3.301s throughput=2.42 job/s return_codes=[0, 0, 0, 0]
```

## Verifikasi akhir dari SQLite

```text
$ sqlite3 data/p09-crash-proof/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status ORDER BY status;"
dead|49
failed|44
ok|2907

$ sqlite3 data/p09-crash-proof/queue.db "SELECT COUNT(*) FROM jobs WHERE status IN ('pending','claimed');"
0

$ sqlite3 data/p09-crash-proof/queue.db "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs;"
0

$ sqlite3 data/p09-crash-proof/queue.db "SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok';"
0

$ sqlite3 data/p09-crash-proof/queue.db "SELECT COUNT(*) FROM jobs WHERE status='ok' AND confirmation IS NULL;"
0

$ sqlite3 data/p09-crash-proof/queue.db "SELECT outcome,COUNT(*) FROM attempts GROUP BY outcome ORDER BY outcome;"
ok|2907
permanent|44
retryable|245
timeout|8

$ sqlite3 data/p09-crash-proof/queue.db "SELECT COUNT(*) FROM attempts WHERE ended_at IS NULL;"
0

$ sqlite3 data/p09-crash-proof/queue.db "SELECT COUNT(*) FROM jobs;"
3000
```

Delapan audit `timeout` adalah tepat delapan klaim yatim dari dua kill (4 worker × 2 kill),
masing-masing beralasan `lease 120 dtk kedaluwarsa`; tidak ada attempt terbuka. Semua 3.000
job terminal: 2.907 `ok`, 44 `failed` permanen, 49 `dead` setelah retry habis. Kegagalan
chaos tidak dihapus atau disamarkan.

## Kesimpulan

- Kill paksa: **2×**.
- Progres sukses: **423 → 804 → 2.907**, naik monoton.
- Terminal: **3.000/3.000 (100%)**; `pending + claimed = 0`.
- Duplikat `external_ref`: **0**.
- Duplikat konfirmasi sukses: **0**; konfirmasi kosong pada sukses: **0**.
- Klaim yatim dipulihkan: **8/8**; attempt terbuka: **0**.

Rekaman layar ditunda ke P14 agar video final memakai alur dan artefak packaging final.
