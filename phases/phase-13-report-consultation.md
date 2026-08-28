# P13 — Laporan Klien + Catatan Konsultasi

**Tujuan sesi:** dua deliverable yang menjual kompetensi: laporan run **0 jargon** + `REPORT.xlsx`,
dan catatan konsultasi 1 halaman yang memposisikan sebagai konsultan, bukan tukang script.

**Prasyarat:** P11 & P12 selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md`, `docs/CLIENT_REPORT.md`,
`docs/CONSULTATION.md`, `docs/THROUGHPUT.md`, `docs/RESUME_PROOF.md`, `data/full50k/run.json`.
**Budget:** sedang.

---

## Langkah

### 1. `src/report.py` → digest `.md` + `REPORT.xlsx` (openpyxl)
Digest ringkas: total/berhasil/gagal/dead, bukti crash-recovery (1 paragraf + angka),
throughput + ekstrapolasi, pernyataan lingkup legal. **0 jargon** — validasi ada daftar kata
teknis terlarang di teks klien (istilah seperti "lease timeout", "BEGIN IMMEDIATE" tidak keluar
ke klien; jelaskan dengan bahasa manusia).
`REPORT.xlsx` sheet: Ringkasan · Per-status · Throughput · Kegagalan (contoh + alasan) · Bukti.

### 2. `docs/CONSULTATION.md` → 1 halaman rapi
Perluas "3 pertanyaan sebelum project bulk automation": (1) ada API? (2) rate limit resmi?
(3) bukti otorisasi? — tiap poin 2–3 kalimat kenapa itu penting & apa dampaknya ke biaya/waktu.
Siap dilampirkan ke proposal.

### 3. Sanitasi contoh
Simpan `assets/sample_REPORT.xlsx` + `assets/sample_daily.md` yang **sudah disanitasi** (boleh
masuk repo). Data mentah tetap gitignored.

```bash
uv run --no-sync python src/report.py --run full50k --out reports/
uv run --no-sync python -m unittest src.test_report -v
```

---

## Output fase
- `src/report.py`, `src/test_report.py`, `reports/` (gitignored), `assets/sample_{REPORT.xlsx,daily.md}`,
  `docs/CONSULTATION.md` final, `docs/CLIENT_REPORT.md` diisi.

## Definition of Done
- [ ] `REPORT.xlsx` 5 sheet terbentuk dari run nyata; tiap angka bisa ditelusuri ke DB.
- [ ] Digest `.md` lolos validator 0-jargon.
- [ ] `docs/CONSULTATION.md` 1 halaman, 3 pertanyaan terjabar.
- [ ] `assets/sample_*` tersanitasi & boleh publik; data mentah tetap gitignored.
- [ ] `uv run … -m unittest src.test_report` lulus.
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`REPORT.xlsx 5 sheet · digest 0 jargon · CONSULTATION 1 hlm · N test lulus`

## Jebakan
- Jargon teknis di laporan klien = tanda "tukang script". Angka + bahasa manusia.
- Jangan bocorkan `next_action`/perintah internal ke laporan klien.
- `assets/sample_*` wajib disanitasi sebelum di-commit — cek tak ada path/host internal sensitif.
