"""Stress test klaim atomik P7 tanpa membuka browser."""

from __future__ import annotations

import json
import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

if __package__:
    from .schema import connect, init_db
    from .store import _begin_immediate, claim_one
else:
    from schema import connect, init_db
    from store import _begin_immediate, claim_one


def _claim_all(db_path: str, worker_id: str, result: multiprocessing.Queue) -> None:
    conn = connect(db_path)
    claimed = []
    while job := claim_one(conn, worker_id):
        claimed.append(job.external_ref)
    conn.close()
    result.put((worker_id, claimed))


class TestConcurrency(unittest.TestCase):
    def test_empat_worker_mengklaim_semua_job_tanpa_irisan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "queue.db"
            conn = init_db(db_path)
            now = 1_000.0
            conn.executemany(
                "INSERT INTO jobs (external_ref, payload, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ((f"REF-{index:04d}", json.dumps({"n": index}), now, now) for index in range(500)),
            )
            conn.commit()
            conn.close()

            result = multiprocessing.Queue()
            processes = [
                multiprocessing.Process(target=_claim_all, args=(str(db_path), f"w-{index}", result))
                for index in range(4)
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join(15)
                self.assertFalse(process.is_alive(), "worker klaim macet")
                self.assertEqual(process.exitcode, 0)

            claimed_by_worker = dict(result.get(timeout=1) for _ in processes)
            sets = list(map(set, claimed_by_worker.values()))
            self.assertEqual(set().union(*sets), {f"REF-{index:04d}" for index in range(500)})
            self.assertEqual(sum(map(len, sets)), 500)
            for index, refs in enumerate(sets):
                self.assertTrue(refs.isdisjoint(set().union(*sets[:index], *sets[index + 1 :])))

    def test_begin_immediate_retry_setelah_database_locked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "queue.db"
            holder = init_db(db_path)
            contender = connect(db_path)
            contender.execute("PRAGMA busy_timeout = 0")
            holder.execute("BEGIN IMMEDIATE")
            store_module = sys.modules[claim_one.__module__]
            with patch.object(store_module.time, "sleep", side_effect=lambda _: holder.rollback()):
                _begin_immediate(contender, retries=2)
            contender.rollback()
            holder.close()
            contender.close()


if __name__ == "__main__":
    unittest.main()
