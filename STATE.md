# SurgeLine — STATE

> File hidup. Dibaca di awal tiap sesi, ditulis ulang di akhir tiap sesi.
> Satu-satunya memori antar sesi agent. Jaga tetap pendek (< 100 baris).

**Terakhir diperbarui:** 2026-08-29 (sesi P13)
**Status project:** 🟨 **JALAN** — 14/15 fase selesai, acceptance 10/12
**Fase aktif:** — (P13 ditutup & ter-push; gerbang kesehatan hijau, 146/146)
**Fase berikutnya:** **P14 Packaging** (tidak ada temuan terbuka; A11+A12 ditutup di sana)

---
## Status fase

| Fase | Status | Catatan |
|---|---|---|
| P0 Bootstrap | ✅ selesai | commit `2409499`; uv+Makefile+env-check.md+smoke test; repo privat dibuat & di-push |
| P1 Target App | ✅ selesai | commit `P01`; `surgeline-target` :8110 healthy, form 6 field, `SL-<8hex>` idempoten, 0 duplikat @600 req |
| P2 Chaos & Kontrak Target | ✅ selesai | commit `P02`; 112/2.000 = 5,60%, mode 38/39/35, 2 run diff=0, oracle PASS |
| P3 Generator Data | ✅ selesai | commit `P03`; 50k CSV+XLSX, 50 dup sengaja, RSS 48,84 MiB datar |
| P4 Kontrak Data & Skema | ✅ selesai | commit `P04`; `docs/SCHEMA.md` terkunci, `src/schema.py` WAL, dedup `1\|1\|0`, 24 test skema |
| P5 Loader | ✅ selesai | commit `P05`; 50k dibaca → 49.950 pending, 50 dup ditolak DB; reload +50k ditolak; RSS 55,71 MiB |
| P6 Worker | ✅ selesai | commit `P06`; 200 job: ok=195 (195 konfirmasi unik, 0 kosong), failed=5; subset 4-mode: ok/retryable/timeout/permanent = 12/12/6/6 |
| P7 Konkurensi | ✅ selesai | commit `P07`; 4 worker, 500 klaim, 0 double-success, 25,86 job/dtk; 2 test konkurensi |
| P8 Ketahanan | ✅ selesai | commit `P08`; chaos 100: ok 80 / failed 10 / dead 10 (semua ber-`last_error`); kill -9 → lease → ok |
| P9 Bukti Crash-Recovery | ✅ selesai | commit `P09`; 3k chaos, kill -9 2×, ok 423→804→2.907, 8 yatim pulih, 0 dup |
| P10 Dashboard | ✅ selesai | commit `P10`; read-only :8120, HTMX 2 dtk, 6 angka + throughput, selisih DB=0 |
| P11 Run Penuh 50k | ✅ selesai | commit `P11`; 49.950 tuntas, ok 48.273/failed 844/dead 833, dup 0/0, 2 kill, 7 yatim pulih, 2.837,8 dtk |
| P12 Throughput | ✅ selesai | commit `P12`; 7 nilai N di subset sama, 81.915 rec/jam @8, jenuh N=8, 6 juta ≈ 3,0 hari |
| P13 Laporan + Konsultasi | ✅ selesai | commit `P13`; `REPORT.xlsx` 5 lembar, digest 0 jargon (51 istilah), CONSULTATION 1 hlm, 24 test |
| P14 Packaging | ⬜ belum | video 2 mnt, `make all`, README publik, audit |

Legenda: ⬜ belum · 🟨 jalan · ✅ selesai · 🟥 blocked

## Artefak yang sudah lahir
- **P0/P1:** `pyproject.toml`/`uv.lock` (3.13), `env-check.md`, `Makefile`; `target/` (FastAPI
  form+konfirmasi, Dockerfile) + `docker-compose.yml` root, `docs/TARGET.md`, 10 test
- **P2/P3:** chaos hash 3 mode + `docs/CHAOS.md` + `scripts/target_oracles.py`; `scripts/gen_data.py` CSV+XLSX write-only (50k, seed 42) + `docs/DATA_DICTIONARY.md`
- **P4/P5:** `src/schema.py` + `docs/SCHEMA.md` **terkunci** (`SCHEMA_VERSION=1`, 24 test); `src/load.py` stream CSV/XLSX + validasi sebelum `INSERT OR IGNORE` (6 test)
- **P6/P7:** `src/store.py` (`claim_one` `BEGIN IMMEDIATE`, transisi+audit satu transaksi),
  `src/worker.py` (Chromium headless, pagar target lokal D14), `src/run.py` runner N proses; 32 test
- **P8:** `store.READY_AT` (backoff+jitter deterministik), dead-letter, `recover_stuck`,
  `src/recover.py`, 16 test. D7/D8 **dikunci**: `MAX_ATTEMPTS=5`, 1 dtk ×2 (atap 30),
  jitter 0-25%, `LEASE_TIMEOUT_SECONDS=120`
- **P9/P10:** `docs/RESUME_PROOF.md` (3.000 job, 2× kill, 8 yatim); `src/dashboard.py` + HTMX lokal,
  SQLite `mode=ro`, 15 test; rekaman & screenshot → P14.
- **P11/R2:** `scripts/run_summary.py` → `data/<run>/run.json`; run penuh `data/full50k/` + log
  kill (gitignored), bukti di `phases/phase-11-full-run.md`; `worker._drain_queue` (jam & sleep
  disuntik). Repo privat `github.com/rayinailham/surgeline`; kolom commit memakai subjek `PNN`.
- **P12:** `src/throughput.py` (jendela wall-clock, tabel skala, titik jenuh, ekstrapolasi) +
  `scripts/scale_bench.py` (sapuan N worker di subset adil, menolak menimpa run lama) +
  `docs/THROUGHPUT.md` (7 nilai N, ulangan < 1%, asumsi terbuka, kalimat proposal); 12 test.
- **P13:** `src/report.py` (query ulang `queue.db` `mode=ro` → digest + `REPORT.xlsx` 5 lembar;
  gerbang 51 istilah terlarang **menolak menulis file** kalau jargon bocor, lembar `Bukti`
  dikecualikan; `--kills`/`--scale` satu-satunya masukan non-DB; `--sanitize` untuk repo) +
  `docs/CONSULTATION.md` + `docs/CLIENT_REPORT.md` + `assets/sample_{daily.md,REPORT.xlsx}`;
  24 test. `docs/ACCEPTANCE.md` dikoreksi: A1/A3/A5/A6/A8 ✅ sejak P5-P11 tapi belum tercentang.

## Fakta terverifikasi tentang mesin ini (P0, 2026-08-28)
- Python **3.13.13** · Docker/Compose/ffmpeg/Make/sqlite3 ada · port project `8110`/`8120`.
- `9router.service` (`:20128`) `active` — JANGAN PERNAH disentuh (AGENTS §0). Bisa memutus sesi sendiri.
- Playwright pip `1.62.0`; jangan prune `~/.cache/ms-playwright` (chrome-devtools pin chromium-1228).
  `make` user = alias `make -j16`; pakai `/usr/bin/make`.

## Metrik (diisi angka nyata saat fase berjalan)

| Metrik | Target | Aktual |
|---|---|---|
| Target app hidup | :8110 healthy | ✅ `surgeline-target` Up (healthy) |
| Target: konfirmasi idempoten per `external_ref` | identik | ✅ 600 req / 300 ref / 32 thread → 303 baris, 303 konfirmasi unik, 0 duplikat |
| Chaos deterministik | ≈5%, 3 mode, 2 run identik | 112/2.000 = 5,60%; 500=38, lambat=39, validasi=35; diff=0 |
| Record data uji | 50.000 | 50.000 CSV + XLSX; 49.950 key unik + 50 dup sengaja; 0 invalid |
| Duplikat external_ref antrean | 0 | 50k dibaca → 49.950 pending; 50 dup ditolak; reload: 0 masuk/50k ditolak; DB dup=0 |
| Latensi sapuan lease (yatim lahir saat antrean penuh) | ≤ lease/2 | **23,0 dtk @ lease 60** (sisa pending 136); kode lama 41,0 dtk (sisa pending 4) — R2 |
| Kill -9 saat run → tetap selesai | ≥2× | **P11 (50k): 2×; ok 0→10.621→21.508→48.273; 7/7 yatim pulih (semua `ok`); terminal 49.950/49.950; dup ref/konfirmasi 0/0**. P9 (3k): 2×, 8/8 yatim pulih |
| Kegagalan target ter-retry/tercatat | 100% | P11 50k: `dead` 833 = **persis** himpunan chaos `server_error` (5 percobaan, 100% ber-`last_error`); `failed` 844 = **persis** himpunan `validation` (422, 1 percobaan, tanpa retry); `slow` 842 + jujur 47.431 semuanya `ok` |
| Gangguan sementara → akhirnya sukses | 100% | target dimatikan di tengah run: 20 job `retryable` → target hidup → 20/20 `ok` di percobaan ke-3 |
| Nomor konfirmasi tersimpan tiap sukses | 100% | P11: 48.273/48.273 `ok` berkonfirmasi, 0 duplikat konfirmasi, 0 `ok` kosong |
| Antrean WAL aktif | `journal_mode=wal` | ✅ persisten di file, terbaca proses lain (sqlite3 CLI) |
| Klaim paralel | 0 double-claim | 4 worker, 500 attempts; 489 ok = 489 ref unik; 0 sukses oleh >1 worker |
| Dashboard vs DB | selisih 0 | P11 skala penuh: 49.950 = ok 48.273 + failed 844 + dead 833, pending/claimed 0; selisih 0 (P10: 64 poll HTTP 200, selisih 0) |
| Throughput | terukur | **81.915 rec/jam @8 worker** (jenuh N=8: N=12 hanya +4,2%, N=16 −0,9%, N=24 −4,7%). Skala: 22.204/40.627/63.565/81.915/85.388/84.631/80.664 rec/jam @ N=1/2/4/8/12/16/24, subset 800 identik (ok 776/failed 17/dead 7 di ketujuhnya). Ulangan N=4 +0,7%, N=8 +0,03%. Skala penuh P11 @4: 61.270 rec/jam (−3,6% vs subset @4 walau 62× lebih besar + 2 kill) |
| Memori generator / loader | datar | gen 10k=49.956/50k=50.008 KiB; loader 10k=50.600/50k=57.044 KiB (+12,74%) |
| Unit test hijau | selalu | **146/146 OK** (+24 test P13); 15 test dashboard OK; `test_target_contract` 40 run berturut, gagal=0 (R1) |
| Laporan klien | 0 jargon, tiap angka dari DB | `REPORT.xlsx` 5 lembar (17/5/10/3/13 baris) + digest dari `full50k`: 49.950 · ok 48.273 (96,6%) · 844 ditolak · 833 habis percobaan · dup 0/0 · 47 mnt 16 dtk · 61.270 data/jam. Validator: digest `[]`, kalimat teknis uji → 5 istilah tertangkap |
| Acceptance project | 12/12 | 10/12 (P12 menutup A7 throughput terukur + ekstrapolasi 6 juta; sisa A8 memori loader ✅ terukur di P5 tapi belum dicentang, A11 salinan bersih & A12 di P14) |

## Temuan audit
- ⬜ Target cold-start: 1 HTTP 500 asli (`PRAGMA journal_mode=WAL` → `database is locked`) saat 4
  worker menabrak container segar. Milik target, worker pulih sendiri. Rapikan di P14, bukan bug D3.
- ✅ R1 & R2 ditutup (commit `4ebcab3`, `5a50f26`): flaky kontrak, dan sapuan lease dijadwalkan
  waktu (41,0 → **23,0 dtk**, ≤ lease/2); masing-masing 2 test regresi.

## Blocker & keputusan masih 🔓
- Tidak ada blocker. D7 & D8 terkunci di P8; D11 terkunci di P10. Tidak ada 🔓 jatuh di P13.
- 🔓 D16 (repo publik) → **butuh izin eksplisit user**, jangan dikunci otomatis.

1. Mesin dipakai paralel: jangan sentuh container di luar `surgeline-*`; `crosscheck-tut-*` (8090) & `~/infra/` haram.
2. Worker dipagari kode: hanya `127.0.0.1`/`localhost` (D14). Sebelum sesi ber-browser:
   `scripts/arch_provision.sh` + `playwright install chromium` (tanpa deps). Field record: SCHEMA §1.
