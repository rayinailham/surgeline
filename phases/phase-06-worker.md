# P6 — Worker Pengisi Form

**Tujuan sesi:** satu worker yang mengambil job dari antrean, membuka target via Playwright,
mengisi form, dan menyimpan **nomor konfirmasi** (D6) atau alasan gagal. Belum paralel (P7),
belum retry canggih (P8) — fokus: satu job → satu submission benar.

**Prasyarat:** P4 (skema), P5 (loader), P1/P2 (target hidup).
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D6, D12), `docs/SCHEMA.md`,
`docs/TARGET.md`, `AGENTS.md` §7.
**Budget:** berat.

---

## Persiapan
```bash
cd surgeline && docker compose up -d && cd ..
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8110/health   # 200
bash /home/rayin/Projects/Testing/crosscheck/scripts/arch_provision.sh
uv run --no-sync playwright install chromium     # TANPA --with-deps
```

### 1. `src/store.py` — lapisan antrean (dipakai worker & dashboard)
Fungsi sempit (agar D5 upgrade-able): `claim_one(worker_id)` (atomik `BEGIN IMMEDIATE`:
`SELECT … WHERE status='pending' LIMIT 1` → `UPDATE status='claimed', worker_id, claimed_at`),
`mark_ok(ref, confirmation)`, `mark_failed(ref, error)`, `release(ref, error)`,
`record_attempt(...)`, `counts()`.

Transisi status **dan** baris audit `attempts` ditulis dalam satu transaksi yang sama
(`docs/SCHEMA.md` §5 aturan 1 menang atas pembacaan "mark_… lalu record_attempt" sebagai
dua panggilan terpisah): `kill -9` di antara keduanya adalah persis yang diuji di P9.

### 2. `src/worker.py`
Loop: `claim_one` → buka `GET /` → isi field dari `payload` → submit → baca halaman hasil:
- ada nomor konfirmasi di selector (D6) → `mark_ok(ref, confirmation)`, audit `outcome=ok`.
- HTTP 500 → `release(...)` ke `pending`, audit `outcome=retryable`; timeout → audit
  `outcome=timeout` (retry sederhana dulu; kebijakan penuh di P8).
- 422 validasi permanen → `mark_failed`, audit `outcome=permanent`.
CLI: `--run <run_id>` + `--once` (satu job) atau `--max-jobs N` (N job lalu berhenti);
`--timeout-ms` untuk menguji jalur timeout terhadap mode chaos `slow`.

### 3. Bukti satu batch
Jalankan worker pada subset (mis. 200 job, chaos ON), lalu:
```bash
sqlite3 data/demo/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
sqlite3 data/demo/queue.db "SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='');"  # 0
```
Setiap `ok` WAJIB punya `confirmation` (D6). Kalau ada `ok` tanpa konfirmasi → worker salah baca halaman.

### 4. Unit test (`src/test_worker.py`) — tanpa jaringan nyata
Mock/stub halaman hasil (HTML fixture): parser menemukan nomor konfirmasi; 500→retryable;
422→permanent; ok tanpa konfirmasi diperlakukan gagal.

---

## Output fase
- `src/store.py`, `src/worker.py`, `src/test_worker.py`. Salin `arch_provision.sh` ke `scripts/` bila jadi runtime.
  (Belum disalin: patch WebKit tidak dipakai worker — worker hanya Chromium, dan
  `playwright install chromium` sudah cukup. Salin saat P14 kalau `make all` membutuhkannya.)

## Definition of Done
- [x] Worker memproses subset job terhadap target `:8110`; hasil tercatat di DB.
- [x] Tiap `ok` punya `confirmation` non-kosong (query = 0 pelanggaran) (A5/D6).
- [x] 500/timeout → job kembali `pending`; 422 validasi → `failed` dgn `last_error`.
- [x] `claim_one` atomik (`BEGIN IMMEDIATE`) — dasar untuk P7.
- [x] `uv run … -m unittest src.test_worker` lulus (pakai fixture, bukan jaringan).
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`subset 200 diproses · ok=195 semuanya berkonfirmasi · permanent=5 · subset chaos 24:
ok=12 retryable=12 timeout=6 permanent=6 · 30 test worker/store lulus (73 total)`

---

## Bukti (2026-08-28)

### Batch 200 job, chaos ON (`data/p06-demo/queue.db`)

```
$ uv run --no-sync python -m src.load --input data/p06-demo/subset200.csv --run p06-demo
dibaca=200 dimasukkan=200 duplikat_ditolak=0

$ uv run --no-sync python -m src.worker --run p06-demo --max-jobs 220 --worker-id w-1
worker=w-1 ok=194 retryable=0 timeout=0 permanent=5      # + 1 job dari smoke run --once

$ sqlite3 data/p06-demo/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
failed|5
ok|195

$ sqlite3 data/p06-demo/queue.db "SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='');"
0

$ sqlite3 data/p06-demo/queue.db "SELECT COUNT(*) AS ok_rows, COUNT(DISTINCT confirmation) AS unik FROM jobs WHERE status='ok';"
195|195

$ sqlite3 data/p06-demo/queue.db "SELECT COUNT(*) FROM jobs WHERE confirmation IS NOT NULL AND confirmation NOT GLOB 'SL-[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]';"
0

$ sqlite3 data/p06-demo/queue.db "SELECT external_ref,last_error FROM jobs WHERE status='failed' LIMIT 2;"
REC-000112|HTTP 422: record ditolak oleh chaos target
REC-000115|HTTP 422: record ditolak oleh chaos target
```

Chaos deterministik hanya menjatuhkan mode `validation` pada 200 `external_ref` pertama
(5/200 = 2,5%; peta chaos dihitung ulang dari `docs/CHAOS.md`). Karena itu jalur 500 dan
timeout dibuktikan pada subset kedua yang sengaja memuat keempat nasib.

### Subset 24 job, 6 per mode chaos (`data/p06-chaos/queue.db`)

```
# Run A — --timeout-ms 1000, jadi mode `slow` (tidur 2 dtk) pasti timeout
$ uv run --no-sync python -m src.worker --run p06-chaos --max-jobs 24 --timeout-ms 1000 --worker-id w-A
worker=w-A ok=6 retryable=6 timeout=6 permanent=6

$ sqlite3 data/p06-chaos/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
failed|6        # 422 validasi -> permanen, tidak di-retry
ok|6            # record bersih
pending|12      # 6 server_error + 6 timeout, dikembalikan untuk retry

$ sqlite3 data/p06-chaos/queue.db "SELECT attempts,COUNT(*) FROM jobs GROUP BY attempts;"
1|24            # tiap job tepat satu percobaan: tidak ada job yang memonopoli worker

# Run B — timeout default 15 dtk, 12 job pending diproses ulang
$ uv run --no-sync python -m src.worker --run p06-chaos --max-jobs 12 --worker-id w-B
worker=w-B ok=6 retryable=6 timeout=0 permanent=0

$ sqlite3 data/p06-chaos/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
failed|6
ok|12           # 6 job `slow` yang tadi timeout kini sukses
pending|6       # server_error tetap gagal (deterministik) -> dead-letter dikunci di P8

$ sqlite3 data/p06-chaos/queue.db "SELECT outcome,COUNT(*) FROM attempts GROUP BY outcome;"
ok|12
permanent|6
retryable|12
timeout|6

$ sqlite3 data/p06-chaos/queue.db "SELECT external_ref,status,attempts,last_error FROM jobs WHERE status='pending' LIMIT 3;"
REC-000215|pending|2|HTTP 500 dari target
REC-000276|pending|2|HTTP 500 dari target
REC-000353|pending|2|HTTP 500 dari target
```

Idempotensi target menutup lubang paling berbahaya di mode `slow` — worker menyerah karena
timeout padahal server sudah menyimpan record:

```
$ sqlite3 -header -column data/p06-chaos/queue.db \
    "SELECT external_ref,worker_id,outcome,confirmation FROM attempts WHERE external_ref='REC-000203' ORDER BY id;"
REC-000203    w-A        timeout
REC-000203    w-B        ok       SL-15bd1258

$ sqlite3 -header -column data/p06-chaos/queue.db \
    "SELECT external_ref,status,attempts,confirmation FROM jobs WHERE external_ref='REC-000203';"
REC-000203    ok      2      SL-15bd1258
```

### Unit test tanpa jaringan

```
$ uv run --no-sync python -m unittest src.test_worker
Ran 30 tests in 0.013s
OK

$ uv run --no-sync python -m unittest discover -s src
Ran 73 tests in 0.281s
OK
```

### Temuan yang diperbaiki di fase ini

`claim_one` semula memilih `pending` dengan `ORDER BY rowid`. Job yang dilepas kembali ke
`pending` langsung jadi kandidat terbaik lagi, jadi satu job `server_error` memakan seluruh
run: **24 percobaan berturut-turut jatuh ke `REC-000215`, 23 job lain tidak tersentuh.**
Perbaikan: urutkan `pending` dengan `ORDER BY updated_at, rowid` + index
`idx_jobs_status_updated_at (status, updated_at)`. Loader menulis `created_at = updated_at`
sehingga urutan awal tetap FIFO. `docs/SCHEMA.md` §3 dan `src/schema.py` diperbarui bersama,
dengan regresi `test_job_yang_dilepas_pindah_ke_belakang_antrean`. Kolom yang sama menopang
kelayakan backoff D7 di P8 — tanpa kolom baru, `SCHEMA_VERSION` tetap 1.

## Jebakan
- Jangan `httpx.post('/submit')` langsung — pitch-nya browser (D12). Worker isi form via Playwright.
- Jangan hit jaringan di unit test — pakai HTML fixture, kalau tidak `make all` salinan bersih gagal.
- Konfirmasi kosong pada status `ok` = cacat, bukan sukses. Tegakkan di kode + test.
- Jangan naikkan worker jadi banyak di sini — konkurensi diuji khusus di P7.
