"""C11 : liaison EXACTE individu/inscription/consommations sur base C8 fictive.

Aucune importation wx ni configuration réelle. La seule mutation d'une ligne
SQLite, dans un test adversarial, porte sur le TemporaryDirectory de recette.
"""
from __future__ import annotations

import os
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from noethys_qt.consumptions_core import ALL_STATES, ConsumptionResult, build_statement
from noethys_qt.consumptions_calendar_core import build_month_statement
from tools.qt_c8_fixture import C8FictiveDatabase, EXPECTED_ROWS
from tools.qt_c8_windows_demo import C8DemoWindow


class C11ExactContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.fixture = C8FictiveDatabase()
        self.addCleanup(self.fixture.close)
        self.window = C8DemoWindow(
            self.fixture.repository, fictive_db=self.fixture, background=False,
        )
        self.addCleanup(self.window.close)
        self.window.show()
        self.window.activate_demo()
        self.app.processEvents()
        self.business = self.window.business_page
        self.page = self.window.page
        self.assertEqual(self.page.list_page.model.rowCount(), 4)

    def _current_ids(self):
        return {r.consumption_id for r in self.page.list_page.model.rows}

    def _expect_scope(self, individual_id, inscription_id, size):
        self.assertEqual(self.page._record_individual_id, individual_id)
        self.assertEqual(self.page._record_inscription_id, inscription_id)
        self.assertEqual(self.page.list_page.model.rowCount(), size)
        self.assertEqual(len(self._current_ids()), size)
        # La famille / l'inscription ne doivent PAS être déduites du nom.
        self.assertTrue(all(
            row.individual_id == individual_id
            for row in self.page.list_page.model.rows
        ))
        self.assertEqual(sum(r.count for r in self.page._date_counts), size)
        self.assertTrue(self.page.record_filter_label.isVisible())
        self.assertTrue(self.page.clear_record_button.isVisible())

    def test_individual_button_opens_28_exact_rows_and_month_counts(self):
        before = self.fixture.dump()
        self.window.tabs.setCurrentWidget(self.business)
        self.business.show_domain("individus")
        row = next(i for i in range(self.business.table.rowCount())
                   if self.business.table.item(i, 0).data(
                       Qt.ItemDataRole.UserRole) == 12)
        self.business.table.selectRow(row)
        self.assertTrue(self.business.individual_consumptions_button.isVisible())
        self.business.individual_consumptions_button.click()
        self.assertIs(self.window.tabs.currentWidget(), self.page)
        self._expect_scope(12, None, 28)
        self.assertIn("Individu #12", self.page.record_filter_label.text())
        self.assertEqual(self.fixture.dump(), before)

    def test_inscription_button_uses_both_ids_not_the_displayed_name(self):
        self.window.tabs.setCurrentWidget(self.business)
        self.business.show_domain("inscriptions", individual_id=12)
        self.assertEqual(self.business.table.rowCount(), 1)
        # Les chaînes de table ne sont PAS une source d'identifiant.
        self.business.table.item(0, 1).setText("Nom de substitution fictif")
        self.business._open_related(0, 0)
        self.assertIs(self.window.tabs.currentWidget(), self.page)
        self._expect_scope(12, 503, 28)
        self.assertIn("Inscription #503", self.page.record_filter_label.text())

    def test_crossed_ids_do_not_fall_back_to_global_results(self):
        self.page.focus_record(individual_id=10, inscription_id=503, year=2026)
        self.assertEqual(self._current_ids(), set())
        self.assertEqual(sum(r.count for r in self.page._date_counts), 0)
        self.assertEqual(self.page._record_inscription_id, 503)
        self.assertIn("0 consommation", self.page.list_page.summary.text())

    def test_adversarial_foreign_individual_in_same_inscription_is_excluded(self):
        # Écriture volontaire UNIQUEMENT sur le fichier temporaire fictif.
        with closing(sqlite3.connect(self.fixture.path)) as connection:
            connection.execute(
                "UPDATE consommations SET IDindividu=10 WHERE IDconso=3"
            )
            connection.commit()
        self.page.focus_record(individual_id=12, inscription_id=503, year=2026)
        self._expect_scope(12, 503, 27)
        self.assertNotIn(3, self._current_ids())
        self.assertEqual(self.fixture.repository.search(
            year=2026, individual_id=12, inscription_id=503
        ).rows, self.page.list_page.model.rows)

    def test_scope_reset_clears_obsolete_day_activity_text_states_and_year(self):
        self.page.list_page.year_spin.setValue(2025)
        self.page.activity_combo.setCurrentIndex(
            self.page.activity_combo.findData(2)
        )
        self.page.list_page.search_edit.setText("Recherche sans résultat")
        self.page.list_page.none_button.click()
        self.window._open_business_consumptions(
            "consommations", individual_id=12, inscription_id=503
        )
        self._expect_scope(12, 503, 28)
        self.assertEqual(self.page.list_page.year_spin.value(), 2026)
        self.assertEqual(self.page.calendar.yearShown(), 2026)
        self.assertIsNone(self.page.activity_combo.currentData())
        self.assertEqual(self.page.list_page.search_edit.text(), "")
        self.assertFalse(self.page.only_day.isChecked())
        self.assertEqual(self.page.list_page.selected_states, ALL_STATES)

    def test_one_search_and_one_month_query_for_single_context_transition(self):
        with patch.object(
            self.fixture.repository, "search",
            wraps=self.fixture.repository.search,
        ) as searching, patch.object(
            self.page.calendar_repository, "month_counts",
            wraps=self.page.calendar_repository.month_counts,
        ) as month:
            self.page.focus_record(individual_id=12, inscription_id=503, year=2026)
            self.assertEqual(searching.call_count, 1)
            self.assertEqual(month.call_count, 1)
            keywords = searching.call_args.kwargs
            self.assertEqual(keywords["individual_id"], 12)
            self.assertEqual(keywords["inscription_id"], 503)
            self.assertEqual(
                month.call_args.kwargs["inscription_id"], 503
            )

    def test_clear_context_removes_exact_filter_and_restores_global_year(self):
        before = self.fixture.dump()
        self.page.focus_record(individual_id=12, inscription_id=503, year=2026)
        self.page.clear_record_button.click()
        self.assertIsNone(self.page._record_individual_id)
        self.assertIsNone(self.page._record_inscription_id)
        self.assertFalse(self.page.record_filter_label.isVisible())
        self.assertFalse(self.page.clear_record_button.isVisible())
        self.assertEqual(self.page.list_page.model.rowCount(), EXPECTED_ROWS)
        self.assertEqual(sum(r.count for r in self.page._date_counts), EXPECTED_ROWS)
        self.assertEqual(self.fixture.dump(), before)

    def test_invalid_ids_and_year_rejected_without_state_changes(self):
        self.page.focus_record(individual_id=12, year=2026)
        old = (self.page._record_individual_id, self.page._record_inscription_id,
               self.page.list_page.model.rows)
        for values in (
            {"individual_id": 0},
            {"individual_id": False},
            {"individual_id": "12 OR 1=1"},
            {"inscription_id": -5},
            {"inscription_id": True},
            {"year": 1899},
            {"year": 2099},
            {"year": True},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.page.focus_record(**values)
            self.assertEqual(
                (self.page._record_individual_id, self.page._record_inscription_id,
                 self.page.list_page.model.rows), old
            )

    def test_old_async_responses_cannot_replace_latest_id_scope(self):
        self.page.focus_record(individual_id=10, year=2026)
        token = self.page.list_page._token
        month_token = self.page._month_token
        self.page.focus_record(individual_id=12, inscription_id=503, year=2026)
        rows = self.page.list_page.model.rows
        counts = self.page._date_counts
        self.page.list_page._completed(token, ConsumptionResult((), False), "")
        self.page._month_completed(month_token, (), "")
        self.assertEqual(self.page.list_page.model.rows, rows)
        self.assertEqual(self.page._date_counts, counts)
        self._expect_scope(12, 503, 28)

    def test_preflight_remains_blocked_on_exact_link(self):
        before = self.fixture.dump()
        self.page.focus_record(individual_id=12, inscription_id=503, year=2026)
        self.page.list_page.table.selectRow(0)
        panel = self.page.preparation_panel
        panel.target_combo.setCurrentIndex(
            panel.target_combo.findData("present")
        )
        panel.preview_button.click()
        self.assertIsNotNone(panel.last_preview)
        self.assertFalse(panel.last_preview.executable)
        self.assertIn("AUCUNE_ECRITURE", panel.output.toPlainText())
        self.assertEqual(self.fixture.dump(), before)

    def test_sql_uses_two_parameterized_exact_conditions(self):
        for marker in ("?", "%s"):
            with self.subTest(marker=marker):
                sql, arguments = build_statement(
                    year=2026, states=ALL_STATES,
                    individual_id=12, inscription_id=503,
                    placeholder=marker,
                )
                self.assertIn("c.IDindividu = " + marker, sql)
                self.assertIn("c.IDinscription = " + marker, sql)
                self.assertNotIn("503", sql)
                self.assertIn(12, arguments)
                self.assertIn(503, arguments)
                month_sql, month_args = build_month_statement(
                    year=2026, month=10, states=ALL_STATES,
                    individual_id=12, inscription_id=503,
                    placeholder=marker,
                )
                self.assertIn("c.IDindividu = " + marker, month_sql)
                self.assertIn("c.IDinscription = " + marker, month_sql)
                self.assertNotIn("503", month_sql)
                self.assertIn(12, month_args)
                self.assertIn(503, month_args)


if __name__ == "__main__":
    unittest.main()
