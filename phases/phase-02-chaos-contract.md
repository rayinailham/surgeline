# P2 — Chaos & Kontrak Target

**Tujuan sesi:** membuat target **sengaja menyebalkan** secara terkendali & reproducible,
lalu mengunci kontraknya + oracle yang membuktikan tiap mode gagal benar-benar muncul.

**Prasyarat:** P1 selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D3), `docs/TARGET.md`, `docs/CHAOS.md`.
**Budget:** sedang.

---

## Langkah

### 1. Suntik chaos deterministik (`target/app.py`)
Aktif kalau `SURGELINE_CHAOS_RATE > 0`. Untuk tiap `POST /submit`, hitung
`h = sha256(seed + external_ref)`; kalau `h mod 1_000_000 / 1_000_000 < rate` → request "ditandai gagal".
Bagi yang ditandai jadi **3 mode** (mis. h mod 3):
- **500** — balas HTTP 500 (kegagalan server sementara → retryable).
- **lambat** — `sleep(N)` lalu tetap sukses (menguji timeout worker, bukan kegagalan permanen).
- **validasi** — balas 422 "record ditolak" (kegagalan permanen → TIDAK di-retry, tercatat).
Deterministik: `external_ref` yang sama selalu jatuh ke nasib yang sama pada seed tetap.

### 2. Kunci kontrak di `docs/CHAOS.md`
Rate default `0.05` (D3), pembagian mode, env yang menyetel (`SURGELINE_CHAOS_RATE/SEED`),
dan **daftar mode gagal + status retryable/permanen** — ini kontrak yang dipatuhi worker P8.

### 3. Oracle target (`scripts/target_oracles.py` + `make target-oracles`)
Buktikan dengan seed tetap + set `external_ref` diketahui:
- proporsi gagal ≈ 5% (toleransi wajar pada N besar, mis. 2.000 request),
- ketiga mode muncul,
- **reproducible**: dua run dengan seed sama → himpunan `external_ref` yang gagal identik.
`make target-oracles` menaikkan target dengan seed uji, menembak N request, mengumpulkan hasil,
assert, lalu menurunkan. (Analog `make oracles` driftwatch: server segar agar tidak basi.)

```bash
make target-oracles     # harus PASS semua, exit 0
```

---

## Output fase
- `target/app.py` (chaos), `docs/CHAOS.md`, `scripts/target_oracles.py`, target `make target-oracles`.

## Definition of Done
- [ ] Chaos aktif saat `rate>0`, mati saat `rate=0`; deterministik terhadap seed+external_ref.
- [ ] 3 mode gagal (500 / lambat / validasi) terbukti muncul.
- [ ] Proporsi gagal ≈ 5% pada N≥2.000 (angka nyata dicatat).
- [ ] Reproducible: 2 run seed sama → set external_ref gagal identik (diff kosong).
- [ ] `docs/CHAOS.md` mengunci rate, mode, retryable/permanen, env penyetel.
- [ ] `make target-oracles` PASS, exit 0.
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`rate≈5% pada N=… · 3 mode muncul · 2 run seed sama identik · target-oracles PASS`

## Jebakan
- Chaos **acak murni** (tanpa seed) = tidak reproducible = oracle & bukti crash-recovery goyah.
  Wajib deterministik terhadap seed + external_ref (D3).
- Mode "validasi" adalah kegagalan **permanen** — worker tak boleh retry selamanya (dipakai P8).
- Jangan bikin rate persis 5% dengan menghitung "tiap ke-20 request". Pakai hash, bukan counter —
  supaya urutan submit tidak mengubah siapa yang gagal.
