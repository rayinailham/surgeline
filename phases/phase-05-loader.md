# P5 — Loader

**Tujuan sesi:** memindahkan 50.000 record dari Excel/CSV ke antrean DB **bertahap** (memori
datar) dengan **dedup di level DB** — duplikat ditolak oleh `UNIQUE`, bukan dicek di memori.

**Prasyarat:** P3 (data) & P4 (skema) selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D4, D5, D10), `docs/SCHEMA.md`,
`docs/DATA_DICTIONARY.md`.
**Budget:** sedang.

---

## Langkah

### 1. `src/load.py`
CLI: `--input data/input/records.xlsx --run <run_id>` → buat `data/<run_id>/queue.db`
(`init_db`), baca file **bertahap** (`openpyxl read_only` iter rows / `pandas` chunksize),
`INSERT OR IGNORE INTO jobs(external_ref,payload,status='pending',...)` per batch dengan
satu transaksi per batch. Catat: baris dibaca, baris dimasukkan, duplikat ditolak (= dibaca − dimasukkan).

### 2. Bukti dedup DB (A2)
```bash
uv run --no-sync python src/load.py --input data/input/records.xlsx --run demo
sqlite3 data/demo/queue.db "SELECT COUNT(*) FROM jobs;"                       # 49950 (50.000 dibaca, 50 natural-key duplikat)
sqlite3 data/demo/queue.db "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs;"   # 0
# load ULANG file yang sama → tetap 49950, tidak dobel:
uv run --no-sync python src/load.py --input data/input/records.xlsx --run demo
sqlite3 data/demo/queue.db "SELECT COUNT(*) FROM jobs;"                       # tetap 49950
```
Jumlah "duplikat ditolak" harus = jumlah duplikat sengaja (P3) + seluruh baris saat load ulang.

### 3. Bukti memori datar (A8)
Ukur RSS puncak loader untuk 50.000 baris (`/usr/bin/time -v`). Harus jauh di bawah "seluruh
file di memori" dan tidak naik linear. Catat angkanya.

### 4. Unit test (`src/test_load.py`)
- load file kecil → jumlah `pending` benar.
- duplikat external_ref dalam file → hanya 1 masuk.
- load ulang idempoten (count tak berubah).
- payload tersimpan sebagai JSON yang bisa dibaca balik.

```bash
uv run --no-sync python -m unittest src.test_load -v
```

---

## Output fase
- `src/load.py`, `src/test_load.py`. (DB di `data/` gitignored.)

## Definition of Done
- [x] 50.000 baris terbaca; 49.950 natural key ter-load; `COUNT(*)` = 49950; `COUNT-DISTINCT external_ref` = 0.
- [x] Load ulang file sama → count tetap (idempoten, dedup DB terbukti).
- [x] Jumlah duplikat ditolak dicatat & cocok dengan duplikat sengaja P3.
- [x] Puncak RSS loader dicatat, datar (A8).
- [x] `uv run … -m unittest src.test_load` lulus.
- [x] **Commit + push berhasil** (D13).

## Metrik selesai
`49.950 pending dari 50.000 baris · dup ditolak 50 · RSS puncak 55,71 MiB · idempoten terbukti · 6 test fokus / 43 test penuh lulus`

## Bukti aktual (2026-08-28)

`/usr/bin/time` tidak tersedia (`/usr/bin/bash: line 1: /usr/bin/time: No such file or directory`),
jadi RSS kernel diukur tanpa dependency melalui stdlib
`resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss` yang membungkus subprocess loader.

```text
$ uv run --no-sync python -c "import resource,subprocess,sys; p=subprocess.run([sys.executable,'src/load.py','--input','data/rss-10000/records.xlsx','--run','p05-rss-10000']); print(f'peak_rss_kib={resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}'); raise SystemExit(p.returncode)"
dibaca=10000 dimasukkan=9950 duplikat_ditolak=50
peak_rss_kib=50600

$ uv run --no-sync python -c "import resource,subprocess,sys; p=subprocess.run([sys.executable,'src/load.py','--input','data/input/records.xlsx','--run','p05-demo']); print(f'peak_rss_kib={resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}'); raise SystemExit(p.returncode)"
dibaca=50000 dimasukkan=49950 duplikat_ditolak=50
peak_rss_kib=57044

$ sqlite3 data/p05-demo/queue.db "SELECT COUNT(*), COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs; SELECT status,COUNT(*) FROM jobs GROUP BY status; PRAGMA journal_mode;"
49950|0
pending|49950
wal

$ uv run --no-sync python src/load.py --input data/input/records.xlsx --run p05-demo
dibaca=50000 dimasukkan=0 duplikat_ditolak=50000

$ sqlite3 data/p05-demo/queue.db "SELECT COUNT(*), COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs;"
49950|0

$ uv run --no-sync python -m unittest src.test_load -v
Ran 6 tests in 0.021s
OK

$ uv run --no-sync python -m compileall -q src scripts && uv run --no-sync python -m unittest discover -s src -v
Ran 43 tests in 0.348s
OK
```

RSS 5× baris hanya naik 6.444 KiB (12,74%): batch 500 + `openpyxl` read-only, bukan
pertumbuhan linear. Ketidaksesuaian angka lama `COUNT(*)=50000` diperbaiki menjadi 49.950:
`docs/DATA_DICTIONARY.md` mengunci 50.000 baris input dengan 50 natural-key duplikat dan D4
mewajibkan dedup DB.

## Jebakan
- Jangan `pandas.read_excel()` tanpa chunk untuk 50k — bisa membengkak. Pakai iterasi read_only
  atau chunksize. Ini inti A8.
- Dedup HARUS di DB (`INSERT OR IGNORE`), bukan `if ref in seen_set` di Python — set 50k di memori
  melawan tujuan A8 dan tidak bertahan lintas run.
- Satu transaksi per batch, bukan per baris (lambat) atau per seluruh file (memori).
