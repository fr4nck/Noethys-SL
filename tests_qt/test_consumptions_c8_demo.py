"""C8 : démonstration Windows réellement isolée des configurations Noethys."""
from __future__ import annotations

import os
import sqlite3
import unittest
from contextlib import closing
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, QThreadPool
from PySide6.QtWidgets import QApplication

from tools.qt_c8_fixture import C8FictiveDatabase, EXPECTED_ROWS, MARKER
from tools.qt_c8_windows_demo import C8DemoWindow


class C8DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.db = C8FictiveDatabase()
        self.addCleanup(self.db.close)
        self.window = C8DemoWindow(self.db.repository, theme="light", background=False)
        self.addCleanup(self.window.close)
        self.window.show()
        self.window.activate_demo()
        self.app.processEvents()

    def test_fixture_is_fully_synthetic_and_temp(self):
        with closing(sqlite3.connect(self.db.path)) as conn:
            self.assertEqual(
                conn.execute("SELECT token FROM c8_marker").fetchone(), (MARKER,),
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM consommations").fetchone()[0],
                EXPECTED_ROWS,
            )
        self.assertIn("noethys-qt-c8-fictif-", str(self.db.path.parent))
        self.assertEqual(len(self.db.repository.search(year=2026).rows), EXPECTED_ROWS)

    def test_calendar_controls_and_preflight_work_without_real_data(self):
        page = self.window.page
        self.assertEqual(page.calendar.selectedDate(), QDate(2026, 10, 2))
        self.assertEqual(page.list_page.model.rowCount(), 4)
        self.assertEqual(sum(count.count for count in page._date_counts), EXPECTED_ROWS)
        self.assertEqual(len(page.list_page.state_checks), 7)
        page.list_page.table.selectRow(0)
        page.preparation_panel.target_combo.setCurrentIndex(
            page.preparation_panel.target_combo.findData("present")
        )
        page.preparation_panel.preview_button.click()
        self.assertIsNotNone(page.preparation_panel.last_preview)
        self.assertFalse(page.preparation_panel.last_preview.executable)
        self.assertIn("AUCUNE_ECRITURE", page.preparation_panel.output.toPlainText())

    def test_theme_switch_keeps_selection_and_data(self):
        page = self.window.page
        page.list_page.table.selectRow(1)
        selection = page.list_page.model.rows[1].consumption_id
        self.window.theme_combo.setCurrentIndex(self.window.theme_combo.findData("dark"))
        self.app.processEvents()
        selected = page.list_page.table.selectionModel().selectedRows()
        self.assertEqual(page.list_page.model.rows[selected[0].row()].consumption_id, selection)
        self.assertEqual(page.list_page.model.rowCount(), 4)
        self.window.theme_combo.setCurrentIndex(self.window.theme_combo.findData("light"))
        self.assertTrue(self.window.banner.isVisible())

    def test_filters_and_resizing_never_remove_read_only_warning(self):
        page = self.window.page
        for dims in ((1000, 680), (1150, 760), (1320, 820)):
            with self.subTest(dims=dims):
                self.window.resize(*dims)
                self.app.processEvents()
                self.assertTrue(self.window.banner.isVisible())
                self.assertTrue(page.preparation_panel.warning.isVisible())
                self.assertGreater(page.list_page.table.viewport().width(), 150)
                self.assertGreater(page.calendar.width(), 150)
        page.list_page.none_button.click()
        self.assertEqual(page.list_page.model.rowCount(), 0)
        page.list_page.all_button.click()
        self.assertEqual(page.list_page.model.rowCount(), 4)

    def test_never_reads_noethys_configuration(self):
        with mock.patch(
            "noethys_qt.activities_native._load_config",
            side_effect=AssertionError("Config.json accessed!"),
        ):
            before = self.db.dump()
            self.window.refresh_button.click()
            self.window.focus_sample_day()
            self.app.processEvents()
            self.assertEqual(before, self.db.dump())


if __name__ == "__main__":
    unittest.main()
