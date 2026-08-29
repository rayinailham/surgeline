# SurgeLine — CLIENT_REPORT

Bentuk, nada, dan aturan laporan yang dikirim ke klien. Dibuat mesin, bukan tangan:
`src/report.py` membacanya ulang dari antrean run yang bersangkutan setiap kali dijalankan.

```bash
# laporan kerja (masuk reports/, gitignored)
uv run --no-sync python src/report.py --run full50k --out reports/ \
    --kills 2 --scale data/p12/scale-all.json

# salinan tersanitasi yang boleh masuk repo
uv run --no-sync python src/report.py --run full50k --out assets --sanitize \
    --kills 2 --scale data/p12/scale-all.json
```

## 1. Dua pembaca, dua bahasa

| Bagian | Pembaca | Aturan |
|---|---|---|
| Digest `.md` + lembar `Ringkasan`, `Per-status`, `Throughput`, `Kegagalan` | klien | **0 jargon**, wajib lolos `report.jargon_violations()` |
| Lembar `Bukti` | orang teknis klien | sengaja teknis: perintah SQL untuk mengulang tiap angka |

Gerbang 0-jargon adalah kode, bukan niat: 51 istilah di `report.FORBIDDEN_JARGON`
(*lease*, *backoff*, `BEGIN IMMEDIATE`, `external_ref`, nama status mentah, dan seterusnya)
dicocokkan sebagai kata utuh, dan `main()` **menolak menulis file** kalau salah satu lolos.
Pencocokannya kata utuh supaya "walau" tidak tertangkap gara-gara "WAL" dan "rapi" tidak
tertangkap gara-gara "API". Lembar `Bukti` dikecualikan lewat `report.JARGON_EXEMPT_SHEETS` —
itu satu-satunya pengecualian, dan itu disengaja: laporan tanpa cara memeriksa ulang hanyalah
klaim.

Pesan kegagalan mentah tidak pernah diteruskan. `report.human_reason()` menerjemahkan tiap
kegagalan menjadi kalimat yang bisa ditindaklanjuti klien: apakah datanya perlu diperbaiki,
atau cukup dikirim ulang. Klien tidak bisa berbuat apa pun dengan "HTTP 500".

## 2. Isi `REPORT.xlsx`

1. **Ringkasan** — kode pekerjaan, jumlah data, hasilnya, lama pengerjaan, berapa kali
   dihentikan paksa, dan empat angka integritas (nomor rujukan kembar, nomor konfirmasi
   kembar, sukses tanpa nomor konfirmasi, gagal tanpa catatan alasan).
2. **Per-status** — tiap hasil dengan jumlah, persentase, dan **artinya** dalam satu kalimat.
3. **Throughput** — kecepatan terukur, jumlah pengiriman berbarengan, titik jenuh, dan
   ekstrapolasi 6 juta data lengkap dengan catatan bahwa itu perpanjangan lurus, bukan
   hasil menjalankan sebanyak itu.
4. **Kegagalan** — kelompok kegagalan, jumlah, alasan manusia, contoh nomor rujukan.
5. **Bukti** — tiap angka + perintah `sqlite3`/`src/throughput.py` untuk mengulangnya.

## 3. Asal angka

Semua dari `data/<run_id>/queue.db` secara read-only (`mode=ro`), di-query ulang saat laporan
dibuat — bukan disalin dari `STATE.md` atau dari `run.json`. Digest dan `REPORT.xlsx` lahir
dari satu objek `RunFacts` yang sama, jadi keduanya tidak bisa berbeda.

Dua masukan yang memang **tidak** ada di DB ditandai apa adanya, dan hanya itu:

- `--kills` — berapa kali pengerjaan dimatikan paksa (dari log operator). Tanpa opsi ini,
  laporan tidak pernah mengklaim pernah dimatikan (ada uji regresinya).
- `--scale` — manifest sapuan N worker P12, untuk baris kecepatan tertinggi & titik jenuh.

Durasi memakai satu definisi saja: jendela jam dinding percobaan pertama sampai terakhir,
sama seperti `docs/THROUGHPUT.md`. Memakai `created_at` job akan ikut menghitung waktu
pemuatan file dan membuat laporan menyebut dua durasi berbeda untuk pekerjaan yang sama.

## 4. Contoh yang boleh dibagikan

`assets/sample_daily.md` dan `assets/sample_REPORT.xlsx` adalah keluaran `--sanitize` dari run
50.000 P11: nomor rujukan contoh disamarkan (`REC-••••••`), dan tidak ada jalur mesin, nama
host, alamat email, atau nama orang di dalamnya. Data mentah dan `reports/` tetap gitignored.

## 5. Angka run `full50k` (P11)

| Keterangan | Nilai |
|---|---|
| Data dikirim | 49.950 |
| Terkirim dan bernomor konfirmasi | 48.273 (96,6%) |
| Ditolak sistem tujuan | 844 (1,7%) |
| Tidak berhasil setelah 5 kali percobaan | 833 (1,7%) |
| Belum selesai | 0 |
| Lama pengerjaan | 47 menit 16 detik |
| Dihentikan paksa | 2 kali; 7 data terselamatkan |
| Nomor rujukan / konfirmasi kembar | 0 / 0 |
| Kecepatan | 61.270 data per jam @ 4 berbarengan (tertinggi terukur 85.388 @ 12) |
