# Laporan pengiriman data — full50k

**Tanggal laporan:** 29 Agustus 2026  
**Asal angka:** catatan pekerjaan pengiriman ini, dibaca ulang saat laporan dibuat. Cara memeriksa tiap angkanya ada di lembar **Bukti** pada `REPORT.xlsx`.

## Hasil

- Data yang dikirim: **49.950**
- Terkirim dan bernomor konfirmasi: **48.273** (96,6%)
- Ditolak sistem tujuan: **844** (1,7%)
- Tidak berhasil setelah 5 kali percobaan: **833** (1,7%)
- Belum selesai saat laporan dibuat: **0**
- Lama pengerjaan: **47 menit 16 detik**

## Tidak ada data yang terkirim dua kali

Nomor rujukan yang muncul lebih dari sekali: **0**. Nomor konfirmasi kembar: **0**. Pengiriman yang tercatat berhasil tetapi nomor konfirmasinya hilang: **0**.

Setiap baris data punya satu nomor rujukan, dan sistem menolak menerima nomor rujukan yang sama dua kali. Memuat ulang file yang sama tidak menambah pekerjaan baru dan tidak mengirim ulang data yang sudah terkirim.

## Pengerjaan tidak hilang walau dihentikan di tengah jalan

Pengerjaan sengaja saya hentikan paksa **2 kali** di tengah jalan, seperti listrik padam. Setiap kali dinyalakan lagi, pekerjaan dilanjutkan dari titik terakhir, bukan diulang dari awal.

Ada **7** data yang sedang dikerjakan tepat saat pengerjaan berhenti. Semuanya ditemukan kembali dan diselesaikan, tanpa satu pun yang terkirim dua kali. Yang tersisa saat laporan ini dibuat: **0**.

## Kecepatan

- Kecepatan pengerjaan ini: **61.270 data per jam** dengan 4 pengiriman berjalan berbarengan.
- Kecepatan tertinggi yang terukur: **85.388 data per jam** dengan 12 pengiriman berbarengan.
- Menambah pengiriman berbarengan di atas **8** tidak lagi mempercepat secara berarti; yang penuh adalah tenaga komputer, jadi mempercepatnya berarti menambah mesin, bukan menambah proses.

Pada kecepatan pengerjaan ini, **6.000.000** data selesai dalam sekitar **97,9 jam ≈ 4,1 hari**. Angka itu perpanjangan lurus dari kecepatan yang benar-benar terukur di sini, bukan hasil menjalankan sebanyak itu. Kecepatan di sistem tujuan Anda akan berbeda: jaringan, batas pengiriman resmi, dan antrean di sisi mereka semuanya memperlambat.

## Kegagalan dan artinya

| Hasil | Jumlah | Apa artinya | Contoh nomor rujukan |
|---|---|---|---|
| Ditolak sistem tujuan | 844 | Isian ditolak sistem tujuan karena tidak lolos pemeriksaan datanya. Penolakan ini tetap, jadi tidak dicoba ulang — data perlu diperbaiki di sumbernya. | REC-••••••, REC-••••••, REC-•••••• |
| Tidak berhasil setelah 5 kali percobaan | 833 | Sistem tujuan sedang bermasalah saat data ini dikirim. Sudah dicoba lima kali dengan jeda yang makin panjang dan tetap gagal; datanya utuh dan bisa dikirim ulang kapan saja. | REC-••••••, REC-••••••, REC-•••••• |

Tidak ada kegagalan yang disembunyikan atau dihapus: semua yang gagal punya catatan alasannya, dan datanya tetap utuh untuk dikirim ulang.

## Lingkup dan izin

Seluruh pengiriman dalam laporan ini ditujukan ke sistem uji milik saya sendiri, yang memang saya buat untuk gagal sekitar 5% agar ketahanannya terbukti. Tidak ada data yang dikirim ke sistem pihak lain, tidak ada pengamanan yang ditembus, dan tidak ada akun orang lain yang dipakai. Untuk pekerjaan sungguhan, izin tertulis dari pemilik sistem tujuan adalah syarat mulai, bukan formalitas.
