# SurgeLine — STATE

> File hidup. Dibaca di awal tiap sesi, ditulis ulang di akhir tiap sesi.
> Satu-satunya memori antar sesi agent. Jaga tetap pendek (< 100 baris).

**Terakhir diperbarui:** 2026-08-28 (sesi P8)
**Status project:** 🟨 **JALAN** — 9/15 fase selesai, acceptance 4/12
**Fase aktif:** — (P8 selesai & ter-push)
**Fase berikutnya:** **P9 — Bukti Crash-Recovery** (kill -9 ≥2× → resume → 0 dup; `docs/RESUME_PROOF.md`)

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
| P9 Bukti Crash-Recovery | ⬜ belum | kill -9 ≥2× → resume → 0 dup, `docs/RESUME_PROOF.md` |
| P10 Dashboard | ⬜ belum | FastAPI+HTMX `:8120`, angka hidup cocok DB |
| P11 Run Penuh 50k | ⬜ belum | 50k + chaos + ≥2 kill → status akhir bersih, 0 dup |
| P12 Throughput | ⬜ belum | record/jam per N worker → ekstrapolasi 6 juta record |
| P13 Laporan + Konsultasi | ⬜ belum | `REPORT.xlsx`, digest 0 jargon, `docs/CONSULTATION.md` |
| P14 Packaging | ⬜ belum | video 2 mnt, `make all`, README publik, audit |

Legenda: ⬜ belum · 🟨 jalan · ✅ selesai · 🟥 blocked

## Artefak yang sudah lahir
- **P0:** `pyproject.toml`/`uv.lock`/`.python-version` (3.13), `env-check.md`, `Makefile`
  (`help env test audit target-up target-down target-oracles`), `src/tests/test_smoke.py` 3 test
- **P1:** `target/` (FastAPI form + validasi + nomor konfirmasi, Dockerfile, requirements ter-pin),
  `docker-compose.yml` root; `docs/TARGET.md` (endpoint, 6 field, selector kontrak D6);
  `src/tests/test_target_contract.py` 5 test (skip otomatis kalau `:8110` mati)
- **P2:** chaos hash tiga mode di target + `docs/CHAOS.md`; `scripts/target_oracles.py`
  + `make target-oracles` (dua target segar × 2.000 request)
- **P3:** `scripts/gen_data.py` CSV+XLSX write-only deterministik (50k, seed 42),
  `docs/DATA_DICTIONARY.md`, 2 test regresi; data hasil tetap gitignored
- **P4:** `src/schema.py` (WAL+busy_timeout, `assert_transition`, `status_counts`),
  `src/tests/test_schema.py` 24 test, `docs/SCHEMA.md` **terkunci** (`SCHEMA_VERSION=1`)
- **P5:** `src/load.py` stream CSV/XLSX + validasi sebelum `INSERT OR IGNORE`;
  `src/test_load.py` 6 test
- **P6:** `src/store.py` (`claim_one` `BEGIN IMMEDIATE`, `mark_ok`/`mark_failed`/`release`,
  transisi + baris audit dalam satu transaksi), `src/worker.py` (Chromium headless, parser
  halaman hasil, pagar target lokal D14), `src/test_worker.py` 30 test dgn fixture HTML
- **P6 perbaikan:** klaim `pending` diurut `updated_at` + index `idx_jobs_status_updated_at`
  (sebelumnya `rowid` → 1 job gagal memakan 24 percobaan, 23 job lain tak tersentuh);
  `docs/SCHEMA.md` §3 & `src/schema.py` diperbarui bersama, `SCHEMA_VERSION` tetap 1
- **P7:** `src/run.py` runner N proses + pembagian limit; retry singkat write lock di `src/store.py`;
  `src/test_concurrency.py` membuktikan union 500 job, irisan worker kosong, dan retry lock
- **P8:** `store.READY_AT` (backoff eksponensial + jitter deterministik, tanpa kolom baru),
  `store.release` → dead-letter saat jatah habis, `store.time_until_ready`,
  `store.recover_stuck` (sapuan lease + menutup baris audit percobaan yang ditinggal mati),
  `src/recover.py` CLI, worker menunggu backoff & menyapu lease berkala;
  `src/test_resilience.py` 16 test. D7/D8 **dikunci**: `MAX_ATTEMPTS=5`, base 1 dtk ×2
  (atap 30 dtk), jitter 0-25%, `LEASE_TIMEOUT_SECONDS=120`
- **P8 koreksi dokumen:** `phases/phase-08` minta kolom `not_before` — bertentangan dengan
  `docs/SCHEMA.md` §3 (SCHEMA menang, AGENTS §5); file fase diperbaiki di sesi yang sama
- Repo privat `github.com/rayinailham/surgeline`, `origin/main` = commit `P07`. Kolom commit
  memakai **subjek** (`PNN`), bukan hash — sebuah commit tidak bisa memuat hash-nya sendiri.

## Fakta terverifikasi tentang mesin ini (P0, 2026-08-28)
- Python project **3.13.13** · Docker/Compose/ffmpeg/Make/sqlite3 CLI ada · port project `8110`/`8120`.
- `9router.service` (`:20128`) `active` — JANGAN PERNAH disentuh (AGENTS §0). Bisa memutus sesi sendiri.
- Playwright pip `1.62.0`; cache `~/.cache/ms-playwright` (2,0 GB) berisi chromium-1228/1234, firefox-1538,
  webkit-2336. Jangan prune (MCP chrome-devtools pin chromium-1228).
- Di shell interaktif user, `make` = alias `make -j16`. Untuk pasti, panggil `/usr/bin/make`.
- Skill `bulk-form-runner` yang disebut portofolio **tidak terpasang** → playbook ditulis sendiri di `docs/` + fase.

## Metrik (diisi angka nyata saat fase berjalan)

| Metrik | Target | Aktual |
|---|---|---|
| Target app hidup | :8110 healthy | ✅ `surgeline-target` Up (healthy) |
| Target: konfirmasi idempoten per `external_ref` | identik | ✅ 600 req / 300 ref / 32 thread → 303 baris, 303 konfirmasi unik, 0 duplikat |
| Chaos deterministik | ≈5%, 3 mode, 2 run identik | 112/2.000 = 5,60%; 500=38, lambat=39, validasi=35; diff=0 |
| Record data uji | 50.000 | 50.000 CSV + XLSX; 49.950 key unik + 50 dup sengaja; 0 invalid |
| Duplikat external_ref antrean | 0 | 50k dibaca → 49.950 pending; 50 dup ditolak; reload: 0 masuk/50k ditolak; DB dup=0 |
| Kill -9 saat run → tetap selesai | ≥2× | 1× (P8/A10): worker mati saat `claimed` → lease → `pending` → `ok`, attempts 2, dup 0. Full run ≥2× di P9 |
| Kegagalan target ter-retry/tercatat | 100% | chaos 100 job: audit ok 80 / retryable 50 / permanent 10; `dead` 10 (5 percobaan, 100% ber-`last_error`), `failed` 10 (422, 1 percobaan, tanpa retry), 0 pending/claimed tersisa |
| Gangguan sementara → akhirnya sukses | 100% | target dimatikan di tengah run: 20 job `retryable` → target hidup → 20/20 `ok` di percobaan ke-3 |
| Nomor konfirmasi tersimpan tiap sukses | 100% | 195/195 (batch 200) + 80/80 (chaos P8) + 20/20 (gangguan sementara); 0 `ok` tanpa konfirmasi, 0 duplikat konfirmasi |
| Antrean WAL aktif | `journal_mode=wal` | ✅ persisten di file, terbaca proses lain (sqlite3 CLI) |
| Klaim paralel | 0 double-claim | 4 worker, 500 attempts; 489 ok = 489 ref unik; 0 sukses oleh >1 worker |
| Dashboard vs DB | selisih 0 | — |
| Throughput | terukur | 25,86 job/dtk @4 worker (500 attempts / 19,335 dtk; baseline P12) |
| Memori generator / loader | datar | gen 10k=49.956/50k=50.008 KiB; loader 10k=50.600/50k=57.044 KiB (+12,74%) |
| Unit test hijau | selalu | 91/91 OK (termasuk 16 test ketahanan P8) |
| Acceptance project | 12/12 | 4/12 (A2 dedup DB, A4 retry/dead-letter, A9 klaim atomik, A10 lease recovery) |

## Blocker & keputusan masih 🔓
- Tidak ada blocker. D7 & D8 **terkunci di P8**. 🔓 D11 (dashboard) → **P10**.
- 🔓 D16 (repo publik) → **butuh izin eksplisit user**, jangan dikunci otomatis.

1. Mesin dipakai user paralel: jangan sentuh container di luar `surgeline-*`, `crosscheck-tut-*` (8090), `~/infra/`.
2. Nama field terkunci & cocok di form target, DATA_DICTIONARY, SCHEMA §1:
   `external_ref, full_name, email, policy_no, amount, notes`; `external_ref` = natural key (D4).
3. Worker dipagari kode: hanya `127.0.0.1`/`localhost` (D14). Sebelum sesi ber-browser jalankan
   `scripts/arch_provision.sh` + `uv run --no-sync playwright install chromium` (tanpa deps);
   Chromium terverifikasi `151.0.7922.34`.
4. Mode chaos `server_error` deterministik: job itu tidak akan pernah sukses — sejak P8 ia
   berhenti sendiri di `dead` setelah 5 percobaan, jadi `--max-jobs` tidak lagi wajib.
5. Perubahan P8 mengubah perilaku run (backoff menambah waktu tunggu job gagal). Bukti P9
   harus dijalankan dari versi ini, bukan diambil dari run P6/P7.
