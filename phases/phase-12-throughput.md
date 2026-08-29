# P12 — Ukur Throughput

**Tujuan sesi:** mengubah run penuh P11 jadi **angka yang bisa dipercaya klien**: record/jam
per N worker, lalu ekstrapolasi jujur ke 6 juta record. Ini yang membuat klien job 18 percaya
kita paham skala (A7).

**Prasyarat:** P11 selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D15), `docs/THROUGHPUT.md`,
`data/full50k/run.json`.
**Budget:** sedang.

---

## Langkah

### 1. `src/throughput.py`
Baca `attempts`/`run.json`: hitung record sukses per satuan waktu. Ukur pada beberapa N worker
(mis. 1, 2, 4, 8) di subset yang sama supaya adil — catat record/jam tiap N + titik jenuh
(di mana menambah worker tak menambah throughput karena SQLite/target jadi bottleneck).

### 2. Ekstrapolasi jujur
```
throughput_terbaik = X record/jam pada N worker
6.000.000 record ≈ 6.000.000 / X jam ≈ Y hari (asumsi target & mesin ini)
```
Tulis **asumsinya terbuka**: ini pada target lokal yang sengaja gagal 5%; platform nyata bisa
lebih lambat (rate limit) atau lebih cepat (kalau ada API → browser tak perlu, lihat CONSULTATION).

### 3. Isi `docs/THROUGHPUT.md`
Tabel N-worker vs record/jam, titik jenuh, ekstrapolasi 6 juta, dan kalimat kunci untuk proposal.

```bash
uv run --no-sync python src/throughput.py --run full50k
```

---

## Output fase
- `src/throughput.py`, `docs/THROUGHPUT.md` (angka nyata + ekstrapolasi + asumsi).

## Definition of Done
- [x] record/jam terukur pada ≥2 nilai N worker (angka nyata, bukan perkiraan).
- [x] Titik jenuh worker teridentifikasi & dicatat.
- [x] Ekstrapolasi 6 juta record ≈ Y hari ditulis dengan asumsinya terbuka (A7).
- [x] `docs/THROUGHPUT.md` lengkap + kalimat siap-proposal.
- [x] **Commit + push berhasil** (D13).

## Metrik selesai
`X rec/jam @ N worker · jenuh di N=… · 6 juta ≈ Y hari (asumsi dicatat)`

## Jebakan
- Jangan ekstrapolasi linear buta ("4 worker 2×, jadi 100 worker 25×") — sebutkan titik jenuh.
- Angka target lokal ≠ angka platform klien. Nyatakan itu, jangan menjual angka lab sebagai janji.
- Jangan benar-benar menjalankan 6 juta (D15) — cukup ekstrapolasi terukur dari 50k.

---

## Bukti (sesi 2026-08-29)

Gerbang kesehatan sebelum & sesudah:

```
$ uv run --no-sync python -m compileall -q src scripts && uv run --no-sync python -m unittest discover -s src
Ran 122 tests in 2.544s

OK
```

Sapuan N worker — subset adil `data/p12/subset.csv` (800 record, dataset 50k P3), target
`127.0.0.1:8110` hidup. Ketujuh run berakhir identik (`ok 776 / failed 17 / dead 7`,
828 percobaan, `attempts/ok=1,067`) → yang berubah hanya jumlah worker:

```
$ uv run --no-sync python scripts/scale_bench.py --label p12 --workers 1 2 4 8
workers=1 processed=828 elapsed=126.322s throughput=6.55 job/s return_codes=[0]
workers=2 processed=828 elapsed=69.233s throughput=11.96 job/s return_codes=[0, 0]
workers=4 processed=828 elapsed=44.450s throughput=18.63 job/s return_codes=[0, 0, 0, 0]
workers=8 processed=828 elapsed=34.690s throughput=23.87 job/s return_codes=[0, 0, 0, 0, 0, 0, 0, 0]

$ uv run --no-sync python scripts/scale_bench.py --label p12 --workers 12 16 24 --manifest data/p12/scale-hi.json
workers=12 processed=828 elapsed=33.452s throughput=24.75 job/s
workers=16 processed=828 elapsed=33.972s throughput=24.37 job/s
workers=24 processed=828 elapsed=35.833s throughput=23.11 job/s

$ uv run --no-sync python src/throughput.py --scale data/p12/scale-all.json
| N worker | run | ok | jendela (dtk) | record/jam | speedup | efisiensi | naik vs N sebelumnya |
|---|---|---|---|---|---|---|---|
| 1 | `p12-n1` | 776 | 125.8 | 22,204 | 1.00× | 100% | — |
| 2 | `p12-n2` | 776 | 68.8 | 40,627 | 1.83× | 92% | +83.0% |
| 4 | `p12-n4` | 776 | 43.9 | 63,565 | 2.86× | 72% | +56.5% |
| 8 | `p12-n8` | 776 | 34.1 | 81,915 | 3.69× | 46% | +28.9% |
| 12 | `p12-n12` | 776 | 32.7 | 85,388 | 3.85× | 32% | +4.2% |
| 16 | `p12-n16` | 776 | 33.0 | 84,631 | 3.81× | 24% | -0.9% |
| 24 | `p12-n24` | 776 | 34.6 | 80,664 | 3.63× | 15% | -4.7% |

titik jenuh: N=8 (terbukti, ambang 10%)
terbaik: 85,388 record/jam @ 12 worker -> 6,000,000 record ≈ 70.3 jam ≈ 2.9 hari
```

Ulangan (urutan berbeda, sebaran < 1%) dan pembanding skala penuh P11:

```
$ uv run --no-sync python src/throughput.py --run p12rep-n4 --workers 4
run=p12rep-n4 workers=4 ok=776/800 window=43.7s ok/s=17.78 ok/jam=63,996 ...
$ uv run --no-sync python src/throughput.py --run p12rep-n8 --workers 8
run=p12rep-n8 workers=8 ok=776/800 window=34.1s ok/s=22.76 ok/jam=81,943 ...
$ uv run --no-sync python src/throughput.py --run full50k
run=full50k workers=4 ok=48273/49950 window=2836.3s ok/s=17.02 ok/jam=61,270 terminal/jam=63,398 attempts/ok=1.104
```

Batasnya CPU worker, bukan target — sampel `docker stats` selama run N=12
(container ≤ 0,52 core dari 16, memori datar; host 68% `ni`, idle 16,7%):

```
surgeline-target cpu=2.58%  mem=42.55MiB / 15.26GiB   %Cpu(s): 45.8 ni, 33.0 id
surgeline-target cpu=52.07% mem=43.31MiB / 15.26GiB   %Cpu(s): 68.1 ni, 16.7 id
surgeline-target cpu=14.06% mem=43.66MiB / 15.26GiB   %Cpu(s): 67.1 ni, 16.3 id
```

Artefak: `src/throughput.py`, `scripts/scale_bench.py`, `docs/THROUGHPUT.md`,
`src/test_throughput.py` (12 test). Run mentah `data/p12*/` (gitignored).
