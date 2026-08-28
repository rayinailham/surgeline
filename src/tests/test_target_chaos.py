"""Regresi classifier chaos deterministik target (D3)."""

import unittest

from target.app import _chaos_mode


class TestTargetChaos(unittest.TestCase):
    def test_rate_zero_mematikan_chaos(self) -> None:
        self.assertTrue(
            all(_chaos_mode(f"REF-{i}", rate=0.0, seed="test") is None for i in range(2_000))
        )

    def test_seed_dan_ref_sama_menghasilkan_nasib_sama(self) -> None:
        first = [_chaos_mode(f"REF-{i}", rate=0.05, seed="test") for i in range(2_000)]
        second = [_chaos_mode(f"REF-{i}", rate=0.05, seed="test") for i in range(2_000)]
        self.assertEqual(first, second)
        self.assertTrue({"server_error", "slow", "validation"}.issubset(first))


if __name__ == "__main__":
    unittest.main()
