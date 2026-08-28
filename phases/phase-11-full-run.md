# P11 — Run Penuh 50.000

**Tujuan sesi:** menjalankan seluruh 50.000 record lewat chaos 5% dengan ≥2 kill di tengah,
sampai status akhir bersih & 0 duplikat. Ini menutup A1, A2, A4 dengan angka pada skala penuh.

**Prasyarat:** P8 tuntas + P10 (dashboard untuk direkam). Semua P5–P9 hijau.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D3, D7, D8), `docs/SCHEMA.md`,
`docs/RESUME_PROOF.md`.
**Budget:** sedang (jam dinding untuk run).

---

## Langkah
```bash
cd surgeline && docker compose up -d && cd ..    # chaos ON (SURGELINE_CHAOS_RATE=0.05)
RUN=full50k
uv run --no-sync python src/load.py --input data/input/records.xlsx --run $RUN
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs;"     # 50000
uv run --no-sync uvicorn src.dashboard:app --port 8120 &    # amati angka naik
uv run --no-sync python src/run.py --run $RUN --workers 4 &
PID=$!; sleep 60; kill -9 $PID                              # KILL #1
uv run --no-sync python src/run.py --run $RUN --workers 4 &
PID=$!; sleep 60; kill -9 $PID                              # KILL #2
uv run --no-sync python src/run.py --run $RUN --workers 4   # sampai TUNTAS

# verifikasi penutup:
sqlite3 data/$RUN/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status IN('ok','failed','dead');"  # 50000
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status IN('pending','claimed');"   # 0
sqlite3 data/$RUN/queue.db "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs;"            # 0
sqlite3 data/$RUN/queue.db "SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok';"  # 0
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='');" # 0
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status='dead' AND last_error IS NULL;"      # 0
```
Catat waktu mulai→selesai (untuk throughput P12). Simpan `run.json` metrik akhir.

---

## Output fase
- `data/full50k/` (gitignored) + `run.json` metrik, ringkasan angka final ditempel ke `STATE.md`.

## Definition of Done
- [ ] 50.000 job berakhir di `ok|failed|dead`; `pending`+`claimed` = 0 (A1).
- [ ] Duplikat external_ref = 0; duplikat confirmation = 0 (A2).
- [ ] Tiap `ok` berkonfirmasi; tiap `dead` ber-`last_error` (A4/A5).
- [ ] ≥2 kill terjadi selama run penuh, tetap tuntas 100% (A3 pada skala penuh).
- [ ] Durasi total dicatat (bahan P12).
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`50000 tuntas · ok=… failed=… dead=… · dup=0 · konfirmasi 100% · durasi …`

## Jebakan
- Kalau `dead` banyak, cek: apakah kegagalan permanen (422) atau retryable yang kehabisan attempts
  karena `max_attempts` terlalu kecil / lease salah. Dead karena permanen itu sah; dead karena
  retry gagal terus perlu diselidiki sebelum klaim "100%".
- Jangan naikkan worker ekstrem demi cepat — catat N yang stabil, itu yang dilaporkan P12.
- Kalau kamu mengubah kode worker/store di sini, itu remediasi — commit terpisah, lalu ulang run.
