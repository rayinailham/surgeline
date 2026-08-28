# P0 — Bootstrap & Environment

**Tujuan sesi:** fondasi bisa jalan — `uv` project berdiri, struktur folder lengkap,
lingkungan diverifikasi nyata (bukan diasumsikan), repo git terpasang & push pertama.

**Prasyarat:** —
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D1, D5, D9, D13), `AGENTS.md`.
**Budget:** ringan.

---

## Langkah

### 1. Verifikasi lingkungan (tulis hasil NYATA ke `env-check.md`)
Cek dan catat versi persis: `uv --version`, `python3 --version`, `docker --version`,
`docker compose version`, `node --version`, `ffmpeg -version | head -1`,
`which wf-recorder grim jq sqlite3`, dan cek port 8110/8120 kosong:
```bash
ss -tlnp | grep -E ':(8110|8120)\b' || echo "8110/8120 bebas"
docker ps --format '{{.Names}} {{.Ports}}'    # pastikan tak bentrok; crosscheck-tut di 8090
```
Kalau `sqlite3` CLI tidak ada, catat — verifikasi antrean nanti pakai `python -c` sebagai gantinya.

### 2. Init `uv` project
`pyproject.toml` dengan dependency inti (versi dibiarkan `uv` yang resolve):
`playwright`, `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `httpx`, `openpyxl`, `pandas`, `faker`.
Lalu `uv sync`. Catat exit code & jumlah paket. **Jangan** `playwright install-deps`.

### 3. Struktur folder (sebagian sudah dibuat scaffold — verifikasi & lengkapi)
```
src/  scripts/  target/  docs/  phases/  assets/  data/(gitignored)  reports/(gitignored)
```
Buat `Makefile` kerangka (target diisi bertahap): `help`, `env`, `test`, `audit` (placeholder).

### 4. Git init + push pertama
```bash
cd surgeline
git init -b main
git remote add origin git@rayin-personal:rayinailham/surgeline.git   # akun PERSONAL (D13)
git add -A && git status --short          # pastikan TIDAK ada .env/data/*.db
```
Cek `.gitignore` sudah menutup `data/`, `reports/`, `.env`, `*.db`. Repo **privat**.
> Jika repo remote belum ada di GitHub, buat privat lebih dulu (akun personal) lalu push.

---

## Output fase
- `env-check.md` (hasil nyata), `pyproject.toml`, `uv.lock`, `Makefile` kerangka, struktur folder.

## Definition of Done
- [x] `env-check.md` berisi versi nyata semua tool + status port 8110/8120 bebas.
- [x] `uv sync` exit 0; jumlah paket dicatat.
- [x] `uv run --no-sync python -c "import playwright, fastapi, openpyxl, pandas, faker"` sukses.
- [x] Struktur folder & `Makefile` kerangka berdiri.
- [x] **Commit + push berhasil** (D13) ke `origin/main`, `git status --short` bersih dari rahasia.

## Bukti (output nyata, sesi 2026-08-28)

```
$ ss -tlnp | grep -E ':(8110|8120)\b' || echo "8110/8120 bebas"
8110/8120 bebas
$ docker ps --format '{{.Names}} {{.Ports}}'
crosscheck-tut-wordpress-1 127.0.0.1:8090->80/tcp
```

```
$ uv sync
Installed 29 packages in 101ms
$ echo $?
0
```

```
$ uv run --no-sync python -c "import sys, playwright, fastapi, openpyxl, pandas, faker; ..."
python 3.13.13
imports OK
exit=0
```

```
$ make test
uv run --no-sync python -m compileall -q src scripts
uv run --no-sync python -m unittest discover -s src -v
test_core_dependencies_importable ... ok
test_python_version ... ok
test_sqlite_supports_wal ... ok
Ran 3 tests in 0.605s
OK
exit=0
```

```
$ make audit
audit: scripts/secret_audit.py belum ada (dibuat di P14) - cek manual
audit manual: bersih
exit=0
$ git status --short      # sebelum commit: 43 file, tanpa .env / data/ / reports/ / *.db
```

```
$ gh repo create rayinailham/surgeline --private ...
https://github.com/rayinailham/surgeline
$ git push -u origin main
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
exit=0
$ gh repo view rayinailham/surgeline --json isPrivate,name,url
{"isPrivate":true,"name":"surgeline","url":"https://github.com/rayinailham/surgeline"}
```

Commit fase: `2409499` — `P00: bootstrap uv project, struktur folder, Makefile, env-check`

## Metrik selesai
`13 tool diverifikasi · uv sync exit 0 · 29 paket (31 entri uv.lock) · make test 3/3 OK · push commit P00 sukses`

## Jebakan
- Jangan `sudo`/`pacman`/`playwright install-deps`. Gagal di Arch.
- Jangan commit `.env`/`data/`/`*.db`. Cek `git status --short` sebelum commit.
- Playwright browser belum wajib di P0 — cukup paket Python. Browser di P6.
