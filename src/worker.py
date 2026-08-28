"""Playwright worker: claim one job, fill the target form, store the confirmation.

Worker mengisi form seperti manusia lewat Chromium headless (D12) — bukan POST langsung —
karena pitch-nya adalah platform tanpa API. Yang dinilai worker adalah apa yang dilihat
browser: status HTTP respons `POST /submit`, isi halaman hasil, dan nomor konfirmasi (D6).

Kebijakan ketahanan (P8) tinggal di `src/store.py`: backoff sebelum job layak diklaim
lagi, dead-letter saat jatah percobaan habis (D7), dan sapuan lease untuk job yang
ditinggal mati worker lain (D8). Worker di sini hanya menaatinya — ia menunggu sampai
ada job yang layak, bukan menutup diri begitu tidak ada job yang bisa langsung diambil.

Etika (D14): worker hanya boleh menembak target lokal milik project. `_assert_local_target`
menegakkannya di kode, bukan sekadar di dokumen.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

if __package__:
    from . import store
    from .schema import LEASE_TIMEOUT_SECONDS, RECORD_FIELDS, connect
else:  # dijalankan sebagai `python src/worker.py`
    import store
    from schema import LEASE_TIMEOUT_SECONDS, RECORD_FIELDS, connect

#: Nomor konfirmasi target (`docs/TARGET.md` §5). Bentuk lain = halaman salah dibaca.
CONFIRMATION_RE = re.compile(r"SL-[0-9a-f]{8}\Z")

#: Host yang boleh ditembak worker (D14). Bukan daftar yang bisa diperluas lewat CLI.
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

#: Status HTTP yang dianggap sementara; sisanya permanen (`docs/SCHEMA.md` §4).
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

#: Tag tanpa penutup; tidak boleh ikut menghitung kedalaman `#error-list`.
VOID_TAGS = frozenset({"br", "hr", "img", "input", "meta", "link", "source", "wbr"})

DEFAULT_BASE_URL = "http://127.0.0.1:8110"
DEFAULT_TIMEOUT_MS = 15_000

#: Batas tidur sekali putaran saat semua job menunggu backoff. Menahan worker lebih lama
#: dari ini membuat sapuan lease (D8) telat menolong job yang ditinggal mati worker lain.
POLL_CAP_SECONDS = 5.0


class WorkerError(RuntimeError):
    """Konfigurasi worker melanggar batas project (etika, path, argumen)."""


@dataclass(frozen=True)
class SubmitResult:
    """Penilaian satu percobaan submit, sebelum menyentuh DB."""

    outcome: str  # ok | retryable | permanent | timeout
    confirmation: str | None = None
    error: str | None = None


class _ResultPageParser(HTMLParser):
    """Baca halaman hasil target lewat kontrak selector `docs/TARGET.md` §4.

    Memakai parser HTML sungguhan, bukan regex atas markup: kalau target mengubah
    urutan atribut atau spasi, worker tidak boleh diam-diam berhenti menemukan
    nomor konfirmasi lalu melaporkan job sukses tanpa konfirmasi.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.confirmation: str | None = None
        self.errors: list[str] = []
        self._error_list_depth = 0
        self._in_error_item = False
        self._item: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: (value or "") for name, value in attrs}
        if self.confirmation is None and "data-confirmation" in attributes:
            # `#confirmation` maupun cadangan `[data-confirmation]` (kontrak D6).
            self.confirmation = attributes["data-confirmation"].strip()
        if self._error_list_depth:
            if tag not in VOID_TAGS:
                self._error_list_depth += 1
            if tag == "li":
                self._in_error_item = True
                self._item = []
        elif attributes.get("id") == "error-list":
            self._error_list_depth = 1

    def handle_endtag(self, tag: str) -> None:
        if not self._error_list_depth:
            return
        if self._in_error_item and tag == "li":
            self.errors.append("".join(self._item).strip())
            self._in_error_item = False
        self._error_list_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_error_item:
            self._item.append(data)


def parse_result_page(html: str) -> tuple[str | None, list[str]]:
    """Kembalikan `(confirmation, errors)` dari halaman hasil atau halaman 422."""
    parser = _ResultPageParser()
    parser.feed(html)
    parser.close()
    confirmation = parser.confirmation
    if confirmation is not None and not CONFIRMATION_RE.fullmatch(confirmation):
        # Bentuk asing lebih berbahaya daripada tidak ada: jangan simpan sebagai sukses.
        confirmation = None
    return confirmation, [message for message in parser.errors if message]


def classify_response(status: int, html: str) -> SubmitResult:
    """Petakan (status HTTP, halaman hasil) ke satu `outcome` `docs/SCHEMA.md` §4."""
    if status in RETRYABLE_STATUSES:
        return SubmitResult(outcome="retryable", error=f"HTTP {status} dari target")
    confirmation, errors = parse_result_page(html)
    if status == 200:
        if confirmation:
            return SubmitResult(outcome="ok", confirmation=confirmation)
        # D6: halaman 200 tanpa nomor konfirmasi dihitung gagal, bukan sukses diam-diam.
        return SubmitResult(
            outcome="permanent", error="halaman hasil 200 tanpa nomor konfirmasi (D6)"
        )
    if status == 422:
        detail = "; ".join(errors) if errors else "ditolak validasi tanpa pesan"
        return SubmitResult(outcome="permanent", error=f"HTTP 422: {detail}")
    return SubmitResult(outcome="permanent", error=f"HTTP {status} tidak diharapkan")


def _assert_local_target(base_url: str) -> None:
    """Tolak URL non-lokal (D14/ETHICS): worker tidak pernah menembak sistem orang."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "") not in LOCAL_HOSTS:
        raise WorkerError(
            f"target harus lokal milik project ({', '.join(sorted(LOCAL_HOSTS))}); "
            f"ditolak: {base_url!r}"
        )


def _field_text(field: str, value: object) -> str:
    """Ubah nilai payload jadi teks yang diketik ke input form."""
    if value is None:
        return ""
    if field == "amount" and isinstance(value, float):
        # Hindari notasi ilmiah (`1e+21`) yang akan ditolak validasi target.
        return f"{value:.2f}"
    return str(value)


def submit_job(page, base_url: str, payload: dict[str, object], timeout_ms: int) -> SubmitResult:
    """Isi satu form di browser dan nilai halaman hasilnya."""
    try:
        page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=timeout_ms)
        for field in RECORD_FIELDS:
            page.fill(f"#{field}", _field_text(field, payload.get(field)), timeout=timeout_ms)
        with page.expect_response(
            lambda response: response.request.method == "POST"
            and urlparse(response.url).path == "/submit",
            timeout=timeout_ms,
        ) as intercepted:
            page.click("#submit-btn", timeout=timeout_ms)
        response = intercepted.value
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        return classify_response(response.status, page.content())
    except PlaywrightTimeoutError as exc:
        # Mode chaos `slow`: server bisa saja tetap menyimpan record. Idempotensi target
        # per `external_ref` yang membuat retry-nya aman, bukan tebakan worker.
        return SubmitResult(outcome="timeout", error=f"timeout {timeout_ms} ms: {str(exc)[:120]}")
    except PlaywrightError as exc:
        return SubmitResult(outcome="retryable", error=f"kegagalan browser: {str(exc)[:200]}")


def _apply(
    conn: sqlite3.Connection, job: store.Job, result: SubmitResult, started_at: float
) -> tuple[str, str]:
    """Tulis hasil satu percobaan ke antrean; kembalikan `(outcome, status akhir)`.

    Outcome adalah penilaian percobaan (baris audit `attempts`), status adalah nasib
    job-nya. Keduanya berbeda tepat pada kasus dead-letter: percobaan terakhir sebuah
    job beracun tetap tercatat `retryable`/`timeout`, tapi job-nya berakhir `dead` (D7).
    """
    if result.outcome == "ok" and result.confirmation:
        store.mark_ok(
            conn,
            job.external_ref,
            result.confirmation,
            worker_id=job.worker_id,
            started_at=started_at,
        )
        return "ok", "ok"
    if result.outcome in {"retryable", "timeout"}:
        status = store.release(
            conn,
            job.external_ref,
            result.error or result.outcome,
            worker_id=job.worker_id,
            started_at=started_at,
            outcome=result.outcome,
        )
        return result.outcome, status
    store.mark_failed(
        conn,
        job.external_ref,
        result.error or "penolakan permanen tanpa pesan",
        worker_id=job.worker_id,
        started_at=started_at,
    )
    return "permanent", "failed"


def run_worker(
    db_path: str | Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    worker_id: str,
    max_jobs: int = 0,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    lease_timeout: float = LEASE_TIMEOUT_SECONDS,
) -> dict[str, int]:
    """Proses job sampai antrean `pending` habis atau `max_jobs` tercapai.

    "Habis" berarti tidak ada satu pun baris `pending` — bukan sekadar tidak ada yang
    layak diklaim detik ini. Job yang sedang menunggu backoff (D7) ditunggu di sini,
    kalau tidak, worker akan pulang lebih dulu dan menyisakan job yang tinggal
    menunggu satu detik. Job `claimed` milik worker lain TIDAK menahan worker ini:
    yang menyelamatkannya adalah sapuan lease, bukan menunggu tanpa batas.
    """
    _assert_local_target(base_url)
    database = Path(db_path)
    if not database.is_file():
        raise WorkerError(f"antrean tidak ditemukan: {database} (jalankan loader dulu)")

    tally = dict.fromkeys(("ok", "retryable", "timeout", "permanent", "dead"), 0)
    processed = 0
    conn = connect(database)
    try:
        # Sapuan pertama sebelum browser dibuka: run sebelumnya bisa saja ditinggal
        # mati (P9), dan job yatimnya harus kembali antre sebelum worker menghitung
        # antrean sudah habis.
        store.recover_stuck(conn, lease_timeout=lease_timeout)
        swept_at = time.monotonic()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(timeout_ms)
            try:
                while max_jobs <= 0 or processed < max_jobs:
                    job = store.claim_one(conn, worker_id)
                    if job is None:
                        if time.monotonic() - swept_at >= lease_timeout / 2:
                            store.recover_stuck(conn, lease_timeout=lease_timeout)
                            swept_at = time.monotonic()
                            continue
                        wait = store.time_until_ready(conn)
                        if wait is None:
                            break
                        time.sleep(min(max(wait, 0.05), POLL_CAP_SECONDS))
                        continue
                    started_at = time.time()
                    result = submit_job(page, base_url, job.payload, timeout_ms)
                    outcome, status = _apply(conn, job, result, started_at)
                    tally[outcome] += 1
                    if status == "dead":
                        tally["dead"] += 1
                    processed += 1
            finally:
                page.close()
                browser.close()
    finally:
        conn.close()
    return tally


def _db_path(run_id: str | None, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    if not run_id:
        raise WorkerError("butuh --run <run_id> atau --db <path>")
    return Path("data") / run_id / "queue.db"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", help="run_id; antrean dibaca dari data/<run_id>/queue.db")
    parser.add_argument("--db", type=Path, help="path queue.db eksplisit (menang atas --run)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="target lokal project")
    parser.add_argument(
        "--max-jobs", type=int, default=0, help="berhenti setelah N job (0 = sampai habis)"
    )
    parser.add_argument("--once", action="store_true", help="proses satu job lalu berhenti")
    parser.add_argument("--worker-id", default=None, help="default: w-<pid>")
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    parser.add_argument(
        "--lease-timeout",
        type=float,
        default=LEASE_TIMEOUT_SECONDS,
        help="detik sebelum job `claimed` dianggap yatim dan ditarik kembali (D8)",
    )
    args = parser.parse_args(argv)

    worker_id = args.worker_id or f"w-{os.getpid()}"
    try:
        tally = run_worker(
            _db_path(args.run, args.db),
            base_url=args.base_url,
            worker_id=worker_id,
            max_jobs=1 if args.once else args.max_jobs,
            timeout_ms=args.timeout_ms,
            lease_timeout=args.lease_timeout,
        )
    except WorkerError as exc:
        parser.error(str(exc))
    print(
        f"worker={worker_id} ok={tally['ok']} retryable={tally['retryable']} "
        f"timeout={tally['timeout']} permanent={tally['permanent']} dead={tally['dead']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
