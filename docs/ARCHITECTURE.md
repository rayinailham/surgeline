# SurgeLine — ARCHITECTURE

Alur data ujung ke ujung, satu halaman. Detail bentuk file/tabel ada di `docs/SCHEMA.md` (P4).

## Gambaran besar

```
  Excel/CSV 50k          Loader              Antrean (SQLite WAL)          Worker ×N
 (scripts/gen_data)  →  (src/load.py)   →   data/<run>/queue.db      →   (src/worker.py)
   sintetis, seed        stream +              tabel jobs:                 Playwright headless
                         INSERT OR IGNORE      pending/claimed/            klaim atomik →
                         (dedup UNIQUE)        ok/failed/dead              isi form target →
                                                    ▲    │                 tangkap nomor konfirmasi
                                                    │    │                       │
                                    lease recovery ─┘    └── dashboard           ▼
                                    (job nyangkut →       (src/dashboard.py) ◄── tulis balik
                                     pending, D8)          FastAPI+HTMX,          (ok+confirmation
                                                           angka hidup            | failed+reason)
                                                                                     │
                                          Target app (Docker lokal, 127.0.0.1:8110) ◄┘
                                          sengaja gagal 5% (500 / lambat / validasi), D3
                                          tiap sukses → nomor konfirmasi unik
```

## Komponen

1. **Generator** (`scripts/gen_data.py`, P3) — 50.000 record sintetis → Excel + CSV, streamed.
2. **Target app** (`target/`, P1–P2) — form + halaman hasil bernomor konfirmasi; chaos 5% deterministik.
3. **Loader** (`src/load.py`, P5) — baca file bertahap, masukkan ke `jobs`, duplikat ditolak DB.
4. **Antrean** (SQLite WAL, P4) — sumber kebenaran state. State machine: `pending→claimed→ok|failed|dead`.
5. **Worker** (`src/worker.py`, P6–P8) — klaim batch atomik, isi form via Playwright, tulis balik
   nomor konfirmasi / alasan gagal; retry + backoff; hormati dead-letter.
6. **Lease recovery** (P8) — job `claimed` melewati `lease_timeout` → dikembalikan ke `pending`.
7. **Dashboard** (`src/dashboard.py`, P10) — read-only, angka hidup cocok DB, throughput.
8. **Throughput & laporan** (P12–P13) — record/jam per N worker → ekstrapolasi 6 juta record.

## Kenapa crash-safe secara struktural (bukan kebetulan)

- **State di DB, bukan di memori proses.** Worker mati → job yang belum commit tetap `pending`
  atau `claimed`; tidak ada state yang hilang bersama proses.
- **Dedup di `UNIQUE`.** Load ulang / resume tidak bisa memasukkan record yang sama dua kali.
- **Klaim atomik `BEGIN IMMEDIATE`.** Dua worker tidak pernah mengerjakan job yang sama.
- **Lease timeout.** Job yang "dibawa mati" worker dikembalikan ke antrean, tidak hilang selamanya.
- **Nomor konfirmasi = bukti idempotensi.** Satu `external_ref` → paling banyak satu nomor konfirmasi.

## Jalur upgrade (dicatat, bukan diimplementasikan — D15)
SQLite → PostgreSQL cukup mengganti lapisan `store` (klaim jadi `SELECT … FOR UPDATE SKIP LOCKED`).
Antarmuka `store` sengaja sempit supaya penggantian ini satu file. Tidak dikerjakan di portofolio ini.
