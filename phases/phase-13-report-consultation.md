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
- [x] `REPORT.xlsx` 5 sheet terbentuk dari run nyata; tiap angka bisa ditelusuri ke DB.
- [x] Digest `.md` lolos validator 0-jargon.
- [x] `docs/CONSULTATION.md` 1 halaman, 3 pertanyaan terjabar.
- [x] `assets/sample_*` tersanitasi & boleh publik; data mentah tetap gitignored.
- [x] `uv run … -m unittest src.test_report` lulus.
- [x] **Commit + push berhasil** (D13).

## Metrik selesai
`REPORT.xlsx 5 sheet · digest 0 jargon · CONSULTATION 1 hlm · N test lulus`

## Jebakan
- Jargon teknis di laporan klien = tanda "tukang script". Angka + bahasa manusia.
- Jangan bocorkan `next_action`/perintah internal ke laporan klien.
- `assets/sample_*` wajib disanitasi sebelum di-commit — cek tak ada path/host internal sensitif.

---

## Bukti (P13, 2026-08-29)

### 1. `REPORT.xlsx` 5 lembar dari run nyata `full50k`

```text
$ uv run --no-sync python src/report.py --run full50k --out reports/ \
      --kills 2 --scale data/p12/scale-all.json
digest : reports/digest.md (0 jargon dari 51 istilah terlarang)
laporan: reports/REPORT.xlsx (5 lembar: Ringkasan, Per-status, Throughput, Kegagalan, Bukti)
angka  : total=49950 ok=48273 failed=844 dead=833 dup_ref=0 dup_conf=0 ok/jam=61,270

$ python -c "load_workbook('reports/REPORT.xlsx')"
lembar: ['Ringkasan', 'Per-status', 'Throughput', 'Kegagalan', 'Bukti']
  Ringkasan: 17 baris x 2 kolom
  Per-status: 5 baris x 4 kolom
  Throughput: 10 baris x 2 kolom
  Kegagalan: 3 baris x 4 kolom
  Bukti: 13 baris x 3 kolom
```

Tiap angka ditelusuri lewat lembar **Bukti**, yang memuat perintah pemeriksanya. Contoh,
baris "Job per status" (`ok=48273 failed=844 dead=833`):

```text
$ sqlite3 "file:data/full50k/queue.db?mode=ro" "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
dead|833
failed|844
ok|48273
```

Angka laporan **tidak** disalin dari `run.json` maupun `STATE.md`: `src/report.py` mem-query
ulang `queue.db` (`mode=ro`) setiap kali dijalankan. Hanya dua masukan yang berasal dari luar
DB dan keduanya eksplisit: `--kills 2` (log operator P11) dan `--scale` (sapuan N worker P12).

### 2. Validator 0-jargon — dan buktinya validator itu menggigit

```text
$ python -c "report.jargon_violations(open('reports/digest.md').read())"
digest        : []
kalimat teknis: ['begin immediate', 'lease', 'pending', 'timeout', 'worker']
```

51 istilah terlarang, dicocokkan sebagai kata utuh ("walau" tidak tertangkap gara-gara "WAL").
`main()` menolak menulis file kalau ada satu saja yang lolos ke teks klien. Lembar `Bukti`
sengaja dikecualikan (`JARGON_EXEMPT_SHEETS`) karena isinya justru perintah SQL verifikasi.
Pesan kegagalan mentah tidak pernah diteruskan: `human_reason()` menerjemahkan HTTP 422 →
"perlu diperbaiki di sumbernya", HTTP 500 → "sudah dicoba lima kali, bisa dikirim ulang".

### 3. `docs/CONSULTATION.md` — 1 halaman, 3 pertanyaan

77 baris: tiap pertanyaan (API resmi · batas pengiriman resmi · bukti otorisasi) dapat 2-3
kalimat kenapa penting + paragraf dampak ke biaya/waktu + pertanyaan ikutan, ditutup tabel
"jawaban → yang terjadi pada project". Berani menuliskan bahwa kalau API-nya ada, project
browser dibatalkan (D12).

### 4. `assets/sample_*` tersanitasi

```text
$ uv run --no-sync python src/report.py --run full50k --out assets --sanitize \
      --kills 2 --scale data/p12/scale-all.json
digest : assets/sample_daily.md (0 jargon dari 51 istilah terlarang)
laporan: assets/sample_REPORT.xlsx (5 lembar: ...)

$ grep -rn "rayin\|127\.0\.0\.1\|/home/" assets/sample_daily.md
sample_daily.md: bersih

$ python -c "hitung jejak di seluruh sel assets/sample_REPORT.xlsx"
rayin -> 0
/home/ -> 0
127.0.0.1 -> 0
localhost -> 0
8110 -> 0
@ -> 0

$ git status --short
?? assets/sample_REPORT.xlsx
?? assets/sample_daily.md
?? src/report.py
?? src/test_report.py
```

Nomor rujukan contoh disamarkan jadi `REC-••••••`; `data/` dan `reports/` tetap gitignored,
`assets/sample_*.xlsx` lolos lewat pengecualian `.gitignore` yang sudah ada sejak P0.

### 5. Test

```text
$ uv run --no-sync python -m unittest src.test_report
Ran 24 tests in 0.162s
OK

$ uv run --no-sync python -m unittest discover -s src
Ran 146 tests in 2.495s
OK
```

24 test baru: gerbang jargon (kata utuh, bukan substring), terjemahan kegagalan (pesan mentah
tidak pernah bocor), angka `RunFacts` dari DB, laporan tanpa `--kills` tidak boleh mengklaim
pernah dimatikan paksa, penyamaran `--sanitize`, dan lima lembar workbook terbaca ulang.
