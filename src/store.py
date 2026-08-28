"""Queue access layer shared by worker (P6-P8) and dashboard (P10).

Semua perubahan state job lewat modul ini, tidak ada worker yang menulis SQL sendiri.
Alasannya ada di `docs/SCHEMA.md` §5: satu transisi = satu transaksi atomik yang
sekaligus menaikkan `attempts`, menulis `updated_at`, dan menyisipkan baris audit
`attempts`. Kalau transisi dan baris audit ditulis terpisah, `kill -9` di antara
keduanya (yang justru diuji di P9) meninggalkan DB yang tidak konsisten.

- D4  dedup DB; modul ini tidak pernah menghapus atau menimpa job.
- D5  klaim atomik `BEGIN IMMEDIATE` -> dua worker tidak pernah memegang job sama.
- D6  `mark_ok` menolak konfirmasi kosong; sukses tanpa konfirmasi = gagal permanen.
- D7  backoff `READY_AT` + dead-letter saat `attempts` habis (`release`).
- D8  `recover_stuck` menarik kembali job yang lease-nya kedaluwarsa.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass

if __package__:
    from .schema import (
        BACKOFF_JITTER_RATIO,
        LEASE_TIMEOUT_SECONDS,
        MAX_ATTEMPTS,
        assert_transition,
        backoff_delay,
        status_counts,
    )
else:
    from schema import (
        BACKOFF_JITTER_RATIO,
        LEASE_TIMEOUT_SECONDS,
        MAX_ATTEMPTS,
        assert_transition,
        backoff_delay,
        status_counts,
    )


class StoreError(RuntimeError):
    """Operasi antrean yang menolak menulis karena melanggar kontrak P4."""


def _ready_at_sql(max_attempts: int = MAX_ATTEMPTS) -> str:
    """Ekspresi SQL "kapan job `pending` ini boleh diklaim lagi" (D7).

    `docs/SCHEMA.md` §3 mengunci backoff dihitung dari `updated_at` + `attempts`,
    **tanpa kolom baru**: satu-satunya cara menjaga `SCHEMA_VERSION = 1` tetap sah
    untuk antrean yang sudah ada. Tangga penundaannya dibangkitkan dari
    `schema.backoff_delay` supaya angka Python dan angka SQL tidak bisa berbeda diam-diam.

    Jitter memakai `rowid % 100` — deterministik per job, jadi run tetap bisa diulang
    (D3), tapi job yang dilepas pada detik yang sama tidak jadi layak serentak.
    """
    branches = " ".join(
        f"WHEN attempts = {step} THEN {backoff_delay(step):.6f}"
        for step in range(1, max_attempts + 1)
    )
    ceiling = backoff_delay(max_attempts)
    return (
        "(updated_at + (CASE WHEN attempts <= 0 THEN 0.0 "
        f"{branches} ELSE {ceiling:.6f} END)"
        f" * (1.0 + (rowid % 100) / 100.0 * {BACKOFF_JITTER_RATIO}))"
    )


#: Dihitung sekali; `max_attempts` hanya diparameterkan untuk test.
READY_AT = _ready_at_sql()


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
    tersentuh.

    P8 menambahkan backoff (D7) di atas kolom yang sama: job `pending` yang sudah
    punya `attempts` baru layak diklaim setelah `READY_AT` terlampaui. Job yang belum
    layak dilewati, bukan mengembalikan None — antrean bisa saja punya job lain yang
    sudah layak. `None` berarti "tidak ada yang layak sekarang", yang belum tentu sama
    dengan "antrean habis"; pemanggil memakai `time_until_ready` untuk membedakannya.

    `attempts` dinaikkan di sini, bukan saat job selesai: worker yang mati di tengah
    submission tetap menghabiskan satu jatah percobaan, jadi job beracun tidak bisa
    berputar selamanya setelah lease-nya dikembalikan (D7/D8).
    """
    stamp = time.time() if now is None else now
    _begin_immediate(conn)
    try:
        row = conn.execute(
            "SELECT external_ref, payload, attempts, status FROM jobs"
            f" WHERE status = 'pending' AND {READY_AT} <= ?"
            f" ORDER BY {READY_AT}, rowid LIMIT 1",
            (stamp,),
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
    exhausted_status: str | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> str:
    """Lepas job dari `claimed` ke status berikutnya + baris audit, satu transaksi.

    `exhausted_status` (dipakai `release`) mengalihkan job ke dead-letter begitu
    `attempts >= max_attempts` (D7). Keputusannya diambil DI DALAM transaksi, dari
    `attempts` yang baru saja dibaca — bukan dari angka yang dibawa pemanggil, yang
    sudah basi begitu worker lain menyentuh job yang sama.

    Mengembalikan status akhir yang benar-benar ditulis.
    """
    stamp = time.time() if now is None else now
    _begin_immediate(conn)
    try:
        row = conn.execute(
            "SELECT status, worker_id, attempts FROM jobs WHERE external_ref = ?",
            (external_ref,),
        ).fetchone()
        if row is None:
            raise StoreError(f"job tidak ada: {external_ref!r}")
        if exhausted_status is not None and row["attempts"] >= max_attempts:
            new_status = exhausted_status
            error = f"habis {max_attempts} percobaan: {error}"
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
    return new_status


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
    max_attempts: int = MAX_ATTEMPTS,
) -> str:
    """`claimed -> pending` untuk kegagalan sementara (500/429/503) atau timeout.

    Job yang sudah memakai `max_attempts` percobaan tidak dikembalikan ke antrean
    melainkan masuk dead-letter `dead` dengan `last_error` terisi (D7). Tanpa batas
    ini, mode chaos `server_error` — yang deterministik dan karena itu TIDAK PERNAH
    sukses — akan diputar selamanya dan run tidak pernah selesai.

    Penundaan sebelum percobaan berikutnya tidak ditulis sebagai kolom: `updated_at`
    yang disegarkan di sini plus `attempts` sudah menentukan `READY_AT` job.

    Mengembalikan status akhir (`pending` atau `dead`).
    """
    if outcome not in {"retryable", "timeout"}:
        raise StoreError(f"release hanya untuk retryable/timeout, bukan {outcome!r}")
    return _finish(
        conn,
        external_ref,
        new_status="pending",
        worker_id=worker_id,
        started_at=started_at,
        outcome=outcome,
        confirmation=None,
        error=error,
        now=now,
        exhausted_status="dead",
        max_attempts=max_attempts,
    )


def time_until_ready(
    conn: sqlite3.Connection, *, now: float | None = None
) -> float | None:
    """Detik sampai job `pending` paling awal layak diklaim; None bila tidak ada.

    Pembeda antara "antrean habis" dan "semua job sedang menunggu backoff". Tanpa ini,
    worker menutup diri begitu `claim_one` mengembalikan None dan job yang tinggal
    menunggu satu detik ikut terlantar sampai run berikutnya.
    """
    stamp = time.time() if now is None else now
    row = conn.execute(
        f"SELECT MIN({READY_AT}) AS ready FROM jobs WHERE status = 'pending'"
    ).fetchone()
    if row is None or row["ready"] is None:
        return None
    return max(0.0, row["ready"] - stamp)


def recover_stuck(
    conn: sqlite3.Connection,
    *,
    lease_timeout: float = LEASE_TIMEOUT_SECONDS,
    max_attempts: int = MAX_ATTEMPTS,
    now: float | None = None,
) -> dict[str, int]:
    """Tarik kembali job `claimed` yang melewati lease (D8); hitungan per status baru.

    Worker yang mati (`kill -9`, P9) meninggalkan job di `claimed` selamanya: tidak ada
    proses yang akan melepasnya, karena state antrean hidup di DB, bukan di memori
    worker itu. Sapuan ini yang membuat crash tidak menghilangkan job.

    `attempts` **tidak** dinaikkan di sini — `claim_one` sudah memakai satu jatah saat
    job diklaim, jadi menaikkannya lagi akan menghukum job dua kali untuk satu percobaan.
    Job yang jatahnya sudah habis langsung ke `dead`, bukan kembali ke `pending`, supaya
    tidak ada baris `pending` yang selamanya tidak layak diklaim.

    Lease harus jauh lebih panjang daripada satu submission normal: sapuan yang terlalu
    agresif merebut job yang masih dikerjakan worker hidup, dan itu jalan menuju submit
    ganda. Pemilik lama tetap tertahan `_finish` (`worker_id` tidak cocok -> StoreError),
    tapi pagar pertamanya adalah nilai `LEASE_TIMEOUT_SECONDS` yang lapang.
    """
    stamp = time.time() if now is None else now
    deadline = stamp - lease_timeout
    recovered = {"pending": 0, "dead": 0}
    _begin_immediate(conn)
    try:
        rows = conn.execute(
            "SELECT external_ref, worker_id, attempts, claimed_at FROM jobs"
            " WHERE status = 'claimed' AND claimed_at IS NOT NULL AND claimed_at <= ?",
            (deadline,),
        ).fetchall()
        for row in rows:
            new_status = "dead" if row["attempts"] >= max_attempts else "pending"
            assert_transition("claimed", new_status)
            error = (
                f"lease {lease_timeout:.0f} dtk kedaluwarsa; worker "
                f"{row['worker_id']!r} tidak menyelesaikan percobaan ini"
            )
            if new_status == "dead":
                error = f"habis {max_attempts} percobaan: {error}"
            conn.execute(
                "UPDATE jobs SET status = ?, worker_id = NULL, claimed_at = NULL,"
                " last_error = ?, updated_at = ?"
                " WHERE external_ref = ? AND status = 'claimed'",
                (new_status, error, stamp, row["external_ref"]),
            )
            # Percobaan yang ditinggal mati tidak pernah menulis baris auditnya sendiri;
            # sapuan ini yang menutupnya, supaya "100% kegagalan tercatat" tetap benar.
            record_attempt(
                conn,
                row["external_ref"],
                worker_id=row["worker_id"] or "unknown",
                started_at=row["claimed_at"],
                ended_at=stamp,
                outcome="timeout",
                error=error,
            )
            recovered[new_status] += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return recovered


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Hitungan job per status; semua status muncul walau nol."""
    return status_counts(conn)


def attempt_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Hitungan baris audit per `outcome` (bukti "100% kegagalan tercatat")."""
    rows = conn.execute("SELECT outcome, COUNT(*) AS n FROM attempts GROUP BY outcome")
    return {row["outcome"]: row["n"] for row in rows}
