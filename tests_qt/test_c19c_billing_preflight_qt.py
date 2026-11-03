"""C19c : widget de precontrole lie a une inscription fictive exacte."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c13_finance_fixture import C13FictiveFinanceDatabase


class C19cQtBillingPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.db = C13FictiveFinanceDatabase()
        self.addCleanup(self.db.close)
        self.tmp = tempfile.TemporaryDirectory(prefix="qt-c19c-settings-")
        self.addCleanup(self.tmp.cleanup)
        ini = QSettings(
            str(Path(self.tmp.name) / "c19c.ini"), QSettings.Format.IniFormat
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=ini):
            self.window = NoethysQtWindow(
                PeopleSearchRepository(self.db.repository.editor_repository),
                SqliteActivityRepository(self.db.path),
                editor_sqlite_path=self.db.path,
                read_only_demo=True, background_queries=False,
                finance_enabled=True, catalog_enabled=False,
                source_label="C19c 100% fixture fictive",
            )
        self.addCleanup(self.window.close)
        self.addCleanup(lambda: QThreadPool.globalInstance().waitForDone(10000))
        self.window.show()
        self.app.processEvents()

    def _open(self):
        self.window._family_requested(100)
        end = time.monotonic() + 5
        while self.window.details_page.loaded_kind != "family":
            self.app.processEvents()
            if time.monotonic() > end:
                self.fail("Fiche famille fictive indisponible")
            QTest.qWait(10)
        self.window.details_page.family_inscriptions_button.click()
        inscriptions = self.window.inscriptions_page
        idx = next(i for i, row in enumerate(inscriptions.model.rows)
                   if row.id == 503)
        inscriptions.table.selectRow(idx)
        inscriptions.consumptions_button.click()
        calendar = self.window.consumptions_page
        calendar.list_page.table.selectRow(0)
        self.app.processEvents()
        return calendar

    def test_preflight_shows_raw_amount_without_modifying_source(self):
        before = self.db.dump()
        calendar = self._open()
        panel = calendar.billing_preflight_panel
        self.assertIsNotNone(panel)
        self.assertTrue(panel.check_button.isEnabled())
        panel.check_button.click()
        self.assertIsNotNone(panel.last_observation)
        self.assertEqual(panel.last_observation.family_id, 100)
        self.assertEqual(panel.last_observation.inscription_id, 503)
        self.assertEqual(panel.last_observation.prestation_id, 303)
        self.assertEqual(panel.last_observation.raw_amount, "0.00")
        self.assertEqual(panel.last_observation.consumption_references, 28)
        self.assertIn("AUCUNE FACTURATION AUTORISEE", panel.output.toPlainText())
        self.assertEqual(self.db.dump(), before)

    def test_preview_clears_after_global_navigation(self):
        calendar = self._open()
        panel = calendar.billing_preflight_panel
        panel.check_button.click()
        self.assertIsNotNone(panel.last_observation)
        self.window.navigate("home")
        self.window.navigate("consumptions")
        self.assertIsNone(panel.last_observation)
        self.assertFalse(panel.check_button.isEnabled())
        self.assertEqual(panel.output.toPlainText(), "")

    def test_changed_family_is_refused_when_clicking(self):
        calendar = self._open()
        panel = calendar.billing_preflight_panel
        with closing(sqlite3.connect(self.db.path)) as db, db:
            db.execute(
                "UPDATE inscriptions SET IDfamille=101 WHERE IDinscription=503"
            )
        panel.check_button.click()
        self.assertIsNone(panel.last_observation)
        self.assertIn("actualiser", panel.output.toPlainText())
        self.assertNotIn("Montant BRUT", panel.output.toPlainText())

    def test_without_exact_family_context_is_disabled(self):
        calendar = self._open()
        panel = calendar.billing_preflight_panel
        calendar.focus_record(individual_id=12)
        self.assertFalse(panel.check_button.isEnabled())
        self.assertIsNone(panel.last_observation)
        self.assertFalse(self.window.consumptions_page.family_invoices_button.isVisible())


if __name__ == "__main__":
    unittest.main()
