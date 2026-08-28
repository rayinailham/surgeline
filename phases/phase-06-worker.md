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
`mark_ok(ref, confirmation)`, `mark_failed(ref, error)`, `record_attempt(...)`, `counts()`.

### 2. `src/worker.py`
Loop: `claim_one` → buka `GET /` → isi field dari `payload` → submit → baca halaman hasil:
- ada nomor konfirmasi di selector (D6) → `mark_ok(ref, confirmation)` + `record_attempt(outcome=ok)`.
- HTTP 500 / timeout → `record_attempt(outcome=retryable)` + kembalikan job ke `pending`
  (retry sederhana dulu; kebijakan penuh di P8).
- 422 validasi permanen → `mark_failed` + `record_attempt(outcome=permanent)`.
CLI: `--run <run_id> --once` (proses N lalu berhenti) untuk uji.

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

## Definition of Done
- [ ] Worker memproses subset job terhadap target `:8110`; hasil tercatat di DB.
- [ ] Tiap `ok` punya `confirmation` non-kosong (query = 0 pelanggaran) (A5/D6).
- [ ] 500/timeout → job kembali `pending`; 422 validasi → `failed` dgn `last_error`.
- [ ] `claim_one` atomik (`BEGIN IMMEDIATE`) — dasar untuk P7.
- [ ] `uv run … -m unittest src.test_worker` lulus (pakai fixture, bukan jaringan).
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`subset N diproses · ok=… semuanya berkonfirmasi · retryable=… · permanent=… · M test lulus`

## Jebakan
- Jangan `httpx.post('/submit')` langsung — pitch-nya browser (D12). Worker isi form via Playwright.
- Jangan hit jaringan di unit test — pakai HTML fixture, kalau tidak `make all` salinan bersih gagal.
- Konfirmasi kosong pada status `ok` = cacat, bukan sukses. Tegakkan di kode + test.
- Jangan naikkan worker jadi banyak di sini — konkurensi diuji khusus di P7.
