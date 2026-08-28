"""Queue access layer shared by worker (P6-P8) and dashboard (P10).

Semua perubahan state job lewat modul ini, tidak ada worker yang menulis SQL sendiri.
Alasannya ada di `docs/SCHEMA.md` §5: satu transisi = satu transaksi atomik yang
sekaligus menaikkan `attempts`, menulis `updated_at`, dan menyisipkan baris audit
`attempts`. Kalau transisi dan baris audit ditulis terpisah, `kill -9` di antara
keduanya (yang justru diuji di P9) meninggalkan DB yang tidak konsisten.

- D4  dedup DB; modul ini tidak pernah menghapus atau menimpa job.
- D5  klaim atomik `BEGIN IMMEDIATE` -> dua worker tidak pernah memegang job sama.
- D6  `mark_ok` menolak konfirmasi kosong; sukses tanpa konfirmasi = gagal permanen.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass

if __package__:
    from .schema import assert_transition, status_counts
else:
    from schema import assert_transition, status_counts


class StoreError(RuntimeError):
    """Operasi antrean yang menolak menulis karena melanggar kontrak P4."""


@dataclass(frozen=True)
class Job:
    """Satu job yang sedang dipegang worker."""

    external_ref: str
    payload: dict[str, object]
    attempts: int
    worker_id: str
    claimed_at: float


def _begin_immediate(conn: sqlite3.Connection, *, retries: int = 5) -> None:
    """Ambil write lock dengan retry singkat bila worker lain sedang commit."""
    for attempt in range(retries):
        try:
            conn.execute("BEGIN IMMEDIATE")
            return
        except sqlite3.OperationalError as error:
            if "database is locked" not in str(error).lower() or attempt == retries - 1:
                raise
            time.sleep(0.05 * (attempt + 1))


def claim_one(conn: sqlite3.Connection, worker_id: str, *, now: float | None = None) -> Job | None:
    """Klaim satu job `pending` secara atomik; None bila antrean habis.

    `BEGIN IMMEDIATE` mengambil kunci penulis sebelum `SELECT`, sehingga dua worker
    tidak pernah membaca baris `pending` yang sama lalu sama-sama meng-`UPDATE`-nya
    (dibuktikan dengan angka di P7).

    Urutan `updated_at` (bukan `rowid`) yang membuat job gagal berpindah ke belakang
    antrean saat dilepas. Dengan `rowid`, satu job yang selalu gagal akan langsung
    diklaim ulang oleh worker yang sama dan memakan seluruh run — terbukti di P6:
    24 percobaan berturut-turut jatuh ke satu `external_ref`, 23 job lain tidak
    tersentuh. Backoff sungguhan (D7) dibangun di atas kolom yang sama di P8.

    `attempts` dinaikkan di sini, bukan saat job selesai: worker yang mati di tengah
    submission tetap menghabiskan satu jatah percobaan, jadi job beracun tidak bisa
    berputar selamanya setelah lease-nya dikembalikan (D7/D8).
    """
    stamp = time.time() if now is None else now
    _begin_immediate(conn)
    try:
        row = conn.execute(
            "SELECT external_ref, payload, attempts, status FROM jobs"
            " WHERE status = 'pending' ORDER BY updated_at, rowid LIMIT 1"
        ).fetchone()
        if row is None:
            conn.execute("COMMIT")
            return None
        assert_transition(row["status"], "claimed")
        conn.execute(
            "UPDATE jobs SET status = 'claimed', worker_id = ?, claimed_at = ?,"
            " attempts = attempts + 1, updated_at = ?"
            " WHERE external_ref = ? AND status = 'pending'",
            (worker_id, stamp, stamp, row["external_ref"]),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return Job(
        external_ref=row["external_ref"],
        payload=json.loads(row["payload"]),
        attempts=row["attempts"] + 1,
        worker_id=worker_id,
        claimed_at=stamp,
    )


def record_attempt(
    conn: sqlite3.Connection,
    external_ref: str,
    *,
    worker_id: str,
    started_at: float,
    ended_at: float,
    outcome: str,
    error: str | None = None,
    confirmation: str | None = None,
) -> None:
    """Sisipkan satu baris audit `attempts`; tidak membuka transaksi sendiri.

    Dipanggil dari dalam transaksi transisi supaya riwayat retry tidak bisa terpisah
    dari state job. `CHECK` pada kolom `outcome` yang menolak nilai asing, bukan kode.
    """
    conn.execute(
        "INSERT INTO attempts"
        " (external_ref, worker_id, started_at, ended_at, outcome, error, confirmation)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (external_ref, worker_id, started_at, ended_at, outcome, error, confirmation),
    )


def _finish(
    conn: sqlite3.Connection,
    external_ref: str,
    *,
    new_status: str,
    worker_id: str,
    started_at: float,
    outcome: str,
    confirmation: str | None,
    error: str | None,
    now: float | None,
) -> None:
    """Lepas job dari `claimed` ke status berikutnya + baris audit, satu transaksi."""
    stamp = time.time() if now is None else now
    _begin_immediate(conn)
    try:
        row = conn.execute(
            "SELECT status, worker_id FROM jobs WHERE external_ref = ?", (external_ref,)
        ).fetchone()
        if row is None:
            raise StoreError(f"job tidak ada: {external_ref!r}")
        assert_transition(row["status"], new_status)
        if row["worker_id"] != worker_id:
            # Lease sudah dipindah ke worker lain (D8). Menulis di sini akan menimpa
            # pekerjaan pemilik baru, jadi tolak keras alih-alih menang diam-diam.
            raise StoreError(
                f"job {external_ref!r} dipegang {row['worker_id']!r}, bukan {worker_id!r}"
            )
        # `worker_id`/`claimed_at` dikosongkan supaya sapuan lease P8 tidak menghitung
        # job yang sudah selesai (docs/SCHEMA.md §5 aturan 4).
        conn.execute(
            "UPDATE jobs SET status = ?, worker_id = NULL, claimed_at = NULL,"
            " confirmation = COALESCE(?, confirmation), last_error = ?, updated_at = ?"
            " WHERE external_ref = ? AND status = 'claimed' AND worker_id = ?",
            (new_status, confirmation, error, stamp, external_ref, worker_id),
        )
        record_attempt(
            conn,
            external_ref,
            worker_id=worker_id,
            started_at=started_at,
            ended_at=stamp,
            outcome=outcome,
            error=error,
            confirmation=confirmation,
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def mark_ok(
    conn: sqlite3.Connection,
    external_ref: str,
    confirmation: str,
    *,
    worker_id: str,
    started_at: float,
    now: float | None = None,
) -> None:
    """`claimed -> ok`. Konfirmasi kosong ditolak: itu bukan sukses (D6)."""
    if not confirmation or not confirmation.strip():
        raise StoreError(f"job {external_ref!r} tidak boleh 'ok' tanpa nomor konfirmasi (D6)")
    _finish(
        conn,
        external_ref,
        new_status="ok",
        worker_id=worker_id,
        started_at=started_at,
        outcome="ok",
        confirmation=confirmation,
        error=None,
        now=now,
    )


def mark_failed(
    conn: sqlite3.Connection,
    external_ref: str,
    error: str,
    *,
    worker_id: str,
    started_at: float,
    now: float | None = None,
) -> None:
    """`claimed -> failed` untuk penolakan permanen (validasi 422, konfirmasi hilang)."""
    _finish(
        conn,
        external_ref,
        new_status="failed",
        worker_id=worker_id,
        started_at=started_at,
        outcome="permanent",
        confirmation=None,
        error=error,
        now=now,
    )


def release(
    conn: sqlite3.Connection,
    external_ref: str,
    error: str,
    *,
    worker_id: str,
    started_at: float,
    outcome: str = "retryable",
    now: float | None = None,
) -> None:
    """`claimed -> pending` untuk kegagalan sementara (500/429/503) atau timeout.

    Kebijakan backoff dan `max_attempts` belum di sini; itu dikunci di P8 (D7).
    """
    if outcome not in {"retryable", "timeout"}:
        raise StoreError(f"release hanya untuk retryable/timeout, bukan {outcome!r}")
    _finish(
        conn,
        external_ref,
        new_status="pending",
        worker_id=worker_id,
        started_at=started_at,
        outcome=outcome,
        confirmation=None,
        error=error,
        now=now,
    )


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Hitungan job per status; semua status muncul walau nol."""
    return status_counts(conn)


def attempt_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Hitungan baris audit per `outcome` (bukti "100% kegagalan tercatat")."""
    rows = conn.execute("SELECT outcome, COUNT(*) AS n FROM attempts GROUP BY outcome")
    return {row["outcome"]: row["n"] for row in rows}
