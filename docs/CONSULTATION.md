# SurgeLine — Catatan Konsultasi

> Satu halaman, siap dilampirkan ke proposal. Tiga pertanyaan ini saya tanyakan **sebelum**
> menyepakati harga dan tenggat pekerjaan bulk automation. Jawabannya mengubah biaya,
> durasi, dan kadang membatalkan kebutuhan akan pekerjaan itu sendiri.

---

## 1. Apakah platformnya punya API resmi?

Kalau ada, pekerjaan ini tidak perlu robot yang membuka halaman dan mengetik seperti manusia.
Satu pengiriman lewat API selesai dalam hitungan puluhan milidetik, sementara lewat halaman
web butuh membuka halaman, menunggu tampilannya siap, mengisi, dan membaca halaman hasil —
puluhan kali lebih lambat dan jauh lebih rapuh, karena satu perubahan tata letak halaman bisa
mematahkan seluruh alur.

**Dampaknya ke Anda:** dengan API, pekerjaan biasanya selesai dalam hitungan jam alih-alih
hari, ongkos mesin turun drastis, dan biaya perawatan jangka panjang mendekati nol. Saya akan
mengatakan ini walau berarti nilai project saya mengecil — menjual robot browser untuk
platform yang punya API adalah menjual masalah, bukan solusi. Kalau API-nya ada tetapi tidak
mencakup semua field yang Anda butuhkan, campuran keduanya biasanya paling murah: API untuk
yang bisa, halaman web untuk sisanya.

**Ikutan yang perlu ditanyakan:** ada dokumentasinya? ada lingkungan uji (sandbox)? berapa
lama menerbitkan kredensialnya? Menunggu kredensial dua minggu mengubah rencana tenggat.

## 2. Berapa batas pengiriman resminya?

Kecepatan sistem saya bukan angka yang menentukan. Yang menentukan adalah batas yang
diizinkan pemilik platform: sekian pengiriman per menit, sekian per akun, sekian per alamat
jaringan. Tanpa angka itu, estimasi durasi apa pun hanyalah tebakan yang enak didengar, dan
tebakan yang meleset akan terlihat sebagai kegagalan saya di minggu ketiga.

**Dampaknya ke Anda:** batas resmi menentukan berapa pengiriman yang boleh berjalan
berbarengan, dan dari sana barulah durasi bisa dihitung jujur. Sistem ini terukur ±82.000
data per jam pada 8 pengiriman berbarengan di satu mesin (`docs/THROUGHPUT.md`), tapi kalau
platform Anda hanya mengizinkan 60 kiriman per menit, angka yang berlaku adalah 3.600 per
jam — dan menambah mesin tidak akan menolong sedikit pun. Melanggar batas itu bukan cuma
soal etika: akun diblokir di tengah jalan jauh lebih mahal daripada menunggu.

**Ikutan yang perlu ditanyakan:** ada jam sibuk yang harus dihindari? apakah pemilik platform
mau memberi jalur khusus untuk pengiriman massal? Sering kali mereka mau, dan sekali telepon
menghemat berhari-hari.

## 3. Mana bukti otorisasinya?

Saya butuh pernyataan tertulis dari pihak yang berwenang atas sistem tujuan bahwa pengiriman
massal ini diizinkan — email dari orang yang tepat sudah cukup. Ini bukan formalitas hukum
yang saya lempar ke Anda: tanpa itu, pekerjaannya bisa berpindah dari "otomasi" ke "akses
tidak sah", dan risikonya menempel ke Anda dan saya sekaligus.

**Dampaknya ke Anda:** kalau izinnya ada, pekerjaan dimulai dan semua energi habis untuk hal
teknis. Kalau belum ada, waktu terbaik mengurusnya adalah sekarang, bukan setelah setengah
data terkirim. Kalau platform tujuan memasang captcha, deteksi robot, atau syarat layanan
yang melarang otomasi, saya berhenti dan mengangkat telepon ke pemiliknya — saya tidak
menembus pengamanan, dan itu batas yang tidak saya negosiasikan per project
(`docs/ETHICS.md`).

**Ikutan yang perlu ditanyakan:** datanya milik siapa? ada data pribadi di dalamnya? berapa
lama boleh saya simpan? Jawaban atas ini menentukan bagaimana file kerja disimpan dan kapan
dihapus.

---

## Ringkasnya

| Jawaban | Yang terjadi pada project |
|---|---|
| Ada API | Robot browser dibatalkan; pekerjaan jadi lebih murah, lebih cepat, lebih awet |
| Batas pengiriman diketahui | Durasi dihitung jujur di depan; jumlah proses paralel disetel ke batas itu |
| Batas tidak diketahui | Mulai pelan dan naik bertahap, atau tunggu jawaban pemilik platform |
| Izin tertulis ada | Pekerjaan dimulai |
| Izin tidak ada, atau ada captcha/anti-robot | Pekerjaan tidak dimulai; saya bantu menghubungi pemilik platform |

Pengiriman apa pun yang tidak bisa memenuhi tiga jawaban di atas lebih baik tidak dikerjakan.
Yang saya jual bukan kecepatan mengisi form, melainkan pekerjaan yang bisa
dipertanggungjawabkan angkanya dan asalnya.
