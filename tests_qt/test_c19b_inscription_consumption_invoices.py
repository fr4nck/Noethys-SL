"""Qt C19b : parcours operateur exact, lecture seule, sans facture inferee.

Dossier famille -> inscriptions -> consommations -> factures de cette
famille ; retour contextuel. Toutes les donnees sont fictives et jetables.
"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c13_finance_fixture import C13FictiveFinanceDatabase


class C19bOperationalRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.db = C13FictiveFinanceDatabase()
        self.addCleanup(self.db.close)
        self.tmp = tempfile.TemporaryDirectory(prefix="qt-c19b-settings-")
        self.addCleanup(self.tmp.cleanup)
        settings = QSettings(
            str(Path(self.tmp.name) / "qt-c19b.ini"), QSettings.Format.IniFormat
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            self.window = NoethysQtWindow(
                PeopleSearchRepository(self.db.repository.editor_repository),
                SqliteActivityRepository(self.db.path),
                editor_sqlite_path=self.db.path,
                requested_theme="light", source_label="C19b : 100 % fictif",
                read_only_demo=True, background_queries=False,
                finance_enabled=True, catalog_enabled=False,
            )
        self.addCleanup(self.window.close)
        self.addCleanup(lambda: QThreadPool.globalInstance().waitForDone(10000))
        self.window.show()
        self.app.processEvents()

    def _wait(self, condition):
        limit = time.monotonic() + 5
        while time.monotonic() < limit:
            self.app.processEvents()
            if condition():
                return
            QTest.qWait(20)
        self.fail("C19b : fiche fictive non chargee")

    def _open_family(self, family_id):
        self.window._family_requested(family_id)
        self._wait(lambda: (
            self.window.details_page.loaded_kind == "family"
            and self.window.details_page.current_id == family_id
        ))
        return self.window.details_page

    def _open_inscription_consumptions(self, family_id, inscription_id):
        family = self._open_family(family_id)
        family.family_inscriptions_button.click()
        ins = self.window.inscriptions_page
        self.assertTrue(ins.model.rows)
        index = next(i for i, row in enumerate(ins.model.rows)
                     if row.id == inscription_id)
        ins.table.selectRow(index)
        self.assertEqual(ins.selected_row().family_id, family_id)
        ins.consumptions_button.click()
        calendar = self.window.consumptions_page
        self.assertIs(self.window.stack.currentWidget(), calendar)
        return ins, calendar

    def test_full_route_family_100_is_exact_and_reversible(self):
        before = self.db.dump()
        ins, calendar = self._open_inscription_consumptions(100, 503)
        self.assertEqual(calendar._record_individual_id, 12)
        self.assertEqual(calendar._record_inscription_id, 503)
        self.assertEqual(calendar._record_family_id, 100)
        self.assertEqual(calendar.list_page.model.rowCount(), 28)
        self.assertTrue(calendar.family_invoices_button.isVisible())
        self.assertTrue(calendar.family_invoices_button.isEnabled())
        calendar.family_invoices_button.click()
        billing = self.window.finance_pages["billing"]
        self.assertIs(self.window.stack.currentWidget(), billing)
        self.assertEqual(billing._family_id, 100)
        self.assertEqual(billing.current_page.kind, "invoices")
        self.assertEqual({row.id for row in billing.current_page.model.rows},
                         {501, 503})
        self.assertTrue(all(row.value("family") == 100
                            for row in billing.current_page.model.rows))
        self.assertEqual(
            billing.current_page.table.editTriggers(),
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.assertEqual(len(self.window._context_history), 3)
        self.assertIn("consommations", self.window.context_label.text().lower())
        self.window.return_to_context()
        self.assertIs(self.window.stack.currentWidget(), calendar)
        self.assertEqual(calendar._record_inscription_id, 503)
        self.assertEqual(calendar._record_family_id, 100)
        self.assertEqual(calendar.list_page.model.rowCount(), 28)
        self.window.return_to_context()
        self.assertIs(self.window.stack.currentWidget(), ins)
        self.assertEqual(ins.selected_row().id, 503)
        self.window.return_to_context()
        self._wait(lambda: self.window.details_page.loaded_kind == "family"
                   and self.window.details_page.current_id == 100)
        self.assertEqual(self.window._context_history, [])
        self.assertEqual(self.db.dump(), before)

    def test_other_family_never_inherits_first_family_invoices(self):
        _ins, calendar = self._open_inscription_consumptions(101, 502)
        self.assertEqual(calendar._record_family_id, 101)
        calendar.family_invoices_button.click()
        billing = self.window.finance_pages["billing"]
        self.assertEqual(billing._family_id, 101)
        self.assertEqual({row.id for row in billing.current_page.model.rows},
                         {502, 990})
        self.assertNotIn(501, {row.id for row in billing.current_page.model.rows})

    def test_individual_alone_does_not_guess_family(self):
        self.window._individual_requested(12)
        self._wait(lambda: self.window.details_page.loaded_kind == "individual")
        self.window.details_page.individual_consumptions_button.click()
        calendar = self.window.consumptions_page
        self.assertEqual(calendar._record_individual_id, 12)
        self.assertIsNone(calendar._record_inscription_id)
        self.assertIsNone(calendar._record_family_id)
        self.assertFalse(calendar.family_invoices_button.isVisible())
        with self.assertRaises(PermissionError):
            self.window._consumption_family_invoices_requested(100)

    def test_invalid_family_context_refused_before_state_change(self):
        _ins, calendar = self._open_inscription_consumptions(100, 503)
        prior = (
            calendar._record_individual_id,
            calendar._record_inscription_id,
            calendar._record_family_id,
            calendar.list_page.model.rows,
        )
        for invalid in (0, -1, True, "100"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                calendar.focus_record(individual_id=12, inscription_id=503,
                                      family_id=invalid)
        with self.assertRaises(ValueError):
            calendar.focus_record(individual_id=12, family_id=100)
        with self.assertRaises(ValueError):
            calendar.focus_record(inscription_id=503, family_id=100)
        self.assertEqual(
            (calendar._record_individual_id, calendar._record_inscription_id,
             calendar._record_family_id, calendar.list_page.model.rows), prior
        )
        with self.assertRaises(PermissionError):
            self.window._consumption_family_invoices_requested(101)
        self.assertIs(self.window.stack.currentWidget(), calendar)

    def test_reassigned_inscription_cannot_open_old_family_invoices(self):
        # Mutation adverse UNIQUEMENT dans la base temporaire inventée.
        import sqlite3
        from contextlib import closing
        _ins, calendar = self._open_inscription_consumptions(100, 503)
        with closing(sqlite3.connect(self.db.path)) as db, db:
            db.execute(
                "UPDATE inscriptions SET IDfamille=101 WHERE IDinscription=503"
            )
        self.window._consumption_family_invoices_requested(100)
        self.assertIn("Inscription modifiée", self.window.statusBar().currentMessage())
        self.assertIs(self.window.stack.currentWidget(), calendar)
        self.assertNotEqual(self.window.finance_pages["billing"]._family_id, 100)

    def test_global_navigation_clears_family_invoice_context(self):
        _ins, calendar = self._open_inscription_consumptions(100, 503)
        self.window.navigate("home")
        self.window.navigate("consumptions")
        self.assertIsNone(calendar._record_individual_id)
        self.assertIsNone(calendar._record_inscription_id)
        self.assertIsNone(calendar._record_family_id)
        self.assertFalse(calendar.family_invoices_button.isVisible())
        self.assertEqual(self.window._context_history, [])

    def test_finance_disabled_keeps_invoice_link_unavailable(self):
        # Vérification indépendante du composant, sans invoquer la finance.
        from noethys_qt.consumptions_calendar_ui import ConsumptionCalendarPage
        page = ConsumptionCalendarPage(
            self.db.repository, background=False, invoices_available=False
        )
        self.addCleanup(page.close)
        page.focus_record(individual_id=12, inscription_id=503, family_id=100)
        self.assertFalse(page.family_invoices_button.isVisible())
        self.assertFalse(page.family_invoices_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
