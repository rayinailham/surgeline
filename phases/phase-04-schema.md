# P4 — Kontrak Data & Skema Antrean

**Tujuan sesi:** mengunci bentuk record + tabel DB antrean sekali untuk selamanya, termasuk
state machine, `UNIQUE` untuk dedup (D4), dan tabel audit percobaan. Setelah P4, bentuk ini
tidak berubah — loader/worker/dashboard semua mengacu ke sini.

**Prasyarat:** P3 selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D4, D5, D6, D7, D8), `docs/SCHEMA.md`,
`docs/DATA_DICTIONARY.md`, `docs/ARCHITECTURE.md`.
**Budget:** sedang.

---

## Langkah

### 1. Definisikan & implementasikan skema (`src/schema.py` + `docs/SCHEMA.md` terkunci)
Tabel `jobs`:
```
external_ref TEXT PRIMARY KEY / UNIQUE   -- natural key, dedup (D4)
payload      TEXT      -- JSON field form
status       TEXT      -- pending|claimed|ok|failed|dead
attempts     INTEGER   -- jumlah percobaan
worker_id    TEXT      -- pemilik saat claimed
claimed_at   REAL      -- epoch, untuk lease (D8)
confirmation TEXT      -- nomor konfirmasi (D6), UNIQUE bila non-null
last_error   TEXT      -- alasan terakhir gagal/dead
created_at, updated_at REAL
```
Tabel `attempts` (audit tiap percobaan): `id, external_ref, worker_id, started_at, ended_at,
outcome (ok|retryable|permanent|timeout), error, confirmation`.
Index: `status`, `(status, claimed_at)`.

`src/schema.py` menyediakan `init_db(path)` yang membuat tabel + pragma WAL:
```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
```

### 2. Kunci state machine di `docs/SCHEMA.md`
Transisi sah: `pending→claimed`, `claimed→ok`, `claimed→failed` (validasi permanen),
`claimed→pending` (retry / lease expired), `pending/claimed→dead` (attempts habis).
Semua transisi lewat transaksi atomik. Tulis diagram + aturannya.

### 3. Unit test skema (`src/test_schema.py`)
- `init_db` membuat tabel + WAL aktif.
- `INSERT OR IGNORE` external_ref sama 2× → tetap 1 baris (dedup terbukti di level DB).
- constraint `UNIQUE(confirmation)` menolak nomor konfirmasi dobel non-null.
- transisi ilegal ditolak / tidak mengubah state (kalau divalidasi di layer store).

```bash
uv run --no-sync python -m unittest src.test_schema -v
```

---

## Output fase
- `src/schema.py`, `src/test_schema.py`, `docs/SCHEMA.md` (terkunci).

## Definition of Done
- [ ] `docs/SCHEMA.md` terkunci: tabel `jobs` + `attempts`, tipe, index, state machine, aturan transisi.
- [ ] `init_db` membuat DB dengan WAL + busy_timeout; diverifikasi `PRAGMA journal_mode` = `wal`.
- [ ] Dedup `UNIQUE(external_ref)` terbukti lewat test (`INSERT OR IGNORE` 2× → 1 baris).
- [ ] `UNIQUE(confirmation)` menolak dobel non-null.
- [ ] `uv run … -m unittest src.test_schema` semua lulus.
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`tabel jobs+attempts · WAL aktif · dedup UNIQUE terbukti · N test lulus`

## Jebakan
- Tanpa WAL, banyak worker menulis akan saling-blok parah. WAL + `busy_timeout` wajib (D5).
- `confirmation` boleh NULL saat pending; `UNIQUE` di SQLite mengizinkan banyak NULL — pas.
- Skema ini kontrak. Kalau P5/P6 butuh kolom baru, ubah di SINI + `docs/SCHEMA.md`, jangan diam-diam.
