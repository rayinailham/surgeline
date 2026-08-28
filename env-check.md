# env-check.md — Verifikasi lingkungan (P0)

Hasil **nyata** dari mesin build, bukan asumsi. Diverifikasi **2026-08-28**.
Ulangi verifikasi ini kalau OS/toolchain berubah (Arch rolling release).

Mesin: CachyOS Linux (turunan Arch), kernel `7.1.5-1-cachyos`, Hyprland/Wayland,
Docker tanpa `sudo`, `sudo` butuh password (tidak tersedia di sesi agent).

---

## 1. Versi tool

| Tool | Perintah | Hasil |
|---|---|---|
| uv | `uv --version` | `uv 0.12.1 (329541a50 2026-07-31 x86_64-unknown-linux-gnu)` |
| Python (sistem) | `python3 --version` | `Python 3.14.6` |
| Python (project) | `uv run --no-sync python -c 'import sys;print(sys.version.split()[0])'` | `3.13.13` (di-pin `.python-version` = `3.13`) |
| Docker | `docker --version` | `Docker version 29.6.2, build dfc4efb1e2` |
| Docker Compose | `docker compose version` | `Docker Compose version 5.3.1` |
| Node | `node --version` | `v24.16.0` |
| ffmpeg | `ffmpeg -version \| head -1` | `ffmpeg version n8.1.2` |
| GNU Make | `/usr/bin/make --version` | `GNU Make 4.4.1` |
| git | `command -v git` | `/usr/bin/git` |
| sqlite3 CLI | `sqlite3 --version` | `3.53.4 2026-07-24` — **ada**, verifikasi antrean boleh pakai CLI |
| wf-recorder | `command -v wf-recorder` | `/home/rayin/.local/bin/wf-recorder` (dipakai P14, video) |
| grim | `command -v grim` | `/usr/bin/grim` |
| jq | `command -v jq` | `/usr/bin/jq` |

> Catatan: di shell interaktif user, `make` adalah alias `make -j16`. Dokumen & Makefile
> selalu memakai `make` biasa; kalau butuh pasti, panggil `/usr/bin/make`.

## 2. Port (D9)

```
$ ss -tlnp | grep -E ':(8110|8120)\b' || echo "8110/8120 bebas"
8110/8120 bebas

$ docker ps --format '{{.Names}} {{.Ports}}'
crosscheck-tut-wordpress-1 127.0.0.1:8090->80/tcp
```

- `8110` (target) dan `8120` (dashboard) **bebas**, siap dipakai di P1/P10.
- Satu-satunya container yang berjalan saat verifikasi: `crosscheck-tut-wordpress-1` di `8090`
  — milik project lain, **jangan disentuh** (AGENTS §1).
- `9router.service` (port `20128`) berstatus `active`. Hanya dibaca, **tidak pernah disentuh**
  (AGENTS §0).

## 3. Dependency Python

```
$ uv sync
Installed 29 packages in 101ms
exit=0
```

29 paket terpasang, 31 entri di `uv.lock`. Versi kunci hasil resolve:

| Paket | Versi |
|---|---|
| playwright | 1.62.0 |
| fastapi | 0.141.1 |
| uvicorn | 0.52.4 |
| jinja2 | 3.1.6 |
| python-multipart | 0.0.32 |
| httpx | 0.28.1 |
| openpyxl | 3.1.5 |
| pandas | 3.0.5 |
| faker | 40.37.0 |
| numpy (transitif) | 2.5.2 |

Verifikasi import:

```
$ uv run --no-sync python -c "import sys, playwright, fastapi, openpyxl, pandas, faker; print(...)"
python 3.13.13
imports OK
exit=0
```

## 4. Browser Playwright (belum wajib di P0, dipakai P6)

Cache device `~/.cache/ms-playwright` (±2,0 GB) sudah berisi:
`chromium-1228`, `chromium-1234`, `chromium_headless_shell-1228`,
`chromium_headless_shell-1234`, `firefox-1538`, `webkit-2336`, `ffmpeg-1011`.

- **Jangan prune** — MCP `chrome-devtools` mem-pin `chromium-1228` (`../AGENTS.md` §4).
- Playwright pip di project ini `1.62.0`; revision Chromium yang dituntutnya diverifikasi di **P6**
  lewat `uv run --no-sync playwright install chromium` (**tanpa** `--with-deps`, tanpa `sudo`).
- **Dilarang** `playwright install-deps` di Arch — hardcode `apt-get`, selalu gagal (`../AGENTS.md` §2).

## 5. Gerbang kesehatan

```
$ make test
uv run --no-sync python -m compileall -q src scripts
uv run --no-sync python -m unittest discover -s src -v
Ran 3 tests in 0.605s
OK
exit=0
```

## 6. Ringkasan

13 tool diverifikasi · `uv sync` exit 0 · 29 paket · port 8110/8120 bebas · `make test` hijau.
Tidak ada blocker untuk P1.
