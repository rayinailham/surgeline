# P11 — Run Penuh 50.000

**Tujuan sesi:** membaca seluruh 50.000 baris input dan menjalankan 49.950 job unik lewat chaos 5% dengan ≥2 kill di tengah,
sampai status akhir bersih & 0 duplikat. Ini menutup A1, A2, A4 dengan angka pada skala penuh.

**Prasyarat:** P8 tuntas + P10 (dashboard untuk direkam). Semua P5–P9 hijau.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D3, D7, D8), `docs/SCHEMA.md`,
`docs/RESUME_PROOF.md`.
**Budget:** sedang (jam dinding untuk run).

---

## Langkah
```bash
cd surgeline && docker compose up -d && cd ..    # chaos ON (SURGELINE_CHAOS_RATE=0.05)
RUN=full50k
uv run --no-sync python src/load.py --input data/input/records.xlsx --run $RUN
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs;"     # 49950 (50 duplikat input ditolak D4)
uv run --no-sync uvicorn src.dashboard:app --port 8120 &    # amati angka naik
uv run --no-sync python src/run.py --run $RUN --workers 4 &
PID=$!; sleep 60; kill -9 $PID                              # KILL #1
uv run --no-sync python src/run.py --run $RUN --workers 4 &
PID=$!; sleep 60; kill -9 $PID                              # KILL #2
uv run --no-sync python src/run.py --run $RUN --workers 4   # sampai TUNTAS

# verifikasi penutup:
sqlite3 data/$RUN/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status IN('ok','failed','dead');"  # 49950
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status IN('pending','claimed');"   # 0
sqlite3 data/$RUN/queue.db "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs;"            # 0
sqlite3 data/$RUN/queue.db "SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok';"  # 0
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='');" # 0
sqlite3 data/$RUN/queue.db "SELECT COUNT(*) FROM jobs WHERE status='dead' AND last_error IS NULL;"      # 0
```
Catat waktu mulai→selesai (untuk throughput P12). Simpan `run.json` metrik akhir.

---

## Output fase
- `data/full50k/` (gitignored) + `run.json` metrik, ringkasan angka final ditempel ke `STATE.md`.

## Definition of Done
- [x] 50.000 baris dibaca, 50 duplikat ditolak DB, dan 49.950 job unik berakhir di `ok|failed|dead`; `pending`+`claimed` = 0 (A1/D4).
- [x] Duplikat external_ref = 0; duplikat confirmation = 0 (A2).
- [x] Tiap `ok` berkonfirmasi; tiap `dead` ber-`last_error` (A4/A5).
- [x] ≥2 kill terjadi selama run penuh, tetap tuntas 100% (A3 pada skala penuh).
- [x] Durasi total dicatat (bahan P12).
- [x] **Commit + push berhasil** (D13).

## Metrik selesai
`50.000 dibaca · 50 duplikat ditolak · 49.950 job unik tuntas · ok=48.273 failed=844 dead=833 · dup ref/konfirmasi 0/0 · konfirmasi 100% · 2 kill · 7 yatim pulih · durasi 2.837,8 dtk (17,01 ok/dtk)`

## Jebakan
- Kalau `dead` banyak, cek: apakah kegagalan permanen (422) atau retryable yang kehabisan attempts
  karena `max_attempts` terlalu kecil / lease salah. Dead karena permanen itu sah; dead karena
  retry gagal terus perlu diselidiki sebelum klaim "100%".
- Jangan naikkan worker ekstrem demi cepat — catat N yang stabil, itu yang dilaporkan P12.
- Kalau kamu mengubah kode worker/store di sini, itu remediasi — commit terpisah, lalu ulang run.

---

## Bukti (sesi 2026-08-29)

Run bersih `full50k`: target di-`docker compose down && up` lebih dulu supaya 49.950
submission benar-benar baru (state target kosong, `no such table: submissions`). Sisa run
sesi terputus **diarsipkan**, tidak ditimpa: `data/full50k-aborted-20260829T0013/`.

### Muat 50.000 baris → 49.950 job unik (D4)

```text
$ uv run --no-sync python src/load.py --input data/input/records.xlsx --run full50k
dibaca=50000 dimasukkan=49950 duplikat_ditolak=50

$ sqlite3 data/full50k/queue.db "SELECT COUNT(*) FROM jobs;"
49950
$ sqlite3 data/full50k/queue.db "PRAGMA journal_mode;"
wal
```

### Dua kill paksa di tengah run penuh (A3)

`kill -9` hanya ke process group runner sendiri (`setsid` + `kill -9 -- -PGID`); tidak ada
container/unit lain yang disentuh. Log runner yang di-kill kosong 0 byte — memang itu
bentuk mati mendadak sebelum sempat mencetak ringkasan.

```text
P11 mulai @ 2026-08-29T06:51:22+07:00
>>> KILL -9 pgid=11180 (kill1) @ 2026-08-29T07:01:22+07:00 ok_saat_kill=10621
=== setelah kill1 ===   claimed|4  failed|164  ok|10621  pending|39161
>>> KILL -9 pgid=22438 (kill2) @ 2026-08-29T07:11:22+07:00 ok_saat_kill=21508
=== setelah kill2 ===   claimed|7  failed|351  ok|21508  pending|28084
>>> final selesai normal rc=0 @ 2026-08-29T07:38:40+07:00
=== setelah final ===   dead|833  failed|844  ok|48273   claimed(yatim)|0

$ tail -1 data/full50k/final.log
workers=4 processed=31097 elapsed=1637.482s throughput=18.99 job/s return_codes=[0, 0, 0, 0]
```

`0 → 10.621 → 21.508 → 48.273`: tiap resume maju dari state SQLite yang sama, bukan mengulang.
Tujuh klaim yatim (4 dari kill1, 3 dari kill2) ditarik sapuan lease 120 dtk (D8) dan
**semuanya berakhir `ok`**. Snapshot `claimed|7` setelah kill2 = 4 yatim lama + 3 yatim baru:

```text
$ sqlite3 ... "SELECT external_ref,worker_id,datetime(started_at,'unixepoch','localtime') diklaim,
               datetime(ended_at,'unixepoch','localtime') disapu, round(ended_at-started_at,1) umur
               FROM attempts WHERE outcome='timeout' ORDER BY id;"
REC-010951|w-4|07:01:22|07:11:23| 600.4      <- 4 yatim kill1, disapu saat pass final start
REC-010952|w-1|07:01:22|07:11:23| 600.4
REC-010953|w-3|07:01:22|07:11:23| 600.3
REC-010954|w-2|07:01:22|07:11:23| 600.3
REC-022177|w-4|07:11:21|07:38:36|1635.2      <- 3 yatim kill2, disapu saat antrean habis
REC-022199|w-3|07:11:22|07:38:36|1633.7
REC-022200|w-1|07:11:22|07:38:36|1633.6

$ sqlite3 ... "SELECT j.status,COUNT(*) FROM jobs j JOIN attempts a USING(external_ref)
               WHERE a.outcome='timeout' GROUP BY j.status;"
ok|7
```

Catatan jujur: 3 yatim kill2 baru disapu 27 menit kemudian, bukan setelah setengah lease
(60 dtk) seperti bunyi D8. Sebabnya `src/worker.py:265` hanya menyapu saat `claim_one`
mengembalikan `None`; selama masih ada 28k `pending`, sapuan berkala tidak pernah jatuh
tempo. Dampaknya **latensi, bukan kehilangan**: run tidak bisa dinyatakan habis sebelum
sapuan itu jalan, jadi 7/7 tetap pulih dan status akhir tetap bersih. Diangkat sebagai
temuan terbuka di `STATE.md` (remediasi kecil, commit terpisah — bukan scope P11).

### Status akhir bersih & 0 duplikat (A1, A2, A4, A5)

```text
$ sqlite3 data/full50k/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
dead|833
failed|844
ok|48273
$ ... "SELECT COUNT(*) FROM jobs WHERE status IN('ok','failed','dead');"          -> 49950
$ ... "SELECT COUNT(*) FROM jobs WHERE status IN('pending','claimed');"           -> 0
$ ... "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs;"                   -> 0
$ ... "SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok';" -> 0
$ ... "SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='');" -> 0
$ ... "SELECT COUNT(*) FROM jobs WHERE status='dead' AND last_error IS NULL;"     -> 0
$ ... "SELECT COUNT(*) FROM jobs WHERE status='failed' AND last_error IS NULL;"   -> 0
```

### `dead=833` itu sah, bukan retry yang bocor (jebakan fase)

Chaos deterministik: `dead` **persis** himpunan record yang di-`server_error` (500 selamanya,
5 percobaan habis, D7), `failed` **persis** himpunan `validation` (422 → permanen, tanpa retry).

```text
prediksi chaos: server_error=833 slow=842 validation=844 jujur=47431 (chaos 2519 / 5,04%)
aktual        : ok=48273 failed=844 dead=833
dead   == prediksi server_error : True
failed == prediksi validation   : True
slow   semuanya ok              : True
jujur  semuanya ok              : True

$ sqlite3 ... "SELECT attempts,COUNT(*) FROM jobs WHERE status='dead' GROUP BY attempts;"    -> 5|833
$ sqlite3 ... "SELECT attempts,COUNT(*) FROM jobs WHERE status='failed' GROUP BY attempts;"  -> 1|844
$ sqlite3 ... "SELECT substr(last_error,1,45),COUNT(*) FROM jobs WHERE status='dead' GROUP BY 1;"
habis 5 percobaan: HTTP 500 dari target|833
```

### Bonus: satu kegagalan target yang TIDAK direncanakan, tetap pulih

`REC-000002` bukan record chaos (`_chaos_mode` = `None`) tetapi kena HTTP 500 asli pada detik
pertama run — target cold-start, 4 worker menabrak `PRAGMA journal_mode=WAL` bersamaan:

```text
File "/app/app.py", line 60, in _connect
    _conn.execute("PRAGMA journal_mode=WAL")
sqlite3.OperationalError: database is locked
```

Worker mengklasifikasikannya `retryable`, dan percobaan kedua sukses:

```text
REC-000002|w-2|retryable|HTTP 500 dari target|0.17|2026-08-29 06:51:23
REC-000002|w-3|ok||0.18|2026-08-29 07:35:50
```

Race cold-start itu **milik target**, bukan pipeline; memperbaikinya bukan scope P11 (D3 —
target tidak "diperbaiki" agar berhenti gagal). Dicatat di `STATE.md` sebagai kandidat P14.

### Durasi & throughput (bahan P12)

```text
mulai 06:51:22 → selesai 07:38:40  =  2.837,8 dtk (47 mnt 18 dtk), termasuk 2 restart pasca-kill
53.290 percobaan / 2.837,8 dtk = 18,78 percobaan/dtk
48.273 sukses  / 2.837,8 dtk = 17,01 ok/dtk  ≈ 61.225 record berhasil/jam @4 worker
pass final saja: 18,99 job/dtk (31.097 percobaan / 1.637,5 dtk)
```

`data/full50k/run.json` (ditulis `scripts/run_summary.py`, read-only `mode=ro`):

```json
{"attempts_by_outcome":{"ok":48273,"permanent":844,"retryable":4166,"timeout":7},
 "attempts_total":53290,"duplicate_confirmation":0,"duplicate_external_ref":0,
 "dead_without_last_error":0,"ok_without_confirmation":0,"duration_seconds":2837.841,
 "jobs_total":49950,"non_terminal":0,"schema_version":1,
 "status":{"dead":833,"failed":844,"ok":48273},"terminal":49950,"workers":4}
```

### Dashboard = DB pada skala penuh (A6)

```text
dashboard :8120           DB
Total       49950         total|49950
Menunggu        0
Dikerjakan      0
Berhasil    48273         ok|48273
Gagal         844         failed|844
Dead-letter   833         dead|833      -> selisih 0
```

### Gerbang kesehatan

```text
$ uv run --no-sync python -m compileall -q src scripts   -> COMPILEALL OK
$ uv run --no-sync python -m unittest discover -s src    -> Ran 108 tests ... OK
```
