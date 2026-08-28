# SurgeLine — STATE

> File hidup. Dibaca di awal tiap sesi, ditulis ulang di akhir tiap sesi.
> Satu-satunya memori antar sesi agent. Jaga tetap pendek (< 100 baris).

**Terakhir diperbarui:** 2026-08-28
**Status project:** 🟨 **JALAN** — 2/15 fase selesai, acceptance 0/12
**Fase aktif:** — (P1 selesai & ter-push)
**Fase berikutnya:** **P2 — Chaos & Kontrak Target** (5% gagal deterministik, oracle, `docs/CHAOS.md`)

---
## Status fase

| Fase | Status | Catatan |
|---|---|---|
| P0 Bootstrap | ✅ selesai | commit `2409499`; uv+Makefile+env-check.md+smoke test; repo privat dibuat & di-push |
| P1 Target App | ✅ selesai | commit `P01`; `surgeline-target` :8110 healthy, form 6 field, `SL-<8hex>` idempoten, 0 duplikat @600 req |
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
- `Makefile` — `help`, `env`, `test`, `audit`, `target-up`, `target-down`
- `src/tests/test_smoke.py` — 3 test (versi python, import dependency inti, pragma WAL D5)
- **P1:** `target/app.py` (FastAPI form + validasi + nomor konfirmasi), `target/Dockerfile`,
  `target/requirements.txt` (ter-pin), `docker-compose.yml` di root (container `surgeline-target`)
- **P1:** `docs/TARGET.md` terisi — endpoint, 6 field + aturan validasi, tabel selector kontrak (D6)
- **P1:** `src/tests/test_target_contract.py` — 5 test (skip otomatis kalau `:8110` mati)
- Repo privat `github.com/rayinailham/surgeline`, `origin/main` = commit `P01` (P0 = `2409499`)
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
| Record diproses | 50.000 | — |
| Duplikat (external_ref & confirmation) | 0 | — |
| Kill -9 saat run → tetap selesai | ≥2× | — |
| Kegagalan target ter-retry/tercatat | 100% | — |
| Nomor konfirmasi tersimpan tiap sukses | 100% | — |
| Dashboard vs DB | selisih 0 | — |
| Throughput | terukur | — |
| Memori loader | datar | — |
| Unit test hijau | selalu | 8/8 OK |
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
4. P1: form target punya **6** field — `external_ref` ditambahkan sebagai natural key (D4),
   karena tanpa kunci itu idempotensi nomor konfirmasi tidak bisa dibuktikan. P4 (`docs/SCHEMA.md`)
   harus memakai nama field yang sama persis: `external_ref, full_name, email, policy_no, amount, notes`.
5. State target = SQLite **di dalam container**. `make target-down` (= `docker compose down`)
   menghapusnya; `docker compose restart` mempertahankannya.
