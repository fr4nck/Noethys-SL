"""C19c : precontrole facturation sur donnees inventees et jetables."""
from __future__ import annotations

import hashlib
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

from noethys_qt.billing_preflight_core import (
    BillingPreflightRepository, BillingObservation,
)
from tools.qt_c13_finance_fixture import C13FictiveFinanceDatabase


class C19cBillingPreflightCoreTests(unittest.TestCase):
    def setUp(self):
        self.fixture = C13FictiveFinanceDatabase()
        self.addCleanup(self.fixture.close)
        self.reader = BillingPreflightRepository(self.fixture.path)

    def check(self, **kw):
        defaults = dict(
            consumption_id=3, inscription_id=503,
            individual_id=12, family_id=100,
            displayed_state="refus", displayed_prestation_id=303,
        )
        defaults.update(kw)
        # Les tests qui evaluent les etats corrects passent leur valeur.
        return self.reader.inspect(**defaults)

    def _state(self, cid):
        with closing(sqlite3.connect(self.fixture.path)) as db:
            return db.execute(
                "SELECT etat FROM consommations WHERE IDconso=?", (cid,)
            ).fetchone()[0]

    def test_raw_amount_not_rounded_and_shared_prestation(self):
        before = hashlib.sha256(self.fixture.path.read_bytes()).hexdigest()
        result = self.check(
            consumption_id=1, inscription_id=501, individual_id=10,
            displayed_state=self._state(1), displayed_prestation_id=301,
        )
        self.assertEqual(result.raw_amount, "12.005")
        self.assertEqual(result.invoice_id, 501)
        self.assertEqual(result.consumption_references, 28)
        self.assertEqual(result.allocation_rows, 1)
        self.assertIn("12.005", result.report)
        self.assertIn("plusieurs consommations", result.report)
        self.assertFalse(result.executable)
        self.assertEqual(hashlib.sha256(self.fixture.path.read_bytes()).hexdigest(), before)

    def test_not_invoiced_service_is_not_a_zero_balance(self):
        result = self.check(displayed_state=self._state(3))
        self.assertEqual(result.raw_amount, "0.00")
        self.assertIsNone(result.invoice_id)
        self.assertIn("aucune identifiee", result.report)
        self.assertNotIn("solde calcule", result.report)
        self.assertFalse(result.executable)

    def test_another_family_not_inferred(self):
        with self.assertRaises(PermissionError):
            self.check(family_id=101, displayed_state=self._state(3))
        with self.assertRaises(PermissionError):
            self.check(individual_id=10, displayed_state=self._state(3))
        with self.assertRaises(PermissionError):
            self.check(inscription_id=502, displayed_state=self._state(3))

    def test_stale_prestation_or_state_rejected(self):
        with self.assertRaisesRegex(ValueError, "modifiee"):
            self.check(displayed_state=self._state(3),
                       displayed_prestation_id=301)
        with self.assertRaisesRegex(ValueError, "modifiee"):
            self.check(displayed_state="non_reel")

    def test_invalid_identifiers_fail_before_sqlite(self):
        with patch(
            "noethys_qt.billing_preflight_core.can_demo_inscription_invoices",
            side_effect=AssertionError("guard must not run"),
        ):
            for invalid in (0, -1, True, "3", None):
                with self.subTest(value=invalid), self.assertRaises(ValueError):
                    self.check(consumption_id=invalid)
            with self.assertRaises(ValueError):
                self.check(family_id=False)
            with self.assertRaises(ValueError):
                self.check(displayed_prestation_id=0)

    def test_missing_consumption_does_not_fall_back(self):
        with self.assertRaises(LookupError):
            self.check(consumption_id=99999)

    def test_account_family_mismatch_flagged_without_reassigning(self):
        with closing(sqlite3.connect(self.fixture.path)) as db, db:
            db.execute(
                "UPDATE prestations SET IDcompte_payeur=202 "
                "WHERE IDprestation=303"
            )
        result = self.check(displayed_state=self._state(3))
        self.assertIn("autre famille", result.report)
        self.assertEqual(result.family_id, 100)

    def test_missing_service_does_not_generate_amount(self):
        with closing(sqlite3.connect(self.fixture.path)) as db, db:
            db.execute("UPDATE consommations SET IDprestation=NULL WHERE IDconso=3")
        result = self.check(
            displayed_state=self._state(3), displayed_prestation_id=None,
        )
        self.assertIsNone(result.prestation_id)
        self.assertIsNone(result.raw_amount)
        self.assertIn("Aucune prestation", result.report)

    def test_missing_invoice_is_reported_not_invented(self):
        with closing(sqlite3.connect(self.fixture.path)) as db, db:
            db.execute("UPDATE prestations SET IDfacture=99999 WHERE IDprestation=303")
        result = self.check(displayed_state=self._state(3))
        self.assertEqual(result.invoice_id, 99999)
        self.assertIn("Facture referencee introuvable", result.report)

    def test_outside_fixture_rejected(self):
        with patch(
            "noethys_qt.billing_preflight_core.can_demo_inscription_invoices",
            return_value=False,
        ):
            with self.assertRaises(PermissionError):
                self.check(displayed_state=self._state(3))

    def test_never_executable_even_when_crafted(self):
        with self.assertRaises(ValueError):
            BillingObservation(
                1, 501, 10, 100, "present", 301, "12.005", 501,
                28, 1, (), executable=True,
            )


if __name__ == "__main__":
    unittest.main()
