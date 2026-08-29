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

## D7 — Retry bertingkat + batas percobaan 🔒 (dikunci P8)
Angka final: `MAX_ATTEMPTS = 5`, backoff `base = 1 dtk`, `factor = 2`, atap `30 dtk`
(tangga 1·2·4·8·16), jitter deterministik 0–25% dari `rowid % 100` job. 429/503/500/timeout
= retryable; penolakan validasi 422 permanen = **tidak** di-retry (langsung `failed`,
alasan tercatat). Jatah habis → `dead` (dead-letter) dengan `last_error` non-NULL.

Jitter sengaja **deterministik**, bukan `random()`: run harus bisa diulang (D3), tapi job
yang dilepas pada detik yang sama tetap tidak boleh jadi layak serentak.

Kelayakan retry dihitung dari `updated_at` + `attempts` yang sudah ada (`store.READY_AT`),
**tanpa kolom `not_before` baru** — `SCHEMA_VERSION` tetap 1 dan antrean yang sedang
berjalan tidak perlu dimigrasi (`docs/SCHEMA.md` §3).

## D8 — Pemulihan job "nyangkut" via lease 🔒 (dikunci P8)
Angka final: `LEASE_TIMEOUT_SECONDS = 120`. Job `claimed` menyimpan `claimed_at` +
`worker_id`; yang melewati lease dianggap yatim dan ditarik `store.recover_stuck` —
dipanggil worker saat startup dan tiap setengah lease, serta berdiri sendiri lewat
`python -m src.recover`. 120 dtk dipilih karena satu submission normal < 1 dtk dan timeout
worker 15 dtk; sapuan yang lebih agresif akan merebut job yang masih dikerjakan worker
hidup, dan itu jalan menuju submit ganda.

Sapuan **tidak** menaikkan `attempts` — `claim_one` sudah memakai satu jatah saat job
diklaim, jadi menaikkannya lagi menghukum satu percobaan dua kali. Job yatim yang jatahnya
sudah habis langsung ke `dead`, bukan `pending`, supaya tidak ada baris `pending` yang
selamanya tidak layak diklaim.

## D9 — Port 🔒
Target `127.0.0.1:8110` (salinan bersih `8111`). Dashboard `127.0.0.1:8120` (salinan bersih
`8121`). Dipilih agar tidak menabrak service device (`8000`, `8090` crosscheck, `8100`
driftwatch, `3000`, `3100`, `3170`, `20080`, `4000`, `2379`, `5540`, `943`, `9443`, `20128`).

## D10 — Generator data 🔒
`scripts/gen_data.py` menghasilkan **50.000** record dummy ke **Excel** (`openpyxl` write-only,
hemat memori) **dan** CSV. Data 100% sintetis (Faker/seed lokal), tanpa PII nyata. Streamed —
tidak pernah menahan 50k baris di memori sekaligus. Bukti hemat memori dibuktikan di P3 & P5
(RSS datar, bukan naik linear terhadap jumlah baris).

## D11 — Dashboard FastAPI + HTMX 🔒 (dikunci P10)
Satu halaman, read-only atas `queue.db`, auto-refresh (HTMX polling). Menampilkan
Total · Pending · Claimed · Berhasil · Gagal · Dead · throughput berjalan. Tanpa auth
(localhost). Angka wajib cocok 1:1 dengan query DB (dibuktikan di P10). Implementasi
memakai koneksi SQLite URI `mode=ro`, polling 2 detik, throughput sukses per menit dari
audit `attempts` dalam jendela 60 detik, dan bind tetap `127.0.0.1:8120` tanpa opsi
`0.0.0.0`. Dipilih agar dashboard tidak dapat menulis antrean, tetap mandiri dari worker,
menunjukkan laju nyata setelah restart, dan tidak mengekspos dashboard tanpa auth ke jaringan.

## D12 — Worker = Playwright headless Chromium 🔒
Worker mengisi form seperti manusia (Playwright headless), bukan `httpx` POST langsung —
karena pitch-nya adalah "platform tanpa API, harus lewat browser". Reuse cache Playwright
device saat membangun; runtime pakai `playwright install chromium` (tanpa `--with-deps`).
Catatan konsultasi (P13) tetap menekankan: **kalau target punya API, browser tidak perlu.**

## D13 — Git: personal, privat, commit tiap fase 🔒
Repo `git@rayin-personal:rayinailham/surgeline.git`, akun **personal** `rayinailham`, **privat**.
Commit + push **wajib** di akhir tiap fase (gerbang di `AGENTS.md` §6). Satu fase = satu commit.
Butuh izin baru user: force-push, hapus branch/repo, ubah history. (Repo publik: D16, sudah diizinkan 2026-08-29.)

## D14 — Etika/legal 🔒
Target uji **hanya milik sendiri**. Tidak ada submission ke sistem pihak lain, tidak ada
bypass captcha/anti-bot. Ditulis terang-terangan di README (D16 saat publik). `docs/ETHICS.md`
menang atas kenyamanan teknis. Ini pembeda dari pelamar yang mau kerja abu-abu.

## D15 — Bukan scope (anti scope-creep) 🔒
Bukan target: captcha solver, anti-bot bypass, submission ke platform tanpa wewenang,
multi-tenant/auth, DB eksternal (Postgres/TiDB) sebagai runtime, message queue eksternal
(RabbitMQ/Redis), deploy cloud, UI admin CRUD, dukungan Windows/macOS. 50.000 record cukup
membuktikan semua klaim pitch — tidak perlu benar-benar 6 juta (cukup ekstrapolasi terukur di P12).

## D16 — Repo publik 🔒 (dikunci 2026-08-29, atas izin eksplisit user)
`github.com/rayinailham/surgeline` **publik** sejak 2026-08-29 (sesi P14), diminta user
secara eksplisit — bukan diputuskan agent. Diflip lewat `gh repo edit --visibility public`
dengan akun personal `rayinailham` (D13).

Gerbang yang dilewati sebelum diflip (bukan hanya `make audit` atas HEAD):
- `make audit` → 91 berkas ter-track, **0 kebocoran**;
- seluruh **riwayat** dipindai, bukan cuma HEAD: 20 commit, 157 blob unik, **0 pola
  kredensial**, dan tidak pernah ada `.env` / `data/` / `reports/` / `*.db` ter-commit.

Yang sekarang ikut terlihat publik, dan memang disengaja (9 "catatan" audit): jalur mesin
`/home/<user>/...` dan catatan lingkungan di dokumen kerja internal (`AGENTS.md`,
`KICKSTART.md`, `env-check.md`, `docs/TARGET.md`, `docs/TOOLS.md`, `phases/`) — nama service
lokal dan port mesin dev, tanpa kredensial. Itu sebabnya pemindai punya tingkat "catatan":
supaya keputusan ini diambil sadar. Menghapusnya dari riwayat = rewrite history, dan itu
**butuh izin baru** (lihat D13).

Masih butuh izin baru: `force-push`, hapus branch/repo, ubah history.
