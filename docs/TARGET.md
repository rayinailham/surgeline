# SurgeLine — TARGET (server form yang diuji)

> Diisi di **P1**. Bagian chaos (D3) dilengkapi di **P2**.
> Target ini **milik project sendiri** (D2/D14) — worker SurgeLine tidak pernah menembak
> situs pihak lain. Lihat `docs/ETHICS.md`.

Target mensimulasikan platform pihak ketiga **tanpa API**: satu-satunya cara mengirim data
adalah mengisi form HTML. Itulah sebabnya worker memakai Playwright (D12), bukan POST langsung.

---

## 1. Cara menjalankan

```bash
cd /home/rayin/Projects/Testing/surgeline
docker compose up -d --build     # atau: make target-up
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8110/health   # 200
docker compose down              # atau: make target-down
```

| Fakta | Nilai |
|---|---|
| Container | `surgeline-target` (prefix `surgeline-` wajib, AGENTS §1) |
| Image | `surgeline-target:local`, base `python:3.13-slim` |
| Port host | `127.0.0.1:8110` → container `8080` (D9; salinan bersih `8111`) |
| Compose file | `docker-compose.yml` **di root project**, bukan `~/infra/` |
| Stack | FastAPI + uvicorn + python-multipart (`target/requirements.txt`, ter-pin) |
| State | SQLite `/app/state/target.db` **di dalam container** (WAL) |

`docker compose down` menghapus container → state target ikut hilang (sengaja: tiap run uji
mulai dari nol). `docker compose restart` mempertahankan state.

## 2. Endpoint

| Method | Path | Sukses | Keterangan |
|---|---|---|---|
| `GET` | `/` | 200 HTML | Halaman form, 6 field |
| `POST` | `/submit` | 200 HTML | Halaman hasil bernomor konfirmasi |
| `POST` | `/submit` | **422** HTML | Ditolak validasi, daftar pesan error |
| `GET` | `/health` | 200 JSON | `{"status":"ok","chaos_rate":0.0,"chaos_seed":"1337"}` |

`/docs` dan `/redoc` dimatikan — target berpura-pura tidak punya API.

## 3. Field form & aturan validasi

Semua dikirim sebagai `application/x-www-form-urlencoded`. Nilai di-`strip()` lebih dulu.

| Field (`name` = `id`) | Wajib | Aturan |
|---|---|---|
| `external_ref` | ya | `^[A-Za-z0-9._-]{1,64}$` — **natural key** (D4), penentu idempotensi |
| `full_name` | ya | tidak kosong, maks 120 karakter |
| `email` | ya | format alamat email (`^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$`) |
| `policy_no` | ya | tidak kosong, maks 40 karakter |
| `amount` | ya | angka, harus **> 0** |
| `notes` | tidak | maks 500 karakter |

Satu request bisa mengembalikan **beberapa** pesan error sekaligus. Penolakan validasi
bersifat **permanen** — bukan kandidat retry (D7); worker mencatatnya sebagai `failed`.

## 4. Selector yang dipakai worker (D6 — kontrak, jangan diubah tanpa mengubah worker)

| Selector | Ada di | Isi |
|---|---|---|
| `#submission-form` | halaman form | elemen `<form>` |
| `#external_ref`, `#full_name`, `#email`, `#policy_no`, `#amount`, `#notes` | halaman form | input per field |
| `#submit-btn` | halaman form | tombol kirim |
| `#confirmation` | halaman hasil | teks nomor konfirmasi, mis. `SL-c8283cdd` |
| `[data-confirmation]` | halaman hasil | nomor konfirmasi sebagai atribut (cadangan) |
| `#result[data-created]` | halaman hasil | `1` = baru dibuat · `0` = idempoten, sudah ada |
| `#echo-external-ref` | halaman hasil | `external_ref` yang diterima server |
| `#error` / `#error-list` | halaman 422 | blok error + `<li>` per pesan |

Nomor konfirmasi **ada di DOM**, bukan hanya di JSON — worker membaca halaman, bukan API.
Submission dianggap **gagal** bila nomor konfirmasi tidak berhasil ditangkap (D6).

## 5. Nomor konfirmasi

- Format: `SL-` + 8 hex huruf kecil → regex `^SL-[0-9a-f]{8}$`.
- Diterbitkan dari `sha256(external_ref + "|" + counter)`; `counter` naik hanya bila hex-nya
  bertabrakan dengan nomor yang sudah terbit. Kolom `confirmation` `UNIQUE` di DB target,
  jadi **keunikan dijamin DB**, bukan harapan pada hash.
- **Idempoten per `external_ref`**: submit ulang `external_ref` yang sama mengembalikan nomor
  yang **sama persis** dan tidak menulis baris kedua (`data-created="0"`). Konsekuensinya,
  field lain pada submit kedua **diabaikan** — baris pertama yang menang.
  Inilah yang membuat "0 duplikat" tetap terbukti walau worker resume setelah crash.

## 6. Chaos (D3) — belum aktif di P1

`docker-compose.yml` sudah menyetel `SURGELINE_CHAOS_RATE=0.0` dan `SURGELINE_CHAOS_SEED=1337`,
dan app sudah membacanya (terlihat di `/health`). **P1 sengaja 100% jujur** supaya P2 bisa
mengukur selisihnya. Mode kegagalan (HTTP 500 / respons lambat / tolak validasi palsu),
pembagiannya, dan rumus deterministiknya dikunci di `docs/CHAOS.md` pada P2.

Kegagalan target adalah **fitur uji**, bukan bug. Dilarang "memperbaiki" target agar
berhenti gagal (AGENTS §3).

## 7. Bukti P1 (2026-08-28)

```
$ docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | grep surgeline
surgeline-target	Up (healthy)	127.0.0.1:8110->8080/tcp

$ curl -sS http://127.0.0.1:8110/health
{"status":"ok","chaos_rate":0.0,"chaos_seed":"1337"}

$ curl -sS -X POST http://127.0.0.1:8110/submit \
    -d 'external_ref=REF-0001&full_name=Uji&email=a@b.co&policy_no=P1&amount=10&notes=x' \
    | grep -o 'SL-[0-9a-f]*'
SL-c8283cdd

# idempotensi: external_ref sama, isi field sengaja dibedakan
submit1: data-confirmation="SL-b3ddff8e"
submit2: data-confirmation="SL-b3ddff8e"   -> identik

# validasi (HTTP 422, tidak ada baris tersimpan)
<li>full_name wajib diisi</li>
<li>email tidak berformat alamat email yang sah</li>
<li>amount harus lebih besar dari 0</li>

# tekanan: 600 request / 300 external_ref / 32 thread
status codes: {200} | tanpa konfirmasi: 0 | confirmation unik: 300
rows=303 distinct_confirmation=303 duplikat=0
```
