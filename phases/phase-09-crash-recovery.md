# P9 — Bukti Crash-Recovery (jantung portofolio)

**Tujuan sesi:** menghasilkan bukti nomor satu: **dimatikan paksa di tengah run → dinyalakan
lagi → lanjut dari posisi terakhir → 0 duplikat.** Ini yang direkam jadi video P14 dan yang
menjual seluruh portofolio.

**Prasyarat:** P8 selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D4, D6, D8), `docs/SCHEMA.md`,
`docs/RESUME_PROOF.md`.
**Budget:** ringan (banyak menunggu, sedikit menulis).

---

## Langkah (target chaos ON, subset cukup besar mis. 3.000–5.000 job)
```bash
cd surgeline && docker compose up -d && cd ..
RUN=crash1
uv run --no-sync python src/load.py --input data/input/records.xlsx --run $RUN
uv run --no-sync python src/run.py --run $RUN --workers 4 &
PID=$!
sleep 25 && kill -9 $PID                              # KILL #1 di tengah
N1=$(sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status='ok';")
echo "setelah kill#1: ok=$N1"

uv run --no-sync python src/run.py --run $RUN --workers 4 &   # runner menjalankan recover_stuck di startup
PID=$!
sleep 25 && kill -9 $PID                              # KILL #2 di tengah
N2=$(sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status='ok';")
echo "setelah kill#2: ok=$N2"

uv run --no-sync python src/run.py --run $RUN --workers 4     # jalankan sampai TUNTAS
# verifikasi akhir:
sqlite3 data/$RUN/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
sqlite3 data/$RUN/queue.db "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs;"                       # 0
sqlite3 data/$RUN/queue.db "SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok';"    # 0
```
Yang harus benar: `N2 > N1 > 0` (maju terus, tak mengulang dari nol), `pending`+`claimed` akhir = 0,
duplikat external_ref = 0, duplikat confirmation = 0. Simpan seluruh output ke `docs/RESUME_PROOF.md`.

## Rekam (opsional di sini, wajib final di P14)
Kalau merekam layar: satu monitor (`wf-recorder -o eDP-1`), tanpa kredensial/jendela kerja user
terlihat. Boleh ditunda ke P14 (catat keputusannya di `STATE.md`).

---

## Output fase
- `docs/RESUME_PROOF.md` (output lengkap 2 kill + verifikasi akhir), rekaman mentah (opsional).

## Definition of Done
- [x] ≥2 `kill -9` di tengah run; `ok` naik monoton (`423 → 804`), bukan reset.
- [x] Run akhir tuntas: 3.000 terminal; `pending`+`claimed` = 0.
- [x] Duplikat `external_ref` = 0 DAN duplikat `confirmation` = 0 (A2/A3).
- [x] Output ditempel di `docs/RESUME_PROOF.md`.
- [x] Keputusan rekaman dicatat di `STATE.md`: ditunda ke P14.
- [x] **Commit + push berhasil** (D13).

## Bukti DoD (2026-08-28)

```text
kill#1 pid=231590 ok=423 claimed=4
kill#2 pid=232283 ok=804 claimed=8

status terminal: dead=49 | failed=44 | ok=2907
pending+claimed=0
duplikat external_ref=0
duplikat confirmation untuk job ok=0
job ok tanpa confirmation=0
klaim yatim dipulihkan=8/8
attempt terbuka=0
```

Output perintah lengkap, termasuk pass antara yang menunggu lease, ada di
`docs/RESUME_PROOF.md`.

## Metrik selesai
`kill#1 ok=N1 · kill#2 ok=N2 · akhir 100% · dup ref=0 · dup konfirmasi=0`

## Jebakan
- Pakai `kill -9`, bukan `kill` biasa — `SIGTERM` bisa ditangani rapi, itu bukan simulasi mati listrik.
- Bukti = **angka sebelum vs sesudah**, bukan "tidak ada error". Kalau `L2 ≈ 2×L1` berarti mengulang.
- Kalau runner tidak memanggil `recover_stuck` saat startup, job yang `claimed` saat di-kill akan
  menggantung sampai lease — pastikan recovery jalan (P8) atau tunggu lease lewat.
- Chaos harus ON — crash-recovery yang cuma teruji di target sempurna tidak meyakinkan klien.
