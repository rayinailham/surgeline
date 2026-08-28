"""Dashboard read-only atas satu antrean SurgeLine (P10, D11).

Satu halaman FastAPI + Jinja2 yang menampilkan hitungan job per status dan throughput
berjalan, di-refresh sendiri lewat HTMX polling. Angkanya bukan angka hias: setiap
kartu berasal dari `store.counts()` (`SELECT status, COUNT(*) ... GROUP BY status`)
dan throughput berasal dari baris audit `attempts` yang benar-benar tercatat, bukan
dari penghitung di memori proses ini (A6).

Batas yang dipegang modul ini:

- **Read-only.** DB dibuka `schema.connect(..., read_only=True)` (URI `mode=ro`).
  Worker sedang menulis di DB yang sama; dashboard tidak boleh ikut antre kunci
  penulis, dan tidak boleh bisa merusak state walau ada bug di sini.
- **Tidak ikut mati bersama worker.** Antrean yang belum ada, run yang hilang, atau
  DB yang sedang dikunci dijawab sebagai halaman 200 dengan pesan — bukan 500 —
  supaya polling HTMX tetap hidup saat run dibunuh (`kill -9`, P9).
- **Bind `127.0.0.1` saja** (D9/D11): tanpa auth, jadi tidak pernah `0.0.0.0`.
- Sumber angka satu-satunya adalah `data/<run_id>/queue.db` (`docs/SCHEMA.md` §2).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if __package__:
    from . import store
    from .schema import JOB_STATUSES, connect
else:  # dijalankan sebagai `python src/dashboard.py`
    import store
    from schema import JOB_STATUSES, connect

#: Akar data run (`docs/SCHEMA.md` §2). Relatif terhadap direktori kerja, seperti worker.
DEFAULT_DATA_DIR = Path("data")

#: Port dashboard dikunci D9; host dikunci D11 (tanpa auth -> localhost saja).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8120

#: Jendela throughput berjalan. Cukup panjang untuk tidak berkedip di antara dua poll,
#: cukup pendek untuk turun terlihat begitu worker dibunuh.
THROUGHPUT_WINDOW_SECONDS = 60.0

#: Nama tampilan status; urutannya juga urutan kartu di halaman.
STATUS_LABELS: tuple[tuple[str, str], ...] = (
    ("pending", "Menunggu"),
    ("claimed", "Dikerjakan"),
    ("ok", "Berhasil"),
    ("failed", "Gagal"),
    ("dead", "Dead-letter"),
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
#: HTMX di-vendor di repo, bukan diambil dari CDN: deliverable harus jalan di mesin
#: klien yang mungkin tanpa internet (D2/D5).
STATIC_DIR = Path(__file__).parent / "static"


class DashboardError(RuntimeError):
    """Konfigurasi dashboard yang tidak bisa dilayani (run tidak ada, dsb.)."""


def queue_path(run: str, *, data_dir: Path = DEFAULT_DATA_DIR) -> Path:
    """Lokasi antrean satu run (`docs/SCHEMA.md` §2)."""
    return Path(data_dir) / run / "queue.db"


def available_runs(*, data_dir: Path = DEFAULT_DATA_DIR) -> list[str]:
    """Run yang punya `queue.db`, terbaru dulu (dipakai saat `--run` tidak diberikan)."""
    root = Path(data_dir)
    if not root.is_dir():
        return []
    runs = [entry for entry in root.iterdir() if (entry / "queue.db").is_file()]
    runs.sort(key=lambda entry: (entry / "queue.db").stat().st_mtime, reverse=True)
    return [entry.name for entry in runs]


def resolve_run(run: str | None, *, data_dir: Path = DEFAULT_DATA_DIR) -> str:
    """`--run` menang; kalau kosong pakai antrean yang paling baru disentuh.

    Dashboard selalu mencetak run_id yang sedang ditampilkan di halaman, jadi
    pemilihan otomatis ini tidak pernah menjadi angka tanpa asal-usul.
    """
    if run:
        return run
    from_env = os.environ.get("SURGELINE_RUN")
    if from_env:
        return from_env
    runs = available_runs(data_dir=data_dir)
    if not runs:
        raise DashboardError(
            f"tidak ada antrean di {Path(data_dir)}/<run_id>/queue.db; "
            "jalankan loader dulu atau berikan --run"
        )
    return runs[0]


def throughput(
    conn: sqlite3.Connection,
    *,
    now: float | None = None,
    window: float = THROUGHPUT_WINDOW_SECONDS,
) -> float:
    """Submission sukses per menit dalam `window` detik terakhir.

    Dihitung dari baris audit `attempts` (`outcome = 'ok'`, `ended_at` di dalam
    jendela), bukan dari delta yang disimpan proses dashboard: dashboard boleh
    di-restart, dibuka di dua tab, atau baru dinyalakan di tengah run tanpa
    mengubah angkanya. Skalanya per menit walau jendelanya bukan 60 detik.
    """
    stamp = time.time() if now is None else now
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM attempts WHERE outcome = 'ok' AND ended_at >= ?",
        (stamp - window,),
    ).fetchone()
    return row["n"] * 60.0 / window


def snapshot(
    conn: sqlite3.Connection,
    *,
    now: float | None = None,
    window: float = THROUGHPUT_WINDOW_SECONDS,
) -> dict[str, object]:
    """Satu potret angka antrean: hitungan per status + total + throughput.

    Semua status muncul walau nol (`schema.status_counts`), sehingga kartu di halaman
    tidak pernah hilang di tengah run dan pembandingan dengan `GROUP BY status`
    tetap 1:1.
    """
    stamp = time.time() if now is None else now
    counts = store.counts(conn)
    done = sum(counts[status] for status in ("ok", "failed", "dead"))
    total = sum(counts.values())
    return {
        "counts": counts,
        "total": total,
        "done": done,
        "remaining": total - done,
        "percent_done": (done * 100.0 / total) if total else 0.0,
        "ok_per_min": throughput(conn, now=stamp, window=window),
        "window_seconds": window,
        "generated_at": stamp,
    }


def read_snapshot(
    path: Path,
    *,
    now: float | None = None,
    window: float = THROUGHPUT_WINDOW_SECONDS,
) -> tuple[dict[str, object] | None, str | None]:
    """Baca satu potret dari `path`; kembalikan `(snapshot, pesan_error)`.

    Kegagalan tidak dilempar ke atas: antrean bisa saja belum dibuat, atau baru
    ditinggal mati worker. Dashboard harus tetap menampilkan halaman (DoD P10),
    jadi errornya jadi pesan, bukan HTTP 500.
    """
    if not path.is_file():
        return None, f"antrean belum ada: {path}"
    try:
        conn = connect(path, read_only=True)
    except sqlite3.Error as error:  # DB ada tapi tidak bisa dibuka read-only
        return None, f"antrean tidak bisa dibuka read-only: {error}"
    try:
        return snapshot(conn, now=now, window=window), None
    except sqlite3.Error as error:  # terkunci / file setengah tertulis
        return None, f"antrean tidak terbaca saat ini: {error}"
    finally:
        conn.close()


def create_app(
    run: str | None = None,
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    window: float = THROUGHPUT_WINDOW_SECONDS,
) -> FastAPI:
    """Bangun app dashboard untuk satu run.

    `run` di-resolve saat app dibuat supaya halaman selalu menyebut run_id yang
    sedang dibaca; path DB-nya sendiri dibaca ulang tiap request, jadi antrean yang
    baru dibuat setelah dashboard menyala tetap muncul tanpa restart.
    """
    resolved = resolve_run(run, data_dir=data_dir)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app = FastAPI(title="SurgeLine — dashboard", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.state.run = resolved
    app.state.data_dir = Path(data_dir)
    app.state.window = window

    def context(request: Request) -> dict[str, object]:
        path = queue_path(app.state.run, data_dir=app.state.data_dir)
        data, error = read_snapshot(path, window=app.state.window)
        return {
            "request": request,
            "run": app.state.run,
            "db_path": str(path),
            "snapshot": data,
            "error": error,
            "labels": STATUS_LABELS,
        }

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html", context(request))

    @app.get("/stats", response_class=HTMLResponse)
    def stats(request: Request) -> HTMLResponse:
        """Fragment yang di-poll HTMX tiap 2 detik (`hx-trigger="every 2s"`)."""
        return templates.TemplateResponse(request, "stats.html", context(request))

    @app.get("/api/stats")
    def api_stats() -> JSONResponse:
        """Angka mentah — dipakai test dan bukti "selisih vs DB = 0" (A6)."""
        path = queue_path(app.state.run, data_dir=app.state.data_dir)
        data, error = read_snapshot(path, window=app.state.window)
        if data is None:
            return JSONResponse({"run": app.state.run, "error": error}, status_code=503)
        payload = {"run": app.state.run, "db_path": str(path), "error": None}
        payload.update({key: value for key, value in data.items() if key != "counts"})
        payload.update({status: data["counts"][status] for status in sorted(JOB_STATUSES)})
        return JSONResponse(payload)

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default=None, help="run_id di data/<run_id>/queue.db")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="D9")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()

    import uvicorn

    try:
        app = create_app(args.run, data_dir=Path(args.data_dir))
    except DashboardError as error:
        parser.error(str(error))
    print(f"dashboard: run={app.state.run} http://{DEFAULT_HOST}:{args.port}")
    uvicorn.run(app, host=DEFAULT_HOST, port=args.port, log_level="warning")
    return 0


#: Entry point untuk `uvicorn src.dashboard:app --port 8120`; run dari `SURGELINE_RUN`
#: atau antrean terbaru. Dibuat malas supaya `import src.dashboard` di test tidak
#: gagal hanya karena `data/` kosong.
def __getattr__(name: str) -> object:
    if name == "app":
        return create_app()
    raise AttributeError(name)


if __name__ == "__main__":
    raise SystemExit(main())
