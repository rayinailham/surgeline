"""Kontrak target app P1 (D6, D9) — regresi selector & validasi.

Test ini melewati (skip) kalau target `:8110` tidak hidup, supaya `make test` tetap
bisa jalan tanpa Docker. Nyalakan dulu dengan `make target-up` untuk mengujinya.
"""

from __future__ import annotations

import re
import unittest
import uuid

import httpx

BASE = "http://127.0.0.1:8110"
CONFIRMATION_RE = re.compile(r'data-confirmation="(SL-[0-9a-f]{8})"')

FORM_FIELDS = ("external_ref", "full_name", "email", "policy_no", "amount", "notes")


def _target_up() -> bool:
    try:
        return httpx.get(f"{BASE}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


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
        ref = f"TEST-{uuid.uuid4().hex[:12]}"
        resp = httpx.post(f"{BASE}/submit", data=_payload(ref), timeout=15)
        self.assertEqual(resp.status_code, 200)
        match = CONFIRMATION_RE.search(resp.text)
        self.assertIsNotNone(match, "selector [data-confirmation] hilang dari halaman hasil")
        self.assertIn('id="confirmation"', resp.text)
        self.assertIn(ref, resp.text)

    def test_nomor_konfirmasi_idempoten_per_external_ref(self) -> None:
        ref = f"TEST-{uuid.uuid4().hex[:12]}"
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


if __name__ == "__main__":
    unittest.main()
