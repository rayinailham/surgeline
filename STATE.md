# SurgeLine — STATE

> File hidup. Dibaca di awal tiap sesi, ditulis ulang di akhir tiap sesi.
> Satu-satunya memori antar sesi agent. Jaga tetap pendek (< 100 baris).

**Terakhir diperbarui:** 2026-08-28 (sesi remediasi R1)
**Status project:** 🟨 **JALAN** — 10/15 fase selesai, acceptance 5/12
**Fase aktif:** — (R1 selesai & ter-push; gerbang kesehatan hijau lagi)
**Fase berikutnya:** **P10 — Dashboard** (FastAPI+HTMX `:8120`, angka hidup cocok DB)

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
| P10 Dashboard | ⬜ belum | FastAPI+HTMX `:8120`, angka hidup cocok DB |
| P11 Run Penuh 50k | ⬜ belum | 50k + chaos + ≥2 kill → status akhir bersih, 0 dup |
| P12 Throughput | ⬜ belum | record/jam per N worker → ekstrapolasi 6 juta record |
| P13 Laporan + Konsultasi | ⬜ belum | `REPORT.xlsx`, digest 0 jargon, `docs/CONSULTATION.md` |
| P14 Packaging | ⬜ belum | video 2 mnt, `make all`, README publik, audit |

Legenda: ⬜ belum · 🟨 jalan · ✅ selesai · 🟥 blocked

## Artefak yang sudah lahir
- **P0:** `pyproject.toml`/`uv.lock`/`.python-version` (3.13), `env-check.md`, `Makefile`, 3 smoke test
- **P1:** `target/` (FastAPI form+validasi+konfirmasi, Dockerfile), `docker-compose.yml` root,
  `docs/TARGET.md` (selector D6), `test_target_contract.py` 7 test (skip kalau `:8110` mati)
- **P2:** chaos hash tiga mode di target + `docs/CHAOS.md`; `scripts/target_oracles.py` + `make target-oracles`
- **P3:** `scripts/gen_data.py` CSV+XLSX write-only (50k, seed 42), `docs/DATA_DICTIONARY.md`, 2 test
- **P4:** `src/schema.py` (WAL, `assert_transition`, `status_counts`), 24 test, `docs/SCHEMA.md` **terkunci** (`SCHEMA_VERSION=1`)
- **P5:** `src/load.py` stream CSV/XLSX + validasi sebelum `INSERT OR IGNORE`; `src/test_load.py` 6 test
- **P6:** `src/store.py` (`claim_one` `BEGIN IMMEDIATE`, `mark_ok`/`mark_failed`/`release`;
  transisi + audit satu transaksi), `src/worker.py` (Chromium headless, parser halaman hasil,
  pagar target lokal D14), `src/test_worker.py` 30 test dgn fixture HTML
- **P7:** `src/run.py` runner N proses + retry write lock; `src/test_concurrency.py` (union 500 job, irisan kosong)
- **P8:** `store.READY_AT` (backoff+jitter deterministik, tanpa kolom baru), `store.release`
  → dead-letter, `store.time_until_ready`, `store.recover_stuck` (sapuan lease + tutup audit
  yatim), `src/recover.py` CLI; `src/test_resilience.py` 16 test. D7/D8 **dikunci**:
  `MAX_ATTEMPTS=5`, base 1 dtk ×2 (atap 30 dtk), jitter 0-25%, `LEASE_TIMEOUT_SECONDS=120`
- **P9:** `docs/RESUME_PROOF.md`; chaos 3.000 job, 2× kill paksa, 8 klaim yatim disapu lease; rekaman → P14.
- **R1:** perbaikan flaky test kontrak target (lihat §Temuan); 2 test regresi baru.
- Repo privat `github.com/rayinailham/surgeline`; kolom commit memakai subjek (`PNN`), bukan hash.

## Fakta terverifikasi tentang mesin ini (P0, 2026-08-28)
- Python **3.13.13** · Docker/Compose/ffmpeg/Make/sqlite3 ada · port project `8110`/`8120`.
- `9router.service` (`:20128`) `active` — JANGAN PERNAH disentuh (AGENTS §0). Bisa memutus sesi sendiri.
- Playwright pip `1.62.0`; jangan prune `~/.cache/ms-playwright` (chrome-devtools pin chromium-1228).
- `make` user = alias `make -j16`; pakai `/usr/bin/make`. Skill `bulk-form-runner` tidak terpasang.

## Metrik (diisi angka nyata saat fase berjalan)

| Metrik | Target | Aktual |
|---|---|---|
| Target app hidup | :8110 healthy | ✅ `surgeline-target` Up (healthy) |
| Target: konfirmasi idempoten per `external_ref` | identik | ✅ 600 req / 300 ref / 32 thread → 303 baris, 303 konfirmasi unik, 0 duplikat |
| Chaos deterministik | ≈5%, 3 mode, 2 run identik | 112/2.000 = 5,60%; 500=38, lambat=39, validasi=35; diff=0 |
| Record data uji | 50.000 | 50.000 CSV + XLSX; 49.950 key unik + 50 dup sengaja; 0 invalid |
| Duplikat external_ref antrean | 0 | 50k dibaca → 49.950 pending; 50 dup ditolak; reload: 0 masuk/50k ditolak; DB dup=0 |
| Kill -9 saat run → tetap selesai | ≥2× | P9: 2×; ok 423→804→2.907; 8/8 klaim yatim pulih; terminal 3.000/3.000; dup ref/konfirmasi 0/0 |
| Kegagalan target ter-retry/tercatat | 100% | chaos 100 job: audit ok 80 / retryable 50 / permanent 10; `dead` 10 (5 percobaan, 100% ber-`last_error`), `failed` 10 (422, 1 percobaan, tanpa retry), 0 pending/claimed tersisa |
| Gangguan sementara → akhirnya sukses | 100% | target dimatikan di tengah run: 20 job `retryable` → target hidup → 20/20 `ok` di percobaan ke-3 |
| Nomor konfirmasi tersimpan tiap sukses | 100% | 195/195 (batch 200) + 80/80 (chaos P8) + 20/20 (gangguan sementara); 0 `ok` tanpa konfirmasi, 0 duplikat konfirmasi |
| Antrean WAL aktif | `journal_mode=wal` | ✅ persisten di file, terbaca proses lain (sqlite3 CLI) |
| Klaim paralel | 0 double-claim | 4 worker, 500 attempts; 489 ok = 489 ref unik; 0 sukses oleh >1 worker |
| Dashboard vs DB | selisih 0 | — |
| Throughput | terukur | 25,86 job/dtk @4 worker (500 attempts / 19,335 dtk; baseline P12) |
| Memori generator / loader | datar | gen 10k=49.956/50k=50.008 KiB; loader 10k=50.600/50k=57.044 KiB (+12,74%) |
| Unit test hijau | selalu | 93/93 OK; `test_target_contract` 40 run berturut, gagal=0 (R1) |
| Acceptance project | 12/12 | 5/12 (A2/A3 dedup+resume, A4 retry/dead-letter, A9 klaim atomik, A10 lease recovery) |

## Temuan audit (ditutup)
- **R1 (2026-08-28, ditutup):** `test_target_contract.py` menarik `external_ref` acak
  (`uuid4`) padahal chaos deterministik atas `external_ref` (D3) → **1.051/20.000 = 5,25%**
  ref kena chaos; 2 test terdampak ≈10% run gerbang merah, menyamar sebagai regresi target.
  Fix: `_honest_ref()` menarik ref sampai `target.app._chaos_mode` (fungsi milik target;
  seed+rate dari `/health` container) bilang bebas chaos. Regresi anti-drift:
  `test_honest_ref_selalu_bebas_chaos` + `test_prediksi_chaos_cocok_dengan_target_hidup`
  (3 mode dibalas 500/422/200 + header `X-SurgeLine-Chaos`). Target tidak disentuh (D3).

## Blocker & keputusan masih 🔓
- Tidak ada blocker. D7 & D8 **terkunci di P8**. 🔓 D11 (dashboard) → **P10**.
- 🔓 D16 (repo publik) → **butuh izin eksplisit user**, jangan dikunci otomatis.

1. Mesin dipakai paralel: jangan sentuh container di luar `surgeline-*`; `crosscheck-tut-*` (8090) & `~/infra/` haram.
2. Field terkunci (form target = DATA_DICTIONARY = SCHEMA §1):
   `external_ref, full_name, email, policy_no, amount, notes`; `external_ref` = natural key (D4).
3. Worker dipagari kode: hanya `127.0.0.1`/`localhost` (D14). Sebelum sesi ber-browser:
   `scripts/arch_provision.sh` + `playwright install chromium` (tanpa deps); Chromium `151.0.7922.34`.
4. Mode chaos `server_error` berhenti di `dead` setelah 5 percobaan. Bukti P9 (versi P8):
   2.907 ok, 44 failed, 49 dead; 0 status nonterminal.
