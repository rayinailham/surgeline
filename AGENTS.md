# AGENTS.md — SurgeLine

Aturan khusus project ini. Aturan lingkungan Arch/Playwright ada di `../AGENTS.md`
dan tetap berlaku penuh — baca itu dulu, jangan diasumsikan sudah hafal.

---

## 0. 🚨 `9router.service` — jangan pernah disentuh

```
unit: 9router.service   ·   port: 20128   ·   ~/.config/systemd/user/9router.service
peran: 9Router local AI proxy
```

Dilarang `stop`/`restart`/`kill`/`disable`/`mask`, mengedit unit-nya, menyentuh
`infra/apps/9router/` atau `infra/data/9router/`, dan memakai port `20128`.

**Kenapa fatal:** ia proxy AI lokal — mematikannya bisa memutus sesi agent itu sendiri,
dan gejalanya tampak seperti sesi mati acak, bukan seperti salah matikan service. **Selalu
sebut nama unit/container secara eksplisit**, jangan pernah wildcard (`systemctl --user stop '*'`,
`docker stop $(docker ps -q)`, `reset-failed` massal). `systemctl --user daemon-reload` aman.

## 1. Larangan keras (tidak bisa dinegosiasi per sesi)

- **Target uji HANYA milik sendiri** (`target/` — container Docker lokal project ini).
  Dilarang keras mengarahkan worker SurgeLine ke form/situs pihak lain, walau "cuma tes".
  Mengisi form massal di sistem orang tanpa otorisasi = masalah hukum, bukan portofolio.
- **Jangan menembus proteksi.** Tidak ada captcha solver, tidak ada bypass anti-bot,
  tidak ada stealth fingerprint. Kalau target nyata butuh itu, jawabannya BERHENTI dan tanya klien.
- **Jangan `sudo`, `pacman`, `playwright install-deps`, atau `--with-deps`.** Selalu gagal di Arch.
- **Container project ini diberi prefix `surgeline-`.** Jangan sentuh container lain:
  `crosscheck-tut-*` (target uji project 1, port 8090 — tanya dulu), dan apa pun milik `infra/`.
- Jangan edit `/home/rayin/infra/docker-compose.yml` (konfigurasi bersama). Project ini
  memakai `docker-compose.yml` **sendiri** di root `surgeline/`, bukan yang di `infra/`.
- Jangan hapus revision browser lama di `~/.cache/ms-playwright` (MCP `chrome-devtools`
  memakai `chromium-1228`).
- Git **sudah diizinkan** untuk project ini (D13): repo
  `git@rayin-personal:rayinailham/surgeline.git`, akun **personal** `rayinailham`.
  Commit dan push **wajib** di akhir tiap fase yang selesai. Jangan pakai akun work
  (`rayin-kantor`) atau sesi MCP GitHub milik akun itu.
  Repo **sudah publik** sejak 2026-08-29 (D16 dikunci atas izin eksplisit user).
  Masih butuh izin baru: `force-push`, hapus branch/repo, ubah history.

## 2. Runtime deliverable wajib berdiri sendiri (D2, D5)

Pipeline ini dikirim ke klien. Apa pun yang dipakai **saat berjalan** ikut jadi syarat pasang
di mesin mereka. Garis pemisahnya: **boleh dipakai saat MEMBANGUN, wajib berdiri sendiri saat BERJALAN.**

| Boleh dipakai saat membangun (device) | Runtime deliverable |
|---|---|
| cache `uv` (`~/.cache/uv`) | dependency lewat `uv.lock` saja |
| cache Playwright (`~/.cache/ms-playwright`) | Chromium via `playwright install chromium` (tanpa deps) |
| MCP `playwright`/`chrome-devtools` (recon 1–2 sampel) | worker pakai script Playwright sendiri |
| image `pandoc/core` untuk PDF laporan | — |

- **Antrean & state = SQLite** (mode WAL), bukan MySQL `:3306` / Redis `:6379` / TiDB `:4000`
  milik device. SQLite harus jalan tanpa pengawasan dan di mesin klien (D5).
- **Target app = container Docker lokal project** (`docker-compose.yml` sendiri), bukan
  service infra device. Target boleh mati/hidup bebas — ia memang disimulasikan gagal.
- Laporan tetap `openpyxl`, bukan MCP `excel`.

## 3. Aturan target app (D2, D9)

- Target berjalan di `127.0.0.1:8110` (salinan bersih `8111`). Dashboard di `127.0.0.1:8120`
  (salinan bersih `8121`). Port dipilih agar tidak menabrak service device (`8000`, `8090`
  crosscheck, `8100` driftwatch, `3000`, `3100`, `3170`, `20080`, `4000`, `2379`, `5540`,
  `943`, `9443`, `20128`). Jangan pindah port tanpa mengubah D9.
- Target **sengaja menyebalkan** (D3): 5% request gagal (500 / lambat / tolak validasi),
  deterministik berdasar seed supaya bisa direproduksi. Kegagalan target adalah fitur uji,
  **bukan** bug yang harus "diperbaiki" di target. Yang diuji adalah ketahanan worker.
- Setiap submission sukses mengembalikan **nomor konfirmasi** unik di halaman hasil.
  Worker wajib menangkap dan menyimpannya (D6). Nomor konfirmasi hilang = submission dianggap gagal.

## 4. Aturan antrean & dedup (D4, D5)

- Dedup **di level database**: kolom natural-key record punya `UNIQUE`. Loader pakai
  `INSERT OR IGNORE` — duplikat ditolak DB, bukan dicek di memori proses. Bukti = query hitung.
- **Data mentah tidak pernah ditimpa.** Antrean = satu file SQLite per run di `data/`.
  `data/` dan `reports/` **gitignored**. Yang masuk repo hanya kode, dokumen, dan contoh
  laporan tersanitasi (`assets/`).
- State machine job: `pending → claimed → ok | failed | dead`. Transisi hanya lewat
  transaksi atomik. Job `claimed` yang melewati lease timeout dikembalikan ke `pending` (D8).
- Klaim worker wajib atomik (`BEGIN IMMEDIATE`): dua worker tidak boleh mengklaim job sama.

## 5. Hierarki dokumen (kalau ada konflik)

1. `docs/DECISIONS.md` — keputusan terkunci. Menang atas semua.
2. `docs/SCHEMA.md` — bentuk record + tabel DB.
3. `docs/ETHICS.md` — batas legal. Menang atas kenyamanan teknis, selalu.
4. `phases/phase-NN-*.md` — instruksi kerja sesi.
5. `docs/ACCEPTANCE.md`, `PLAN.md`, `README.md`.

Menemukan file bawah bertentangan dengan file atas → **perbaiki file bawah di sesi yang sama**,
jangan diamkan, jangan diam-diam ikut yang salah.

## 6. Gerbang commit (D13) — tidak boleh dilewat

Sebuah fase **belum** ✅ sebelum tiga hal ini berhasil, berurutan:

```bash
make audit                    # atau scripts/secret_audit.py; wajib 0 kebocoran (sebelum P14: cek manual)
git add -A && git status --short
git commit -m "PNN: <ringkas>"     # body memuat artefak + metrik selesai
git push
```

- Sebelum `make audit` ada (sebelum P14), cek manual: `git status --short` tidak boleh memuat
  `.env`, `data/`, `reports/`, `auth/`, `*.db`, `*.sqlite*`.
- Kalau `push` gagal, fase tetap 🟨 di `STATE.md` dan alasannya dicatat. Jangan klaim selesai.
- Satu fase = satu commit. Riwayat commit adalah bagian bukti portofolio
  ("15 commit, 15 fase, tiap commit punya metrik").

## 7. Sebelum menyentuh browser/Playwright di sesi mana pun

```bash
bash /home/rayin/Projects/Testing/crosscheck/scripts/arch_provision.sh   # idempotent, tanpa sudo
```
Kalau SurgeLine butuh Playwright sendiri sebagai runtime, salin script itu ke `scripts/` di P6 —
jangan panggil lintas-project di kode produksi. `playwright install chromium` (tanpa `--with-deps`).

## 8. Alur sesi

`KICKSTART.md` adalah prompt universalnya; `STATE.md` adalah satu-satunya memori antar sesi.
Satu fase per sesi. DoD dicentang hanya dengan output perintah nyata, bukan klaim,
lalu ditutup dengan commit + push (§6).
