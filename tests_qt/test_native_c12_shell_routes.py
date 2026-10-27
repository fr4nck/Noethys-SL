"""C12 : recette de la coque native Qt, pas seulement du démonstrateur C8.

Tout se déroule sur C8FictiveDatabase (TemporaryDirectory). Aucun test
ne charge Config.json, les bases utilisateur, ou un service d'écriture.
"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QThreadPool, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.noethys_native import NAVIGATION, NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from noethys_qt.inscriptions_readonly import (
    InscriptionLink, InscriptionRepository, build_inscription_query,
)
from tools.qt_c8_fixture import C8FictiveDatabase, EXPECTED_ROWS


class C12NativeShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.db = C8FictiveDatabase()
        self.addCleanup(self.db.close)
        self.settings_dir = tempfile.TemporaryDirectory(prefix="noethys-c12-settings-")
        self.addCleanup(self.settings_dir.cleanup)
        settings_file = Path(self.settings_dir.name) / "qt-c12.ini"
        self.repo = PeopleSearchRepository(self.db.repository.editor_repository)
        with patch(
            "noethys_qt.noethys_native.QSettings",
            return_value=QSettings(str(settings_file), QSettings.Format.IniFormat),
        ):
            self.window = NoethysQtWindow(
                self.repo, SqliteActivityRepository(self.db.path),
                editor_sqlite_path=self.db.path,
                source_label="BASE 100% FICTIVE — C12",
                requested_theme="light",
                background_queries=False,
            )
        self.addCleanup(self.window.close)
        self.addCleanup(lambda: QThreadPool.globalInstance().waitForDone(10000))
        self.window.show()
        self.app.processEvents()

    def _wait(self, condition, what="signal Qt", duration=4.0):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            self.app.processEvents()
            if condition():
                return
            QTest.qWait(15)
        self.fail("Délai Qt C12 dépassé : " + what)

    def _open_person(self, ident=12):
        self.window._individual_requested(ident)
        self._wait(
            lambda: self.window.details_page.loaded_kind == "individual"
            and self.window.details_page.current_id == ident,
            "fiche individu",
        )
        return self.window.details_page

    def _open_family(self, ident=100):
        self.window._family_requested(ident)
        self._wait(
            lambda: self.window.details_page.loaded_kind == "family"
            and self.window.details_page.current_id == ident,
            "fiche famille",
        )
        return self.window.details_page

    def test_navigation_is_one_shell_with_enabled_inscriptions(self):
        names = [item[0] for item in NAVIGATION]
        self.assertEqual(names, (
            ["home", "people", "activities", "inscriptions", "consumptions",
             "billing", "payments", "accounting"]
        ))
        self.assertEqual(self.window.navigation.count(), 8)
        self.window.navigate("inscriptions")
        self.assertIs(self.window.stack.currentWidget(), self.window.inscriptions_page)
        self.assertEqual(self.window.inscriptions_page.model.rowCount(), 4)
        self.assertTrue(bool(
            self.window.inscriptions_page.table.editTriggers()
            == QAbstractItemView.EditTrigger.NoEditTriggers
        ))
        self.window.navigate("consumptions")
        self.assertIs(self.window.stack.currentWidget(), self.window.consumptions_page)
        self.assertEqual(
            self.window.consumptions_page.list_page.model.rowCount(), 4
        )

    def test_keyboard_shortcuts_are_explicit_for_new_domains(self):
        self.assertEqual(
            self.window.inscriptions_action.shortcut(), QKeySequence("Alt+4")
        )
        self.assertEqual(
            self.window.consumptions_action.shortcut(), QKeySequence("Alt+5")
        )
        self.assertEqual(
            self.window.back_context_action.shortcut(), QKeySequence("Alt+Left")
        )
        self.window.inscriptions_action.trigger()
        self.assertIs(self.window.stack.currentWidget(), self.window.inscriptions_page)
        self.window.consumptions_action.trigger()
        self.assertIs(self.window.stack.currentWidget(), self.window.consumptions_page)

    def test_family_detail_opens_only_family_inscriptions_and_returns(self):
        before = self.db.dump()
        family = self._open_family(100)
        self.assertTrue(family.family_inscriptions_button.isVisible())
        self.assertFalse(family.individual_inscriptions_button.isVisible())
        family.family_inscriptions_button.click()
        page = self.window.inscriptions_page
        self.assertIs(self.window.stack.currentWidget(), page)
        self.assertEqual(page.model.rowCount(), 2)
        self.assertEqual({r.id for r in page.model.rows}, {501, 503})
        self.assertIn("Famille #100", page.context_label.text())
        self.assertTrue(self.window.context_bar.isVisible())
        self.window.context_back_button.click()
        self._wait(lambda: self.window.details_page.loaded_kind == "family"
                   and self.window.details_page.current_id == 100,
                   "retour dossier famille")
        self.assertIs(self.window.stack.currentWidget(), family)
        self.assertFalse(self.window.context_bar.isVisible())
        self.assertEqual(self.db.dump(), before)

    def test_individual_detail_includes_enrollments_and_consumptions(self):
        details = self._open_person(12)
        self.assertTrue(details.individual_inscriptions_button.isVisible())
        self.assertTrue(details.individual_consumptions_button.isVisible())
        details.individual_inscriptions_button.click()
        page = self.window.inscriptions_page
        self.assertEqual(page.model.rowCount(), 1)
        self.assertEqual(page.model.rows[0].id, 503)
        self.assertEqual(page._filters["individual_id"], 12)
        self.window.return_to_context()
        self._wait(lambda: self.window.details_page.loaded_kind == "individual"
                   and self.window.details_page.current_id == 12)
        details.individual_consumptions_button.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.consumptions_page)
        self.assertEqual(self.window.consumptions_page._record_individual_id, 12)
        self.assertIsNone(self.window.consumptions_page._record_inscription_id)
        self.assertEqual(self.window.consumptions_page.list_page.model.rowCount(), 28)
        self.assertTrue(all(r.individual_id == 12 for r in
                            self.window.consumptions_page.list_page.model.rows))
        self.window.return_to_context()
        self._wait(lambda: self.window.details_page.loaded_kind == "individual"
                   and self.window.details_page.current_id == 12)

    def test_inscription_resolves_source_keys_not_displayed_name(self):
        window = self.window
        window.navigate("inscriptions")
        page = window.inscriptions_page
        index = next(i for i, row in enumerate(page.model.rows) if row.id == 503)
        page.table.selectRow(index)
        selection = page.selected_row()
        self.assertEqual(selection.individual_id, 12)
        # La donnée affichée ne doit pas piloter le lien.
        page.search_edit.setText("Démonstration")
        page.refresh()
        self.assertEqual(page.model.rowCount(), 1)
        page.table.selectRow(0)
        page.consumptions_button.click()
        self.assertIs(window.stack.currentWidget(), window.consumptions_page)
        cal = window.consumptions_page
        self.assertEqual(cal._record_individual_id, 12)
        self.assertEqual(cal._record_inscription_id, 503)
        self.assertEqual(cal.list_page.model.rowCount(), 28)
        self.assertEqual(sum(d.count for d in cal._date_counts), 28)
        self.assertIn("Inscription #503", cal.record_filter_label.text())

    def test_returns_to_same_inscription_context_and_selected_row(self):
        win = self.window
        self._open_person(12).individual_inscriptions_button.click()
        page = win.inscriptions_page
        self.assertEqual(page._filters["individual_id"], 12)
        page.table.selectRow(0)
        self.assertEqual(page.selected_row().id, 503)
        page.consumptions_button.click()
        win.return_to_context()
        self.assertIs(win.stack.currentWidget(), page)
        self.assertEqual(page._filters["individual_id"], 12)
        self.assertEqual(page.model.rowCount(), 1)
        self.assertEqual(page.selected_row().id, 503)

    def test_direct_menu_clears_stale_link_and_restores_general_list(self):
        win = self.window
        self._open_person(12).individual_consumptions_button.click()
        cal = win.consumptions_page
        self.assertEqual(cal._record_individual_id, 12)
        win.navigate("people")
        win.navigate("consumptions")
        self.assertIsNone(cal._record_individual_id)
        self.assertIsNone(cal._record_inscription_id)
        self.assertFalse(win.context_back_button.isVisible())
        self.assertEqual(cal.list_page.model.rowCount(), 112)

    def test_global_inscriptions_entry_undoes_family_filter(self):
        self._open_family(100).family_inscriptions_button.click()
        ins = self.window.inscriptions_page
        self.assertEqual(ins.model.rowCount(), 2)
        self.window.navigate("home")
        self.window.navigate("inscriptions")
        self.assertIsNone(ins._filters["family_id"])
        self.assertEqual(ins.model.rowCount(), 4)
        self.assertFalse(self.window.context_back_button.isVisible())

    def test_second_navigation_does_not_query_twice(self):
        window = self.window
        with patch.object(
            window.inscriptions_repository, "search",
            wraps=window.inscriptions_repository.search,
        ) as query:
            window.navigate("inscriptions")
            self.assertEqual(query.call_count, 1)
            window.navigate("home")
            window.navigate("inscriptions")
            # Revenir sur Inscriptions recharge une fois, pas deux.
            self.assertEqual(query.call_count, 2)
        with patch.object(
            window.consumptions_repository, "search",
            wraps=window.consumptions_repository.search,
        ) as query:
            window.navigate("consumptions")
            self.assertEqual(query.call_count, 1)

    def test_invalid_link_refuses_navigation_and_never_reads_external(self):
        win = self.window
        win.navigate("inscriptions")
        before = self.db.dump()
        for wrong in (-1, 0, 98765, True):
            with self.subTest(wrong=wrong):
                win._inscription_consumptions_requested(wrong)
                self.assertIs(win.stack.currentWidget(), win.inscriptions_page)
                self.assertNotIn("consumptions", win.statusBar().currentMessage().lower())
        self.assertEqual(self.db.dump(), before)

    def test_link_resolver_validates_before_connecting(self):
        repo = self.window.inscriptions_repository
        with patch.object(repo.editor_repository, "_connect",
                          side_effect=AssertionError("Connection forbidden")):
            for invalid in (-1, 0, True, "503 OR 1=1"):
                with self.subTest(value=invalid), self.assertRaises(ValueError):
                    repo.resolve_link(invalid)

    def test_resolver_returns_only_exact_sql_keys(self):
        from noethys_qt.inscriptions_readonly import _valid_id
        result = self.window.inscriptions_repository.resolve_link(503)
        self.assertIsInstance(result, InscriptionLink)
        self.assertEqual(
            (result.inscription_id, result.individual_id,
             result.family_id, result.activity_id),
            (503, 12, 100, 1),
        )
        with self.assertRaises(LookupError):
            self.window.inscriptions_repository.resolve_link(99999)
        query, values = build_inscription_query(individual_id=12, placeholder="%s")
        self.assertIn("s.IDindividu = %s", query)
        self.assertNotIn("503", query)
        self.assertEqual(values[0], 12)

    def test_unchanged_synthetic_database_after_complete_navigation(self):
        before = self.db.dump()
        self._open_family(101).family_inscriptions_button.click()
        page = self.window.inscriptions_page
        self.assertEqual({r.id for r in page.model.rows}, {502, 504})
        page.table.selectRow(0)
        page.consumptions_button.click()
        self.window.return_to_context()
        self.window.navigate("home")
        self.window.navigate("consumptions")
        self.assertEqual(self.db.dump(), before)

    def test_two_level_back_restores_inscription_then_family_details(self):
        details = self._open_family(100)
        details.family_inscriptions_button.click()
        inscriptions = self.window.inscriptions_page
        self.assertEqual({r.id for r in inscriptions.model.rows}, {501, 503})
        self.assertEqual(len(self.window._context_history), 1)
        index = next(i for i, row in enumerate(inscriptions.model.rows)
                     if row.id == 503)
        inscriptions.table.selectRow(index)
        inscriptions.consumptions_button.click()
        self.assertEqual(len(self.window._context_history), 2)
        self.assertIs(self.window.stack.currentWidget(), self.window.consumptions_page)
        self.assertIn("Retour à la liste", self.window.context_label.text())
        self.window.return_to_context()
        self.assertEqual(len(self.window._context_history), 1)
        self.assertIs(self.window.stack.currentWidget(), inscriptions)
        self.assertEqual(inscriptions.selected_row().id, 503)
        self.assertIn("fiche family #100", self.window.context_label.text())
        self.window.return_to_context()
        self._wait(lambda: self.window.details_page.loaded_kind == "family"
                   and self.window.details_page.current_id == 100)
        self.assertIs(self.window.stack.currentWidget(), details)
        self.assertFalse(self.window.context_bar.isVisible())
        self.assertEqual(self.window._context_history, [])

    def test_context_history_does_not_survive_unrelated_navigation(self):
        self._open_person(12).individual_inscriptions_button.click()
        self.assertEqual(len(self.window._context_history), 1)
        self.window.navigate("home")
        self.assertEqual(self.window._context_history, [])
        self.window.navigate("consumptions")
        self.assertIsNone(self.window._return_context)
        self.assertFalse(self.window.context_back_button.isVisible())

    def test_all_pending_business_writers_still_unavailable(self):
        self.window.navigate("inscriptions")
        self.assertEqual(
            self.window.inscriptions_page.table.editTriggers(),
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.window.navigate("consumptions")
        page = self.window.consumptions_page
        self.assertEqual(
            page.list_page.table.editTriggers(),
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        page.list_page.table.selectRow(0)
        page.preparation_panel.target_combo.setCurrentIndex(
            page.preparation_panel.target_combo.findData("present")
        )
        page.preparation_panel.preview_button.click()
        self._wait(lambda: page.preparation_panel.last_preview is not None)
        self.assertFalse(page.preparation_panel.last_preview.executable)
        self.assertIn("AUCUNE_ECRITURE", page.preparation_panel.output.toPlainText())


if __name__ == "__main__":
    unittest.main()
