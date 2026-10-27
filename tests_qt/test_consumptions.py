"""Recette SQLite fictive et filtres du premier lot Consommations Qt."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from noethys_qt.consumptions_core import (
    ALL_STATES, OTHER, ConsumptionRepository, build_statement, state_label,
)
from noethys_qt.activity_editor import NativeActivityEditorRepository


class ConsumptionSqlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fictive_DATA.dat"
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, nom TEXT, prenom TEXT);
                CREATE TABLE activites (IDactivite INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE unites (IDunite INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE groupes (IDgroupe INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE prestations (IDprestation INTEGER PRIMARY KEY, montant TEXT);
                CREATE TABLE consommations (
                    IDconso INTEGER PRIMARY KEY, IDindividu INTEGER, IDactivite INTEGER,
                    IDunite INTEGER, IDgroupe INTEGER, IDprestation INTEGER,
                    date TEXT, etat TEXT, heure_debut TEXT, heure_fin TEXT
                );
                INSERT INTO individus VALUES (101, 'Dupont', 'Éloïse');
                INSERT INTO individus VALUES (102, 'Durand', 'Malo');
                INSERT INTO activites VALUES (1, 'Sport scolaire');
                INSERT INTO activites VALUES (2, 'Centre de loisirs');
                INSERT INTO unites VALUES (11, 'Séance');
                INSERT INTO groupes VALUES (21, 'Jeunes');
                INSERT INTO prestations VALUES (31, '12.345');
            """)
            data = [
                (1, 101, 1, "2026-01-01", "reservation"),
                (2, 102, 2, "2026-02-01", "present"),
                (3, 101, 1, "2026-02-08", "absentj"),
                (4, 102, 2, "2026-02-15", "absenti"),
                (5, 101, 1, "2026-03-01", "attente"),
                (6, 102, 2, "2026-04-01", "refus"),
                (7, 101, 1, "2026-05-01", None),
                (8, 102, 2, "2026-06-01", "nouveau_code"),
                (9, 101, 1, "2026-07-01", ""),
                (10, 101, 1, "2025-12-31", "reservation"),
                (11, 102, 2, "2027-01-01", "present"),
            ]
            db.executemany(
                """INSERT INTO consommations
                   (IDconso, IDindividu, IDactivite, IDunite, IDgroupe,
                    IDprestation, date, etat, heure_debut, heure_fin)
                   VALUES (?, ?, ?, 11, 21, 31, ?, ?, '09:00', '10:00')""",
                data,
            )
        self.repository = ConsumptionRepository(NativeActivityEditorRepository(self.path))

    def test_all_states_including_unknown_null_and_empty(self):
        result = self.repository.search(year=2026)
        self.assertEqual(len(result.rows), 9)
        self.assertFalse(result.has_more)
        self.assertEqual({row.consumption_id for row in result.rows}, set(range(1, 10)))
        self.assertEqual(state_label("nouveau_code"), "Autre : nouveau_code")
        self.assertEqual(state_label(None), "Non renseigné")

    def test_each_canonical_state_is_selectable(self):
        expected = {
            "reservation": 1, "present": 2, "absentj": 3,
            "absenti": 4, "attente": 5, "refus": 6,
        }
        for code, ident in expected.items():
            with self.subTest(code=code):
                rows = self.repository.search(year=2026, states=(code,)).rows
                self.assertEqual([row.consumption_id for row in rows], [ident])

    def test_other_state_includes_unknown_null_and_empty_only(self):
        rows = self.repository.search(year=2026, states={OTHER}).rows
        self.assertEqual({row.consumption_id for row in rows}, {7, 8, 9})

    def test_year_bounds_are_inclusive_for_december(self):
        self.assertEqual(
            [row.consumption_id for row in self.repository.search(year=2025).rows], [10]
        )
        self.assertEqual(
            [row.consumption_id for row in self.repository.search(year=2027).rows], [11]
        )

    def test_activity_filter_and_numeric_ids(self):
        rows = self.repository.search(year=2026, states=ALL_STATES, activity_id=1).rows
        self.assertEqual({row.consumption_id for row in rows}, {1, 3, 5, 7, 9})
        result = self.repository.search(year=2026, text="2")
        self.assertIn(2, {row.consumption_id for row in result.rows})

    def test_search_is_parameterized_and_escapes_wildcards(self):
        self.assertEqual(
            [r.consumption_id for r in self.repository.search(year=2026, text="Dupont").rows],
            [9, 7, 5, 3, 1],
        )
        self.assertEqual(self.repository.search(year=2026, text="%").rows, ())
        self.assertEqual(self.repository.search(year=2026, text="' OR 1=1 --").rows, ())
        statement, values = build_statement(year=2026, states=ALL_STATES, text="%", placeholder="%s")
        self.assertNotIn("1=1", statement)
        self.assertIn("%!%%", values)
        self.assertIn("LIMIT %s", statement)

    def test_limit_is_sql_side_with_no_misleading_count(self):
        result = self.repository.search(year=2026, limit=2)
        self.assertEqual([r.consumption_id for r in result.rows], [9, 8])
        self.assertTrue(result.has_more)
        self.assertEqual(result.rows[0].amount_label, "12,35 €")
        self.assertEqual(result.rows[0].hours_label, "09:00–10:00")

    def test_empty_selection_does_not_connect_to_database(self):
        with mock.patch.object(self.repository.editor_repository, "_connect", side_effect=AssertionError):
            result = self.repository.search(year=2026, states=())
        self.assertEqual(result.rows, ())

    def test_invalid_state_year_and_limit_are_rejected(self):
        with self.assertRaises(ValueError):
            build_statement(year=2026, states=("unexpected",))
        with self.assertRaises(ValueError):
            build_statement(year=1899, states=ALL_STATES)
        with self.assertRaises(ValueError):
            build_statement(year=2026, states=ALL_STATES, limit=50000)

    def test_sqlite_database_remains_unchanged(self):
        with sqlite3.connect(self.path) as db:
            before = list(db.iterdump())
        self.repository.search(year=2026, states={OTHER}, text="Durand")
        with sqlite3.connect(self.path) as db:
            after = list(db.iterdump())
        self.assertEqual(before, after)


class ConsumptionQtTests(ConsumptionSqlTests):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_page_checkboxes_are_clickable_and_never_disappear(self):
        from noethys_qt.consumptions_ui import ConsumptionPage
        page = ConsumptionPage(self.repository, background=False)
        self.addCleanup(page.close)
        page.year_spin.setValue(2026)
        page.activate()
        self.assertEqual(len(page.state_checks), 7)
        self.assertEqual(page.model.rowCount(), 9)
        page.none_button.click()
        self.assertEqual(page.model.rowCount(), 0)
        self.assertIn("Aucun état", page.summary.text())
        page.state_checks["absentj"].click()
        self.assertEqual([row.consumption_id for row in page.model.rows], [3])
        page.all_button.click()
        self.assertEqual(page.model.rowCount(), 9)

    def test_page_read_only_table_exposes_faithful_amount_and_id(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QAbstractItemView
        from noethys_qt.consumptions_ui import ConsumptionPage
        page = ConsumptionPage(self.repository, background=False)
        self.addCleanup(page.close)
        page.year_spin.setValue(2026)
        page.activate()
        self.assertEqual(page.model.data(page.model.index(0, 0)), "9")
        self.assertEqual(page.model.data(page.model.index(0, 10)), "12,35 €")
        self.assertEqual(
            page.table.editTriggers(), QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.assertEqual(
            page.model.data(page.model.index(0, 0), int(Qt.ItemDataRole.UserRole)).consumption_id,
            9,
        )


if __name__ == "__main__":
    unittest.main()
