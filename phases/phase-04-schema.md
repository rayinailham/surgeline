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

### 3. Unit test skema (`src/tests/test_schema.py`)
- `init_db` membuat tabel + WAL aktif.
- `INSERT OR IGNORE` external_ref sama 2× → tetap 1 baris (dedup terbukti di level DB).
- constraint `UNIQUE(confirmation)` menolak nomor konfirmasi dobel non-null.
- transisi ilegal ditolak / tidak mengubah state (kalau divalidasi di layer store).

```bash
uv run --no-sync python -m unittest discover -s src -p "test_schema.py" -v
```

---

## Output fase
- `src/schema.py`, `src/tests/test_schema.py`, `docs/SCHEMA.md` (terkunci).

## Definition of Done
- [x] `docs/SCHEMA.md` terkunci: tabel `jobs` + `attempts`, tipe, index, state machine, aturan transisi.
- [x] `init_db` membuat DB dengan WAL + busy_timeout; diverifikasi `PRAGMA journal_mode` = `wal`.
- [x] Dedup `UNIQUE(external_ref)` terbukti lewat test (`INSERT OR IGNORE` 2× → 1 baris).
- [x] `UNIQUE(confirmation)` menolak dobel non-null.
- [x] `uv run … -m unittest discover -s src -p "test_schema.py"` semua lulus.
- [x] **Commit + push berhasil** (D13).

## Metrik selesai
`tabel jobs+attempts · WAL aktif · dedup UNIQUE terbukti · N test lulus`

## Jebakan
- Tanpa WAL, banyak worker menulis akan saling-blok parah. WAL + `busy_timeout` wajib (D5).
- `confirmation` boleh NULL saat pending; `UNIQUE` di SQLite mengizinkan banyak NULL — pas.
- Skema ini kontrak. Kalau P5/P6 butuh kolom baru, ubah di SINI + `docs/SCHEMA.md`, jangan diam-diam.

---

## Bukti (sesi 2026-08-28)

Semua DoD dicentang dengan output perintah nyata di bawah.

### `docs/SCHEMA.md` terkunci

`docs/SCHEMA.md` tidak lagi stub: record 6 field, tabel `jobs` + `attempts` + `meta`,
tipe/constraint per kolom, dua index `jobs` + dua index `attempts`, diagram state machine,
tabel transisi sah, 5 aturan transisi, tabel pragma, pemetaan `outcome` ↔ mode chaos
(`docs/CHAOS.md`), dan §7 jebakan. `SCHEMA_VERSION = 1`.

### `init_db` → WAL + busy_timeout, terbaca dari proses lain

```
$ uv run --no-sync python -c "from src.schema import init_db; init_db('data/p4-verify/queue.db').close()"
$ sqlite3 data/p4-verify/queue.db "PRAGMA journal_mode; PRAGMA foreign_keys;"
wal
0
```

`journal_mode=wal` persisten di file. `foreign_keys=0` dari CLI memang benar dan sudah
didokumentasikan: pragma itu per-koneksi, dan `src/schema.py:connect()` menyetelnya di
setiap proses (dibuktikan `test_wal_persisten_untuk_koneksi_proses_lain`).

### Skema nyata di disk

```
$ sqlite3 data/p4-verify/queue.db ".schema"
CREATE TABLE jobs (
        external_ref TEXT    NOT NULL PRIMARY KEY,
        payload      TEXT    NOT NULL,
        status       TEXT    NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'claimed', 'ok', 'failed', 'dead')),
        attempts     INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        worker_id    TEXT,
        claimed_at   REAL,
        confirmation TEXT     UNIQUE,
        last_error   TEXT,
        created_at   REAL    NOT NULL,
        updated_at   REAL    NOT NULL
    );
CREATE INDEX idx_jobs_status ON jobs (status);
CREATE INDEX idx_jobs_status_claimed_at ON jobs (status, claimed_at);
CREATE TABLE attempts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        external_ref TEXT    NOT NULL REFERENCES jobs (external_ref) ON DELETE CASCADE,
        worker_id    TEXT    NOT NULL,
        started_at   REAL    NOT NULL,
        ended_at     REAL,
        outcome      TEXT    NOT NULL
                     CHECK (outcome IN ('ok', 'retryable', 'permanent', 'timeout')),
        error        TEXT,
        confirmation TEXT
    );
CREATE INDEX idx_attempts_external_ref ON attempts (external_ref);
CREATE INDEX idx_attempts_outcome ON attempts (outcome);
CREATE TABLE meta (key TEXT NOT NULL PRIMARY KEY, value TEXT NOT NULL);
```

### Dedup `UNIQUE(external_ref)` — `INSERT OR IGNORE` 2× → 1 baris (D4)

```
$ sqlite3 data/p4-verify/queue.db "
INSERT OR IGNORE INTO jobs (external_ref,payload,created_at,updated_at) VALUES ('REC-000001','{}',1,1);
INSERT OR IGNORE INTO jobs (external_ref,payload,created_at,updated_at) VALUES ('REC-000001','{}',2,2);
SELECT COUNT(*), COUNT(DISTINCT external_ref), COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs;"
1|1|0
```

### `UNIQUE(confirmation)` menolak dobel non-NULL (D6)

```
$ sqlite3 data/p4-verify/queue.db "
UPDATE jobs SET status='ok', confirmation='SL-abcd1234' WHERE external_ref='REC-000001';
INSERT INTO jobs (external_ref,payload,status,confirmation,created_at,updated_at)
  VALUES ('REC-000002','{}','ok','SL-abcd1234',3,3);"
Error in 2nd command line argument: UNIQUE constraint failed: jobs.confirmation
exit=1
```

Banyak `confirmation IS NULL` tetap diizinkan (dua job `pending` masuk setelahnya):

```
ok|1
pending|2
```

### Test

```
$ uv run --no-sync python -m unittest discover -s src -p "test_schema.py" -v
Ran 24 tests in 0.013s
OK

$ uv run --no-sync python -m compileall -q src scripts && uv run --no-sync python -m unittest discover -s src
COMPILE OK
Ran 37 tests in 0.251s
OK
```

### Temuan yang dibayar di muka untuk P5

`INSERT OR IGNORE` menelan **semua** pelanggaran constraint, bukan hanya bentrok
`external_ref`: status di luar `CHECK` dan `attempts` negatif ikut hilang tanpa error.
Loader P5 wajib memvalidasi record sebelum insert dan memakai `rowcount` untuk membedakan
"dilewati karena duplikat" dari "masuk". Dikunci di `docs/SCHEMA.md` §7 + test
`test_or_ignore_menelan_pelanggaran_constraint_bukan_hanya_duplikat`.

### Koreksi file fase ini

File fase semula menyebut `src/test_schema.py` dan `python -m unittest src.test_schema`.
Layout repo sejak P0 menaruh test di `src/tests/` (`discover -s src`), jadi jalur dan
perintah di atas diperbaiki di sesi yang sama (AGENTS §5: file fase kalah dari layout
yang sudah terkunci di fase sebelumnya).

**Metrik selesai:** `tabel jobs+attempts+meta · WAL aktif · dedup UNIQUE terbukti (1|1|0) ·
UNIQUE(confirmation) menolak dobel · 24 test skema lulus · 37/37 suite lulus`
