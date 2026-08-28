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
- [ ] `env-check.md` berisi versi nyata semua tool + status port 8110/8120 bebas.
- [ ] `uv sync` exit 0; jumlah paket dicatat.
- [ ] `uv run --no-sync python -c "import playwright, fastapi, openpyxl, pandas, faker"` sukses.
- [ ] Struktur folder & `Makefile` kerangka berdiri.
- [ ] **Commit + push berhasil** (D13) ke `origin/main`, `git status --short` bersih dari rahasia.

## Metrik selesai
`N tool diverifikasi · uv sync exit 0 · M paket · push commit P00 sukses`

## Jebakan
- Jangan `sudo`/`pacman`/`playwright install-deps`. Gagal di Arch.
- Jangan commit `.env`/`data/`/`*.db`. Cek `git status --short` sebelum commit.
- Playwright browser belum wajib di P0 — cukup paket Python. Browser di P6.
