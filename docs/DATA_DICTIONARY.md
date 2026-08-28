# SurgeLine — Data Dictionary

Dataset P3 berisi data **100% sintetis** untuk target lokal milik project. Tidak ada PII nyata.
Generator deterministik: `scripts/gen_data.py`, Faker locale `id_ID`, seed `42`.

## Kontrak dataset

| Field | Tipe | Contoh | Aturan target |
|---|---|---|---|
| `external_ref` | string | `REC-000001` | Wajib; pola `[A-Za-z0-9._-]{1,64}`; **natural key** |
| `full_name` | string | `Budi Saputra` | Wajib; tidak kosong; maksimum 120 karakter |
| `email` | string | `budi@example.org` | Wajib; alamat email valid |
| `policy_no` | string | `POL-00000001` | Wajib; tidak kosong; maksimum 40 karakter |
| `amount` | decimal | `125000.50` | Wajib; angka lebih besar dari 0 |
| `notes` | string | `Data sintetis untuk pengujian lokal.` | Opsional; maksimum 500 karakter |

## Bentuk canonical P3

- Perintah: `uv run --no-sync python scripts/gen_data.py --rows 50000 --seed 42 --out data/input`
- Output: `data/input/records.csv` dan `data/input/records.xlsx`.
- Total: **50.000 baris data** pada masing-masing file, di luar satu header.
- Natural key unik: **49.950**.
- Duplikat sengaja: **50 baris** terakhir mengulang `REC-000001` sampai `REC-000050`.
- Tujuan duplikat: membuktikan `UNIQUE` + `INSERT OR IGNORE` di loader P5.
- CSV dan XLSX ditulis bersamaan dari iterator yang sama; urutan dan nilai cocok.
- Excel memakai `Workbook(write_only=True)`; pembacaan verifikasi memakai `read_only=True`.
- Generator menolak berjalan bila salah satu output sudah ada; data mentah tidak ditimpa.

Generator tidak menyimpan kumpulan record di memori. Faker, workbook write-only, dan satu tuple
record aktif memberi penggunaan memori yang tidak tumbuh linear terhadap jumlah baris. Bukti RSS
aktual P3 tercatat pada `phases/phase-03-data-generator.md` dan `STATE.md`.
