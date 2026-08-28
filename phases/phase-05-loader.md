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
sqlite3 data/demo/queue.db "SELECT COUNT(*) FROM jobs;"                       # 50000 (bukan 50000+dup)
sqlite3 data/demo/queue.db "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs;"   # 0
# load ULANG file yang sama → tetap 50000, tidak dobel:
uv run --no-sync python src/load.py --input data/input/records.xlsx --run demo
sqlite3 data/demo/queue.db "SELECT COUNT(*) FROM jobs;"                       # tetap 50000
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
- [ ] 50.000 record ter-load; `COUNT(*)` = 50000; `COUNT-DISTINCT external_ref` = 0.
- [ ] Load ulang file sama → count tetap (idempoten, dedup DB terbukti).
- [ ] Jumlah duplikat ditolak dicatat & cocok dengan duplikat sengaja P3.
- [ ] Puncak RSS loader dicatat, datar (A8).
- [ ] `uv run … -m unittest src.test_load` lulus.
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`50000 pending · dup ditolak … · RSS puncak … MB · idempoten terbukti · N test lulus`

## Jebakan
- Jangan `pandas.read_excel()` tanpa chunk untuk 50k — bisa membengkak. Pakai iterasi read_only
  atau chunksize. Ini inti A8.
- Dedup HARUS di DB (`INSERT OR IGNORE`), bukan `if ref in seen_set` di Python — set 50k di memori
  melawan tujuan A8 dan tidak bertahan lintas run.
- Satu transaksi per batch, bukan per baris (lambat) atau per seluruh file (memori).
