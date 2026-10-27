"""C10 : fiches et navigation contextualisée, données intégralement fictives."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from tools.qt_c8_fixture import C8FictiveDatabase
from tools.qt_c8_windows_demo import C8DemoWindow


class C10BusinessDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = C8FictiveDatabase()
        self.addCleanup(self.db.close)
        self.window = C8DemoWindow(
            self.db.repository, fictive_db=self.db, background=False
        )
        self.addCleanup(self.window.close)
        self.window.show()
        self.window.activate_demo()
        self.window.tabs.setCurrentWidget(self.window.business_page)
        self.app.processEvents()
        self.page = self.window.business_page

    def test_initial_family_detail_shows_raw_indicators_not_inferred_roles(self):
        self.assertEqual(self.page.domain, "familles")
        self.assertEqual(self.page.table.rowCount(), 2)
        self.assertIn("Famille #100", self.page.detail_title.text())
        details = self.page.detail_body.text()
        self.assertIn("Camille Exemple", details)
        self.assertIn("Alex Démonstration", details)
        self.assertIn("catégorie brute=", details)
        self.assertNotIn("Représentant", details)
        self.assertNotIn("Enfant", details)

    def test_family_row_drills_only_to_its_members(self):
        self.page.table.selectRow(1)  # famille #101
        self.page.related_button.click()
        self.assertEqual(self.page.domain, "individus")
        self.assertIn("famille #101", self.page.title.text())
        self.assertEqual(self.page.table.rowCount(), 2)
        visible = [
            self.page.table.item(i, 1).text()
            for i in range(self.page.table.rowCount())
        ]
        self.assertEqual(set(visible), {"Fictif", "Test"})
        self.assertNotIn("Exemple", visible)

    def test_individual_drills_only_to_its_inscriptions(self):
        self.page.show_domain("individus")
        self.assertEqual(self.page.table.rowCount(), 4)
        # Identifiants conservés dans UserRole, pas dépendants d'un index.
        row = next(
            i for i in range(self.page.table.rowCount())
            if self.page.table.item(i, 0).data(Qt.ItemDataRole.UserRole) == 12
        )
        self.page.table.selectRow(row)
        self.assertIn("Alex Démonstration", self.page.detail_title.text())
        self.assertIn("Adresse référencée", self.page.detail_body.text())
        self.page.related_button.click()
        self.assertEqual(self.page.domain, "inscriptions")
        self.assertIn("individu #12", self.page.title.text())
        self.assertEqual(self.page.table.rowCount(), 1)
        self.assertEqual(self.page.table.item(0, 0).text(), "503")

    def test_activity_drills_only_to_its_inscriptions(self):
        self.page.show_domain("activites")
        self.assertEqual(self.page.table.rowCount(), 2)
        index = next(
            i for i in range(2)
            if self.page.table.item(i, 0).text() == "2"
        )
        self.page._open_related(index, 0)
        self.assertEqual(self.page.domain, "inscriptions")
        self.assertIn("activité #2", self.page.title.text())
        self.assertEqual(
            {self.page.table.item(i, 0).text() for i in range(self.page.table.rowCount())},
            {"502", "504"},
        )

    def test_back_restores_previous_family_and_selection(self):
        self.page.table.selectRow(1)
        self.page._open_related(1, 0)
        self.page._open_related(0, 0)
        self.assertEqual(self.page.domain, "inscriptions")
        self.page.go_back()
        self.assertEqual(self.page.domain, "individus")
        self.assertEqual(self.page.table.rowCount(), 2)
        self.page.go_back()
        self.assertEqual(self.page.domain, "familles")
        self.assertEqual(self.page._selected_id(), 101)
        self.assertFalse(self.page.back_button.isEnabled())

    def test_search_filters_visible_items_without_writing_or_requerying(self):
        before = self.db.dump()
        self.page.show_domain("individus")
        with patch.object(self.page, "_read", side_effect=AssertionError("New SQL read")):
            self.page.search.setText("Fictif")
            self.assertEqual(self.page.table.rowCount(), 1)
            self.assertEqual(self.page.table.item(0, 1).text(), "Fictif")
            self.page.search.setText("Introuvable")
            self.assertEqual(self.page.table.rowCount(), 0)
            self.assertFalse(self.page.related_button.isEnabled())
            self.page.search.clear()
            self.assertEqual(self.page.table.rowCount(), 4)
        self.assertEqual(before, self.db.dump())

    def test_opening_calendar_never_implies_exact_registration_filter(self):
        self.page.show_domain("inscriptions", individual_id=12)
        self.assertEqual(self.page.table.rowCount(), 1)
        self.assertIn("calendrier suivant est global", self.page.detail_body.text())
        self.page._open_related(0, 0)
        self.assertIs(self.window.tabs.currentWidget(), self.window.page)
        self.assertEqual(self.window.page.list_page.model.rowCount(), 4)

    def test_no_real_database_path_substitution(self):
        original = self.db.path
        with tempfile.TemporaryDirectory() as outside:
            foreign = Path(outside) / "another.sqlite"
            with closing(sqlite3.connect(foreign)) as conn:
                conn.execute("CREATE TABLE c8_marker (token TEXT)")
                conn.commit()
            self.db.path = foreign
            try:
                with self.assertRaises(RuntimeError):
                    self.page.show_domain("individus")
            finally:
                self.db.path = original
            self.assertEqual(self.page.domain, "familles")
            with closing(sqlite3.connect(foreign)) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT name FROM sqlite_master WHERE name='c8_marker'"
                    ).fetchone(), ("c8_marker",),
                )

    def test_keyboard_activation_and_no_editor(self):
        self.page.show_domain("familles")
        self.page.table.selectRow(0)
        self.page.table.setFocus()
        QTest.keyClick(self.page.table, Qt.Key.Key_Return)
        self.app.processEvents()
        # La touche Entrée agit via itemActivated selon le style/OS Qt ;
        # le double clic explicite reste le chemin principal.
        if self.page.domain == "familles":
            self.page._open_related(0, 0)
        self.assertEqual(self.page.domain, "individus")
        self.assertEqual(self.page.table.editTriggers(), self.page.table.EditTrigger.NoEditTriggers)

    def test_theme_and_resize_preserve_domain_detail_and_snapshot(self):
        initial = self.db.dump()
        self.page.show_domain("individus", family_id=100)
        self.page.table.selectRow(0)
        ident = self.page._selected_id()
        for theme in ("dark", "light"):
            self.window.theme_combo.setCurrentIndex(
                self.window.theme_combo.findData(theme)
            )
            self.window.resize(1050, 720)
            self.app.processEvents()
            self.assertEqual(self.page._selected_id(), ident)
            self.assertTrue(self.page.detail_title.text())
            self.assertTrue(self.window.banner.isVisible())
        self.assertEqual(self.db.dump(), initial)


if __name__ == "__main__":
    unittest.main()
