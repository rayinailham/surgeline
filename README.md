# SurgeLine

> Sistem bulk form submission yang tahan diputus di tengah jalan: 50.000 record,
> nol duplikat, dimatikan paksa berkali-kali, tetap selesai 100%.

**Status:** dalam pengerjaan. README publik untuk klien adalah deliverable fase P14.
Dokumen ini hanya peta internal.

## Momen yang dijual

> "Saya matikan paksa sistemnya di record ke-23.000, saya nyalakan lagi, dan dia lanjut
> dari record ke-23.001 — tanpa satu pun duplikat."

Satu demo crash-recovery. Itu yang memisahkan portofolio ini dari 50 pelamar lain yang
cuma bilang "saya bisa Playwright".

## Mulai dari mana

| Kalau kamu ingin… | Buka |
|---|---|
| menjalankan sesi kerja agent | `KICKSTART.md` (satu prompt, dipakai berulang) |
| tahu posisi progres sekarang | `STATE.md` |
| tahu seluruh rencana & fase | `PLAN.md` |
| tahu arsitektur & alur data | `docs/ARCHITECTURE.md` |
| tahu tools apa & cara pakainya | `docs/TOOLS.md` |
| tahu keputusan yang sudah dikunci | `docs/DECISIONS.md` |
| tahu bentuk tiap file & tabel DB | `docs/SCHEMA.md` (dikunci di P4) |
| tahu spesifikasi app target & mode gagalnya | `docs/TARGET.md`, `docs/CHAOS.md` |
| tahu batas etika & legal | `docs/ETHICS.md` |
| tahu bentuk laporan ke klien | `docs/CLIENT_REPORT.md` |
| tahu kapan project ini boleh disebut selesai | `docs/ACCEPTANCE.md` |
| aturan mesin & larangan | `AGENTS.md` lalu `../AGENTS.md` |

## Sumber portofolio

`../portfolio/portfolio_03_bulk_form_runner.md` — pitch, job sasaran (Job 18: Web Automation
Developer for Bulk Form Processing, $20–45/jam), deliverable.
Project sebelumnya (selesai): `../crosscheck/`, `../driftwatch/`.

## Legal — dibaca lebih dulu

Target uji **hanya milik sendiri** (`target/`, container Docker lokal). SurgeLine tidak
pernah dipakai mengisi form di situs pihak lain tanpa otorisasi. Ini ditulis terang-terangan
karena klien serius justru menghargainya. Detail: `docs/ETHICS.md`.
