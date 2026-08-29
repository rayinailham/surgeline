# SurgeLine — THROUGHPUT (diukur di P12)

> Semua angka di halaman ini keluar dari `queue.db` run nyata lewat `src/throughput.py`,
> bukan dari perkiraan. Perintah untuk mengulangnya ada di §7. Batas kepercayaannya
> ditulis di §5 — **angka lab bukan janji produksi**.

**Ringkas:** 81.915 record/jam pada 8 worker. Menambah worker di atas 8 memberi kurang
dari 5%, di atas 12 justru menurun. Pada laju itu, 6.000.000 record ≈ **73 jam ≈ 3,0 hari**
di mesin ini, dengan asumsi §5.

---

## 1. Cara mengukurnya (kenapa perbandingannya adil)

Tiap nilai N mendapat **antrean baru dari file input yang sama**
(`data/p12/subset.csv`, 800 record pertama dari dataset 50k P3). Chaos target
deterministik dari `sha256(seed + external_ref)` (D3, `docs/CHAOS.md`) dan diputuskan
**sebelum** penyimpanan idempoten, jadi tiap N menghadapi himpunan kegagalan yang persis
sama. Buktinya: ketujuh run berakhir identik — `ok 776 / failed 17 / dead 7`, 828 percobaan,
`attempts/ok = 1,067`. Yang berubah cuma jumlah worker.

Definisi laju (`src/throughput.py`):

- **Jendela** = `MIN(attempts.started_at)` .. `MAX(COALESCE(attempts.ended_at, started_at))`.
  Jam dinding, **termasuk** waktu tunggu backoff D7 dan jeda saat worker dibunuh — bukan
  penjumlahan waktu sibuk. Klien membayar jam dinding.
- **record/jam** = job `ok` per jendela. Hanya submission bernomor konfirmasi yang dihitung
  sukses (D6); `failed`/`dead` hanya masuk kolom `terminal/jam` di keluaran CLI.

Target `127.0.0.1:8110` sama, hidup, dan tidak di-restart antar-N: chaos-nya tetap menyala
untuk tiap percobaan, jadi restart hanya akan menambah derau cold-start tanpa mengubah beban.

## 2. Tabel skala N worker (800 record, subset sama)

| N worker | run | ok | jendela (dtk) | record/jam | speedup | efisiensi | naik vs N sebelumnya |
|---|---|---|---|---|---|---|---|
| 1 | `p12-n1` | 776 | 125,8 | 22.204 | 1,00× | 100% | — |
| 2 | `p12-n2` | 776 | 68,8 | 40.627 | 1,83× | 92% | +83,0% |
| 4 | `p12-n4` | 776 | 43,9 | 63.565 | 2,86× | 72% | +56,5% |
| **8** | `p12-n8` | 776 | 34,1 | **81.915** | 3,69× | 46% | +28,9% |
| 12 | `p12-n12` | 776 | 32,7 | 85.388 | 3,85× | 32% | +4,2% |
| 16 | `p12-n16` | 776 | 33,0 | 84.631 | 3,81× | 24% | −0,9% |
| 24 | `p12-n24` | 776 | 34,6 | 80.664 | 3,63× | 15% | −4,7% |

**Titik jenuh: N = 8** (terbukti, ambang 10%). Dari 8 ke 12 worker throughput hanya naik
4,2% sambil memakai 50% proses lebih banyak; dari 12 ke 16 dan 24 justru **turun**.
Puncak absolut ada di N=12 (85.388 record/jam), tapi 3.473 record/jam tambahan itu tidak
sepadan dengan 4 proses Chromium ekstra — **8 worker adalah titik operasi yang disarankan.**

Efisiensi turun jauh sebelum jenuh: pada 8 worker tiap worker hanya memberi 46% dari
penskalaan ideal. Itu normal untuk pekerjaan yang lewat browser, dan justru alasan kenapa
"tambah worker" bukan jawaban untuk semua masalah kecepatan.

## 3. Angka ini bisa diulang

| Ukuran | Run pertama | Ulangan | Selisih |
|---|---|---|---|
| N=4 | 63.565 rec/jam (`p12-n4`) | 63.996 (`p12rep-n4`) | +0,7% |
| N=8 | 81.915 rec/jam (`p12-n8`) | 81.943 (`p12rep-n8`) | +0,03% |
| N=12 | 85.388 rec/jam (`p12-n12`) | 85.636 (`p12cpu-n12`) | +0,3% |

Ulangan dijalankan setelah seluruh sapuan selesai, urutannya berbeda; sebarannya < 1%.

## 4. Laju tidak runtuh saat antrean membesar

| Run | Record | N worker | Kondisi | record/jam |
|---|---|---|---|---|
| `p12-n4` | 800 | 4 | bersih | 63.565 |
| `full50k` (P11) | 49.950 | 4 | + 2× `kill -9`, chaos penuh | 61.270 |

Antrean **62× lebih besar** dan dua kali dimatikan paksa hanya menurunkan laju 3,6%.
Itu konsekuensi D5: state ada di SQLite berindeks, bukan di memori proses, jadi biaya per
job tidak tumbuh bersama panjang antrean. `attempts/ok` naik dari 1,067 ke 1,104 — selisihnya
adalah percobaan yang hilang bersama worker yang dibunuh, lalu dipulihkan sapuan lease (D8).

**Apa yang menjadi batas.** Selama run N=12, container target hanya memakai ≤ 0,52 core
dari 16 (`docker stats`: 2,58% / 52,07% / 14,06% dari satu core, memori datar ~43 MiB),
sementara CPU host terpakai 68% `ni` dengan sisa idle 16,7%. Jadi yang jenuh adalah
**CPU mesin worker (Chromium headless)**, bukan target app dan bukan penulisan SQLite.
Konsekuensinya: menaikkan angka ini butuh CPU/mesin lebih banyak, bukan antrean lain.
Catatan jujur: sampelnya kasar (3 titik di dalam jendela 33 detik), cukup untuk menyingkirkan
target app sebagai tersangka, tidak cukup untuk memecah biaya per-komponen.

## 5. Ekstrapolasi 6 juta record — dengan asumsinya terbuka

Linear dari laju terukur, `jam = 6.000.000 / (record per jam)`:

| Dasar | record/jam | 6 juta record |
|---|---|---|
| 12 worker (puncak subset) | 85.388 | 70,3 jam ≈ **2,9 hari** |
| **8 worker (titik operasi)** | **81.915** | **73,2 jam ≈ 3,0 hari** |
| 4 worker, skala penuh 50k + 2 kill (P11) | 61.270 | 97,9 jam ≈ **4,1 hari** |

Rentang jujur di mesin ini: **2,9 – 4,1 hari**, dan angka yang dipakai untuk berjanji
adalah yang konservatif, bukan yang terbaik.

**Asumsi yang harus ikut dibaca:**

1. **Target lokal.** Semua angka melawan container target project ini di `127.0.0.1:8110`:
   tanpa latensi jaringan, tanpa rate limit, tanpa antrean di sisi server. Platform nyata
   hampir selalu lebih lambat.
2. **Satu mesin.** 16 core, 15,3 GiB RAM, satu file SQLite WAL. Menjalankan di banyak mesin
   sekaligus **tidak diuji** dan di luar scope (D15) — jangan dijanjikan.
3. **Kegagalan 5% deterministik** (D3) sudah termasuk di dalam angka, begitu pula retry
   backoff-nya (D7). Platform dengan pola gagal berbeda akan bergeser.
4. **Linear tanpa jenuh baru.** Ekstrapolasi ini hanya memperpanjang durasi pada laju tetap;
   ia tidak mengasumsikan tambahan worker. 6 juta record juga berarti file antrean ~120×
   lebih besar dari run 50k — §4 menunjukkan biaya per job datar sampai 50k, bukan sampai 6 juta.
5. **6 juta record tidak pernah benar-benar dijalankan** (D15). Ini ekstrapolasi terukur dari
   50.000, bukan hasil pengukuran 6 juta.
6. **Rate limit klien menang atas angka ini.** Kalau platform tujuan membatasi (atau
   memakai captcha/anti-bot), jawabannya bukan menambah worker — lihat `docs/ETHICS.md`
   dan `docs/CONSULTATION.md`.

## 6. Kalimat siap-proposal

> Pipeline ini terukur **±82.000 record/jam dengan 8 worker** di satu mesin 16-core, melawan
> target yang sengaja menggagalkan 5% request. Pada laju itu, **6 juta record selesai dalam
> sekitar 3 hari**; memakai angka konservatif dari run 50.000 penuh yang dua kali saya matikan
> paksa di tengah jalan, sekitar **4 hari**. Menambah worker di atas 8 hanya memberi 4% —
> yang jenuh adalah CPU mesin, jadi mempercepatnya berarti menambah mesin, bukan menambah
> proses. Semua angka ini dari mesin saya dan target saya sendiri; angka di platform Anda
> akan bergantung pada rate limit dan latensinya, dan **kalau platform Anda punya API,
> browser tidak diperlukan sama sekali dan angkanya akan jauh lebih besar.**

## 7. Mengulang pengukuran ini

```bash
make target-up
head -n 801 data/input/records.csv > data/p12/subset.csv    # subset adil, 800 record
uv run --no-sync python scripts/scale_bench.py --label p12 --workers 1 2 4 8 12 16 24
uv run --no-sync python src/throughput.py --scale data/p12/scale-all.json
uv run --no-sync python src/throughput.py --run full50k      # pembanding skala penuh P11
```

`scripts/scale_bench.py` menolak menimpa `data/<label>-n<N>/` yang sudah ada (D5: data mentah
tidak pernah ditimpa) — pakai `--label` baru untuk mengulang. Aritmetika jendela, titik jenuh,
dan ekstrapolasi dijaga 12 test di `src/test_throughput.py`.
