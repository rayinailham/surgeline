# SurgeLine — Acceptance Criteria & Metrik Selesai

Dua lapis: **acceptance project** (gerbang untuk menyebut portofolio ini layak dipajang)
dan **acceptance per fase** (gerbang untuk lanjut ke fase berikutnya).
Angka mengikuti `docs/DECISIONS.md`. Kalau berbeda, DECISIONS menang.

---

## Bagian A — Acceptance project (final)

Diambil dari `../portfolio/portfolio_03_bulk_form_runner.md`, diperketat dengan angka +
perintah pembuktinya.

| # | Kriteria | Status | Perintah pembukti |
|---|---|---|---|
| A1 | 50.000 record diproses sampai tuntas | ✅ P11 (49.950 job terminal: ok 48.273 / failed 844 / dead 833; pending+claimed 0) | `sqlite3 queue.db "SELECT COUNT(*) FROM jobs WHERE status IN('ok','failed','dead')"` = 50000, `pending`+`claimed` = 0 |
| A2 | Duplikat **nol**, dibuktikan query | ✅ P5/P8 (subset; skala 50k di P11) | `SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs` = 0 · `SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok'` = 0 |
| A3 | Dimatikan paksa ≥2× di tengah run → tetap selesai 100%, tanpa duplikat | ✅ P9 (3k, 2 kill, 8 yatim) & P11 (50k, 2 kill, 7 yatim, dup 0/0) | `docs/RESUME_PROOF.md`: log 2 `kill -9` + hitung sebelum/sesudah + total akhir 50000 + dup 0 |
| A4 | Target sengaja error 5% → semua gagal ter-retry & akhirnya berhasil ATAU tercatat rapi alasannya | ✅ P8 (chaos 100: ok 80 / failed 10 / dead 10, semua ber-`last_error`; gangguan sementara 20/20 ok) | `SELECT status,COUNT(*) FROM jobs GROUP BY status` · tiap `dead` punya `last_error` non-null |
| A5 | Nomor konfirmasi tersimpan untuk setiap submission berhasil | ✅ P11 (48.273/48.273 berkonfirmasi, 0 kembar, 0 kosong) | `SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='')` = 0 |
| A6 | Dashboard menampilkan angka yang cocok dengan isi database | ✅ P10 (64 poll HTTP 200, selisih 0) & P11 (skala penuh, selisih 0) | screenshot dashboard vs `GROUP BY status` pada detik yang sama, selisih 0 |
| A7 | Throughput terukur, ditulis dalam angka (bukan perkiraan) | ✅ P12 (81.915 rec/jam @8 worker, 7 nilai N, jenuh N=8, 6 juta ≈ 3,0 hari) | `docs/THROUGHPUT.md`: record/jam per N worker + ekstrapolasi 6 juta ≈ Y hari |
| A8 | Impor 50.000 baris Excel tidak membuat memori membengkak | ✅ P5 (RSS loader 10k=50.600 KiB, 50k=57.044 KiB → +12,74%, bukan 5×) | grafik/tabel RSS loader datar (≤ ambang), bukan naik linear terhadap baris |
| A9 | Klaim atomik: N worker paralel, 0 job dikerjakan dua worker | ✅ P7 (4 worker, 500 klaim, 0 double-success) | `SELECT external_ref,COUNT(*) FROM attempts GROUP BY external_ref HAVING COUNT(*)>… ` / bukti tak ada double-claim |
| A10 | Job "nyangkut" (worker mati saat claimed) dipulihkan, tidak hilang | ✅ P8 (`kill -9` saat `claimed` → lease → `pending` → `ok`, dup 0) | uji lease: bunuh worker saat `claimed` → job kembali `pending` → akhirnya `ok` |
| A11 | Reproducible satu perintah di salinan bersih | ⬜ | `rsync` ke folder baru → `make all` (port 8111/8121) exit 0, hasil sama |
| A12 | Nol kredensial bocor; target milik sendiri dinyatakan di README | ⬜ | `make audit` → 0 kebocoran · `.env`/`data/`/`*.db` tak ter-track · README memuat pernyataan legal |

Project baru boleh disebut **selesai** kalau A1–A12 semuanya ✅.
Status saat ini: **10/12** — sisa A11 (salinan bersih) & A12 (audit + README publik), keduanya di P14.

> Kolom status di atas dikoreksi di P13: P9-P12 sudah menutup A1/A3/A5/A6, dan A8 sudah
> terukur sejak P5, tetapi tabel ini belum ikut diperbarui saat itu.

---

## Bagian B — Definition of Done per fase

Ringkasan. DoD lengkapnya ada di masing-masing `phases/phase-NN-*.md` dan **di sanalah**
kotaknya dicentang beserta output perintahnya.

| Fase | Gerbang lanjut | Menyumbang ke |
|---|---|---|
| P0 | `uv sync` sukses, `env-check.md` berisi hasil nyata, struktur folder berdiri | — |
| P1 | target app hidup di `:8110`, form submit → nomor konfirmasi, `docker compose up` bersih | A5 |
| P2 | chaos 5% deterministik (500/lambat/validasi) + oracle target lulus, `docs/CHAOS.md` | A4 |
| P3 | 50.000 record Excel+CSV, generator streamed, memori datar, `docs/DATA_DICTIONARY.md` | A8 |
| P4 | `docs/SCHEMA.md` terkunci: record + tabel `jobs`/`attempts`, state machine, `UNIQUE` | A2 |
| P5 | loader stream → antrean, dedup DB terbukti, memori datar, unit test | A2, A8 |
| P6 | worker isi 1 form → nomor konfirmasi tersimpan / alasan gagal tercatat, unit test | A5 |
| P7 | N worker paralel, klaim atomik, 0 double-claim terbukti | A9 |
| P8 | retry+backoff, dead-letter, lease recovery job nyangkut, unit test | A4, A10 |
| P9 | kill -9 ≥2× → resume → 0 duplikat, `docs/RESUME_PROOF.md` | A3 |
| P10 | dashboard hidup, angka cocok DB 1:1 | A6 |
| P11 | run penuh 50k + chaos + ≥2 kill → status akhir bersih, 0 dup | A1, A2, A4 |
| P12 | `docs/THROUGHPUT.md` angka nyata + ekstrapolasi 6 juta record | A7 |
| P13 | `REPORT.xlsx` 5 lembar + digest 0 jargon + `docs/CONSULTATION.md` 3 pertanyaan | — |
| P14 | video 2 mnt, `make all` exit 0 salinan bersih, audit bersih, README publik | A11, A12 |

---

## Bagian C — Gerbang commit (D13)

Berlaku untuk **setiap** fase, tanpa kecuali:

- [ ] pemindaian rahasia bersih (`make audit`, atau cek manual sebelum P14)
- [ ] `git commit -m "PNN: <ringkas>"` berhasil
- [ ] `git push` berhasil ke `git@rayin-personal:rayinailham/surgeline.git`
- [ ] baru setelah itu fase boleh ditandai ✅ di `STATE.md`

15 fase → 15 commit, tiap commit membawa metrik selesainya di body.

---

## Bagian D — Yang **bukan** kriteria selesai (anti scope-creep, lihat D15)

- Bukan target: captcha solver, anti-bot bypass, submission ke platform tanpa wewenang.
- Bukan target: 6 juta record benar-benar dijalankan (cukup 50k + ekstrapolasi terukur P12).
- Bukan target: Postgres/TiDB/Redis/RabbitMQ sebagai runtime, deploy cloud, multi-user auth,
  UI admin CRUD, dukungan Windows/macOS.
