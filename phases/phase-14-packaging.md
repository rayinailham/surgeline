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
Rekam satu monitor (`wf-recorder -o eDP-1`), tanpa kredensial/jendela kerja user terlihat.
Encode ≤ 1080p. Simpan `assets/demo.mp4`.

### 2. Screenshot: sebelum / saat crash / setelah selesai (`assets/`).

### 3. Diagram arsitektur (`assets/architecture.png` — dari PlantUML infra `:20080` atau inline).

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
- `assets/{demo.mp4, before.png, crash.png, after.png, architecture.png}`, `Makefile` lengkap,
  `scripts/secret_audit.py`, README publik, `docs/PITCH.md` (opsional naskah lisan).

## Definition of Done
- [ ] Video 2 mnt menampilkan siklus naik→crash→resume→50k 0 dup; tanpa kredensial terlihat.
- [ ] 3 screenshot (sebelum/crash/setelah) + diagram arsitektur ada.
- [ ] `make all` di salinan bersih (port 8111/8121) exit 0, hasil sama (50000, dup 0) (A11).
- [ ] `make audit` → 0 kebocoran; `.env`/`data/`/`*.db` tak ter-track (A12).
- [ ] README publik memuat arsitektur + momen crash-recovery + pernyataan legal (D14).
- [ ] Repo publik TIDAK dijadikan publik tanpa izin user (D16).
- [ ] **Commit + push berhasil** (D13); STATE.md → PROJECT COMPLETE, acceptance 12/12.

## Metrik selesai
`demo.mp4 … dtk · make all salinan bersih exit 0 · audit 0 bocor · A1–A12 ✅`

## Jebakan
- Video yang menampilkan terminal user / token / path pribadi = gagal. Cek frame sebelum simpan.
- `make all` salinan bersih WAJIB tanpa jaringan ke situs luar — target lokal saja. Test yang
  hit jaringan akan menggagalkannya (dari P6 sudah diwanti).
- Repo publik butuh izin eksplisit user (D16). Sampai itu, tetap privat.
- Jangan pakai port 8110/8120 untuk gladi bersih kalau run asli masih jalan — pakai 8111/8121 (D9).
