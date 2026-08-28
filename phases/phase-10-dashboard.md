# P10 — Dashboard

**Tujuan sesi:** satu halaman FastAPI + HTMX yang menampilkan angka hidup antrean —
Total · Pending · Claimed · Berhasil · Gagal · Dead · throughput — dan angkanya **cocok 1:1**
dengan query DB (A6). Ini yang direkam "angka naik" di video P14.

**Prasyarat:** P4 (skema); berguna penuh setelah P6. Boleh dikerjakan sebagai sesi terpisah.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D9, D11), `docs/SCHEMA.md`, `src/store.py`.
**Budget:** sedang.

---

## Langkah

### 1. `src/dashboard.py` (FastAPI + Jinja2 + HTMX)
- `GET /` → halaman: kartu angka + tabel per-status + throughput berjalan (ok/menit).
- `GET /stats` → fragment HTML (atau JSON) di-poll HTMX tiap 1–2 dtk (`hx-get`, `hx-trigger="every 2s"`).
- Sumber angka: `store.counts()` = `SELECT status, COUNT(*) FROM jobs GROUP BY status` pada
  `data/<run_id>/queue.db`. Read-only, buka DB mode `ro` bila bisa. Port `8120` (D9).
- `--run <run_id>` memilih DB mana yang ditampilkan.

### 2. Bukti cocok DB (A6)
```bash
uv run --no-sync uvicorn src.dashboard:app --port 8120 &
curl -sS localhost:8120/stats | grep -oE '[0-9]+'         # angka dashboard
sqlite3 data/<run>/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"   # angka DB
```
Ambil kedua snapshot pada detik yang sama saat run berjalan → selisih 0. Screenshot untuk P14.

### 3. Ketahanan tampilan
Saat run dibunuh (P9), dashboard tetap membaca DB & menampilkan angka terakhir tanpa crash
(read-only, tak ikut mati bersama worker). Uji: kill worker, refresh dashboard → tetap tampil.

---

## Output fase
- `src/dashboard.py`, `src/templates/` (HTML), unit/asap test ringan (`src/test_dashboard.py`).

## Definition of Done
- [ ] Dashboard hidup di `:8120`, menampilkan Total/Pending/Claimed/Berhasil/Gagal/Dead + throughput.
- [ ] Angka `/stats` = angka `GROUP BY status` DB pada detik sama, selisih 0 (A6).
- [ ] Auto-refresh HTMX bekerja (angka berubah saat run jalan).
- [ ] Dashboard tetap tampil saat worker dibunuh (read-only, tak crash).
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`dashboard :8120 · 6 angka + throughput · selisih vs DB = 0 · auto-refresh jalan`

## Jebakan
- Jangan buka DB write-mode di dashboard — worker sedang menulis; cukup read-only.
- Angka "throughput" harus dari data nyata (delta ok / delta waktu), bukan angka hias.
- Tanpa auth, HANYA bind `127.0.0.1` (D11) — jangan `0.0.0.0`.
