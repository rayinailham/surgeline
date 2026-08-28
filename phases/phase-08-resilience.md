# P8 — Ketahanan: Retry, Dead-letter & Lease Recovery

**Tujuan sesi:** membuat sistem menyelesaikan 100% walau target gagal 5% — retry bertingkat
untuk yang retryable, dead-letter untuk yang habis percobaan, dan pemulihan job "nyangkut"
(worker mati saat `claimed`) via lease timeout. Ini menyumbang A4 & A10.

**Prasyarat:** P7 selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D3, D7, D8), `docs/SCHEMA.md`,
`docs/CHAOS.md`, `src/store.py`, `src/worker.py`.
**Budget:** sedang.

---

## Langkah

### 1. Retry bertingkat + backoff (D7)
`store`/`worker`: job `retryable` dikembalikan ke `pending` dengan backoff eksponensial +
jitter, dan `claim_one` hanya mengambil job `pending` yang backoff-nya sudah lewat.
`attempts >= max_attempts` → `dead` dengan `last_error`. Kegagalan **permanen** (422 validasi)
langsung `failed`, TIDAK di-retry (kontrak `docs/CHAOS.md`).

> **Koreksi P8 (versi awal file ini keliru).** Jangan menambah kolom `not_before`:
> `docs/SCHEMA.md` §3 mengunci kelayakan retry dihitung dari `updated_at` + `attempts`
> yang sudah ada, tanpa kolom baru, supaya `SCHEMA_VERSION` tetap 1. SCHEMA menang atas
> file fase (AGENTS §5). Ekspresinya `store.READY_AT`.
> `attempts` juga tidak dinaikkan saat pelepasan — `claim_one` sudah memakainya saat klaim.

### 2. Lease recovery job nyangkut (D8)
Fungsi `recover_stuck(lease_timeout)`: job `claimed` dengan `now - claimed_at > lease_timeout`
→ kembalikan ke `pending`. Dipanggil worker saat startup + berkala, dan berdiri sendiri
lewat `python -m src.recover`.

> **Koreksi P8:** sapuan **tidak** menaikkan `attempts` (sudah dipakai `claim_one`; menaikkan
> lagi menghukum satu percobaan dua kali). Job yatim yang jatahnya sudah habis masuk `dead`,
> bukan `pending` — kalau tidak, ia jadi baris `pending` yang tidak akan pernah layak diklaim
> dan run tidak pernah bisa dinyatakan selesai.

### 3. Bukti (A4 & A10)
```bash
# A4: run subset chaos ON sampai selesai — semua retryable akhirnya ok, permanent tercatat:
sqlite3 db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
sqlite3 db "SELECT COUNT(*) FROM jobs WHERE status='dead' AND last_error IS NULL;"   # 0
# A10: bunuh worker saat sebuah job 'claimed' → job kembali pending → akhirnya ok:
#   claim job manual/one worker, kill -9 sebelum mark_ok, jalankan recover_stuck, lanjut.
```
Tunjukkan satu `external_ref` menempuh `claimed → (worker mati) → pending → ok`, tanpa duplikat.

### 4. Unit test (`src/test_resilience.py`)
backoff naik per attempt; backoff menahan job dari klaim; max_attempts→dead; permanent tak di-retry;
`recover_stuck` mengembalikan job yang melewati lease saja (yang masih fresh tidak disentuh).

```bash
uv run --no-sync python -m unittest src.test_resilience -v
```

---

## Output fase
- `src/worker.py` & `src/store.py` (diperkaya), `src/recover.py` (atau di store), `src/test_resilience.py`.
- Kunci angka D7/D8 (max_attempts, base/factor, lease_timeout) di `docs/SCHEMA.md`/`DECISIONS.md`.

## Definition of Done
- [x] Retryable → retry backoff sampai ok atau `dead`; tiap `dead` punya `last_error` (A4).
- [x] Permanent (422) → `failed` tanpa retry, alasan tercatat.
- [x] `recover_stuck` mengembalikan job yang melewati lease; job fresh tidak disentuh.
- [x] Bukti satu job `claimed→pending(recovered)→ok` tanpa duplikat (A10).
- [x] Angka D7/D8 dikunci di dokumen.
- [x] `uv run … -m unittest src.test_resilience` lulus.
- [x] **Commit + push berhasil** (D13).

## Bukti

### A4a — subset chaos 100 record (10 `server_error` · 10 `slow` · 10 `validation` · 70 normal)

```
$ uv run --no-sync python -m src.load --input subset100.csv --run p08-chaos
dibaca=100 dimasukkan=100 duplikat_ditolak=0

$ uv run --no-sync python -m src.run --run p08-chaos --workers 4 --timeout-ms 15000
worker=w-3 ok=20 retryable=6  timeout=0 permanent=2 dead=2
worker=w-4 ok=19 retryable=16 timeout=0 permanent=3 dead=2
worker=w-1 ok=20 retryable=16 timeout=0 permanent=4 dead=3
worker=w-2 ok=21 retryable=12 timeout=0 permanent=1 dead=3
workers=4 processed=140 elapsed=26.599s throughput=5.26 job/s return_codes=[0, 0, 0, 0]

$ sqlite3 data/p08-chaos/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
dead|10
failed|10
ok|80
                                       # 0 pending, 0 claimed -> run benar-benar selesai
$ sqlite3 … "SELECT COUNT(*) FROM jobs WHERE status='dead' AND (last_error IS NULL OR last_error='');"
0
$ sqlite3 … "SELECT COUNT(*) FROM jobs WHERE status='failed' AND (last_error IS NULL OR last_error='');"
0
$ sqlite3 … "SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='');"
0
$ sqlite3 … dup_ref '|' dup_konfirmasi
0|0
$ sqlite3 … "SELECT outcome,COUNT(*) FROM attempts GROUP BY outcome;"
ok|80
permanent|10
retryable|50                           # 10 job x 5 percobaan: tiap kegagalan tercatat
$ sqlite3 … "SELECT status,MIN(attempts),MAX(attempts),COUNT(*) FROM jobs GROUP BY status;"
dead|5|5|10                            # habis jatah, persis 10 job mode `server_error`
failed|1|1|10                          # 422 tidak pernah di-retry: berhenti di percobaan 1
ok|1|1|80                              # termasuk 10 job `slow` (timeout worker 15 dtk > 2 dtk)
$ sqlite3 … "SELECT external_ref,attempts,substr(last_error,1,70) FROM jobs WHERE status='dead' LIMIT 3;"
REC-000215|5|habis 5 percobaan: HTTP 500 dari target
REC-000276|5|habis 5 percobaan: HTTP 500 dari target
REC-000353|5|habis 5 percobaan: HTTP 500 dari target
$ sqlite3 … "SELECT external_ref,attempts,substr(last_error,1,70) FROM jobs WHERE status='failed' LIMIT 3;"
REC-000112|1|HTTP 422: record ditolak oleh chaos target
REC-000115|1|HTTP 422: record ditolak oleh chaos target
REC-000149|1|HTTP 422: record ditolak oleh chaos target
```

Mode `server_error` deterministik (D3): job itu **tidak akan pernah** sukses, berapa kali pun
dicoba. "Semua retryable akhirnya ok" karena itu mustahil untuk subset ini; yang dituntut A4
adalah cabang keduanya — tercatat rapi alasannya: 5 percobaan, `dead`, `last_error` terisi.
Cabang "retry akhirnya berhasil" dibuktikan terpisah di A4b dengan gangguan yang memang
sementara.

### A4b — gangguan sementara: target mati di tengah run, lalu hidup lagi

```
$ docker compose stop target && curl … http://127.0.0.1:8110/health
health saat mati: 000                  (curl: Failed to connect ... Could not connect to server)

$ uv run --no-sync python -m src.worker --run p08-transient --worker-id w-outage --max-jobs 20
worker=w-outage ok=0 retryable=20 timeout=0 permanent=0 dead=0
$ sqlite3 data/p08-transient/queue.db "SELECT status,COUNT(*),MIN(attempts),MAX(attempts) FROM jobs GROUP BY status;"
pending|20|1|1                         # dikembalikan ke antrean, bukan dibuang
REC-040001|kegagalan browser: Page.goto: net::ERR_CONNECTION_REFUSED at

$ docker compose start target
$ uv run --no-sync python -m src.run --run p08-transient --workers 2 --timeout-ms 15000
workers=2 processed=40 elapsed=3.616s throughput=11.06 job/s return_codes=[0, 0]
$ sqlite3 … "SELECT status,COUNT(*),MIN(attempts),MAX(attempts) FROM jobs GROUP BY status;"
ok|20|3|3                              # 20/20 berhasil setelah 2 kegagalan sementara
$ sqlite3 … ok_tanpa_konfirmasi '|' dup_konfirmasi
0|0
$ sqlite3 … "SELECT worker_id,outcome,… FROM attempts WHERE external_ref='REC-040001' ORDER BY id;"
w-outage|retryable|kegagalan browser: Page.goto: net::ERR_C
w-1|retryable|kegagalan browser: Page.goto: net::ERR_S
w-2|ok|SL-e5a4f0d4                     # retryable -> retryable -> ok, satu konfirmasi saja
```

### A10 — worker dibunuh `kill -9` saat job `claimed`

Job pertama antrean sengaja dipilih ber-mode chaos `slow` (target tidur 2 dtk), supaya
worker benar-benar tertangkap dalam keadaan `claimed` — bukan lomba waktu yang untung-untungan.

```
[1] worker dijalankan, pid=201220
[2] job REC-045020 claimed oleh w-korban (attempts=1)
[3] kill -9 pid=201220 -> exitcode=-9 (-9 = SIGKILL)
[4] setelah worker mati: {'status': 'claimed', 'worker_id': 'w-korban', 'attempts': 1}
    <- yatim, tidak ada proses yang akan melepasnya

[5] $ uv run --no-sync python -m src.recover --run p08-lease --lease-timeout 120
    lease=120s recovered_pending=0 recovered_dead=0 claimed=1 dead=0 failed=0 ok=0 pending=2
    ^ klaim masih segar -> TIDAK direbut (pagar terhadap submit ganda)
[6] setelah menunggu 6 dtk:
    $ uv run --no-sync python -m src.recover --run p08-lease --lease-timeout 5
    lease=5s recovered_pending=1 recovered_dead=0 claimed=0 dead=0 failed=0 ok=0 pending=3
    REC-045020|pending||1|lease 5 dtk kedaluwarsa; worker 'w-korban' tidak menyelesaik…
[7] $ uv run --no-sync python -m src.worker --run p08-lease --worker-id w-pengganti
    worker=w-pengganti ok=3 retryable=0 timeout=0 permanent=0 dead=0
[8] sqlite3 … "SELECT status,COUNT(*) FROM jobs GROUP BY status;"   -> ok|3
[9] REC-045020|ok|2|SL-332fa84a                    # claimed -> pending -> ok, attempts 2
[10] jejak audit REC-045020:
     w-korban   |timeout|lease 5 dtk kedaluwarsa; worker 'w-korban' tidak men…
     w-pengganti|ok     |SL-332fa84a
[11] duplikat ref|konfirmasi: 0|0
```

### Unit test

```
$ uv run --no-sync python -m unittest src.test_resilience
Ran 16 tests in 0.014s
OK
$ uv run --no-sync python -m unittest discover -s src
Ran 91 tests in 0.339s
OK
```

## Metrik selesai
`chaos 100 job: ok 80 · failed 10 (422, 1 percobaan, tanpa retry) · dead 10 (5 percobaan,
semua ber-last_error) · 50 baris audit retryable · 0 pending/claimed tersisa ·
gangguan sementara: 20/20 ok di percobaan ke-3 · lease: kill -9 → claimed→pending→ok,
klaim segar tidak direbut · duplikat ref/konfirmasi 0|0 · 91 test lulus (16 baru)`

## Jebakan
- Retry tanpa penundaan = badai retry ketat yang membombardir target. Backoff wajib
  (di sini lewat `store.READY_AT`, bukan kolom `not_before` — lihat koreksi di Langkah 1).
- Jangan retry kegagalan permanen (422) — itu bukan gangguan sementara, cuma memutar tak berujung.
- `recover_stuck` yang terlalu agresif (lease terlalu pendek) merebut job yang masih diproses →
  bisa dobel submit. Lease harus > durasi submission normal + margin (D8).
- **Perubahan di P8 mengubah perilaku run.** Setelah ini, jalankan ulang bukti P9 dari versi baru.
