# SurgeLine — SCHEMA (terkunci di P4)

> **Kontrak.** Bentuk record dan tabel antrean tidak berubah setelah P4. Loader (P5),
> worker (P6–P8), lease recovery (P8), dan dashboard (P10) semuanya mengacu ke sini.
> Implementasi runtime-nya adalah `src/schema.py`; dokumen ini dan modul itu wajib cocok
> (dijaga oleh `src/tests/test_schema.py`). Butuh kolom baru di fase lanjut? Ubah di
> **kedua** tempat sekaligus, jangan diam-diam.
>
> Hierarki: `docs/DECISIONS.md` menang atas file ini; file ini menang atas `phases/`.

`SCHEMA_VERSION = 1`

---

## 1. Record

Bentuk satu record, identik dengan `docs/DATA_DICTIONARY.md` dan 6 field form target
(`docs/TARGET.md`). Urutan ini juga urutan kolom CSV/XLSX generator P3.

| Field | Tipe | Wajib | Aturan |
|---|---|---|---|
| `external_ref` | TEXT | ya | **Natural key** (D4). Pola `[A-Za-z0-9._-]{1,64}` |
| `full_name` | TEXT | ya | tidak kosong, ≤ 120 karakter |
| `email` | TEXT | ya | alamat email valid |
| `policy_no` | TEXT | ya | tidak kosong, ≤ 40 karakter |
| `amount` | REAL | ya | > 0 |
| `notes` | TEXT | tidak | ≤ 500 karakter |

Di antrean, keenam field disimpan sebagai satu blob JSON di kolom `jobs.payload`;
hanya `external_ref` yang dinaikkan jadi kolom tersendiri, karena hanya ia yang
dipakai untuk dedup dan penguncian.

## 2. Lokasi file

```
data/<run_id>/queue.db        antrean SQLite (WAL), sumber kebenaran state
data/<run_id>/queue.db-wal    write-ahead log (otomatis)
data/<run_id>/queue.db-shm    shared memory index (otomatis)
data/<run_id>/run.json        metrik run (ditulis P11): run_id, waktu, N worker, hitungan akhir
```

`data/` dan `reports/` gitignored (AGENTS §4). Data mentah tidak pernah ditimpa: satu run
= satu direktori. `run_id` baru juga jalan keluar bila `SCHEMA_VERSION` berubah — tidak ada
migrasi in-place di project ini.

## 3. Tabel `jobs`

Satu baris = satu record yang harus disubmit. Ini satu-satunya sumber kebenaran state:
tidak ada progres yang hidup di memori proses worker (itu dasar klaim crash-safe P9).

| Kolom | Tipe | Constraint | Guna |
|---|---|---|---|
| `external_ref` | TEXT | `NOT NULL PRIMARY KEY` | natural key, dedup (D4) |
| `payload` | TEXT | `NOT NULL` | JSON keenam field record |
| `status` | TEXT | `NOT NULL DEFAULT 'pending'`, `CHECK IN (pending, claimed, ok, failed, dead)` | state machine §5 |
| `attempts` | INTEGER | `NOT NULL DEFAULT 0`, `CHECK >= 0` | jumlah percobaan, batas `max_attempts` (D7) |
| `worker_id` | TEXT | nullable | pemilik saat `claimed` (D8) |
| `claimed_at` | REAL | nullable | epoch klaim, dasar lease timeout (D8) |
| `confirmation` | TEXT | `UNIQUE`, nullable | nomor konfirmasi target (D6) |
| `last_error` | TEXT | nullable | alasan terakhir gagal / dead |
| `created_at` | REAL | `NOT NULL` | epoch saat loader memasukkan |
| `updated_at` | REAL | `NOT NULL` | epoch perubahan terakhir |

**`NOT NULL` pada primary key itu disengaja.** SQLite tetap mengizinkan `NULL` di kolom
`TEXT PRIMARY KEY` (warisan kompatibilitas); tanpa `NOT NULL` eksplisit, banyak baris
ber-`external_ref` kosong bisa lolos dan dedup D4 bocor.

**`UNIQUE` pada `confirmation` memakai semantik NULL SQLite.** Banyak baris boleh
`confirmation IS NULL` (semua job yang belum sukses), tapi dua job tidak akan pernah
menyimpan nomor konfirmasi yang sama. Ini yang membuat "satu record → paling banyak satu
submission" terbukti secara struktural, bukan lewat pengecekan di kode (D6).

Index:

| Index | Kolom | Query yang dilayani |
|---|---|---|
| `idx_jobs_status` | `(status)` | hitungan dashboard, ambil batch `pending` |
| `idx_jobs_status_claimed_at` | `(status, claimed_at)` | sapuan lease: `claimed` lewat timeout (D8) |
| `idx_jobs_status_updated_at` | `(status, updated_at)` | klaim job `pending` terlama dulu (P6); kelayakan backoff D7 (P8) |

**Klaim mengambil `pending` dengan `updated_at` terkecil, bukan `rowid` terkecil.**
Loader menulis `created_at = updated_at`, jadi urutan awalnya tetap FIFO; bedanya muncul
saat job dilepas kembali ke `pending`, yang menyegarkan `updated_at` dan memindahkannya ke
belakang antrean. Tanpa itu, satu job yang selalu gagal langsung diklaim ulang oleh worker
yang sama dan memonopoli run — terukur di P6: 24 percobaan berturut-turut jatuh ke satu
`external_ref` dan 23 job lain tidak tersentuh. Ini prasyarat backoff D7 di P8, yang
menghitung kelayakan retry dari `updated_at` + `attempts` (bukan kolom baru).

**Kelayakan retry (dikunci P8, D7).** Job `pending` baru boleh diklaim setelah

```text
READY_AT = updated_at + backoff(attempts) * (1 + (rowid % 100)/100 * 0.25)
backoff(a) = min(1.0 * 2^(a-1), 30.0)   # a = attempts terpakai; backoff(0) = 0
```

Angka terkunci: `MAX_ATTEMPTS = 5`, base 1 dtk, faktor 2, atap 30 dtk, jitter 0–25%.
Tangga penundaannya: 1 · 2 · 4 · 8 · 16 detik. Ekspresi SQL-nya dibangkitkan
`src/store.py:_ready_at_sql()` dari `schema.backoff_delay()` yang sama, supaya angka
Python dan angka SQL tidak bisa berbeda diam-diam. Jitter memakai `rowid % 100`:
deterministik per job (run tetap bisa diulang, D3) tapi job yang dilepas pada detik yang
sama tidak jadi layak serentak. `claim_one` **melewati** job yang belum layak, bukan
mengembalikan None — satu job yang sedang menunggu tidak boleh membekukan antrean;
`store.time_until_ready()` yang membedakan "antrean habis" dari "semua sedang menunggu".

## 4. Tabel `attempts` (audit)

Satu baris = satu percobaan submit. Tidak pernah di-`UPDATE` untuk percobaan lama:
riwayat retry adalah bukti portofolio ("100% kegagalan target ter-retry/tercatat").

| Kolom | Tipe | Constraint |
|---|---|---|
| `id` | INTEGER | `PRIMARY KEY AUTOINCREMENT` |
| `external_ref` | TEXT | `NOT NULL REFERENCES jobs(external_ref) ON DELETE CASCADE` |
| `worker_id` | TEXT | `NOT NULL` |
| `started_at` | REAL | `NOT NULL` |
| `ended_at` | REAL | nullable (masih berjalan / worker mati di tengah) |
| `outcome` | TEXT | `NOT NULL`, `CHECK IN (ok, retryable, permanent, timeout)` |
| `error` | TEXT | nullable |
| `confirmation` | TEXT | nullable — sengaja **tidak** `UNIQUE` (§4a) |

Index: `idx_attempts_external_ref (external_ref)`, `idx_attempts_outcome (outcome)`.

**§4a — kenapa `attempts.confirmation` tidak `UNIQUE`:** target idempoten per
`external_ref` (P1), jadi percobaan ulang atas record yang sebenarnya sudah sukses
(mis. mode chaos `slow` yang bikin worker timeout padahal server menerima) akan
mengembalikan nomor konfirmasi yang **sama**. Itu bukti bagus, bukan pelanggaran —
`UNIQUE` di tabel audit justru akan menolak merekamnya. Keunikan dijaga di `jobs`.

Pemetaan `outcome` ke mode chaos (`docs/CHAOS.md`), dipakai worker P8:

| Kejadian | `outcome` | Aksi |
|---|---|---|
| submit sukses + nomor konfirmasi terbaca | `ok` | `claimed → ok` |
| HTTP 500 (`server_error`), 429/503, kegagalan jaringan | `retryable` | `claimed → pending`, backoff (D7) |
| timeout menunggu respons (`slow`) | `timeout` | `claimed → pending`, backoff (D7) |
| HTTP 422 penolakan validasi (`validation`) | `permanent` | `claimed → failed`, **tanpa** retry |
| sukses tapi nomor konfirmasi tidak terbaca | `permanent` | dihitung gagal (D6) |
| percobaan ditinggal mati worker, lease kedaluwarsa | `timeout` | `claimed → pending`, ditulis sapuan lease (D8) |

Percobaan yang worker-nya mati tidak pernah menulis baris auditnya sendiri;
`store.recover_stuck` yang menutupnya (memakai `claimed_at` sebagai `started_at` dan
`worker_id` milik worker yang mati), supaya klaim "100% kegagalan tercatat" tetap benar.

## 5. State machine

```
                    ┌──────────────────────────────┐
                    │      retry / lease habis      │
                    ▼                               │
   loader ──▶ pending ──────────────▶ claimed ──────┘
              │  INSERT OR IGNORE    │  BEGIN IMMEDIATE
              │  (D4)                │  (satu pemilik saja)
              │                      ├────────────▶ ok       konfirmasi tersimpan (D6)
              │                      ├────────────▶ failed   penolakan permanen
              │                      └────────────▶ dead     attempts habis (D7)
              └───────────────────────────────────▶ dead     attempts habis (D7)
```

Transisi sah:

| Dari | Ke | Kapan |
|---|---|---|
| `pending` | `claimed` | worker mengklaim, `BEGIN IMMEDIATE`, set `worker_id` + `claimed_at` |
| `pending` | `dead` | `attempts >= max_attempts` saat disapu (D7) |
| `claimed` | `ok` | submit sukses **dan** `confirmation` non-NULL tersimpan (D6) |
| `claimed` | `failed` | penolakan permanen (validasi 422, atau sukses tanpa konfirmasi) |
| `claimed` | `pending` | retry setelah kegagalan sementara, **atau** lease kedaluwarsa (D8) |
| `claimed` | `dead` | jatah percobaan habis (D7): `attempts >= MAX_ATTEMPTS` saat dilepas, termasuk saat job yatim disapu lease |

`ok`, `failed`, `dead` **terminal** — tidak ada jalan keluar. Requeue manual bukan scope
(D15); ulangi dengan `run_id` baru.

Aturan wajib:

1. Setiap transisi terjadi dalam **satu** transaksi atomik yang juga menaikkan `attempts`,
   menulis `updated_at`, dan menyisipkan baris `attempts` bila relevan.
2. Klaim memakai `BEGIN IMMEDIATE` sehingga dua worker tidak pernah mengklaim job yang
   sama (dibuktikan dengan angka di P7).
3. `claimed → claimed` **ilegal** — itulah bentuk double-claim, jadi state machine
   menolaknya, bukan sekadar tidak diharapkan.
4. Meninggalkan `claimed`: bersihkan `worker_id` dan `claimed_at` supaya sapuan lease
   tidak salah menghitung job yang sudah selesai.
5. `assert_transition()` di `src/schema.py` dipanggil lapisan store sebelum menulis;
   transisi ilegal menaikkan `SchemaError`, bukan diam-diam menulis baris salah.
6. Keputusan dead-letter diambil **di dalam** transaksi pelepasan, dari `attempts` yang
   baru dibaca — bukan dari angka yang dibawa pemanggil, yang sudah basi begitu worker
   lain menyentuh job yang sama (`store._finish(exhausted_status=...)`, P8).
7. Sapuan lease **tidak** menaikkan `attempts`: jatahnya sudah dipakai `claim_one`.
   Job yatim yang jatahnya habis masuk `dead`, bukan `pending` — baris `pending` yang
   tidak akan pernah layak diklaim membuat run tidak pernah bisa dinyatakan selesai (D8).

## 6. Pragma koneksi (D5)

Diterapkan `src/schema.py:connect()` untuk **setiap** koneksi, termasuk milik worker dan
dashboard yang membuka DB yang sudah ada. Dashboard P10 memakai `read_only=True` (URI
`mode=ro`) dan melewati penetapan `journal_mode` karena itu operasi tulis; mode WAL yang
sudah persisten tetap terbaca:

| Pragma | Nilai | Alasan |
|---|---|---|
| `journal_mode` | `WAL` | banyak pembaca + satu penulis tanpa saling-blok. Persisten di file |
| `busy_timeout` | `5000` | tunggu kunci penulis; per-koneksi, wajib diset ulang tiap proses |
| `synchronous` | `NORMAL` | di WAL tetap tahan `kill -9` proses (yang diuji P9); hanya kegagalan daya/OS yang bisa memakan transaksi terakhir. Jauh lebih cepat untuk 50k job |
| `foreign_keys` | `ON` | `attempts` tidak boleh menunjuk job hantu; per-koneksi |

## 7. Jebakan yang sudah dibayar di muka

- **`INSERT OR IGNORE` menelan SEMUA pelanggaran constraint**, bukan hanya bentrok
  `external_ref` — `CHECK` status, `CHECK attempts`, dan `UNIQUE(confirmation)` ikut
  didiamkan. Loader P5 wajib memvalidasi record sebelum insert dan memakai `rowcount`
  untuk membedakan "dilewati karena duplikat" dari "masuk". Tanpa itu, record cacat
  hilang tanpa jejak dan hitungan dedup jadi bohong.
  (`test_or_ignore_menelan_pelanggaran_constraint_bukan_hanya_duplikat`)
- **Muat ulang di tengah run tidak boleh mengembalikan job selesai ke `pending`.**
  `INSERT OR IGNORE` memang melewati baris yang sudah ada; jangan pernah menggantinya
  dengan `INSERT OR REPLACE`, yang akan menghapus `status`, `confirmation`, dan `attempts`.
  (`test_insert_or_ignore_tidak_menimpa_progres_job`)
- **`journal_mode` persisten, `busy_timeout` tidak.** Buka DB tanpa `connect()` → tetap
  WAL, tapi tanpa `busy_timeout` → `database is locked` di bawah N worker.
- **Retry tanpa penundaan = badai retry.** Sebelum P8, job yang dilepas langsung layak
  diklaim lagi; yang menahannya cuma urutan `updated_at`. Dengan antrean kecil, satu job
  beracun tetap diputar secepat loop worker. `READY_AT` yang menutup lubang itu.
  (`test_job_yang_baru_dilepas_belum_layak_diklaim`)
- **Worker tidak boleh pulang saat antrean cuma sedang menunggu.** `claim_one` yang
  mengembalikan None berarti "tidak ada yang layak sekarang", bukan "antrean habis".
  Menyamakan keduanya membuat job yang tinggal menunggu satu detik terlantar sampai run
  berikutnya. (`test_time_until_ready_membedakan_antrean_habis_dari_antrean_menunggu`)
- **`init_db` idempoten** dan dipanggil ulang saat resume; ia tidak pernah menghapus data,
  dan menolak DB dengan `SCHEMA_VERSION` berbeda.

## 8. Verifikasi

```bash
uv run --no-sync python -m unittest discover -s src -p "test_schema.py" -v
uv run --no-sync python -m unittest src.test_resilience -v      # backoff, dead-letter, lease (P8)
```
