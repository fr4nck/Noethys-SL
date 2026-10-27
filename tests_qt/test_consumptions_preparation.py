"""C3 : simulation du changement d'état sans aucune écriture SQL."""
from __future__ import annotations

import datetime as dt
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.consumptions_core import Consumption, ConsumptionRepository
from noethys_qt.consumptions_preparation_core import (
    ConsumptionPreflightRepository, PreflightSnapshot, assess_transition,
)


class ConsumptionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "base-fictive_DATA.dat"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE consommations (
                    IDconso INTEGER PRIMARY KEY, date TEXT, etat TEXT,
                    verrouillage INTEGER, forfait INTEGER, IDprestation INTEGER,
                    IDindividu INTEGER, IDactivite INTEGER, IDinscription INTEGER,
                    IDevenement INTEGER
                );
                CREATE TABLE prestations (
                    IDprestation INTEGER PRIMARY KEY, IDfacture INTEGER,
                    forfait_date_debut TEXT
                );
                CREATE TABLE ventilation (
                    IDventilation INTEGER PRIMARY KEY, IDprestation INTEGER,
                    montant TEXT
                );
                INSERT INTO prestations VALUES (100, NULL, NULL);
                INSERT INTO prestations VALUES (101, 900, NULL);
                INSERT INTO prestations VALUES (102, NULL, NULL);
                INSERT INTO ventilation VALUES (200, 102, '0.00');
                INSERT INTO consommations VALUES
                    (1, '2026-10-20', 'reservation', 0, NULL, 100, 10, 20, 30, NULL);
                INSERT INTO consommations VALUES
                    (2, '2026-10-21', 'present', 1, NULL, 100, 10, 20, 30, NULL);
                INSERT INTO consommations VALUES
                    (3, '2026-10-22', 'reservation', 0, 2, 100, 10, 20, 30, NULL);
                INSERT INTO consommations VALUES
                    (4, '2026-10-23', 'reservation', 0, NULL, 101, 10, 20, 30, NULL);
                INSERT INTO consommations VALUES
                    (5, '2026-10-24', 'reservation', 0, NULL, 102, 10, 20, 30, NULL);
                INSERT INTO consommations VALUES
                    (6, '2026-10-25', 'reservation', 0, NULL, 100, 10, 20, NULL, NULL);
                INSERT INTO consommations VALUES
                    (7, '2026-10-26', 'inconnu', 0, NULL, 100, 10, 20, 30, NULL);
                INSERT INTO consommations VALUES
                    (8, '2026-10-27', 'reservation', 0, NULL, 999, 10, 20, 30, NULL);
            """)
        self.editor = NativeActivityEditorRepository(self.path)
        self.reader = ConsumptionPreflightRepository(ConsumptionRepository(self.editor))

    def row(self, ident=1, *, state="reservation", date=None, prestation=100):
        dates = {
            1: "2026-10-20", 2: "2026-10-21", 3: "2026-10-22",
            4: "2026-10-23", 5: "2026-10-24", 6: "2026-10-25",
            7: "2026-10-26", 8: "2026-10-27",
        }
        return Consumption(
            consumption_id=ident, date=date or dates.get(ident, "2026-10-20"),
            state=state, activity="Sport", unit="Séance", group="ALSH",
            last_name="Fictif", first_name="Enfant", start_time=None,
            end_time=None, prestation_id=prestation, amount=None,
            individual_id=10, activity_id=20,
        )

    def codes(self, ident=1, target="present", *, state="reservation", prestation=100):
        return {
            i.code for i in self.reader.inspect(
                self.row(ident, state=state, prestation=prestation), target
            ).issues
        }

    def test_healthy_row_remains_unexecutable_until_business_parity(self):
        proposal = self.reader.inspect(self.row(), "present")
        self.assertFalse(proposal.executable)
        self.assertEqual(proposal.snapshot.state, "reservation")
        self.assertIn("DROITS_NON_VERIFIES", {i.code for i in proposal.issues})
        self.assertIn("PERIODE_NON_VERIFIEE", {i.code for i in proposal.issues})
        self.assertIn("FACTURATION_NON_RACCORDEE", {i.code for i in proposal.issues})
        self.assertIn("AUCUNE_ECRITURE", {i.code for i in proposal.issues})
        self.assertIn("SIMULATION UNIQUEMENT", proposal.report)

    def test_financial_boundary_is_blocked_both_directions(self):
        self.assertIn("FRONTIERE_FACTURATION", self.codes(target="absentj"))
        self.assertNotIn("FRONTIERE_FACTURATION", self.codes(target="absenti"))
        preview = self.reader.inspect(self.row(2, state="present"), "refus")
        self.assertIn("FRONTIERE_FACTURATION", {i.code for i in preview.issues})

    def test_same_state_does_not_create_change(self):
        self.assertIn("AUCUN_CHANGEMENT", self.codes(target="reservation"))

    def test_lock_and_forfait_and_invoice(self):
        self.assertIn("VERROUILLAGE", self.codes(2, state="present"))
        self.assertIn("FORFAIT", self.codes(3))
        self.assertIn("FACTURE", self.codes(4, prestation=101))

    def test_ventilation_blocks_even_when_amount_is_zero(self):
        self.assertIn("VENTILATION", self.codes(5, prestation=102))

    def test_missing_inscription_and_orphan_prestation(self):
        self.assertIn("INSCRIPTION", self.codes(6))
        self.assertIn("PRESTATION_ABSENTE", self.codes(8, prestation=999))

    def test_unknown_existing_state_is_blocked(self):
        self.assertIn("ETAT_INCONNU", self.codes(7, state="inconnu"))

    def test_expired_selection_detects_state_changes(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE consommations SET etat='absentj' WHERE IDconso=1")
        preview = self.reader.inspect(self.row(), "present")
        self.assertIn("SELECTION_PERIMEE", {issue.code for issue in preview.issues})
        self.assertEqual(preview.snapshot.state, "absentj")

    def test_expired_selection_detects_prestation_and_date_changes(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "UPDATE consommations SET IDprestation=102, date='2026-10-19' WHERE IDconso=1"
            )
        preview = self.reader.inspect(self.row(), "present")
        self.assertIn("SELECTION_PERIMEE", {issue.code for issue in preview.issues})

    def test_missing_row_and_unknown_target_fail_closed(self):
        proposal = self.reader.inspect(self.row(99), "present")
        self.assertIn("DISPARUE", {issue.code for issue in proposal.issues})
        with self.assertRaises(ValueError):
            self.reader.inspect(self.row(), "supprimer")
        with self.assertRaises(ValueError):
            assess_transition(self.row(), "inventé", None)

    def test_snapshot_cannot_enable_writer(self):
        from noethys_qt.consumptions_preparation_core import TransitionPreview
        with self.assertRaises(ValueError):
            TransitionPreview(1, "reservation", "present", None, (), executable=True)

    def test_query_is_read_only_with_unchanged_schema_and_rows(self):
        with closing(sqlite3.connect(self.path)) as db:
            before = list(db.iterdump())
        self.reader.inspect(self.row(), "present")
        self.reader.inspect(self.row(4, prestation=101), "absentj")
        with closing(sqlite3.connect(self.path)) as db:
            after = list(db.iterdump())
        self.assertEqual(before, after)

    def test_configured_database_without_guard_refused(self):
        configured = ConsumptionPreflightRepository(
            ConsumptionRepository(NativeActivityEditorRepository(None))
        )
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                configured.inspect(self.row(), "present")


class ConsumptionPreflightQtTests(ConsumptionPreflightTests):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_only_reads_on_explicit_click(self):
        from noethys_qt.consumptions_preparation_ui import ConsumptionPreparationPanel
        panel = ConsumptionPreparationPanel(ConsumptionRepository(self.editor), background=False)
        self.addCleanup(panel.close)
        with mock.patch.object(self.editor, "_connect", side_effect=AssertionError("SQL before click")):
            panel.set_row(self.row())
            panel.target_combo.setCurrentIndex(panel.target_combo.findData("present"))
            self.assertTrue(panel.preview_button.isEnabled())
        panel.preview_button.click()
        self.assertIsNotNone(panel.last_preview)
        self.assertFalse(panel.last_preview.executable)
        self.assertIn("AUCUNE_ECRITURE", panel.output.toPlainText())
        panel.set_row(None)
        self.assertFalse(panel.preview_button.isEnabled())
        self.assertIsNone(panel.last_preview)
        self.assertEqual(panel.output.toPlainText(), "")

    def test_panel_cannot_propose_unknown_state(self):
        from noethys_qt.consumptions_preparation_ui import ConsumptionPreparationPanel
        panel = ConsumptionPreparationPanel(ConsumptionRepository(self.editor), background=False)
        self.addCleanup(panel.close)
        panel.set_row(self.row())
        self.assertEqual(panel.target_combo.count(), 7)
        self.assertEqual(panel.target_combo.findData("supprimer"), -1)

    def test_selection_switch_invalidates_old_preview(self):
        from noethys_qt.consumptions_preparation_ui import ConsumptionPreparationPanel
        panel = ConsumptionPreparationPanel(ConsumptionRepository(self.editor), background=False)
        self.addCleanup(panel.close)
        panel.set_row(self.row())
        panel.target_combo.setCurrentIndex(panel.target_combo.findData("present"))
        panel.inspect()
        self.assertIsNotNone(panel.last_preview)
        panel.set_row(self.row(2, state="present"))
        self.assertIsNone(panel.last_preview)


if __name__ == "__main__":
    unittest.main()
