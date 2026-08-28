# SurgeLine — TOOLS

Tiap tool: kenapa dipakai + perintah persisnya. Aturan besar: **pakai ulang saat membangun,
runtime deliverable berdiri sendiri** (D2/D5, AGENTS §2).

| Tool | Dipakai untuk | Kenapa ini, bukan yang lain |
|---|---|---|
| `uv` | venv, lock, jalankan | Konsisten project 1/2. Cache device dipakai saat build; klien cukup `uv sync`. |
| Docker + compose (lokal project) | host **target app** yang diuji | Simulasi platform remote tanpa API secara sah. Compose milik project, bukan `~/infra/`. |
| FastAPI / Flask | app target (form + hasil + nomor konfirmasi) & dashboard | Ringan, satu file, mudah menyuntik chaos. |
| HTMX | dashboard angka hidup tanpa build FE | Satu halaman, polling, tanpa toolchain JS. |
| Playwright (headless Chromium) | worker pengisi form | Pitch = platform tanpa API → wajib lewat browser (D12). |
| SQLite (WAL) | antrean + state + dedup | Runtime tanpa server DB; jalan di mesin klien (D5). Dedup lewat `UNIQUE`. |
| pandas + openpyxl | generate & baca Excel besar bertahap | `openpyxl` write-only + baca chunked = memori datar (D10). |
| GNU Make | orkestrasi (`make all`, `make audit`, dll.) | Satu perintah reproduksi end-to-end. |
| `unittest` | test | Tanpa dependency tambahan (D1). |
| `sqlite3` CLI + `jq` + `wc` | verifikasi hemat token | Jangan baca 50k baris; agregasi via query. |
| pandoc/core (image device) | PDF laporan/case study | Reuse image, `docker run --rm`. Jangan pasang texlive. |
| MCP `playwright`/`chrome-devtools` | recon 1–2 sampel halaman target | Mahal token — bukan untuk pekerjaan berulang. |

## Perintah yang sering dipakai

```bash
# target app
cd surgeline && docker compose up -d && cd ..
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8110/health

# test & compile
cd surgeline
uv run --no-sync python -m compileall -q src scripts
uv run --no-sync python -m unittest discover -s src -v

# inspeksi antrean tanpa baca mentah
sqlite3 data/<run_id>/queue.db "SELECT status,COUNT(*) FROM jobs GROUP BY status;"
sqlite3 data/<run_id>/queue.db "SELECT COUNT(*)-COUNT(DISTINCT external_ref) AS dup FROM jobs;"

# Playwright siap (idempotent, tanpa sudo)
bash /home/rayin/Projects/Testing/crosscheck/scripts/arch_provision.sh
```

## Larangan tool (ringkas)
- Jangan `sudo`, `pacman`, `playwright install-deps`, `--with-deps`.
- Jangan pakai MySQL/Redis/TiDB device sebagai runtime deliverable.
- Jangan `docker pull` tanpa cek `docker images` dulu.
- Jangan sentuh container non-`surgeline-` (khususnya `crosscheck-tut-*` dan infra).
