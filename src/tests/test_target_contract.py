"""Kontrak target app P1 (D6, D9) — regresi selector & validasi.

Test ini melewati (skip) kalau target `:8110` tidak hidup, supaya `make test` tetap
bisa jalan tanpa Docker. Nyalakan dulu dengan `make target-up` untuk mengujinya.
"""

from __future__ import annotations

import re
import unittest
import uuid

import httpx

from target.app import _chaos_mode

BASE = "http://127.0.0.1:8110"
CONFIRMATION_RE = re.compile(r'data-confirmation="(SL-[0-9a-f]{8})"')

FORM_FIELDS = ("external_ref", "full_name", "email", "policy_no", "amount", "notes")

_health: dict[str, object] | None = None


def _target_up() -> bool:
    global _health
    try:
        response = httpx.get(f"{BASE}/health", timeout=2)
    except httpx.HTTPError:
        return False
    if response.status_code != 200:
        return False
    _health = response.json()
    return True


def _chaos_config() -> tuple[str, float]:
    """Seed & rate milik container yang hidup (bukan env proses test)."""
    assert _health is not None, "_target_up() harus dipanggil lebih dulu"
    return str(_health["chaos_seed"]), float(_health["chaos_rate"])


def _honest_ref(prefix: str = "TEST") -> str:
    """`external_ref` acak yang dijamin TIDAK ditandai chaos (D3).

    Chaos target deterministik atas `external_ref` (docs/CHAOS.md), jadi ref acak
    punya peluang `chaos_rate` (~5%) membuat test kontrak merah tanpa ada yang rusak.
    Nasibnya dihitung lewat `target.app._chaos_mode` yang sama persis dipakai target,
    supaya helper ini tidak bisa melenceng dari kontrak.
    """
    seed, rate = _chaos_config()
    for _ in range(1_000):
        ref = f"{prefix}-{uuid.uuid4().hex[:12]}"
        if _chaos_mode(ref, rate=rate, seed=seed) is None:
            return ref
    raise RuntimeError(f"tidak menemukan external_ref bebas chaos (rate={rate})")


def _marked_ref(mode: str, prefix: str = "CHAOS") -> str:
    """`external_ref` yang dijamin ditandai chaos `mode` (untuk test anti-drift)."""
    seed, rate = _chaos_config()
    for index in range(200_000):
        ref = f"{prefix}-{mode}-{index}"
        if _chaos_mode(ref, rate=rate, seed=seed) == mode:
            return ref
    raise RuntimeError(f"tidak menemukan external_ref bermode {mode}")


def _payload(ref: str, **overrides: str) -> dict[str, str]:
    data = {
        "external_ref": ref,
        "full_name": "Uji Kontrak",
        "email": "uji@contoh.co",
        "policy_no": "POL-1",
        "amount": "10.5",
        "notes": "",
    }
    data.update(overrides)
    return data


@unittest.skipUnless(_target_up(), "target :8110 tidak hidup (jalankan `make target-up`)")
class TestTargetContract(unittest.TestCase):
    def test_health_ok(self) -> None:
        body = httpx.get(f"{BASE}/health", timeout=5).json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("chaos_rate", body)

    def test_form_menyajikan_semua_field(self) -> None:
        page = httpx.get(f"{BASE}/", timeout=5).text
        for field in FORM_FIELDS:
            self.assertIn(f'name="{field}"', page, f"field {field} hilang dari form")
        self.assertIn('id="submission-form"', page)

    def test_submit_valid_mengembalikan_nomor_konfirmasi(self) -> None:
        ref = _honest_ref()
        resp = httpx.post(f"{BASE}/submit", data=_payload(ref), timeout=15)
        self.assertEqual(resp.status_code, 200)
        match = CONFIRMATION_RE.search(resp.text)
        self.assertIsNotNone(match, "selector [data-confirmation] hilang dari halaman hasil")
        self.assertIn('id="confirmation"', resp.text)
        self.assertIn(ref, resp.text)

    def test_nomor_konfirmasi_idempoten_per_external_ref(self) -> None:
        ref = _honest_ref()
        first = httpx.post(f"{BASE}/submit", data=_payload(ref), timeout=15)
        second = httpx.post(
            f"{BASE}/submit", data=_payload(ref, full_name="Beda", amount="99"), timeout=15
        )
        conf1 = CONFIRMATION_RE.search(first.text).group(1)
        conf2 = CONFIRMATION_RE.search(second.text).group(1)
        self.assertEqual(conf1, conf2)
        self.assertIn('data-created="1"', first.text)
        self.assertIn('data-created="0"', second.text)

    def test_input_invalid_ditolak_422(self) -> None:
        kasus = {
            "email bukan email": _payload("TEST-BAD-1", email="bukan-email"),
            "amount nol": _payload("TEST-BAD-2", amount="0"),
            "amount negatif": _payload("TEST-BAD-3", amount="-1"),
            "amount bukan angka": _payload("TEST-BAD-4", amount="abc"),
            "full_name kosong": _payload("TEST-BAD-5", full_name=""),
            "external_ref kosong": _payload("", full_name="Ada"),
        }
        for nama, data in kasus.items():
            with self.subTest(nama):
                resp = httpx.post(f"{BASE}/submit", data=data, timeout=15)
                self.assertEqual(resp.status_code, 422)
                self.assertIn('id="error-list"', resp.text)
                self.assertIsNone(CONFIRMATION_RE.search(resp.text))

    def test_honest_ref_selalu_bebas_chaos(self) -> None:
        """Regresi: helper tidak boleh mengembalikan ref yang ditandai chaos."""
        seed, rate = _chaos_config()
        self.assertGreater(rate, 0.0, "target uji harus menyalakan chaos (D3)")
        refs = [_honest_ref() for _ in range(2_000)]
        self.assertEqual(len(set(refs)), len(refs), "helper mengembalikan ref kembar")
        marked = [r for r in refs if _chaos_mode(r, rate=rate, seed=seed) is not None]
        self.assertEqual(marked, [], f"{len(marked)} ref bertanda chaos lolos dari helper")

    def test_prediksi_chaos_cocok_dengan_target_hidup(self) -> None:
        """Anti-drift: `_chaos_mode` yang dipakai helper = perilaku target sebenarnya.

        Kalau kontrak chaos berubah tapi helper tidak, test ini merah — bukan test
        kontrak lain yang merah secara acak.
        """
        harapan = {"server_error": 500, "validation": 422, "slow": 200}
        for mode, status in harapan.items():
            with self.subTest(mode):
                ref = _marked_ref(mode)
                resp = httpx.post(f"{BASE}/submit", data=_payload(ref), timeout=30)
                self.assertEqual(resp.status_code, status)
                self.assertEqual(resp.headers.get("X-SurgeLine-Chaos"), mode)

        ref = _honest_ref("HONEST")
        resp = httpx.post(f"{BASE}/submit", data=_payload(ref), timeout=15)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.headers.get("X-SurgeLine-Chaos"))


if __name__ == "__main__":
    unittest.main()
