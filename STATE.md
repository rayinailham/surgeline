# SurgeLine — STATE

> File hidup. Dibaca di awal tiap sesi, ditulis ulang di akhir tiap sesi.
> Satu-satunya memori antar sesi agent. Jaga tetap pendek (< 100 baris).

**Terakhir diperbarui:** 2026-08-28
**Status project:** 🟨 **JALAN** — 1/15 fase selesai, acceptance 0/12
**Fase aktif:** — (P0 selesai & ter-push)
**Fase berikutnya:** **P1 — Target App** (`docker-compose.yml` project, form `:8110`, nomor konfirmasi)

---
## Status fase

| Fase | Status | Catatan |
|---|---|---|
| P0 Bootstrap | ✅ selesai | commit `2409499`; uv+Makefile+env-check.md+smoke test; repo privat dibuat & di-push |
| P1 Target App | ⬜ belum | app form Docker `:8110`, submit → nomor konfirmasi, `docker-compose.yml` lokal |
| P2 Chaos & Kontrak Target | ⬜ belum | 5% gagal deterministik (500/lambat/validasi), oracle target, `docs/CHAOS.md` |
| P3 Generator Data | ⬜ belum | 50.000 record Excel+CSV, streamed, `docs/DATA_DICTIONARY.md` |
| P4 Kontrak Data & Skema | ⬜ belum | `docs/SCHEMA.md` terkunci: record + tabel `jobs`/`attempts`, `UNIQUE`, state machine |
| P5 Loader | ⬜ belum | `src/load.py` stream → antrean, dedup DB, memori datar, unit test |
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
- `Makefile` — `help`, `env`, `test`, `audit`; `target-up`/`target-down` masih stub (diisi P1)
- `src/tests/test_smoke.py` — 3 test (versi python, import dependency inti, pragma WAL D5)
- Repo privat `github.com/rayinailham/surgeline`, `origin/main` = `2409499`

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
| Record diproses | 50.000 | — |
| Duplikat (external_ref & confirmation) | 0 | — |
| Kill -9 saat run → tetap selesai | ≥2× | — |
| Kegagalan target ter-retry/tercatat | 100% | — |
| Nomor konfirmasi tersimpan tiap sukses | 100% | — |
| Dashboard vs DB | selisih 0 | — |
| Throughput | terukur | — |
| Memori loader | datar | — |
| Unit test hijau | selalu | 3/3 OK |
| Acceptance project | 12/12 | 0/12 |

## Blocker & keputusan masih 🔓
- Tidak ada blocker.
- 🔓 D7 (retry/backoff, `max_attempts`) & D8 (lease timeout) → dikunci di **P8**.
- 🔓 D11 (detail dashboard) → dikunci di **P10**.
- 🔓 D16 (repo publik) → **butuh izin eksplisit user**, jangan dikunci otomatis.

## Catatan tersisa untuk user
1. Repo GitHub dibuat sesi ini: `rayinailham/surgeline`, **privat**, akun personal. Push pertama OK.
2. P0 memakai **dua** commit (kode fase + bookkeeping DoD/STATE) karena DoD baru bisa dicentang
   setelah push berhasil. Mulai P1: update DoD & STATE **sebelum** commit → kembali 1 fase = 1 commit.
3. Mesin dipakai user paralel: jangan restart container di luar `surgeline-*`, jangan sentuh
   `crosscheck-tut-*` (8090) dan `/home/rayin/infra/`.
