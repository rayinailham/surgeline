# P7 — Konkurensi & Klaim Atomik

**Tujuan sesi:** menjalankan N worker paralel di atas SQLite WAL tanpa dua worker mengerjakan
job yang sama. Bukti = tidak ada `external_ref` yang diklaim/diproses dua kali (A9).

**Prasyarat:** P6 selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D5), `docs/SCHEMA.md`, `src/store.py`.
**Budget:** sedang.

---

## Langkah

### 1. Runner multi-worker (`src/run.py`)
Spawn `--workers N` proses/asyncio worker di atas run yang sama. Tiap worker `worker_id` unik.
Klaim tetap lewat `claim_one` atomik (`BEGIN IMMEDIATE` + `busy_timeout`). Tangani
`database is locked` dengan retry singkat, bukan crash.

### 2. Bukti tanpa double-claim (A9)
Tabel `attempts` mencatat tiap percobaan. Setelah run subset dengan N=4:
```bash
# tidak ada job ok oleh >1 worker berbeda pada percobaan sukses:
sqlite3 data/demo/queue.db "
  SELECT external_ref, COUNT(DISTINCT worker_id) w
  FROM attempts WHERE outcome='ok' GROUP BY external_ref HAVING w>1;"   # 0 baris
# total ok = jumlah distinct external_ref ok (tak ada dobel sukses):
sqlite3 data/demo/queue.db "SELECT COUNT(*) FROM jobs WHERE status='ok';"
```
Catat: N worker, throughput kasar (job/detik), 0 double-claim.

### 3. Uji stres klaim (unit/integrasi)
Test yang menembakkan banyak `claim_one` konkuren pada DB kecil → tiap job diklaim tepat satu
worker (himpunan hasil tak beririsan, union = semua job).

```bash
uv run --no-sync python src/run.py --run demo --workers 4 --limit 500
uv run --no-sync python -m unittest src.test_concurrency -v
```

---

## Output fase
- `src/run.py`, `src/test_concurrency.py`.

## Definition of Done
- [x] N=4 worker jalan paralel di satu run; selesai tanpa crash `database is locked`.
- [x] 0 job sukses oleh >1 worker (query di atas = 0 baris) (A9).
- [x] Union job yang diklaim = semua job; irisan antar worker kosong (test).
- [x] Throughput kasar N worker dicatat (jadi baseline P12).
- [x] `uv run … -m unittest src.test_concurrency` lulus.
- [x] **Commit + push berhasil** (D13).

## Metrik selesai
`4 worker · 0 double-claim · 25,86 job/dtk · 2 test konkurensi lulus`

## Bukti nyata (2026-08-28)

```text
$ uv run --no-sync python src/run.py --run p07-demo --workers 4 --limit 500
worker=w-3 ok=124 retryable=1 timeout=0 permanent=0
worker=w-4 ok=119 retryable=1 timeout=0 permanent=5
worker=w-1 ok=125 retryable=0 timeout=0 permanent=0
worker=w-2 ok=121 retryable=1 timeout=0 permanent=3
workers=4 processed=500 elapsed=19.335s throughput=25.86 job/s return_codes=[0, 0, 0, 0]

$ sqlite3 data/p07-demo/queue.db "<query bukti A9>"
double_success_multi_worker|0
ok_jobs|489
distinct_ok_refs|489
workers_seen|4
attempt_rows|500
duplicate_attempt_refs|0

$ uv run --no-sync python -m unittest src.test_concurrency -v
Ran 2 tests in 0.041s
OK

$ uv run --no-sync python -m unittest discover -s src -v
Ran 75 tests in 0.322s
OK
```

Tiga job `pending` dan delapan `failed` adalah chaos target yang disengaja. Batas retry/dead-letter
baru dikunci di P8; P7 membuktikan 500 klaim paralel dan auditnya, bukan status terminal penuh.

## Jebakan
- `SELECT` lalu `UPDATE` di transaksi terpisah = balapan (dua worker ambil job sama). Harus satu
  transaksi `BEGIN IMMEDIATE`.
- `database is locked` normal di SQLite; tangani dengan `busy_timeout` + retry, jangan matikan worker.
- Terlalu banyak worker menulis ke satu SQLite ada titik jenuh — catat N yang sehat untuk P12,
  jangan paksa ratusan.
