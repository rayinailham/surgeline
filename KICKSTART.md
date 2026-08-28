# SurgeLine — Prompt Kickstart (universal)

Satu prompt, dipakai kapan saja, sesi keberapa pun, dari fase 0 sampai selesai.
Agent menentukan sendiri posisi progres dari `STATE.md`. **Tidak perlu diedit.**

Kirim isi blok di bawah ini apa adanya, berulang kali, sampai `STATE.md` berbunyi
`PROJECT COMPLETE`.

---

## Prompt

```
Project: SurgeLine — bulk form submission: target app → loader → antrean → worker → dashboard.
Root: /home/rayin/Projects/Testing/surgeline

LARANGAN MUTLAK — berlaku sepanjang sesi, sebelum langkah apa pun:
  JANGAN PERNAH menyentuh `9router.service` (systemd USER unit, port 20128,
  9Router local AI proxy). Dilarang stop/restart/kill/disable/mask, mengedit unit-nya,
  menyentuh infra/apps/9router atau infra/data/9router, dan memakai port 20128.
  Ia proxy AI lokal — mematikannya bisa memutus sesi ini sendiri, gejalanya tampak seperti
  sesi mati acak. SELALU sebut nama unit/container eksplisit, JANGAN PERNAH wildcard
  (`systemctl --user stop '*'`, `docker stop $(docker ps -q)`, reset-failed massal).
  `systemctl --user daemon-reload` aman.

  TARGET UJI HANYA MILIK SENDIRI: container `surgeline-*` di target/. Dilarang mengarahkan
  worker ke form/situs pihak lain. Tidak menembus captcha/anti-bot. (docs/ETHICS.md menang.)

LANGKAH 1 — ORIENTASI (lakukan ini dulu, sebelum apa pun):

1. Baca berurutan: surgeline/AGENTS.md, lalu ../AGENTS.md (aturan Arch — wajib),
   lalu surgeline/STATE.md, lalu surgeline/docs/DECISIONS.md (keputusan terkunci —
   jangan dinegosiasi ulang).

2. Cocokkan klaim dengan kenyataan disk:
     ls -R surgeline/src surgeline/scripts surgeline/target 2>/dev/null
     ls surgeline/data surgeline/reports 2>/dev/null | head -20
     docker ps --format '{{.Names}} {{.Ports}}' | grep surgeline
     git -C surgeline log --oneline | head -20
   Kalau STATE.md berbeda dengan disk, DISK yang benar. Perbaiki STATE.md sebelum lanjut.
   Kalau STATE.md bilang sebuah fase ✅ tapi tidak ada commit untuk fase itu, fase itu
   BELUM selesai (D13) — turunkan statusnya jadi 🟨.

3. Jalankan gerbang kesehatan sebelum memilih fase (lewati bagian yang belum ada):
     cd surgeline
     uv run --no-sync python -m compileall -q src scripts
     uv run --no-sync python -m unittest discover -s src -v
     cd ..
   Kalau salah satu gagal, atau `STATE.md` mencatat temuan audit / bug terbuka yang
   memengaruhi correctness, dedup, crash-recovery, keamanan, atau acceptance:
   JANGAN lanjut ke fase berikutnya. Kerjakan remediasi terkecil lebih dulu, tambah test
   regresi, verifikasi penuh, commit terpisah, lalu update `STATE.md`. Temuan audit terbuka
   menang atas pemilihan fase otomatis.

4. Tentukan sendiri fase mana yang dikerjakan sesi ini:

     P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8 → P9 → P11 → P12 → P13 → P14
                              └─► P10 (dashboard, butuh P4; berguna penuh sejak P6)

   - Ambil fase belum-selesai dengan nomor terkecil yang semua prasyaratnya sudah ✅.
   - Kalau ada fase bertanda 🟨 (jalan) atau 🟥 (blocked), selesaikan itu dulu.
   - P9 (bukti crash-recovery) didahulukan begitu P8 selesai — itu jantung portofolio.
   - P10 (dashboard) boleh diambil setelah P4 kalau P5–P8 belum semua siap dan kamu ingin
     memisahkan sesi, tapi JANGAN dahulukan P10/P13/P14 di atas P8/P9.
   - P11 butuh P8 tuntas + P10. P12 butuh P11. P14 butuh semua termasuk P9 & P11.

5. Buka HANYA file fase terpilih: surgeline/phases/phase-NN-*.md
   Lalu buka file yang disebut di bagian "Read-set" fase itu. Tidak lebih.
   Kalau file fase bertentangan dengan docs/DECISIONS.md, docs/SCHEMA.md, atau
   docs/ETHICS.md: ketiganya menang, dan perbaiki file fase itu di sesi yang sama.

6. Sebelum mulai kerja, sebutkan ke saya dalam 3 baris: fase/remediasi yang kamu pilih,
   alasannya, dan apa yang akan lahir di akhir sesi.

LANGKAH 2 — SIAPKAN (hanya kalau fase terpilih menyentuhnya):

   Target app (P1+, dan tiap fase yang menjalankan worker):
     cd surgeline && docker compose up -d && cd ..
     curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8110/health   # harus 200
     Container diberi prefix surgeline-. JANGAN sentuh container lain.

   Browser/Playwright (P6+):
     bash /home/rayin/Projects/Testing/crosscheck/scripts/arch_provision.sh
     JANGAN `playwright install-deps`, `--with-deps`, `sudo`, atau `pacman`. Selalu gagal di Arch.

LANGKAH 3 — KERJAKAN:

Jika mengerjakan fase, selesaikan sampai SEMUA "Definition of Done"-nya tercentang dengan
bukti nyata (output perintah yang ditempel), bukan klaim.

ATURAN HEMAT TOKEN (wajib):
- Jangan baca file fase selain yang terpilih.
- Jangan baca ../HARNESS.md, ../portfolio/, ../crosscheck/, ../driftwatch/ — kutipan yang
  perlu sudah ada di file fase dan docs/.
- Jangan baca data mentah (50k baris CSV / tabel DB). Agregasi dengan wc -l / head /
  `sqlite3 db "SELECT status,COUNT(*) FROM jobs GROUP BY status"` / jq.
- Jangan buka halaman target satu per satu. MCP browser hanya 1–2 sampel untuk recon.
- Playwright hanya di worker produksi. Pekerjaan berulang lain pakai httpx/script.

ATURAN ETIKA (tidak bisa dinegosiasi — docs/ETHICS.md menang atas kenyamanan teknis):
- Worker HANYA menembak target milik sendiri (127.0.0.1:8110). Tidak pernah situs orang.
- Tidak menembus captcha/anti-bot/WAF. Tidak login ke akun orang lain.
- Kegagalan 5% target adalah fitur uji — JANGAN "perbaiki" target agar tidak gagal.
  Yang diuji adalah ketahanan worker menghadapi kegagalan itu.

ATURAN KERJA:
- Kerjakan lewat Bash sebisa mungkin. Verifikasi tiap langkah, jangan asumsi.
- Patch kecil dan reversible. Jangan refactor yang tidak diminta.
- PAKAI ULANG infra device saat membangun (cache uv, cache Playwright, image pandoc, MCP),
  TAPI runtime deliverable wajib berdiri sendiri (D2/D5): antrean SQLite (bukan
  MySQL/Redis/TiDB device), target container project sendiri (bukan service infra),
  laporan openpyxl (bukan MCP excel). Sebelum menambah tool: cek `docker images`+`docker ps`.
- Container project diberi prefix surgeline-. Jangan sentuh crosscheck-tut-* atau infra.
- Kalau gagal, laporkan output error persis. Jangan diperhalus, jangan diklaim sukses.
- Kalau sebuah keputusan 🔓 di DECISIONS.md jatuh di fase ini, kunci sekarang dan tulis
  alasannya. Kecuali D16 (repo publik) — itu butuh izin eksplisit saya.
- Bukti crash-recovery / dedup / throughput adalah ANGKA dari query, bukan "tidak ada error".

LANGKAH 4 — PENUTUP SESI (wajib, jangan dilewat):

1. Centang DoD di file fase dan tempel output perintahnya (fase) ATAU catat temuan +
   test regresi + verifikasi di STATE.md (remediasi).
2. GERBANG COMMIT (D13) — fase BELUM ✅ sebelum tiga langkah ini berhasil:
     make audit          # atau cek manual sebelum P14: git status --short tidak boleh memuat
                         # .env, data/, reports/, auth/, *.db, *.sqlite*
     git add -A && git status --short
     git commit -m "PNN: <ringkas>"     # body memuat artefak + metrik selesai
     git push
   Remote: git@rayin-personal:rayinailham/surgeline.git (akun PERSONAL, repo privat).
   Jangan pakai akun work. Kalau push gagal, fase tetap 🟨 dan alasannya dicatat.
   Satu fase = satu commit.
3. Update surgeline/STATE.md:
   - tabel status fase (⬜ belum · 🟨 jalan · ✅ selesai · 🟥 blocked)
   - tanggal, fase aktif, fase berikutnya
   - artefak baru yang lahir
   - tabel metrik diisi ANGKA NYATA dari file/DB hasil, bukan perkiraan
   - blocker / keputusan yang masih 🔓
   - jaga STATE.md tetap < 100 baris; buang catatan yang sudah tidak relevan
4. Laporkan ke saya: fase/remediasi apa yang selesai, metrik dan hasil test, hash commit-nya,
   dan apa yang jadi fase berikutnya.

Selesaikan SATU fase atau SATU paket remediasi saja per sesi. Jangan lanjut ke fase
berikutnya, kecuali fase itu bertanda "ringan" di PLAN.md dan pekerjaan sekarang sudah
100% selesai termasuk push-nya.
```

---

## Cara memakai

1. Buka sesi baru di `/home/rayin/Projects/Testing`.
2. Tempel blok prompt di atas apa adanya.
3. Agent menyebut fase yang dipilihnya dalam 3 baris — baca sebentar, lalu biarkan jalan.
4. Di akhir sesi ia melapor + sudah commit & push.
5. Sesi berikutnya: **tempel prompt yang sama persis**. Tidak ada yang perlu diubah.

## Catatan

- Fase pertama kalau `STATE.md` masih perawan: **P0 — Bootstrap**.
- **Memaksa fase tertentu:** tambah satu baris di akhir prompt:
  `Abaikan pemilihan otomatis, kerjakan fase P06.`
- **Sesi terputus di tengah fase:** prompt yang sama tetap dipakai — agent melihat 🟨 dan lanjut.
- **Ada bug/temuan audit terbuka:** prompt yang sama menghentikan pemilihan fase, menyelesaikan
  remediasi dengan test regresi, lalu commit terpisah.
- **Kalau agent mengklaim fase selesai tanpa commit:** langkah orientasi 2 sudah menyuruhnya
  menurunkan status sendiri. Kalau tetap terjadi, tunjukkan langkah 4 poin 2 kepadanya.
