# P8 — Ketahanan: Retry, Dead-letter & Lease Recovery

**Tujuan sesi:** membuat sistem menyelesaikan 100% walau target gagal 5% — retry bertingkat
untuk yang retryable, dead-letter untuk yang habis percobaan, dan pemulihan job "nyangkut"
(worker mati saat `claimed`) via lease timeout. Ini menyumbang A4 & A10.

**Prasyarat:** P7 selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D3, D7, D8), `docs/SCHEMA.md`,
`docs/CHAOS.md`, `src/store.py`, `src/worker.py`.
**Budget:** sedang.

---

## Langkah

### 1. Retry bertingkat + backoff (D7)
`store`/`worker`: job `retryable` → naikkan `attempts`, jadwalkan retry dengan backoff
eksponensial + jitter (`base * factor^attempts`), kembalikan ke `pending` dengan `not_before`
timestamp. `claim_one` hanya mengambil job `pending` yang `not_before <= now`.
`attempts >= max_attempts` → `dead` dengan `last_error`. Kegagalan **permanen** (422 validasi)
langsung `failed`, TIDAK di-retry (kontrak `docs/CHAOS.md`).

### 2. Lease recovery job nyangkut (D8)
Fungsi `recover_stuck(lease_timeout)`: job `claimed` dengan `now - claimed_at > lease_timeout`
→ kembalikan ke `pending` (naikkan attempts). Dipanggil saat startup runner + berkala.

### 3. Bukti (A4 & A10)
```bash
# A4: run subset chaos ON sampai selesai — semua retryable akhirnya ok, permanent tercatat:
sqlite3 db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
sqlite3 db "SELECT COUNT(*) FROM jobs WHERE status='dead' AND last_error IS NULL;"   # 0
# A10: bunuh worker saat sebuah job 'claimed' → job kembali pending → akhirnya ok:
#   claim job manual/one worker, kill -9 sebelum mark_ok, jalankan recover_stuck, lanjut.
```
Tunjukkan satu `external_ref` menempuh `claimed → (worker mati) → pending → ok`, tanpa duplikat.

### 4. Unit test (`src/test_resilience.py`)
backoff naik per attempt; `not_before` menahan job; max_attempts→dead; permanent tak di-retry;
`recover_stuck` mengembalikan job yang melewati lease saja (yang masih fresh tidak disentuh).

```bash
uv run --no-sync python -m unittest src.test_resilience -v
```

---

## Output fase
- `src/worker.py` & `src/store.py` (diperkaya), `src/recover.py` (atau di store), `src/test_resilience.py`.
- Kunci angka D7/D8 (max_attempts, base/factor, lease_timeout) di `docs/SCHEMA.md`/`DECISIONS.md`.

## Definition of Done
- [ ] Retryable → retry backoff sampai ok atau `dead`; tiap `dead` punya `last_error` (A4).
- [ ] Permanent (422) → `failed` tanpa retry, alasan tercatat.
- [ ] `recover_stuck` mengembalikan job yang melewati lease; job fresh tidak disentuh.
- [ ] Bukti satu job `claimed→pending(recovered)→ok` tanpa duplikat (A10).
- [ ] Angka D7/D8 dikunci di dokumen.
- [ ] `uv run … -m unittest src.test_resilience` lulus.
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`retryable→ok … · dead … (semua ber-last_error) · lease recovery terbukti · N test lulus`

## Jebakan
- Retry tanpa `not_before` = badai retry ketat yang membombardir target. Backoff wajib.
- Jangan retry kegagalan permanen (422) — itu bukan gangguan sementara, cuma memutar tak berujung.
- `recover_stuck` yang terlalu agresif (lease terlalu pendek) merebut job yang masih diproses →
  bisa dobel submit. Lease harus > durasi submission normal + margin (D8).
- **Perubahan di P8 mengubah perilaku run.** Setelah ini, jalankan ulang bukti P9 dari versi baru.
