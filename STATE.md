# SurgeLine — STATE

> File hidup. Dibaca di awal tiap sesi, ditulis ulang di akhir tiap sesi.
> Satu-satunya memori antar sesi agent. Jaga tetap pendek (< 100 baris).

**Terakhir diperbarui:** 2026-08-28 (sesi P6)
**Status project:** 🟨 **JALAN** — 7/15 fase selesai, acceptance 1/12
**Fase aktif:** — (P6 selesai & ter-push)
**Fase berikutnya:** **P7 — Konkurensi** (N worker paralel, 0 double-claim; dasar `claim_one` sudah ada)

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
| P7 Konkurensi | ⬜ belum | N worker paralel, klaim atomik, 0 double-claim |
| P8 Ketahanan | ⬜ belum | retry+backoff, dead-letter, lease recovery |
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
- Repo privat `github.com/rayinailham/surgeline`, `origin/main` = commit `P06`. Kolom commit
  memakai **subjek** (`PNN`), bukan hash — sebuah commit tidak bisa memuat hash-nya sendiri.

## Fakta terverifikasi tentang mesin ini (P0, 2026-08-28)
- uv `0.12.1` · python project **3.13.13** (sistem 3.14.6) · Docker `29.6.2` · Compose `5.3.1` ·
  Node `v24.16.0` · ffmpeg `n8.1.2` · GNU Make `4.4.1` · sqlite3 CLI `3.53.4` **ada**
- Port `8110`/`8120` project. Container lain saat cek: `crosscheck-tut-wordpress-1` (8090) — jangan sentuh.
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
| Kill -9 saat run → tetap selesai | ≥2× | — |
| Kegagalan target ter-retry/tercatat | 100% | subset 24: 36 percobaan tercatat (ok 12, retryable 12, timeout 6, permanent 6); 500 → `pending`, 422 → `failed` + `last_error` |
| Nomor konfirmasi tersimpan tiap sukses | 100% | 195/195 (batch 200) + 12/12 (subset chaos); 0 `ok` tanpa konfirmasi, 0 bentuk di luar `SL-<8hex>` |
| Antrean WAL aktif | `journal_mode=wal` | ✅ persisten di file, terbaca proses lain (sqlite3 CLI) |
| Dashboard vs DB | selisih 0 | — |
| Throughput | terukur | — |
| Memori generator / loader | datar | gen 10k=49.956/50k=50.008 KiB; loader 10k=50.600/50k=57.044 KiB (+12,74%) |
| Unit test hijau | selalu | 73/73 OK (worker+store 30) |
| Acceptance project | 12/12 | 1/12 (A2 dedup DB) |

## Blocker & keputusan masih 🔓
- Tidak ada blocker. 🔓 D7 (retry/backoff, `max_attempts`) & D8 (lease) → **P8**; 🔓 D11 (dashboard) → **P10**.
- 🔓 D16 (repo publik) → **butuh izin eksplisit user**, jangan dikunci otomatis.

## Catatan tersisa untuk user
1. Mesin dipakai user paralel: jangan sentuh container di luar `surgeline-*`, `crosscheck-tut-*` (8090), `~/infra/`.
2. Nama field terkunci & cocok di form target, DATA_DICTIONARY, SCHEMA §1:
   `external_ref, full_name, email, policy_no, amount, notes`; `external_ref` = natural key (D4).
3. Worker dipagari kode: hanya `127.0.0.1`/`localhost` (D14). Sebelum sesi ber-browser jalankan
   `scripts/arch_provision.sh` + `uv run --no-sync playwright install chromium` (tanpa deps);
   Chromium terverifikasi `151.0.7922.34`.
4. Mode chaos `server_error` deterministik: job itu tidak akan pernah sukses. Sampai P8
   memasang `max_attempts`/dead-letter, jalankan worker dengan `--max-jobs` supaya run
   tidak berputar di job yang pasti gagal.
