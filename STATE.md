# SurgeLine — STATE

> File hidup. Dibaca di awal tiap sesi, ditulis ulang di akhir tiap sesi.
> Satu-satunya memori antar sesi agent. Jaga tetap pendek (< 100 baris).

**Terakhir diperbarui:** 2026-08-28 (sesi P5)
**Status project:** 🟨 **JALAN** — 6/15 fase selesai, acceptance 1/12
**Fase aktif:** — (P5 selesai & ter-push)
**Fase berikutnya:** **P6 — Worker** (`src/worker.py` Playwright headless → target lokal `:8110`)

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
| P6 Worker | ⬜ belum | `src/worker.py` Playwright: klaim → isi → tangkap nomor konfirmasi |
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
- `pyproject.toml`, `uv.lock`, `.python-version` (3.13) — dependency terkunci, reproducible
- `env-check.md` — verifikasi lingkungan nyata (versi tool, port, browser cache)
- `Makefile` — `help`, `env`, `test`, `audit`, `target-up`, `target-down`
- `src/tests/test_smoke.py` — 3 test (versi python, import dependency inti, pragma WAL D5)
- **P1:** `target/app.py` (FastAPI form + validasi + nomor konfirmasi), `target/Dockerfile`,
  `target/requirements.txt` (ter-pin), `docker-compose.yml` di root (container `surgeline-target`)
- **P1:** `docs/TARGET.md` terisi — endpoint, 6 field + aturan validasi, tabel selector kontrak (D6)
- **P1:** `src/tests/test_target_contract.py` — 5 test (skip otomatis kalau `:8110` mati)
- **P2:** chaos hash deterministik tiga mode di target; `docs/CHAOS.md` mengunci kontrak worker P8
- **P2:** `scripts/target_oracles.py` + `make target-oracles`; dua target segar × 2.000 request
- **P3:** `scripts/gen_data.py` → CSV + XLSX write-only deterministik; 50.000 row, seed 42
- **P3:** `docs/DATA_DICTIONARY.md` + 2 test regresi generator; data hasil tetap gitignored
- **P4:** `src/schema.py` (`init_db`/`connect`/`assert_transition`/`status_counts`, WAL+busy_timeout),
  `src/tests/test_schema.py` (24 test), `docs/SCHEMA.md` **terkunci** (`SCHEMA_VERSION=1`)
- **P5:** `src/load.py` stream CSV/XLSX, validasi sebelum `INSERT OR IGNORE`, transaksi batch;
  `src/test_load.py` 6 test; DB bukti `data/p05-demo/queue.db` gitignored
- Repo privat `github.com/rayinailham/surgeline`, `origin/main` = commit `P05` (P0 = `2409499`)
  Sebuah commit tidak bisa memuat hash-nya sendiri, jadi mulai P1 kolom commit memakai
  **subjek** (`PNN`), bukan hash. Hash dilihat dengan `git log --oneline`.

## Fakta terverifikasi tentang mesin ini (P0, 2026-08-28)
- uv `0.12.1` · python project **3.13.13** (sistem 3.14.6, di-pin ke 3.13) · Docker `29.6.2` ·
  Compose `5.3.1` · Node `v24.16.0` · ffmpeg `n8.1.2` · GNU Make `4.4.1` · sqlite3 CLI `3.53.4` **ada**
- Port `8110` & `8120` **bebas**. Container jalan saat cek: hanya `crosscheck-tut-wordpress-1` (8090) — jangan sentuh.
- `9router.service` (`:20128`) `active` — JANGAN PERNAH disentuh (AGENTS §0). Bisa memutus sesi sendiri.
- Playwright pip `1.62.0`; cache `~/.cache/ms-playwright` (2,0 GB) berisi chromium-1228/1234, firefox-1538,
  webkit-2336. Jangan prune (MCP chrome-devtools pin chromium-1228). `playwright install chromium` baru di P6.
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
| Kegagalan target ter-retry/tercatat | 100% | — |
| Nomor konfirmasi tersimpan tiap sukses | 100% | — |
| Antrean WAL aktif | `journal_mode=wal` | ✅ persisten di file, terbaca proses lain (sqlite3 CLI) |
| Dashboard vs DB | selisih 0 | — |
| Throughput | terukur | — |
| Memori generator / loader | datar | gen 10k=49.956/50k=50.008 KiB; loader 10k=50.600/50k=57.044 KiB (+12,74%) |
| Unit test hijau | selalu | 43/43 OK (loader 6/6) |
| Acceptance project | 12/12 | 1/12 (A2 dedup DB) |

## Blocker & keputusan masih 🔓
- Tidak ada blocker.
- 🔓 D7 (retry/backoff, `max_attempts`) & D8 (lease timeout) → dikunci di **P8**.
- 🔓 D11 (detail dashboard) → dikunci di **P10**.
- 🔓 D16 (repo publik) → **butuh izin eksplisit user**, jangan dikunci otomatis.

## Catatan tersisa untuk user
1. Repo GitHub dibuat sesi ini: `rayinailham/surgeline`, **privat**, akun personal. Push pertama OK.
2. Mesin dipakai user paralel: jangan restart container di luar `surgeline-*`, jangan sentuh
   `crosscheck-tut-*` (8090) dan `/home/rayin/infra/`.
3. Nama field terkunci di 3 tempat yang sudah cocok (form target, DATA_DICTIONARY, SCHEMA §1):
   `external_ref, full_name, email, policy_no, amount, notes`. `external_ref` = natural key (D4).
4. P6 wajib menjalankan `scripts/arch_provision.sh` dulu, worker hanya target lokal `127.0.0.1:8110`,
   dan tangkap nomor konfirmasi; `playwright install chromium` tanpa deps.
