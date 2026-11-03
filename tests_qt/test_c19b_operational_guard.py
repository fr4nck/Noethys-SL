"""Refus par défaut du lien facture Qt C19b hors fixture 100% inventée."""
import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from noethys_qt.c19b_operational_guard import can_demo_inscription_invoices


class C19bGuardTests(unittest.TestCase):
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
            """)

    def test_marked_temporary_fixture_only(self):
        original = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertTrue(can_demo_inscription_invoices(
            self.path, read_only_demo=True
        ))
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), original)

    def test_normal_mode_and_missing_path_denied(self):
        self.assertFalse(can_demo_inscription_invoices(
            self.path, read_only_demo=False
        ))
        self.assertFalse(can_demo_inscription_invoices(None, read_only_demo=True))
        self.assertFalse(can_demo_inscription_invoices(
            self.path.with_name("absent.sqlite"), read_only_demo=True
        ))

    def test_missing_and_wrong_markers_denied(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM c13_marker")
        self.assertFalse(can_demo_inscription_invoices(
            self.path, read_only_demo=True
        ))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO c13_marker VALUES ('FORGED')")
        self.assertFalse(can_demo_inscription_invoices(
            self.path, read_only_demo=True
        ))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM c13_marker")
            db.execute("DELETE FROM c8_marker")
        self.assertFalse(can_demo_inscription_invoices(
            self.path, read_only_demo=True
        ))

    def test_filename_and_temporary_directory_guard_precedes_sql(self):
        alien = self.path.with_name("autre_fichier.sqlite")
        with patch("noethys_qt.c19b_operational_guard.sqlite3.connect",
                   side_effect=AssertionError("Aucune connexion permise")):
            self.assertFalse(can_demo_inscription_invoices(
                alien, read_only_demo=True
            ))
            self.assertFalse(can_demo_inscription_invoices(
                self.path, read_only_demo=False
            ))


if __name__ == "__main__":
    unittest.main()
