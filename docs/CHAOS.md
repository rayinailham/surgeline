# SurgeLine — CHAOS

> Kontrak terkunci P2 untuk kegagalan buatan target (D3). Kegagalan ini fitur uji,
> bukan bug yang boleh dihapus. Worker hanya boleh mengarah ke target lokal milik project.

## Konfigurasi

| Env target | Default | Arti |
|---|---:|---|
| `SURGELINE_CHAOS_RATE` | `0.05` | Proporsi record yang ditandai chaos; rentang `0.0`–`1.0` |
| `SURGELINE_CHAOS_SEED` | `1337` | Seed reproducibility |
| `SURGELINE_CHAOS_DELAY_SECONDS` | `2.0` | Lama tidur mode `slow`; harus non-negatif |

`rate=0.0` mematikan seluruh chaos. `docker-compose.yml` menerima override ketiga env
tersebut dan memakai default tabel di atas.

## Penentuan deterministik

Untuk setiap submission valid, target menghitung:

```text
h = integer(sha256(UTF-8(seed + external_ref)))
marked = (h mod 1_000_000) / 1_000_000 < rate
mode = [server_error, slow, validation][h mod 3]
```

Record yang tidak `marked` diproses normal. Seed dan `external_ref` sama selalu memberi
nasib sama, tanpa bergantung urutan request atau jumlah worker.

## Mode dan kontrak worker P8

| Mode | Respons target | Sifat | Aksi worker P8 |
|---|---|---|---|
| `server_error` | HTTP 500 | sementara, retryable | retry + backoff |
| `slow` | tidur, lalu HTTP 200 + konfirmasi | timeout-nya sementara, retryable | retry bila timeout; idempotensi target mencegah duplikat |
| `validation` | HTTP 422, `record ditolak oleh chaos target` | permanen | jangan retry; status `failed` + alasan |

Respons chaos membawa header diagnostik `X-SurgeLine-Chaos` dengan nama mode. Header hanya
untuk oracle target; worker produksi tetap menilai HTTP, timeout, DOM error, dan konfirmasi.

## Oracle P2

`make target-oracles` dua kali membangun target segar dengan seed tetap, masing-masing
menembak 2.000 `external_ref` sintetis, lalu menurunkannya. Oracle mengharuskan:

- rate aktual dalam 3,5%–6,5%;
- ketiga mode muncul dan status HTTP cocok kontrak;
- mode `slow` benar-benar menunggu;
- peta `external_ref → mode` dua run identik (`diff=0`).

Oracle hanya menembak `http://127.0.0.1:8110`, target milik project sendiri.
