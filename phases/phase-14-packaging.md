# P14 — Visual, Packaging & Gladi Bersih

**Tujuan sesi:** membungkus semuanya jadi portofolio yang bisa dipajang: video 2 menit,
screenshot, diagram arsitektur, `make all` reproducible di salinan bersih, README publik,
dan audit rahasia bersih. Menutup A11 & A12.

**Prasyarat:** semua fase, khususnya P9 (bukti) & P11 (run penuh) selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D9, D14, D16), `docs/RESUME_PROOF.md`,
`docs/ARCHITECTURE.md`, `docs/THROUGHPUT.md`, `docs/ETHICS.md`.
**Budget:** berat.

---

## Langkah

### 1. Video 2 menit (deliverable paling penting)
Alur wajib: dashboard jalan angka naik → proses dimatikan paksa di tengah → dinyalakan lagi →
lanjut dari posisi terakhir → selesai 50.000 sukses, 0 duplikat (tampilkan query dup=0).
Encode ≤ 1080p. Simpan `assets/demo.mp4`.

Rekam lewat skill `device-screen-recording`: satu jendela ber-allowlist di **output headless
sekali-pakai** (`record-segment.sh`), **bukan** monitor fisik `eDP-1`. Merekam monitor fisik
melanggar jebakan fase ini sendiri (jendela kerja/kredensial user ikut terekam) dan sudah
diganti di sesi P14. Browser demo memakai profil sementara mode kiosk (tanpa tab, bookmark,
atau address bar user).

### 2. Screenshot: sebelum / saat crash / setelah selesai (`assets/`).

### 3. Diagram arsitektur (`assets/architecture.png`)
Sumbernya ikut repo (`assets/architecture.dot`, dirender `make diagram` dengan Graphviz).
PlantUML `:20080` milik `infra/` tidak dipakai: containernya mati dan menyalakannya berarti
menyentuh infra device — sedangkan `dot` sudah ada dan hanya dipakai saat membangun (D2/D5).

### 4. `Makefile` lengkap — `make all` end-to-end
Target: `target-up`, `gen-data`, `load`, `run`, `dashboard`, `report`, `audit`, `test`,
`target-oracles`, `clean`, dan `all` yang merangkai pipeline pada port salinan bersih (8111/8121).

### 5. `scripts/secret_audit.py` + `make audit`
Pindai repo: tak ada `.env`, kredensial, host/path internal sensitif, `*.db`, `data/` ter-track.

### 6. Gladi bersih reproducible (A11)
```bash
rsync -a --exclude data --exclude reports --exclude .venv surgeline/ /tmp/surgeline-clean/
cd /tmp/surgeline-clean && cp .env.example .env
# set port salinan bersih 8111/8121, seed sama
make all      # exit 0, hasil sama: 50000, dup 0
```

### 7. README publik
Arsitektur digambar jelas, momen crash-recovery di atas, **pernyataan legal** (target milik
sendiri, D14) ditulis terang-terangan. Jangan jadikan repo publik tanpa izin user (D16).

---

## Output fase
- `assets/{demo.mp4, before.png, crash.png, after.png, architecture.png, architecture.dot}`,
  `Makefile` lengkap, `scripts/secret_audit.py` (+ test), skrip demo (`scripts/demo_*.sh`,
  `scripts/make_demo_video.sh`), README publik.

## Definition of Done
- [x] Video 2 mnt menampilkan siklus naik→crash→resume→50k 0 dup; tanpa kredensial terlihat.

```
$ ffprobe -v error -show_entries stream=index,codec_type,codec_name -of csv=p=0 assets/demo.mp4
0,h264,video                       # satu stream video, TIDAK ada audio
$ ffprobe -v error -show_entries format=duration,size -of csv=p=0 assets/demo.mp4
113.866667,2199828                 # 1 mnt 53,9 dtk · 2,2 MB · 1920x1080 · yuv420p
```
Isi: kartu judul 4 dtk → dashboard hidup 830 dtk dipercepat 10× (83 dtk) berisi 2× `kill -9`
dan pemulihannya → segmen bukti query 21 dtk → kartu penutup 6 dtk. Direkam di output
**headless sekali-pakai** dengan allowlist satu window class (`firefox` untuk dashboard,
`foot` untuk bukti); browser memakai profil sementara mode kiosk. Tidak ada jendela kerja user,
terminal user, token, atau jalur `/home/...` di frame mana pun. Angka di kartu penutup dibaca
`scripts/make_demo_video.sh` langsung dari `queue.db`, bukan diketik tangan.

- [x] 3 screenshot (sebelum/crash/setelah) + diagram arsitektur ada.

```
assets/before.png  1920x1080  ok 31.727 · sisa 17.660 · laju 1.568/mnt (berjalan normal)
assets/crash.png   1920x1080  ok 35.993 membeku · claimed 7 (yatim) · laju 1.510 -> 1.147
assets/after.png   1920x1080  49.950 / 49.950 (100%) · pending 0 · claimed 0 · dead-letter 833
assets/architecture.png  2987x793  (sumber assets/architecture.dot, `make diagram`)
```

- [x] `make all` di salinan bersih (port 8111/8121) exit 0, hasil sama (50000, dup 0) (A11).

```
$ rsync -a --exclude data --exclude reports --exclude .venv surgeline/ /tmp/surgeline-clean/
$ cd /tmp/surgeline-clean && cp .env.example .env && make setup
$ make all RUN=p14-clean WORKERS=8 TARGET_PORT=8111 DASH_PORT=8121 \
           TARGET_CONTAINER=surgeline-target-clean ; echo "EXIT=$?"
dibaca=50000 dimasukkan=49950 duplikat_ditolak=50
angka  : total=49950 ok=48273 failed=844 dead=833 dup_ref=0 dup_conf=0 ok/jam=98,650
total     : 49950      sisa      : 0        dup ref   : 0
dup konf  : 0          ok kosong : 0
dead : 833   failed : 844   ok : 48273
verify OK: antrean tuntas, dup_ref=0, dup_konf=0, ok tanpa nomor konfirmasi=0
EXIT=0
```
Hasilnya **identik** dengan run asli P11 (`ok 48.273 / failed 844 / dead 833`) walau di folder
baru, venv baru, container baru, dan port berbeda — chaos deterministik D3 terbukti sampai ke
level angka akhir.

- [x] `make audit` → 0 kebocoran; `.env`/`data/`/`*.db` tak ter-track (A12).

```
$ make audit
CATATAN (9) — jalur mesin di dokumen kerja internal, disengaja:
  [jalur] AGENTS.md:33 · KICKSTART.md:15,83,151 · docs/TARGET.md:15 · docs/TOOLS.md:38
  [jalur] env-check.md:25 · phases/phase-06-worker.md:18
audit: 91 berkas ter-track dipindai, 0 kebocoran.
$ uv run --no-sync python -m unittest src.test_secret_audit   # 15 test: tiap pola dibuktikan menangkap
Ran 15 tests — OK
```
Pemindai punya dua tingkat: **kebocoran** (exit 1 — kredensial, artefak runtime ter-track,
entri `.gitignore` hilang, jalur mesin di berkas yang dibaca klien) dan **catatan** (exit 0 —
jalur mesin di dokumen kerja internal, sengaja dibiarkan dan dicetak supaya keputusan D16
diambil sadar).

- [x] README publik memuat arsitektur + momen crash-recovery + pernyataan legal (D14).
      Urutan: judul → diagram → **pernyataan legal** → momen crash-recovery (tabel 10.621 →
      21.508 → 48.273 + video + 2 screenshot) → angka nyata → cara menjalankan → laporan klien
      → yang sengaja tidak dikerjakan → peta dokumen.
- [x] Repo publik TIDAK dijadikan publik tanpa izin user (D16). Repo tetap **privat**; D16 masih 🔓.
- [x] **Commit + push berhasil** (D13); STATE.md → PROJECT COMPLETE, acceptance 12/12.

## Metrik selesai
`demo.mp4 113,9 dtk · make all salinan bersih exit 0 (49.950 · dup 0/0) · audit 0 bocor · A1–A12 ✅`

## Jebakan
- Video yang menampilkan terminal user / token / path pribadi = gagal. Cek frame sebelum simpan.
- `make all` salinan bersih WAJIB tanpa jaringan ke situs luar — target lokal saja. Test yang
  hit jaringan akan menggagalkannya (dari P6 sudah diwanti).
- Repo publik butuh izin eksplisit user (D16). Sampai itu, tetap privat.
- Jangan pakai port 8110/8120 untuk gladi bersih kalau run asli masih jalan — pakai 8111/8121 (D9).
