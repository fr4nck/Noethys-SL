"""Lot Qt C2 : calendrier indépendant des 300 premières consommations."""
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
from noethys_qt.consumptions_core import ALL_STATES, OTHER, ConsumptionRepository, build_statement
from noethys_qt.consumptions_calendar_core import (
    ConsumptionCalendarRepository, build_month_statement,
)


class ConsumptionCalendarSqlTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "recette-fictive_DATA.dat"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, nom TEXT, prenom TEXT);
                CREATE TABLE activites (IDactivite INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE unites (IDunite INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE groupes (IDgroupe INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE evenements (IDevenement INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE prestations (IDprestation INTEGER PRIMARY KEY, montant TEXT);
                CREATE TABLE consommations (
                    IDconso INTEGER PRIMARY KEY, IDindividu INTEGER, IDactivite INTEGER,
                    IDunite INTEGER, IDgroupe INTEGER, IDprestation INTEGER,
                    date TEXT, etat TEXT, heure_debut TEXT, heure_fin TEXT, IDevenement INTEGER
                );
                INSERT INTO individus VALUES (10, 'Martin', 'Camille');
                INSERT INTO individus VALUES (11, 'Le Gall', 'Morgan');
                INSERT INTO activites VALUES (1, 'Sport scolaire');
                INSERT INTO activites VALUES (2, 'Gymnastique');
                INSERT INTO unites VALUES (11, 'Créneau');
                INSERT INTO groupes VALUES (21, 'Jeunes');
                INSERT INTO evenements VALUES (41, 'Tournoi du samedi');
                INSERT INTO prestations VALUES (31, '24.005');
            """)
            db.executemany(
                """INSERT INTO consommations
                   (IDconso, IDindividu, IDactivite, IDunite, IDgroupe,
                    IDprestation, date, etat, heure_debut, heure_fin, IDevenement)
                   VALUES (?, ?, ?, 11, 21, 31, ?, ?, '10:00', '11:00', ?)""",
                [
                    (1, 10, 1, "2026-10-01", "reservation", None),
                    (2, 11, 2, "2026-10-01", "present", None),
                    (3, 10, 1, "2026-10-02", "absentj", 41),
                    (4, 10, 1, "2026-10-02", None, None),
                    (5, 11, 2, "2026-10-17", "autre_etat", None),
                    (6, 10, 1, "2026-09-30", "reservation", None),
                    (7, 11, 1, "2026-11-01", "reservation", None),
                    (8, 10, 1, "2025-10-01", "reservation", None),
                ],
            )
        self.core = ConsumptionRepository(NativeActivityEditorRepository(self.path))
        self.calendar = ConsumptionCalendarRepository(self.core)

    def test_month_counts_are_exact_and_bound_to_month(self):
        counts = self.calendar.month_counts(year=2026, month=10)
        self.assertEqual([(x.date.isoformat(), x.count) for x in counts], [
            ("2026-10-01", 2), ("2026-10-02", 2), ("2026-10-17", 1),
        ])

    def test_activity_filter_and_six_states_are_consistent_with_list(self):
        for state in ("reservation", "present", "absentj", "absenti", "attente", "refus", OTHER):
            with self.subTest(state=state):
                items = self.core.search(year=2026, states=(state,), activity_id=1).rows
                counts = self.calendar.month_counts(
                    year=2026, month=10, states=(state,), activity_id=1
                )
                expected = sum(row.date.startswith("2026-10-") for row in items)
                self.assertEqual(sum(x.count for x in counts), expected)
        activities = self.calendar.list_activities()
        self.assertEqual(activities, ((2, "Gymnastique"), (1, "Sport scolaire")))

    def test_unknown_null_and_case_day_boundaries(self):
        rows = self.calendar.month_counts(year=2026, month=10, states={OTHER})
        self.assertEqual([(r.date.day, r.count) for r in rows], [(2, 1), (17, 1)])
        self.assertEqual(self.calendar.month_counts(year=2026, month=9)[0].date.day, 30)
        self.assertEqual(self.calendar.month_counts(year=2026, month=11)[0].date.day, 1)
        self.assertEqual(sum(x.count for x in self.calendar.month_counts(year=2025, month=10)), 1)

    def test_search_filter_matches_day_counts_not_only_table(self):
        for query in ("Martin", "Camille", "Sport", "1", "%", "' OR 1=1 --"):
            with self.subTest(query=query):
                list_rows = self.core.search(year=2026, text=query).rows
                month = self.calendar.month_counts(year=2026, month=10, text=query)
                self.assertEqual(
                    sum(r.count for r in month),
                    sum(format(r.date)[:7] == "2026-10" for r in list_rows),
                )
        statement, values = build_month_statement(
            year=2026, month=10, states={OTHER}, text="%", placeholder="%s"
        )
        self.assertIn("GROUP BY c.date", statement)
        self.assertIn("%!%%", values)
        self.assertNotIn("1=1", statement)

    def test_day_exact_filter_never_overflows_year(self):
        rows = self.core.search(year=2026, day=dt.date(2026, 10, 2)).rows
        self.assertEqual([r.consumption_id for r in rows], [4, 3])
        self.assertEqual(rows[1].event_id, 41)
        self.assertEqual(rows[1].event_name, "Tournoi du samedi")
        self.assertIsNone(rows[0].event_id)
        with self.assertRaises(ValueError):
            build_statement(year=2025, day=dt.date(2026, 10, 2), states=ALL_STATES)
        with self.assertRaises(ValueError):
            build_statement(year=2026, day="2026-10-02", states=ALL_STATES)

    def test_calendar_does_not_infer_count_from_bounded_rows(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany(
                """INSERT INTO consommations
                   (IDconso, IDindividu, IDactivite, IDunite, IDgroupe,
                    IDprestation, date, etat, heure_debut, heure_fin, IDevenement)
                   VALUES (?, 10, 1, 11, 21, 31, '2026-10-03', 'present', NULL, NULL, NULL)""",
                [(1000 + i,) for i in range(305)],
            )
        table = self.core.search(year=2026)
        self.assertTrue(table.has_more)
        self.assertEqual(len(table.rows), 300)
        counts = self.calendar.month_counts(year=2026, month=10)
        self.assertEqual(sum(day.count for day in counts), 310)
        self.assertEqual([day.count for day in counts if day.date.day == 3], [305])

    def test_invalid_month_activity_and_states_are_rejected(self):
        for arguments in (
            {"year": 2026, "month": 0, "states": ALL_STATES},
            {"year": 2026, "month": 13, "states": ALL_STATES},
            {"year": 2099, "month": 10, "states": ALL_STATES},
            {"year": 2026, "month": 10, "states": ("inconnu",)},
            {"year": 2026, "month": 10, "states": ALL_STATES, "activity_id": -1},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                build_month_statement(**arguments)

    def test_empty_state_filter_never_connects(self):
        with mock.patch.object(self.core.editor_repository, "_connect", side_effect=AssertionError):
            self.assertEqual(self.calendar.month_counts(year=2026, month=10, states=()), ())

    def test_no_write_before_and_after_month_read(self):
        with closing(sqlite3.connect(self.path)) as db:
            before = list(db.iterdump())
        self.core.search(year=2026, day=dt.date(2026, 10, 1))
        self.calendar.month_counts(year=2026, month=10)
        self.calendar.list_activities()
        with closing(sqlite3.connect(self.path)) as db:
            after = list(db.iterdump())
        self.assertEqual(before, after)


class ConsumptionCalendarQtTests(ConsumptionCalendarSqlTests):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_calendar_drills_into_date_and_returns_to_year(self):
        from PySide6.QtCore import QDate
        from noethys_qt.consumptions_calendar_ui import ConsumptionCalendarPage
        page = ConsumptionCalendarPage(self.core, background=False)
        self.addCleanup(page.close)
        page.activate()
        page.list_page.year_spin.setValue(2026)
        page.calendar.setSelectedDate(QDate(2026, 10, 2))
        self.assertTrue(page.only_day.isChecked())
        self.assertEqual({r.consumption_id for r in page.list_page.model.rows}, {3, 4})
        self.assertEqual(sum(d.count for d in page._date_counts), 5)
        page.year_button.click()
        self.assertFalse(page.only_day.isChecked())
        self.assertEqual(len(page.list_page.model.rows), 7)

    def test_calendar_activity_filter_and_event_detail(self):
        from PySide6.QtCore import QDate
        from noethys_qt.consumptions_calendar_ui import ConsumptionCalendarPage
        page = ConsumptionCalendarPage(self.core, background=False)
        self.addCleanup(page.close)
        page.activate()
        page.list_page.year_spin.setValue(2026)
        page.calendar.setSelectedDate(QDate(2026, 10, 2))
        index = page.activity_combo.findData(1)
        self.assertGreaterEqual(index, 1)
        page.activity_combo.setCurrentIndex(index)
        self.assertEqual([r.consumption_id for r in page.list_page.model.rows], [4, 3])
        page.list_page.table.selectRow(1)
        self.assertIn("Événement #41", page.details_label.text())
        page.list_page.table.selectRow(0)
        self.assertIn("Aucun événement lié", page.details_label.text())
        self.assertEqual(sum(d.count for d in page._date_counts), 3)
        self.assertEqual(page.calendar.selectedDate(), QDate(2026, 10, 2))

    def test_state_changes_update_calendar_and_table_coherently(self):
        from PySide6.QtCore import QDate
        from noethys_qt.consumptions_calendar_ui import ConsumptionCalendarPage
        page = ConsumptionCalendarPage(self.core, background=False)
        self.addCleanup(page.close)
        page.activate()
        page.list_page.year_spin.setValue(2026)
        page.calendar.setSelectedDate(QDate(2026, 10, 1))
        page.list_page.none_button.click()
        self.assertEqual(page.list_page.model.rowCount(), 0)
        self.assertEqual(page._date_counts, ())
        page.list_page.state_checks["reservation"].click()
        self.assertEqual([r.consumption_id for r in page.list_page.model.rows], [1])
        self.assertEqual(sum(r.count for r in page._date_counts), 1)

    def test_month_change_is_not_confused_with_another_year(self):
        from PySide6.QtCore import QDate
        from noethys_qt.consumptions_calendar_ui import ConsumptionCalendarPage
        page = ConsumptionCalendarPage(self.core, background=False)
        self.addCleanup(page.close)
        page.activate()
        page.calendar.setSelectedDate(QDate(2025, 10, 1))
        self.assertEqual(page.list_page.year_spin.value(), 2025)
        self.assertEqual([r.consumption_id for r in page.list_page.model.rows], [8])
        self.assertEqual(sum(r.count for r in page._date_counts), 1)


if __name__ == "__main__":
    unittest.main()
