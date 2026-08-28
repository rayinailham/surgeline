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
- [ ] record/jam terukur pada ≥2 nilai N worker (angka nyata, bukan perkiraan).
- [ ] Titik jenuh worker teridentifikasi & dicatat.
- [ ] Ekstrapolasi 6 juta record ≈ Y hari ditulis dengan asumsinya terbuka (A7).
- [ ] `docs/THROUGHPUT.md` lengkap + kalimat siap-proposal.
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`X rec/jam @ N worker · jenuh di N=… · 6 juta ≈ Y hari (asumsi dicatat)`

## Jebakan
- Jangan ekstrapolasi linear buta ("4 worker 2×, jadi 100 worker 25×") — sebutkan titik jenuh.
- Angka target lokal ≠ angka platform klien. Nyatakan itu, jangan menjual angka lab sebagai janji.
- Jangan benar-benar menjalankan 6 juta (D15) — cukup ekstrapolasi terukur dari 50k.
