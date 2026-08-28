"""Kontrak skema antrean SurgeLine (P4, terkunci).

Sumber kebenaran runtime untuk `docs/SCHEMA.md`. Loader (P5), worker (P6-P8),
lease recovery (P8), dan dashboard (P10) semuanya mengacu ke modul ini.

Keputusan yang diwujudkan di sini:
- D4  dedup di level DB: `external_ref` NOT NULL + PRIMARY KEY, loader `INSERT OR IGNORE`.
- D5  SQLite mode WAL + `busy_timeout`, klaim atomik `BEGIN IMMEDIATE`.
- D6  `confirmation` UNIQUE bila non-NULL; sukses tanpa konfirmasi dihitung gagal.
- D7  `attempts` + `last_error` menopang retry/backoff dan dead-letter.
- D8  `worker_id` + `claimed_at` menopang pemulihan job yatim lewat lease.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from urllib.parse import quote

SCHEMA_VERSION = 1

#: Field record yang dimuat loader; harus cocok `docs/DATA_DICTIONARY.md` dan form target.
RECORD_FIELDS: tuple[str, ...] = (
    "external_ref",
    "full_name",
    "email",
    "policy_no",
    "amount",
    "notes",
)

#: Natural key record (D4).
NATURAL_KEY = "external_ref"

#: Status job yang sah.
JOB_STATUSES: frozenset[str] = frozenset({"pending", "claimed", "ok", "failed", "dead"})

#: Status akhir; job di status ini tidak pernah dikerjakan ulang.
TERMINAL_STATUSES: frozenset[str] = frozenset({"ok", "failed", "dead"})

#: Hasil satu percobaan pada tabel audit `attempts`.
ATTEMPT_OUTCOMES: frozenset[str] = frozenset({"ok", "retryable", "permanent", "timeout"})

#: Batas percobaan sebelum job masuk dead-letter (D7, dikunci P8).
MAX_ATTEMPTS = 5

#: Backoff eksponensial antar percobaan (D7, dikunci P8): 1, 2, 4, 8, 16 detik.
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_FACTOR = 2.0
#: Atap backoff; tanpa ini attempt ke-N di run panjang bisa menidurkan job berjam-jam.
BACKOFF_CAP_SECONDS = 30.0
#: Jitter deterministik: penundaan dipanjangkan 0-25% menurut `rowid % 100` job,
#: supaya job yang dilepas pada detik yang sama tidak jadi layak serentak — tanpa
#: mengorbankan reproducibility (D3: run harus bisa diulang).
BACKOFF_JITTER_RATIO = 0.25

#: Umur maksimal klaim sebelum job dianggap yatim dan ditarik kembali (D8, dikunci P8).
#: Harus jauh di atas durasi submission normal (target `slow` tidur 2 dtk, timeout
#: worker 15 dtk) supaya sapuan lease tidak merebut job yang masih dikerjakan.
LEASE_TIMEOUT_SECONDS = 120.0

#: State machine antrean (P4). Transisi di luar peta ini ilegal.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    # worker mengklaim job lewat satu transaksi `BEGIN IMMEDIATE`
    "pending": frozenset({"claimed", "dead"}),
    # ok = sukses + konfirmasi tersimpan; failed = penolakan permanen;
    # pending = dilepas untuk retry atau lease kedaluwarsa; dead = jatah percobaan habis
    "claimed": frozenset({"ok", "failed", "pending", "dead"}),
    "ok": frozenset(),
    "failed": frozenset(),
    "dead": frozenset(),
}

_PRAGMAS: tuple[str, ...] = (
    # WAL: banyak worker membaca sementara satu menulis (D5).
    "PRAGMA journal_mode=WAL",
    # Tunggu kunci penulis, jangan langsung `database is locked` (D5).
    "PRAGMA busy_timeout=5000",
    # Di WAL, NORMAL tetap tahan `kill -9` proses (yang diuji di P9); hanya kegagalan
    # daya/OS yang bisa memakan transaksi terakhir. Jauh lebih cepat untuk 50k job.
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
)

_DDL: tuple[str, ...] = (
    # PRIMARY KEY TEXT di SQLite tetap mengizinkan NULL; NOT NULL wajib eksplisit
    # supaya dedup D4 tidak bisa ditembus baris ber-external_ref kosong.
    """
    CREATE TABLE IF NOT EXISTS jobs (
        external_ref TEXT    NOT NULL PRIMARY KEY,
        payload      TEXT    NOT NULL,
        status       TEXT    NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'claimed', 'ok', 'failed', 'dead')),
        attempts     INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        worker_id    TEXT,
        claimed_at   REAL,
        confirmation TEXT     UNIQUE,
        last_error   TEXT,
        created_at   REAL    NOT NULL,
        updated_at   REAL    NOT NULL
    )
    """,
    # Antrean membaca `WHERE status='pending'`; recovery lease membaca
    # `WHERE status='claimed' AND claimed_at < ?` (D8). Klaim mengurutkan pending
    # berdasar `updated_at` supaya job yang baru dilepas tidak langsung diklaim ulang
    # dan memonopoli worker (P6); kelayakan backoff D7 dihitung dari kolom yang sama.
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_status_claimed_at ON jobs (status, claimed_at)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_status_updated_at ON jobs (status, updated_at)",
    """
    CREATE TABLE IF NOT EXISTS attempts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        external_ref TEXT    NOT NULL REFERENCES jobs (external_ref) ON DELETE CASCADE,
        worker_id    TEXT    NOT NULL,
        started_at   REAL    NOT NULL,
        ended_at     REAL,
        outcome      TEXT    NOT NULL
                     CHECK (outcome IN ('ok', 'retryable', 'permanent', 'timeout')),
        error        TEXT,
        confirmation TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_attempts_external_ref ON attempts (external_ref)",
    "CREATE INDEX IF NOT EXISTS idx_attempts_outcome ON attempts (outcome)",
    """
    CREATE TABLE IF NOT EXISTS meta (
        key   TEXT NOT NULL PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
)


class SchemaError(RuntimeError):
    """Pelanggaran kontrak skema yang terdeteksi sebelum menyentuh DB."""


def connect(path: str | Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Buka koneksi antrean dengan pragma wajib (D5).

    Dipakai baik oleh `init_db` maupun oleh proses lain (worker, dashboard) yang
    membuka DB yang sudah ada. `journal_mode` bersifat persisten di file, tapi
    `busy_timeout` dan `foreign_keys` per-koneksi, jadi harus diset di tiap proses.

    `read_only=True` (dipakai dashboard P10) membuka DB lewat URI `mode=ro`: SQLite
    sendiri yang menolak setiap penulisan, jadi pembaca tidak bisa merebut kunci
    penulis dari worker yang sedang berjalan walau ada bug di kode pemanggil.
    `PRAGMA journal_mode=WAL` dilewati untuk koneksi ini — mengganti journal mode
    adalah operasi tulis, dan file-nya memang sudah WAL sejak `init_db`.
    """
    if read_only:
        uri = f"file:{quote(str(Path(path).resolve()))}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    else:
        conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        if read_only and "journal_mode" in pragma:
            continue
        conn.execute(pragma)
    return conn


def init_db(path: str | Path) -> sqlite3.Connection:
    """Buat/pastikan skema antrean pada `path`, kembalikan koneksi terbuka.

    Idempoten: aman dipanggil ulang pada DB yang sudah terisi (resume, P9).
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(target)
    try:
        for statement in _DDL:
            conn.execute(statement)
        now = time.time()
        conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
            ("created_at", repr(now)),
        )
        _verify_schema_version(conn)
    except Exception:
        conn.close()
        raise
    return conn


def _verify_schema_version(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    found = int(row["value"])
    if found != SCHEMA_VERSION:
        raise SchemaError(
            f"schema_version DB {found} != kode {SCHEMA_VERSION}; "
            "pakai run_id baru, jangan migrasi diam-diam"
        )


def is_valid_transition(current: str, new: str) -> bool:
    """True bila `current -> new` ada di state machine P4."""
    return new in ALLOWED_TRANSITIONS.get(current, frozenset())


def assert_transition(current: str, new: str) -> None:
    """Naikkan `SchemaError` untuk transisi ilegal.

    Dipakai lapisan store (P5+) sebelum menulis, supaya bug state machine muncul
    sebagai error keras dan bukan sebagai baris DB yang diam-diam salah.
    """
    if current not in JOB_STATUSES:
        raise SchemaError(f"status asal tidak dikenal: {current!r}")
    if new not in JOB_STATUSES:
        raise SchemaError(f"status tujuan tidak dikenal: {new!r}")
    if not is_valid_transition(current, new):
        raise SchemaError(f"transisi ilegal: {current} -> {new}")


def status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Hitung job per status; semua status muncul walau nol (dipakai P10)."""
    counts = dict.fromkeys(sorted(JOB_STATUSES), 0)
    for row in conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"):
        counts[row["status"]] = row["n"]
    return counts


def backoff_delay(attempts: int, *, base: float = BACKOFF_BASE_SECONDS,
                  factor: float = BACKOFF_FACTOR, cap: float = BACKOFF_CAP_SECONDS) -> float:
    """Jeda minimum sebelum job boleh diklaim ulang setelah `attempts` percobaan (D7).

    `attempts` adalah jumlah percobaan yang SUDAH dipakai, jadi percobaan pertama
    (`attempts=0`) tidak pernah ditunda. Tanpa jeda ini, satu job yang selalu gagal
    diklaim ulang secepat loop worker berputar dan membombardir target.
    """
    if attempts <= 0:
        return 0.0
    return min(base * factor ** (attempts - 1), cap)
