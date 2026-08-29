"""SurgeLine target app — server form yang diuji (D2).

Ini BUKAN bagian dari pipeline deliverable. Ia mensimulasikan platform pihak ketiga
tanpa API: form HTML, validasi server-side, halaman hasil bernomor konfirmasi (D6).

Chaos deterministik (D3) dikendalikan lewat SURGELINE_CHAOS_RATE/SEED.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import sqlite3
import threading
import time
from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse

DB_PATH = os.environ.get("SURGELINE_TARGET_DB", "/app/state/target.db")
CHAOS_RATE = float(os.environ.get("SURGELINE_CHAOS_RATE", "0.05"))
CHAOS_SEED = os.environ.get("SURGELINE_CHAOS_SEED", "1337")
CHAOS_DELAY_SECONDS = float(os.environ.get("SURGELINE_CHAOS_DELAY_SECONDS", "2.0"))

if not 0.0 <= CHAOS_RATE <= 1.0:
    raise ValueError("SURGELINE_CHAOS_RATE harus antara 0.0 dan 1.0")
if CHAOS_DELAY_SECONDS < 0.0:
    raise ValueError("SURGELINE_CHAOS_DELAY_SECONDS tidak boleh negatif")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
REF_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_lock = threading.Lock()
_init_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    external_ref TEXT PRIMARY KEY,
    confirmation TEXT NOT NULL UNIQUE,
    full_name    TEXT NOT NULL,
    email        TEXT NOT NULL,
    policy_no    TEXT NOT NULL,
    amount       TEXT NOT NULL,
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    """Satu koneksi proses-lebar; tulis diserialkan oleh _lock.

    Inisialisasi ikut dikunci: tanpa itu, beberapa thread request yang menabrak
    container yang baru hidup sama-sama membuka koneksi dan menjalankan
    `PRAGMA journal_mode=WAL` bersamaan, dan yang kalah balas `database is locked`
    (HTTP 500 asli, di luar chaos D3).
    """
    global _conn
    if _conn is None:
        with _init_lock:
            if _conn is None:
                os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
                conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15.0)
                conn.execute("PRAGMA busy_timeout=15000")
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.executescript(SCHEMA)
                conn.commit()
                _conn = conn
    return _conn


def _mint(external_ref: str) -> Iterator[str]:
    """Calon nomor konfirmasi SL-<8 hex>: hash(external_ref + counter tabrakan)."""
    for salt in range(4096):
        digest = hashlib.sha256(f"{external_ref}|{salt}".encode()).hexdigest()
        yield f"SL-{digest[:8]}"


def _store(external_ref: str, fields: dict[str, str]) -> tuple[str, bool]:
    """Kembalikan (confirmation, created). Idempoten per external_ref."""
    conn = _connect()
    with _lock:
        row = conn.execute(
            "SELECT confirmation FROM submissions WHERE external_ref = ?", (external_ref,)
        ).fetchone()
        if row is not None:
            return row[0], False

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for confirmation in _mint(external_ref):
            try:
                conn.execute(
                    "INSERT INTO submissions (external_ref, confirmation, full_name,"
                    " email, policy_no, amount, notes, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        external_ref,
                        confirmation,
                        fields["full_name"],
                        fields["email"],
                        fields["policy_no"],
                        fields["amount"],
                        fields["notes"],
                        now,
                    ),
                )
                conn.commit()
                return confirmation, True
            except sqlite3.IntegrityError:
                # Tabrakan nomor konfirmasi (bukan external_ref) -> naikkan counter.
                conn.rollback()
                continue
        raise RuntimeError("gagal menerbitkan nomor konfirmasi unik")


def _validate(values: dict[str, str]) -> list[str]:
    errors: list[str] = []

    ref = values["external_ref"]
    if not ref:
        errors.append("external_ref wajib diisi")
    elif not REF_RE.match(ref):
        errors.append("external_ref hanya boleh A-Z a-z 0-9 . _ - (maks 64 karakter)")

    if not values["full_name"]:
        errors.append("full_name wajib diisi")
    elif len(values["full_name"]) > 120:
        errors.append("full_name maksimal 120 karakter")

    if not values["email"]:
        errors.append("email wajib diisi")
    elif not EMAIL_RE.match(values["email"]):
        errors.append("email tidak berformat alamat email yang sah")

    if not values["policy_no"]:
        errors.append("policy_no wajib diisi")
    elif len(values["policy_no"]) > 40:
        errors.append("policy_no maksimal 40 karakter")

    if not values["amount"]:
        errors.append("amount wajib diisi")
    else:
        try:
            if float(values["amount"]) <= 0:
                errors.append("amount harus lebih besar dari 0")
        except ValueError:
            errors.append("amount harus berupa angka")

    if len(values["notes"]) > 500:
        errors.append("notes maksimal 500 karakter")

    return errors


def _chaos_mode(
    external_ref: str, *, rate: float = CHAOS_RATE, seed: str = CHAOS_SEED
) -> str | None:
    """Nasib reproducible dari sha256(seed + external_ref), atau None bila jujur."""
    value = int.from_bytes(hashlib.sha256(f"{seed}{external_ref}".encode()).digest(), "big")
    if value % 1_000_000 / 1_000_000 >= rate:
        return None
    return ("server_error", "slow", "validation")[value % 3]


PAGE = """<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<title>{title}</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;max-width:44rem;margin:2rem auto;padding:0 1rem}}
 label{{display:block;margin:.75rem 0 .2rem;font-weight:600}}
 input,textarea{{width:100%;padding:.45rem;font:inherit;box-sizing:border-box}}
 button{{margin-top:1.25rem;padding:.55rem 1.4rem;font:inherit}}
 .err{{border-left:4px solid #b00;background:#fee;padding:.6rem .9rem;margin:1rem 0}}
 .ok{{border-left:4px solid #070;background:#efe;padding:.6rem .9rem;margin:1rem 0}}
 #confirmation{{font:700 1.6rem/1.3 ui-monospace,monospace;letter-spacing:.05em}}
</style></head><body>
<h1>{title}</h1>
{body}
</body></html>
"""

FORM_FIELDS = """
<form id="submission-form" method="post" action="/submit">
  <label for="external_ref">Nomor referensi (external_ref)</label>
  <input id="external_ref" name="external_ref" type="text" required>
  <label for="full_name">Nama lengkap</label>
  <input id="full_name" name="full_name" type="text" required>
  <label for="email">Email</label>
  <input id="email" name="email" type="text" required>
  <label for="policy_no">Nomor polis</label>
  <input id="policy_no" name="policy_no" type="text" required>
  <label for="amount">Nilai (amount)</label>
  <input id="amount" name="amount" type="text" required>
  <label for="notes">Catatan</label>
  <textarea id="notes" name="notes" rows="3"></textarea>
  <button id="submit-btn" type="submit">Kirim</button>
</form>
"""


def _form_page(errors: list[str] | None = None) -> str:
    body = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        body += (
            f'<div class="err" id="error" data-error="validation">'
            f"<strong>Pengajuan ditolak validasi.</strong>"
            f'<ul id="error-list">{items}</ul></div>'
        )
    return PAGE.format(title="Formulir Pengajuan Klaim", body=body + FORM_FIELDS)


app = FastAPI(title="SurgeLine Target", docs_url=None, redoc_url=None)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(_form_page())


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "chaos_rate": CHAOS_RATE, "chaos_seed": CHAOS_SEED})


@app.post("/submit", response_class=HTMLResponse)
def submit(
    external_ref: str = Form(default=""),
    full_name: str = Form(default=""),
    email: str = Form(default=""),
    policy_no: str = Form(default=""),
    amount: str = Form(default=""),
    notes: str = Form(default=""),
) -> HTMLResponse:
    values = {
        "external_ref": external_ref.strip(),
        "full_name": full_name.strip(),
        "email": email.strip(),
        "policy_no": policy_no.strip(),
        "amount": amount.strip(),
        "notes": notes.strip(),
    }

    errors = _validate(values)
    if errors:
        return HTMLResponse(_form_page(errors), status_code=422)

    ref = values.pop("external_ref")
    chaos_mode = _chaos_mode(ref)
    if chaos_mode == "server_error":
        return HTMLResponse(
            PAGE.format(
                title="Gangguan Server",
                body='<div class="err" id="error">Gangguan server sementara.</div>',
            ),
            status_code=500,
            headers={"X-SurgeLine-Chaos": chaos_mode},
        )
    if chaos_mode == "validation":
        return HTMLResponse(
            _form_page(["record ditolak oleh chaos target"]),
            status_code=422,
            headers={"X-SurgeLine-Chaos": chaos_mode},
        )
    if chaos_mode == "slow":
        time.sleep(CHAOS_DELAY_SECONDS)

    confirmation, created = _store(ref, values)

    body = (
        '<div class="ok" id="result" data-created="{created}">'
        "<p>Pengajuan diterima. Simpan nomor konfirmasi berikut:</p>"
        '<div id="confirmation" data-confirmation="{conf}">{conf}</div>'
        '<p>Referensi: <span id="echo-external-ref">{ref}</span></p>'
        "</div>"
        '<p><a id="back" href="/">Kirim pengajuan lain</a></p>'
    ).format(created="1" if created else "0", conf=confirmation, ref=html.escape(ref))

    headers = {"X-SurgeLine-Chaos": chaos_mode} if chaos_mode else None
    return HTMLResponse(PAGE.format(title="Pengajuan Diterima", body=body), headers=headers)
