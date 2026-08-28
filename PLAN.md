# SurgeLine — Master Plan

Total **15 fase (P0–P14)**. Tiap fase dirancang selesai dalam **satu sesi agent**
(muat dalam satu context window ~264k), tanpa perlu membaca fase lain.

Sumber: `../portfolio/portfolio_03_bulk_form_runner.md`.
Pola kerja diwarisi dari project 1 (`../crosscheck/`, selesai 11/11) dan project 2
(`../driftwatch/`, jalan) — keduanya membuktikan: satu fase = satu artefak = satu commit.

---

## Prinsip pemecahan fase

1. **Siapkan program yang diuji DULU, baru bangun penguji.** P0–P3 melahirkan target app +
   data uji; QA/automation baru mulai P5. Tidak ada penguji tanpa yang diuji.
2. **Satu fase = satu artefak konkret.** Kalau tidak lahir file baru, fase itu belum selesai.
3. **Satu fase = satu jenis pekerjaan.** Jangan campur "bangun worker" dengan "bikin dashboard".
4. **Read-set eksplisit.** Tiap file fase menyebut file apa saja yang boleh dibaca. Di luar itu, jangan.
5. **Handoff lewat file, bukan ingatan.** `STATE.md` satu-satunya memori antar sesi.
6. **Yang pernah ambigu dikunci sekali** di `docs/DECISIONS.md`; bentuk file & tabel DB di `docs/SCHEMA.md`.
7. **Bukti > klaim.** DoD dicentang hanya dengan output perintah yang benar-benar dijalankan.
8. **Bukti utama = angka.** "Resume jalan" bukan "tidak ada error", tapi "N1 sebelum → N2 sesudah, duplikat 0".

---

## Peta fase

| # | Fase | Output utama | Berat token |
|---|---|---|---|
| P0 | Bootstrap & Environment | `pyproject.toml`, `uv.lock`, struktur folder, `env-check.md` | ringan |
| P1 | Target App — Server Form | `target/` app Docker + `docker-compose.yml` lokal, nomor konfirmasi di hasil | **berat** |
| P2 | Chaos & Kontrak Target | mode gagal 5% deterministik (500 / lambat / validasi), `docs/TARGET.md`, `docs/CHAOS.md`, oracle target | sedang |
| P3 | Generator Data 50.000 | `scripts/gen_data.py` → Excel + CSV 50k baris, streamed, `docs/DATA_DICTIONARY.md` | sedang |
| P4 | Kontrak Data & Skema Antrean | `docs/SCHEMA.md` terkunci: record + tabel DB (state machine, unique key dedup) | sedang |
| P5 | Loader | `src/load.py` — baca CSV/Excel bertahap → antrean DB, dedup level-DB, memori datar | sedang |
| P6 | Worker Pengisi Form | `src/worker.py` — Playwright headless: klaim → isi → tangkap nomor konfirmasi / alasan gagal | **berat** |
| P7 | Konkurensi & Klaim Atomik | N worker paralel, klaim tanpa tabrakan (BEGIN IMMEDIATE), bukti 0 double-claim | sedang |
| P8 | Ketahanan — Retry & Requeue | retry bertingkat + backoff + batas percobaan, dead-letter, pemulihan job "nyangkut" (lease) | sedang |
| P9 | Bukti Crash-Recovery | kill -9 ≥2× di tengah → resume → 100% selesai, 0 duplikat, `docs/RESUME_PROOF.md` | ringan |
| P10 | Dashboard | `src/dashboard.py` FastAPI+HTMX — Total\|Pending\|Berhasil\|Gagal\|Dead, angka hidup cocok DB | sedang |
| P11 | Run Penuh 50.000 | jalankan 50k lewat chaos 5% + ≥2 kill → 0 dup (query), semua gagal ter-retry/tercatat | sedang |
| P12 | Ukur Throughput | `src/throughput.py` — record/jam per N worker → ekstrapolasi 6 juta record ≈ Y hari | sedang |
| P13 | Laporan Klien + Konsultasi | `src/report.py` → digest + `REPORT.xlsx`; `docs/CONSULTATION.md` "3 pertanyaan sebelum project bulk" | sedang |
| P14 | Visual, Packaging & Gladi Bersih | video 2 mnt (naik→crash→resume→50k 0 dup), diagram, `Makefile make all`, README publik, audit | **berat** |

**Total ≈ 16–20 jam kerja aktif**, plus jam dinding untuk run penuh P11.

---

## Ketergantungan

```
P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9 (bukti crash-recovery)
                          │                    │
                          └─► P10 (dashboard)  │
                                   │           │
                          P11 ◄────┴───────────┘   (butuh P8 tuntas + P10 untuk demo)
                          P11 → P12 → P13 → P14
```

Aturan turunan:
- **P9 didahulukan begitu P8 selesai.** Bukti "diputus lalu lanjut" adalah jantung portofolio;
  fase kosmetik (P10, P13, P14) tidak boleh mendahuluinya.
- **P10 butuh P4** (skema antrean) saja untuk mulai; angka hidupnya baru bermakna setelah P5/P6.
- **P11 butuh P8 tuntas** (retry + requeue + lease) dan **P10** (dashboard untuk direkam saat crash).
- **P12 butuh P11** (angka throughput nyata, bukan perkiraan).
- **P14 butuh semua**, termasuk P9 dan P11 — video menampilkan run nyata yang diputus lalu lanjut.

---

## Jalur kritis (kenapa urutannya begitu)

Portofolio ini menjual **satu bukti di atas segalanya**:

| Bukti | Lahir di | Kenapa klien peduli |
|---|---|---|
| "Diputus lalu lanjut, 0 duplikat" | P9 | pesaing kirim script yang mengulang dari nol & submit dobel |
| "Selesai 100% walau target gagal 5%" | P8 → P11 | pesaing kirim script yang diam-diam kehilangan 5% record |
| "Angka throughput nyata untuk 6 juta record" | P12 | pesaing menjanjikan skala tanpa hitungan |

Tiga bukti itu alasan P8 dan P9 tidak boleh ditunda demi dashboard yang cantik.

---

## Aturan sesi agent

**Awal sesi — baca ini saja:**
```
surgeline/STATE.md
surgeline/docs/DECISIONS.md
surgeline/phases/phase-NN-<nama>.md
```
Plus file yang disebut di bagian "Read-set" fase tersebut. Tidak lebih.

**Akhir sesi — wajib:**
1. Centang DoD di file fase (edit di tempat) dengan output perintah nyata.
2. Update `STATE.md`: status fase, artefak baru, angka metrik nyata, blocker.
3. Gerbang commit (D13): audit rahasia → `git commit` → `git push`. Baru fase ✅.
4. Jangan lanjut fase berikutnya di sesi yang sama kecuali fase itu **ringan** dan
   fase sekarang sudah 100% selesai termasuk push.

**Yang membuat sesi boros token (hindari):**
- Membaca `data/**` mentah (50k baris). Pakai `wc -l`, `head`, `sqlite3 … COUNT(*)`, `jq`.
- Membaca `../HARNESS.md`, `../portfolio/`, atau project lain — kutipan yang perlu sudah disalin.
- Membuka halaman target satu per satu di browser. MCP browser hanya untuk 1–2 sampel recon.
- Memakai Playwright untuk pekerjaan berulang di luar worker produksi.

---

## Definisi "project selesai"

Semua checklist di `docs/ACCEPTANCE.md` (A1–A12) tercentang, **dan** orang lain bisa
menjalankan seluruh pipeline dari nol dengan satu perintah (`make all`) dan mendapat
hasil yang sama: 50.000 record, 0 duplikat, walau diputus paksa.

## Dokumen kunci

| File | Peran |
|---|---|
| `docs/DECISIONS.md` | keputusan terkunci (D1–D16). Menang atas dokumen lain. |
| `docs/SCHEMA.md` | bentuk record + tabel DB antrean. Dikunci di P4. |
| `docs/ETHICS.md` | batas legal (target milik sendiri). Menang atas kenyamanan teknis. |
| `docs/TARGET.md` | spesifikasi app form yang diuji. |
| `docs/CHAOS.md` | model kegagalan 5% + oracle target. |
| `docs/ARCHITECTURE.md` | alur data loader → antrean → worker → dashboard, satu halaman. |
| `docs/TOOLS.md` | tiap tool: kenapa dipakai + perintah persisnya. |
| `docs/CLIENT_REPORT.md` | bentuk, nada, dan irama laporan ke klien. |
| `docs/CONSULTATION.md` | "3 pertanyaan sebelum project bulk automation" (P13). |
