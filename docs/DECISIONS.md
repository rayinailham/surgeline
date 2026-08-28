# SurgeLine — DECISIONS

Keputusan terkunci. **Menang atas semua dokumen lain.** Yang pernah ambigu dikunci sekali
di sini, tidak dinegosiasi ulang tiap sesi. 🔒 = terkunci · 🔓 = akan dikunci saat fase terkait.

---

## D1 — Bahasa & runtime 🔒
Python. Venv lewat `uv` (`uv run`). Test `unittest` (bukan pytest — konsisten dgn project 1/2,
tidak menambah dependency). Orkestrasi GNU Make. Produksi selalu `uv run --no-sync`.

## D2 — Target app adalah container Docker milik project 🔒
Target uji = app form sederhana yang **dibangun & dimiliki sendiri**, dijalankan lewat
`docker-compose.yml` **di root project** (bukan `~/infra/`). Container diberi prefix `surgeline-`.
Alasan: mensimulasikan platform remote tanpa API (asuransi/logistik/pemerintahan) secara sah,
tanpa menyentuh sistem orang. Ini juga nilai jual portofolio: "diuji terhadap sistem yang
sengaja dibuat gagal 5%, sistem saya tetap 100%."

## D3 — Target sengaja "menyebalkan", deterministik 🔒
Target menyuntik **5% kegagalan** dari total request, terbagi 3 mode: HTTP 500, respons lambat
(sleep), dan penolakan validasi. Kegagalan **deterministik berdasar seed + kunci record**, bukan
acak murni — supaya run bisa direproduksi dan oracle bisa diuji. Rincian dikunci di `docs/CHAOS.md` (P2).
Kegagalan target = fitur uji. Dilarang "memperbaiki" target agar berhenti gagal.

## D4 — Dedup di level database 🔒
Natural key record (`external_ref`) diberi constraint `UNIQUE` di tabel `jobs`. Loader memakai
`INSERT OR IGNORE`. Duplikat ditolak oleh DB, bukan dicek di memori proses. Bukti = query hitung
(`SELECT COUNT(*)-COUNT(DISTINCT external_ref)` = 0). Ini yang membuat "0 duplikat walau di-load
berkali-kali / di-resume" terbukti secara struktural, bukan kebetulan.

## D5 — Antrean & state = SQLite (mode WAL) 🔒
State antrean disimpan di satu file SQLite per run (`data/<run_id>/queue.db`), mode WAL supaya
banyak worker bisa baca sambil satu menulis. Bukan MySQL/Redis/TiDB device — deliverable harus
jalan di mesin klien tanpa server DB. Jalur upgrade ke PostgreSQL dicatat di `docs/ARCHITECTURE.md`
tapi **tidak** diimplementasikan (bukan scope). Klaim atomik pakai `BEGIN IMMEDIATE`.

## D6 — Nomor konfirmasi wajib ditangkap 🔒
Tiap submission sukses → target mengembalikan **nomor konfirmasi unik** di halaman hasil.
Worker menangkap & menyimpannya ke kolom `confirmation`. Submission "sukses" tanpa nomor
konfirmasi tersimpan dihitung **gagal** (indikasi worker salah baca halaman hasil).

## D7 — Retry bertingkat + batas percobaan 🔓 (P8)
Job gagal di-retry dengan backoff eksponensial (mis. base 1 dtk, faktor 2, jitter). Batas
`max_attempts` (usulan 5). Habis batas → status `dead` (dead-letter) dengan `last_error`.
Angka final dikunci di P8 + `docs/SCHEMA.md`. 429/503/timeout/500 = retryable; penolakan
validasi permanen = **tidak** di-retry (langsung `failed`, tercatat alasannya).

## D8 — Pemulihan job "nyangkut" via lease 🔓 (P8)
Job `claimed` menyimpan `claimed_at` + `worker_id`. Job yang `claimed` lebih lama dari
`lease_timeout` (usulan 120 dtk) tanpa selesai dianggap yatim (worker mati) dan dikembalikan
ke `pending` oleh proses recovery saat startup/berkala. Ini yang membuat crash worker di
tengah submission tidak menghilangkan job itu selamanya.

## D9 — Port 🔒
Target `127.0.0.1:8110` (salinan bersih `8111`). Dashboard `127.0.0.1:8120` (salinan bersih
`8121`). Dipilih agar tidak menabrak service device (`8000`, `8090` crosscheck, `8100`
driftwatch, `3000`, `3100`, `3170`, `20080`, `4000`, `2379`, `5540`, `943`, `9443`, `20128`).

## D10 — Generator data 🔒
`scripts/gen_data.py` menghasilkan **50.000** record dummy ke **Excel** (`openpyxl` write-only,
hemat memori) **dan** CSV. Data 100% sintetis (Faker/seed lokal), tanpa PII nyata. Streamed —
tidak pernah menahan 50k baris di memori sekaligus. Bukti hemat memori dibuktikan di P3 & P5
(RSS datar, bukan naik linear terhadap jumlah baris).

## D11 — Dashboard FastAPI + HTMX 🔓 (P10)
Satu halaman, read-only atas `queue.db`, auto-refresh (HTMX polling). Menampilkan
Total · Pending · Claimed · Berhasil · Gagal · Dead · throughput berjalan. Tanpa auth
(localhost). Angka wajib cocok 1:1 dengan query DB (dibuktikan di P10).

## D12 — Worker = Playwright headless Chromium 🔒
Worker mengisi form seperti manusia (Playwright headless), bukan `httpx` POST langsung —
karena pitch-nya adalah "platform tanpa API, harus lewat browser". Reuse cache Playwright
device saat membangun; runtime pakai `playwright install chromium` (tanpa `--with-deps`).
Catatan konsultasi (P13) tetap menekankan: **kalau target punya API, browser tidak perlu.**

## D13 — Git: personal, privat, commit tiap fase 🔒
Repo `git@rayin-personal:rayinailham/surgeline.git`, akun **personal** `rayinailham`, **privat**.
Commit + push **wajib** di akhir tiap fase (gerbang di `AGENTS.md` §6). Satu fase = satu commit.
Butuh izin baru user: repo publik (D16), force-push, hapus branch/repo, ubah history.

## D14 — Etika/legal 🔒
Target uji **hanya milik sendiri**. Tidak ada submission ke sistem pihak lain, tidak ada
bypass captcha/anti-bot. Ditulis terang-terangan di README (D16 saat publik). `docs/ETHICS.md`
menang atas kenyamanan teknis. Ini pembeda dari pelamar yang mau kerja abu-abu.

## D15 — Bukan scope (anti scope-creep) 🔒
Bukan target: captcha solver, anti-bot bypass, submission ke platform tanpa wewenang,
multi-tenant/auth, DB eksternal (Postgres/TiDB) sebagai runtime, message queue eksternal
(RabbitMQ/Redis), deploy cloud, UI admin CRUD, dukungan Windows/macOS. 50.000 record cukup
membuktikan semua klaim pitch — tidak perlu benar-benar 6 juta (cukup ekstrapolasi terukur di P12).

## D16 — Repo publik 🔓 (butuh izin eksplisit user)
Menjadikan repo publik butuh persetujuan user, tidak boleh dikunci otomatis oleh agent.
