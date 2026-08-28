# SurgeLine — ETHICS

Batas legal & etika. **Menang atas kenyamanan teknis, selalu.** (D14)

## Aturan mutlak

1. **Target uji hanya milik sendiri.** Worker SurgeLine hanya boleh menembak `127.0.0.1:8110`
   (container `surgeline-*` di `target/`). Dilarang keras diarahkan ke form/situs pihak lain,
   walau "cuma tes sebentar". Mengisi form massal di sistem orang tanpa otorisasi tertulis =
   masalah hukum, bukan portofolio.
2. **Tidak menembus proteksi.** Tidak ada captcha solver, anti-bot bypass, stealth fingerprint,
   atau peniruan identitas. Kalau sebuah target nyata butuh itu untuk ditembus, jawaban yang
   benar adalah BERHENTI dan tanya klien soal otorisasi — bukan mencari celah.
3. **Data uji 100% sintetis.** 50.000 record dibuat dari generator lokal (seed/Faker), tanpa
   PII nyata. Tidak ada data orang sungguhan yang diproses.
4. **Kegagalan target adalah simulasi yang dimiliki sendiri.** Menyuntik 5% error ke target
   sendiri itu sah — itu laboratorium. Menyuntik beban/error ke sistem orang tidak pernah sah.

## Kenapa ini justru nilai jual

Klien serius untuk job bulk automation (asuransi, logistik, pemerintahan, dealer) **menghargai**
kontraktor yang menolak kerja abu-abu. Kalimat di README publik — "hanya diuji terhadap target
milik sendiri; pertanyaan pertama saya ke klien selalu: apakah platformnya punya API, dan mana
bukti otorisasinya" — memposisikan sebagai konsultan, bukan tukang script. Itu memisahkan dari
pelamar yang menjanjikan "bisa isi form di situs apa pun".

## Diformalkan di

- Catatan konsultasi 1 halaman (`docs/CONSULTATION.md`, P13): 3 pertanyaan wajib sebelum project
  bulk automation dimulai — (1) apakah ada API? (2) berapa rate limit resmi? (3) mana bukti otorisasi?
- README publik (P14): pernyataan lingkup legal ditulis di atas, bukan disembunyikan.
