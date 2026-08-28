# P1 — Target App (Server Form yang Diuji)

**Tujuan sesi:** melahirkan **program yang akan diuji** — app form Docker milik sendiri,
punya halaman form, validasi, dan halaman hasil dengan **nomor konfirmasi unik**. Tanpa ini,
tidak ada yang bisa diuji. (Rule user: siapkan program yang dites DULU.)

**Prasyarat:** P0 selesai.
**Read-set:** `STATE.md`, file ini, `docs/DECISIONS.md` (D2, D6, D9), `docs/TARGET.md`, `AGENTS.md` §3.
**Budget:** berat.

---

## Langkah

### 1. App form (`target/app.py` — FastAPI atau Flask)
Endpoint:
- `GET /` → HTML form: minimal 5 field (mis. `full_name`, `email`, `policy_no`, `amount`, `notes`).
- `POST /submit` → validasi server-side; sukses → halaman hasil berisi **nomor konfirmasi** unik
  (mis. `SL-<8 hex>` dari hash `external_ref` + counter, disimpan agar idempoten per `external_ref`).
- `GET /health` → 200 `{"status":"ok"}`.
- Validasi: `email` harus format email, `amount` numerik > 0, field wajib tak boleh kosong.
  Input invalid → HTTP 422 + pesan (ini nanti jadi salah satu mode "gagal validasi" chaos P2).

Nomor konfirmasi wajib **muncul di DOM halaman hasil** dengan selector stabil
(mis. `#confirmation` atau `[data-confirmation]`) — worker P6 menangkapnya lewat selector itu (D6).

### 2. Dockerfile + `docker-compose.yml` (di root project, BUKAN ~/infra)
```yaml
# docker-compose.yml
services:
  target:
    build: ./target
    container_name: surgeline-target
    ports: ["127.0.0.1:8110:8080"]
    environment:
      SURGELINE_CHAOS_RATE: "0.0"      # P1 tanpa chaos dulu; chaos diaktifkan P2
      SURGELINE_CHAOS_SEED: "1337"
    restart: unless-stopped
```
Container **prefix `surgeline-`** (AGENTS §1). Port `8110` (D9).

### 3. Bukti hidup
```bash
docker compose up -d --build
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8110/health          # 200
# submit satu form via curl, tangkap nomor konfirmasi:
curl -sS -X POST http://127.0.0.1:8110/submit -d 'full_name=Uji&email=a@b.co&policy_no=P1&amount=10&notes=x' | grep -o 'SL-[0-9a-f]*'
```
Isi `docs/TARGET.md`: daftar endpoint, field, aturan validasi, selector nomor konfirmasi, cara run.

### 4. Idempotensi nomor konfirmasi
Submit `external_ref` yang **sama** dua kali → nomor konfirmasi **sama** (target menyimpan map
`external_ref → confirmation`). Ini membuat "0 duplikat" bisa dibuktikan bahkan bila worker
tak sengaja submit ulang. Uji dengan 2 curl identik, bandingkan nomornya.

---

## Output fase
- `target/app.py`, `target/Dockerfile`, `target/requirements.txt`, `docker-compose.yml`, `docs/TARGET.md`.

## Definition of Done
- [ ] `docker compose up -d --build` sukses; `surgeline-target` running di `:8110`.
- [ ] `GET /health` → 200; `GET /` menyajikan form 5 field.
- [ ] `POST /submit` valid → halaman hasil dengan nomor konfirmasi di selector stabil.
- [ ] Input invalid → 422 + pesan (belum chaos; ini validasi asli).
- [ ] `external_ref` sama disubmit 2× → nomor konfirmasi identik (idempoten).
- [ ] `docs/TARGET.md` lengkap (endpoint, field, validasi, selector, cara run).
- [ ] **Commit + push berhasil** (D13).

## Metrik selesai
`target :8110 up · health 200 · submit→konfirmasi SL-xxxx · idempoten terbukti`

## Jebakan
- Jangan taruh compose di `~/infra/docker-compose.yml` (AGENTS §1). Punya project sendiri.
- Belum aktifkan chaos di P1 — target harus 100% sukses dulu supaya P2 bisa mengukur selisih.
- Nomor konfirmasi harus di DOM dengan selector stabil, bukan cuma di JSON — worker baca halaman.
