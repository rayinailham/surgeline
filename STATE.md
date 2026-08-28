# SurgeLine — STATE

> File hidup. Dibaca di awal tiap sesi, ditulis ulang di akhir tiap sesi.
> Satu-satunya memori antar sesi agent. Jaga tetap pendek (< 100 baris).

**Terakhir diperbarui:** 2026-08-28 (scaffold rencana dibuat; belum ada fase dikerjakan)
**Status project:** ⬜ **BELUM MULAI** — 0/15 fase, acceptance 0/12
**Fase aktif:** —
**Fase berikutnya:** **P0 — Bootstrap & Environment**

---
## Status fase

| Fase | Status | Catatan |
|---|---|---|
| P0 Bootstrap | ⬜ belum | `pyproject.toml`, `uv.lock`, struktur folder, `env-check.md`, git init + push kosong |
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

## Fakta terverifikasi tentang mesin ini (dikonfirmasi saat scaffold, verifikasi ulang di P0)
- Repo portofolio lain pakai akun **personal**: `git@rayin-personal:rayinailham/*.git` (privat).
- Port terpakai di device: `8090` (crosscheck-tut WordPress, JANGAN sentuh), `8000/3000/3100/3170/
  20080/4000/2379/5540/943/9443/3306/6379/20128`. Driftwatch pakai `8100`. → SurgeLine ambil
  **8110** (target) & **8120** (dashboard); salinan bersih 8111/8121 (D9).
- `9router.service` port `20128` — JANGAN PERNAH disentuh (AGENTS §0). Bisa memutus sesi sendiri.
- Skill `bulk-form-runner` yang disebut portofolio **tidak terpasang** → playbook ditulis sendiri
  di `docs/ARCHITECTURE.md` + fase.
- Belum diverifikasi (cek di P0): `docker`, `uv`, `ffmpeg`, `wf-recorder`, versi Playwright/Chromium.

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
| Acceptance project | 12/12 | 0/12 |

## Catatan tersisa untuk user
1. Scaffold rencana selesai: PLAN, KICKSTART, AGENTS, DECISIONS, ETHICS, TOOLS, ARCHITECTURE,
   ACCEPTANCE, 15 file fase, doc stubs. **Belum ada kode/commit** — P0 yang mulai.
2. Nama & akun git dipilih user: **surgeline** · **personal** (`rayinailham`, privat).
3. Repo publik (D16) butuh izin eksplisit user — jangan otomatis.
4. Mesin dipakai user paralel: jangan restart container di luar `surgeline-*`, jangan sentuh
   `crosscheck-tut-*` (8090) dan `/home/rayin/infra/`.
