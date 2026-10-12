import datetime as dt
import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from noethys_qt.activities_prototype import (
    ActivitiesWindow,
    ActivityRow,
    ActivityTableModel,
    SqliteActivityRepository,
)


class ActivitiesPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _remove_database(database: Path) -> None:
        # ``sqlite3.Connection`` n'est pas fermé par son context manager : sur
        # Windows le handle peut survivre jusqu'au prochain cycle GC, ce qui
        # suffit à bloquer unlink(). Le test force ce cycle avant le nettoyage.
        gc.collect()
        database.unlink(missing_ok=True)

    def _make_database(self) -> Path:
        handle, filename = tempfile.mkstemp(suffix="_DATA.dat")
        os.close(handle)
        database = Path(filename)
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                """
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY,
                    nom TEXT,
                    abrege TEXT,
                    date_debut TEXT,
                    date_fin TEXT
                )
                """
            )
            connection.executemany(
                "INSERT INTO activites VALUES (?, ?, ?, ?, ?)",
                [
                    (1, "Accueil de loisirs", "ALSH", "2026-01-01", "2999-01-01"),
                    (2, "Ancienne activité", "OLD", "2020-01-01", "2020-12-31"),
                    (3, "Activité illimitée", "ILL", "1977-01-01", "2999-01-01"),
                ],
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(self._remove_database, database)
        return database

    def test_sqlite_repository_reads_noethys_activity_shape(self):
        repository = SqliteActivityRepository(self._make_database())
        rows = repository.fetch()

        self.assertEqual([row.activity_id for row in rows], [2, 1, 3])
        self.assertEqual(rows[1].name, "Accueil de loisirs")
        self.assertEqual(rows[1].short_name, "ALSH")

    def test_open_filter_keeps_only_non_expired_activities(self):
        repository = SqliteActivityRepository(self._make_database())
        rows = repository.fetch(only_open=True)

        self.assertEqual({row.activity_id for row in rows}, {1, 3})

    def test_period_format_preserves_historic_unlimited_rule(self):
        row = ActivityRow(
            activity_id=3,
            name="Activité illimitée",
            short_name="ILL",
            start_date=dt.date(1977, 1, 1),
            end_date=dt.date(2999, 1, 1),
        )
        self.assertEqual(row.period, "Illimitée")

    def test_table_model_exposes_historic_columns_and_sort_values(self):
        row = ActivityRow(
            activity_id=7,
            name="Zumba",
            short_name="ZUM",
            start_date=dt.date(2026, 9, 1),
            end_date=dt.date(2027, 6, 30),
        )
        model = ActivityTableModel([row])

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.columnCount(), 4)
        self.assertEqual(model.data(model.index(0, 1)), "Zumba")
        self.assertEqual(
            model.data(model.index(0, 3), ActivityTableModel.SORT_ROLE),
            "2027-06-30",
        )

    def test_window_smoke_loads_real_sqlite_rows_without_wx_loop(self):
        repository = SqliteActivityRepository(self._make_database())
        window = ActivitiesWindow(repository, requested_theme="system")
        self.addCleanup(window.close)

        self.assertEqual(window.proxy.rowCount(), 3)
        self.assertTrue(window.table.isColumnHidden(0))
        self.assertEqual(
            window.table.selectionBehavior(),
            window.table.SelectionBehavior.SelectRows,
        )
        self.assertEqual(
            window.table.horizontalHeader().sectionResizeMode(1),
            window.table.horizontalHeader().ResizeMode.Stretch,
        )
        self.assertEqual(
            window.model.flags(window.model.index(0, 1)),
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable,
        )


if __name__ == "__main__":
    unittest.main()
