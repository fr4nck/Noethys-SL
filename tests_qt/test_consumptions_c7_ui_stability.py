"""C7 : stress d'interactions Qt et stabilité des modèles en lecture seule.

Tous les tests utilisent les fixtures SQLite fictives du lot C2.
Ces contrôles ne démontrent pas à eux seuls l'absence de scintillement
sur un vrai poste Windows, mais détectent les resets et reflows évitables.
"""
from __future__ import annotations

import os
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from noethys_qt.consumptions_calendar_ui import ConsumptionCalendarPage
from noethys_qt.consumptions_core import ConsumptionResult
import test_consumptions_calendar as c2


class C7VisualStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Réutiliser la fixture C2 sans exposer les 9 tests du parent à
        # une seconde découverte unittest (la classe n'en hérite pas).
        self.fixture = c2.ConsumptionCalendarSqlTests(
            "test_month_counts_are_exact_and_bound_to_month"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.page = ConsumptionCalendarPage(self.fixture.core, background=False)
        self.addCleanup(self.page.close)
        self.page.resize(1240, 800)
        self.page.show()
        self.app.processEvents()
        self.page.activate()
        self.page.list_page.year_spin.setValue(2026)
        self.page.calendar.setSelectedDate(QDate(2026, 10, 2))
        self.app.processEvents()
        self.assertEqual(
            {row.consumption_id for row in self.page.list_page.model.rows},
            {3, 4},
        )

    def _selected_id(self):
        indices = self.page.list_page.table.selectionModel().selectedRows()
        if not indices:
            return None
        return self.page.list_page.model.rows[indices[0].row()].consumption_id

    def test_repeated_refresh_preserves_selection_and_avoids_model_resets(self):
        table = self.page.list_page.table
        table.selectRow(1)
        selected = self._selected_id()
        self.assertEqual(selected, 3)
        spy = QSignalSpy(self.page.list_page.model.modelReset)
        for _ in range(15):
            self.page.refresh()
            self.app.processEvents()
        self.assertEqual(spy.count(), 0)
        self.assertEqual(self._selected_id(), selected)
        self.assertIn("Consommation #3", self.page.details_label.text())
        self.assertTrue(table.isEnabled())

    def test_month_refresh_does_not_rebuild_unchanged_day_list(self):
        marker = self.page.day_list.item(1)
        self.assertIsNotNone(marker)
        count = self.page.day_list.count()
        for _ in range(8):
            self.page.refresh_month()
            self.app.processEvents()
        self.assertIs(self.page.day_list.item(1), marker)
        self.assertEqual(self.page.day_list.count(), count)
        self.assertEqual(sum(row.count for row in self.page._date_counts), 5)

    def test_bulk_state_select_recomputes_month_once_not_seven_times(self):
        with patch.object(
            self.page.calendar_repository, "month_counts",
            wraps=self.page.calendar_repository.month_counts,
        ) as query:
            self.page.list_page.none_button.click()
            self.assertEqual(query.call_count, 0)
            self.assertEqual(self.page.list_page.model.rowCount(), 0)
            self.assertEqual(self.page.day_list.count(), 0)
            self.page.list_page.all_button.click()
            self.assertEqual(query.call_count, 1)
            self.assertEqual(len(self.page.list_page.selected_states), 7)
            self.page.list_page.all_button.click()
            self.assertEqual(query.call_count, 1)
        self.assertEqual(
            {row.consumption_id for row in self.page.list_page.model.rows},
            {3, 4},
        )

    def test_data_change_keeps_id_selection_and_updates_visible_detail(self):
        self.page.list_page.table.selectRow(1)
        self.assertEqual(self._selected_id(), 3)
        spy = QSignalSpy(self.page.list_page.model.modelReset)
        # Mutation de fixture seulement, jamais via l'interface Qt.
        with closing(sqlite3.connect(self.fixture.path)) as connection, connection:
            connection.execute("UPDATE prestations SET montant='26.00' WHERE IDprestation=31")
        self.page.list_page.refresh()
        self.app.processEvents()
        self.assertEqual(spy.count(), 1)
        self.assertEqual(self._selected_id(), 3)
        self.assertIn("26,00 €", self.page.details_label.text())
        self.assertFalse(self.page.preparation_panel.preview_button.isEnabled())

    def test_state_filter_removing_selected_row_clears_detail_safely(self):
        self.page.list_page.table.selectRow(1)
        self.assertEqual(self._selected_id(), 3)
        self.page.list_page.none_button.click()
        self.page.list_page.state_checks["present"].click()
        self.assertIsNone(self._selected_id())
        self.assertEqual(self.page.list_page.model.rowCount(), 0)
        self.assertIn("Sélectionnez", self.page.details_label.text())
        self.assertIsNone(self.page.preparation_panel.last_preview)

    def test_keyboard_enter_selects_day_and_arrow_moves_between_consumptions(self):
        self.page.calendar.setSelectedDate(QDate(2026, 10, 1))
        self.page.day_list.setCurrentRow(1)  # 02/10
        self.page.day_list.setFocus()
        QTest.keyClick(self.page.day_list, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(self.page.calendar.selectedDate(), QDate(2026, 10, 2))
        self.assertEqual(self.page.list_page.model.rowCount(), 2)
        table = self.page.list_page.table
        table.selectRow(0)
        table.setFocus()
        QTest.keyClick(table, Qt.Key.Key_Down)
        self.app.processEvents()
        self.assertEqual(self._selected_id(), 3)
        self.assertIn("Consommation #3", self.page.details_label.text())
        self.assertTrue(table.editTriggers() == table.EditTrigger.NoEditTriggers)

    def test_rapid_date_activity_and_resize_changes_end_in_coherent_state(self):
        for cycle in range(12):
            self.page.resize(1000 + (cycle % 3) * 160, 675 + (cycle % 2) * 105)
            self.page.calendar.setSelectedDate(QDate(2026, 10, 1 + cycle % 2))
            idx = self.page.activity_combo.findData(1 if cycle % 2 else 2)
            self.page.activity_combo.setCurrentIndex(idx)
            self.app.processEvents()
            self.assertGreater(self.page.list_page.table.viewport().width(), 120)
            self.assertEqual(self.page.list_page.year_spin.value(), 2026)
            self.assertTrue(self.page.list_page.table.isEnabled())
        self.page.activity_combo.setCurrentIndex(0)
        self.page.calendar.setSelectedDate(QDate(2026, 10, 2))
        self.app.processEvents()
        self.assertEqual(
            {row.consumption_id for row in self.page.list_page.model.rows},
            {3, 4},
        )
        self.assertEqual(sum(row.count for row in self.page._date_counts), 5)

    def test_stale_list_and_month_results_cannot_replace_current_selection(self):
        self.page.list_page.table.selectRow(1)
        old_token = self.page.list_page._token - 1
        old_month_token = self.page._month_token - 1
        month_before = self.page._date_counts
        fake = ConsumptionResult((), False)
        self.page.list_page._completed(old_token, fake, "")
        self.page._month_completed(old_month_token, (), "")
        self.assertEqual(self._selected_id(), 3)
        self.assertEqual(len(self.page.list_page.model.rows), 2)
        self.assertEqual(self.page._date_counts, month_before)

    def test_column_widths_remain_stable_on_filters_and_refresh(self):
        table = self.page.list_page.table
        before = [table.columnWidth(n) for n in (0, 1, 2, 4, 5, 7, 8, 9, 10)]
        self.page.list_page.none_button.click()
        self.page.list_page.all_button.click()
        self.page.refresh()
        self.app.processEvents()
        after = [table.columnWidth(n) for n in (0, 1, 2, 4, 5, 7, 8, 9, 10)]
        self.assertEqual(before, after)
        self.assertTrue(self.page.preparation_panel.warning.isVisible())


if __name__ == "__main__":
    unittest.main()
