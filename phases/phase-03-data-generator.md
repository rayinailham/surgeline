# P3 — Generator Data 50.000

**Tujuan sesi:** melahirkan dataset uji 50.000 record sintetis ke Excel + CSV, dibuat & dibaca
**bertahap** supaya memori datar — ini menyumbang bukti A8 ("impor Excel tak membengkakkan memori").

**Prasyarat:** P0 selesai (butuh P1/P2 tidak wajib).
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D10), `docs/TARGET.md` (field form).
**Budget:** sedang.

---

## Langkah

### 1. `scripts/gen_data.py`
Hasilkan **50.000** record sintetis (Faker + seed tetap) dengan field yang cocok form target
(P1): `external_ref` (natural key unik, mis. `REC-000001`), `full_name`, `email`, `policy_no`,
`amount`, `notes`. Tulis ke **Excel** (`openpyxl` **write-only** mode — kunci hemat memori) DAN CSV.
CLI: `--rows 50000 --seed 42 --out data/input`.

Sisipkan sengaja **sejumlah kecil baris duplikat `external_ref`** (mis. 50 baris) — supaya P5
bisa membuktikan dedup DB menolaknya. Catat berapa yang disisipkan.

### 2. Bukti memori datar
Ukur RSS selama generate (mis. `/usr/bin/time -v` atau sampling `ps`), buktikan RSS **tidak**
naik sebanding jumlah baris. Catat puncak RSS untuk 50.000 baris.

### 3. `docs/DATA_DICTIONARY.md`
Field, tipe, contoh, mana natural key, aturan yang harus lolos validasi target, jumlah baris,
jumlah duplikat sengaja, seed.

```bash
uv run --no-sync python scripts/gen_data.py --rows 50000 --seed 42 --out data/input
wc -l data/input/records.csv                 # 50001 (header + 50000)
python -c "import openpyxl; wb=openpyxl.load_workbook('data/input/records.xlsx', read_only=True); ws=wb.active; print(ws.max_row)"
```

---

## Output fase
- `scripts/gen_data.py`, `data/input/records.{xlsx,csv}` (gitignored), `docs/DATA_DICTIONARY.md`.

## Definition of Done
- [ ] 50.000 record dihasilkan ke Excel + CSV (angka baris diverifikasi).
- [ ] Generator streamed: puncak RSS dicatat & jelas tidak linear terhadap baris (A8).
- [ ] Sejumlah duplikat `external_ref` sengaja disisipkan; jumlahnya dicatat (untuk P5).
- [ ] `docs/DATA_DICTIONARY.md` lengkap.
- [ ] **Commit + push berhasil** (D13) — file data TIDAK ikut (gitignored), hanya script + doc.

## Metrik selesai
`50.000 baris xlsx+csv · puncak RSS … MB (datar) · dup sengaja … · seed 42`

## Jebakan
- `openpyxl` mode normal menahan seluruh workbook di memori — WAJIB `write_only=True` untuk tulis,
  `read_only=True` untuk baca. Ini inti klaim A8.
- Jangan commit file `.xlsx`/`.csv` besar — `.gitignore` sudah menutup; verifikasi `git status`.
- Data sintetis, tanpa PII nyata (D14/ETHICS).
