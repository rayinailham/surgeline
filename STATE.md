# SurgeLine — STATE

> File hidup. Dibaca di awal tiap sesi, ditulis ulang di akhir tiap sesi.
> Satu-satunya memori antar sesi agent. Jaga tetap pendek (< 100 baris).

**Terakhir diperbarui:** 2026-08-29 (sesi P14)
**Status project:** ✅ **PROJECT COMPLETE** — 15/15 fase selesai, acceptance **12/12**
**Fase aktif:** — **Fase berikutnya:** — (tidak ada; repo sudah publik, D16 terkunci)

---
## Status fase

| Fase | Status | Catatan |
|---|---|---|
| P0 Bootstrap | ✅ | commit `2409499`; uv+Makefile+env-check.md+smoke test; repo privat |
| P1 Target App | ✅ | commit `P01`; `surgeline-target` :8110, form 6 field, `SL-<8hex>` idempoten |
| P2 Chaos & Kontrak | ✅ | commit `P02`; 112/2.000 = 5,60%, mode 38/39/35, 2 run diff=0 |
| P3 Generator Data | ✅ | commit `P03`; 50k CSV+XLSX, 50 dup sengaja, RSS 48,84 MiB datar |
| P4 Kontrak Skema | ✅ | commit `P04`; `docs/SCHEMA.md` terkunci, WAL, dedup `1\|1\|0`, 24 test |
| P5 Loader | ✅ | commit `P05`; 50k → 49.950 pending, reload +50k ditolak DB |
| P6 Worker | ✅ | commit `P06`; 200 job: ok=195 (konfirmasi unik), 4 mode gagal terbukti |
| P7 Konkurensi | ✅ | commit `P07`; 4 worker, 500 klaim, 0 double-success |
| P8 Ketahanan | ✅ | commit `P08`; chaos 100: 80/10/10, semua `dead` ber-`last_error` |
| P9 Bukti Crash-Recovery | ✅ | commit `P09`; 3k chaos, 2× kill -9, 8 yatim pulih, 0 dup |
| P10 Dashboard | ✅ | commit `P10`; read-only :8120, HTMX 2 dtk, selisih DB=0 |
| P11 Run Penuh 50k | ✅ | commit `P11`; 49.950 tuntas, 2 kill, 7 yatim pulih, dup 0/0 |
| P12 Throughput | ✅ | commit `P12`; 81.915 rec/jam @8, jenuh N=8, 6 juta ≈ 3,0 hari |
| P13 Laporan + Konsultasi | ✅ | commit `bb78dfc`; `REPORT.xlsx` 5 lembar, digest 0 jargon |
| P14 Packaging | ✅ | commit `P14`; demo.mp4 113,9 dtk, salinan bersih exit 0, audit 0 bocor |

Legenda: ⬜ belum · 🟨 jalan · ✅ selesai · 🟥 blocked

## Artefak yang sudah lahir
- **P0–P5:** `pyproject.toml`/`uv.lock`, `Makefile`, `target/` + `docker-compose.yml`,
  `scripts/gen_data.py`, `src/schema.py` + `docs/SCHEMA.md` (terkunci), `src/load.py`
- **P6–P9:** `src/store.py` (`claim_one` `BEGIN IMMEDIATE`, `READY_AT` backoff+jitter),
  `src/worker.py` (Chromium headless, pagar target lokal D14), `src/run.py`, `src/recover.py`,
  `docs/RESUME_PROOF.md`. D7/D8 dikunci: `MAX_ATTEMPTS=5`, 1 dtk ×2 (atap 30), `LEASE=120`
- **P10–P13:** `src/dashboard.py` (SQLite `mode=ro`, HTMX), `scripts/run_summary.py`,
  `src/throughput.py` + `scripts/scale_bench.py` + `docs/THROUGHPUT.md`, `src/report.py`
  (gerbang 51 istilah jargon) + `docs/CONSULTATION.md` + `assets/sample_*`
- **P14:** `assets/demo.mp4` (113,9 dtk, 1080p, tanpa audio) + `before/crash/after.png` +
  `architecture.{dot,png}`; `Makefile` lengkap (`setup`/`all`/`verify`/`diagram`/`demo-video`);
  `scripts/secret_audit.py` + 15 test; `scripts/demo_{crash_run,dashboard,evidence}.sh` +
  `scripts/make_demo_video.sh`; README publik (legal D14 di atas); `docker-compose.yml`
  parametrik (port + nama container) untuk salinan bersih

## Fakta terverifikasi tentang mesin ini
- Python **3.13.13** · Docker/Compose/ffmpeg/Make/sqlite3/graphviz ada · port project `8110`/`8120`
  (salinan bersih `8111`/`8121`).
- `9router.service` (`:20128`) — JANGAN PERNAH disentuh (AGENTS §0). Bisa memutus sesi sendiri.
- Playwright pip `1.62.0`; jangan prune `~/.cache/ms-playwright` (chrome-devtools pin chromium-1228).
  `make` user = alias `make -j16`; pakai `/usr/bin/make`.
- Rekaman layar: skill `device-screen-recording` (output headless sekali-pakai, allowlist satu
  window class). Browser demo = `firefox --kiosk` profil sementara (Chromium `--app` membuka
  **dua** window dengan class sama → ditolak allowlist).

## Metrik (angka nyata dari file/DB hasil)

| Metrik | Target | Aktual |
|---|---|---|
| Record diproses tuntas | 50.000 | **49.950** terminal (50 dup ditolak DB); `pending`+`claimed` = 0 |
| Duplikat ref / konfirmasi | 0 / 0 | **0 / 0** di P11, P14 salinan bersih, dan P14 demo |
| Kill -9 saat run → tetap selesai | ≥2× | P11: 2×, ok 0→10.621→21.508→48.273, 7/7 yatim pulih · P14 demo: 2×, kill saat 35.990 & 48.273 → 48.273 akhir · P9: 2×, 8/8 yatim |
| Nomor konfirmasi tiap sukses | 100% | 48.273/48.273 `ok` berkonfirmasi, 0 kembar, 0 kosong |
| Kegagalan target tercatat | 100% | `dead` 833 = himpunan chaos `server_error` (5 percobaan, semua ber-`last_error`); `failed` 844 = `validation` 422 tanpa retry |
| Throughput | terukur | 81.915 rec/jam @8 (jenuh N=8); salinan bersih P14 @8: 98.650 ok/jam; run penuh P11 @4: 61.270 |
| Memori loader 10k→50k | datar | 50.600 → 57.044 KiB (+12,74%, bukan 5×) |
| Dashboard vs DB | selisih 0 | P10 (64 poll) & P11/P14 skala penuh: selisih 0 |
| Reproducible salinan bersih | exit 0 | `/tmp/surgeline-clean` port 8111: `make all` **exit 0**, ok 48.273 / failed 844 / dead 833 — **identik** dengan P11 |
| Audit rahasia | 0 kebocoran | 91 berkas ter-track, 0 kebocoran, 9 catatan jalur mesin di dokumen internal (disengaja) |
| Unit test hijau | selalu | **163/163 OK** (+2 cold-start, +15 audit) |
| Video demo | ≤ 2 mnt | **113,9 dtk** · 1920x1080 h264 yuv420p · tanpa audio · tanpa jendela/kredensial user |
| Acceptance project | 12/12 | **12/12** (A11 & A12 ditutup di P14) |

## Temuan audit
- ✅ Cold-start target ditutup di P14: `_connect()` tidak terkunci → beberapa thread request
  menjalankan `PRAGMA journal_mode=WAL` bersamaan → HTTP 500 asli `database is locked`.
  Perbaikan: init di balik `_init_lock` (double-checked) + `busy_timeout=15000`. Reproduksi
  perilaku lama: 15 koneksi terbuka + `OperationalError: database is locked`; sesudah: 1 koneksi,
  0 galat. 2 test regresi (`src/tests/test_target_coldstart.py`).
- ✅ R1 & R2 ditutup di P11 (`4ebcab3`, `5a50f26`): flaky kontrak; sapuan lease 41,0 → 23,0 dtk.
- Tidak ada temuan terbuka.

## Blocker & keputusan masih 🔓
- Tidak ada blocker. **Semua keputusan D1–D16 terkunci** — tidak ada 🔓 tersisa.
- D16 dikunci 2026-08-29 atas izin eksplisit user: repo `github.com/rayinailham/surgeline`
  kini **PUBLIK**. Gerbang sebelum flip: `make audit` 0 kebocoran + sapuan seluruh riwayat
  (20 commit, 157 blob, 0 pola kredensial, 0 artefak runtime pernah ter-commit).
- Masih butuh izin baru: `force-push`, hapus branch/repo, ubah history (mis. kalau nanti
  jalur mesin di dokumen internal mau dihapus dari riwayat).

1. Mesin dipakai paralel: jangan sentuh container di luar `surgeline-*`; `crosscheck-tut-*` (8090) & `~/infra/` haram.
2. Worker dipagari kode: hanya `127.0.0.1`/`localhost` (D14). Sebelum sesi ber-browser:
   `scripts/arch_provision.sh` + `playwright install chromium` (tanpa deps). Field record: SCHEMA §1.
