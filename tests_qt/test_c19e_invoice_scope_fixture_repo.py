"""C19e : source SQL fictive exacte, readonly, et controles exhaustifs."""
from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from noethys_qt.invoice_scope_fixture_repo import (
    C19eFictiveInvoiceScopeRepository,
)
from noethys_qt.legacy_write_barrier import PermissionSnapshot, PeriodSnapshot

AUTHOR = PermissionSnapshot(
    7, {("facturation_factures", "creer"): "restriction_activites:1;2"},
    complete=True,
)
DATES = PeriodSnapshot((), complete=True)


class C19eFictiveSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="noethys-qt-c8-fictif-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "C8_DEMONSTRATION_FICTIVE.sqlite"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE c8_marker(token TEXT);
                CREATE TABLE c13_marker(token TEXT);
                INSERT INTO c8_marker VALUES ('NOETHYS_QT_C8_ONLY_FAKE_FIXTURE_20261027');
                INSERT INTO c13_marker VALUES ('C13_FINANCE_FICTIVE_ONLY');
                CREATE TABLE comptes_payeurs (
                    IDcompte_payeur INTEGER PRIMARY KEY,
                    IDfamille INTEGER
                );
                CREATE TABLE prestations (
                    IDprestation INTEGER PRIMARY KEY,
                    IDcompte_payeur INTEGER,
                    date TEXT, montant TEXT, IDfacture INTEGER
                );
                CREATE TABLE consommations (
                    IDconso INTEGER PRIMARY KEY, IDprestation INTEGER,
                    IDactivite INTEGER
                );
                INSERT INTO comptes_payeurs VALUES (201, 100), (202, 101);
                INSERT INTO prestations VALUES
                    (301,201,'2026-10-05','12.005',NULL),
                    (302,201,'2026-10-06','-1.005',NULL),
                    (303,202,'2026-10-07','0.00',501),
                    (304,201,'2026-10-08','1000.0003',NULL);
                INSERT INTO consommations VALUES
                    (1,301,1), (2,301,1), (3,302,2), (4,303,1);
            """)
        self.reader = C19eFictiveInvoiceScopeRepository(self.path)

    def inspect(self, *, activities=(1, 2), prestations=(301, 302),
                family=100, payer=201, perm=AUTHOR, periods=DATES):
        return self.reader.inspect(
            activity_ids=activities,
            prestation_ids=prestations,
            family_id=family,
            payer_id=payer,
            permissions=perm,
            periods=periods,
        )

    def test_fixture_marker_and_sql_are_read_only(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        report = self.inspect()
        self.assertEqual(report.checked_prestation_ids, (301, 302))
        self.assertEqual([c.status for _, c in report.permissions], ["DECLARE"] * 2)
        self.assertFalse(report.executable)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)

    def test_prestation_shared_by_two_consumptions_is_deduplicated(self):
        report = self.inspect()
        self.assertEqual(report.checked_prestation_ids, (301, 302))
        self.assertNotIn("PRESTATION_INVALIDE_OU_DOUBLON", report.findings)

    def test_existing_invoice_of_other_family_is_reported(self):
        report = self.inspect(
            activities=(1,), prestations=(303,), family=101, payer=202,
        )
        self.assertIn("PRESTATION_DEJA_FACTUREE", report.findings)
        self.assertFalse(report.executable)

    def test_cross_family_prestations_cannot_be_merged(self):
        report = self.inspect(
            activities=(1, 2), prestations=(301, 303),
        )
        self.assertIn("COMPTE_PAYEUR_OU_FAMILLE_INCOHERENT", report.findings)
        self.assertIn("ACTIVITES_PRESTATIONS_NON_EXHAUSTIVES", report.findings)

    def test_missing_prestation_is_not_silently_dropped(self):
        report = self.inspect(
            activities=(1, 2), prestations=(301, 999999),
        )
        self.assertEqual(report.checked_prestation_ids, (301, 999999))
        self.assertIn("ACTIVITE_PRESTATION_INVALIDE", report.findings)
        self.assertIn("COMPTE_PAYEUR_OU_FAMILLE_INCOHERENT", report.findings)
        self.assertFalse(report.executable)

    def test_multiple_activities_per_prestation_is_ambiguous(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO consommations VALUES (5,301,2)")
        report = self.inspect()
        self.assertIn("ACTIVITE_PRESTATION_INVALIDE", report.findings)
        self.assertFalse(report.executable)

    def test_prestation_without_consumption_is_not_assigned_to_activity(self):
        report = self.inspect(
            activities=(1,), prestations=(304,),
        )
        self.assertIn("ACTIVITE_PRESTATION_INVALIDE", report.findings)

    def test_no_rights_does_not_create_authority(self):
        report = self.inspect(perm=None)
        self.assertTrue(all(c.status == "INCONNU" for _, c in report.permissions))
        self.assertFalse(report.executable)

    def test_unavailable_period_inventory_is_not_open(self):
        report = self.inspect(periods=None)
        self.assertTrue(all(c.status == "INCONNU" for _, c in report.periods))
        self.assertIn("PERIODES_MANQUANTES_OU_VERROUILLEES", report.findings)

    def test_invalid_id_sets_rejected_before_database(self):
        with patch(
            "noethys_qt.invoice_scope_fixture_repo.can_demo_inscription_invoices",
            side_effect=AssertionError("Should not open SQL"),
        ):
            for activities, prestations in (
                ((), (301,)),
                ((1, True), (301,)),
                ((1, 1), (301,)),
                ((1,), ()),
                ((1,), ("301",)),
                ((1,), (301, 301)),
                ((1,), tuple(range(1, 67))),
            ):
                with self.subTest(a=activities, p=prestations), self.assertRaises(ValueError):
                    self.inspect(activities=activities, prestations=prestations)
            with self.assertRaises(ValueError):
                self.inspect(family=True)

    def test_invalid_path_rejected_without_sql_reads(self):
        external = C19eFictiveInvoiceScopeRepository(
            self.path.with_name("local-prod.sqlite")
        )
        with self.assertRaises(PermissionError):
            external.inspect(
                activity_ids=(1,), prestation_ids=(301,),
                family_id=100, payer_id=201,
            )

    def test_removed_marker_rejects_before_query(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM c13_marker")
        with self.assertRaises(PermissionError):
            self.inspect()

    def test_prestation_amount_is_never_recomputed_or_rounded(self):
        before = self.path.read_bytes()
        report = self.inspect(
            activities=(1, 2), prestations=(301, 302),
        )
        self.assertNotIn("MONTANT_BRUT_NON_NUMERIQUE", report.findings)
        self.assertNotIn("MONTANT_BRUT_NON_FINI", report.findings)
        self.assertEqual(self.path.read_bytes(), before)

    def test_prestation_with_modified_payer_is_rechecked(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE prestations SET IDcompte_payeur=202 WHERE IDprestation=301")
        report = self.inspect()
        self.assertIn("COMPTE_PAYEUR_OU_FAMILLE_INCOHERENT", report.findings)

    def test_sql_injection_string_never_reaches_sql(self):
        with self.assertRaises(ValueError):
            self.inspect(prestations=("301 OR 1=1",))

    def test_no_writer_or_mysql_connection_is_exposed(self):
        self.assertFalse(hasattr(self.reader, "create_invoice"))
        self.assertFalse(hasattr(self.reader, "commit"))
        self.assertFalse(self.inspect().executable)


if __name__ == "__main__":
    unittest.main()
