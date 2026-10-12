import datetime as dt
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_calendar import (
    ActivityCalendarPage,
    ActivityCalendarRepository,
    CalendarEvent,
)
from noethys_qt.activity_editor import NativeActivityEditorRepository


class ActivityCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _database(self) -> Path:
        handle, filename = tempfile.mkstemp(suffix="_DATA.dat")
        os.close(handle)
        path = Path(filename)
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY,
                    nom TEXT,
                    date_debut TEXT,
                    date_fin TEXT
                );
                CREATE TABLE groupes (
                    IDgroupe INTEGER PRIMARY KEY,
                    IDactivite INTEGER,
                    nom TEXT,
                    ordre INTEGER
                );
                CREATE TABLE unites (
                    IDunite INTEGER PRIMARY KEY,
                    IDactivite INTEGER,
                    nom TEXT,
                    abrege TEXT,
                    type TEXT,
                    date_debut TEXT,
                    date_fin TEXT,
                    ordre INTEGER
                );
                CREATE TABLE unites_groupes (
                    IDunite INTEGER,
                    IDgroupe INTEGER
                );
                CREATE TABLE unites_remplissage (
                    IDunite_remplissage INTEGER PRIMARY KEY,
                    IDactivite INTEGER,
                    nom TEXT,
                    abrege TEXT,
                    date_debut TEXT,
                    date_fin TEXT,
                    ordre INTEGER
                );
                CREATE TABLE ouvertures (
                    IDouverture INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    IDunite INTEGER,
                    IDgroupe INTEGER,
                    date TEXT
                );
                CREATE TABLE remplissage (
                    IDremplissage INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    IDunite_remplissage INTEGER,
                    IDgroupe INTEGER,
                    date TEXT,
                    places INTEGER
                );
                CREATE TABLE consommations (
                    IDconso INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    IDunite INTEGER,
                    IDgroupe INTEGER,
                    IDevenement INTEGER,
                    date TEXT
                );
                CREATE TABLE evenements (
                    IDevenement INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    IDunite INTEGER,
                    IDgroupe INTEGER,
                    date TEXT,
                    nom TEXT,
                    description TEXT,
                    capacite_max INTEGER,
                    heure_debut TEXT,
                    heure_fin TEXT,
                    montant REAL
                );
                CREATE TABLE tarifs (
                    IDtarif INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDevenement INTEGER,
                    IDactivite INTEGER
                );
                CREATE TABLE tarifs_lignes (
                    IDligne INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDtarif INTEGER
                );
                CREATE TABLE questionnaire_filtres (
                    IDfiltre INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDtarif INTEGER
                );
                CREATE TABLE combi_tarifs (
                    IDcombi_tarif INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDtarif INTEGER
                );
                CREATE TABLE combi_tarifs_unites (
                    IDcombi_tarif_unite INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDtarif INTEGER
                );

                INSERT INTO activites VALUES (7, 'ALSH', '2026-01-01', '2026-12-31');
                INSERT INTO groupes VALUES (1, 7, 'Petits', 1);
                INSERT INTO groupes VALUES (2, 7, 'Grands', 2);
                INSERT INTO unites VALUES (10, 7, 'Sortie', 'Sortie', 'Evenement', '2026-01-01', '2026-12-31', 1);
                INSERT INTO unites VALUES (11, 7, 'Journée', 'Jour', 'Unitaire', '2026-01-01', '2026-12-31', 2);
                INSERT INTO unites_groupes VALUES (11, 1);
                INSERT INTO unites_remplissage VALUES (20, 7, 'Places', 'Places', '2026-01-01', '2026-12-31', 1);
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def _repo(self, path: Path) -> ActivityCalendarRepository:
        return ActivityCalendarRepository(NativeActivityEditorRepository(path))

    def test_month_roundtrip_writes_openings_fillings_and_event(self):
        path = self._database()
        connection = sqlite3.connect(path)
        try:
            connection.execute("INSERT INTO ouvertures (IDactivite, IDunite, IDgroupe, date) VALUES (7, 10, 1, '2026-09-02')")
            connection.execute(
                """INSERT INTO evenements
                   (IDactivite, IDunite, IDgroupe, date, nom, description, capacite_max, heure_debut, heure_fin, montant)
                   VALUES (7, 10, 1, '2026-09-02', 'Cinéma', '', 20, '14:00', '16:00', 5.0)"""
            )
            connection.commit()
        finally:
            connection.close()

        repo = self._repo(path)
        data = repo.load_month(7, 2026, 9)
        self.assertIn((dt.date(2026, 9, 2), 1, 10), data.openings)
        self.assertEqual(data.events[0].name, "Cinéma")

        event = data.events[0]
        openings = set(data.openings)
        openings.add((dt.date(2026, 9, 3), 1, 11))
        fillings = {(dt.date(2026, 9, 3), 1, 20): 36}
        repo.save_month(
            7,
            2026,
            9,
            openings,
            fillings,
            [CalendarEvent(
                event.event_id, event.activity_id, event.unit_id, event.group_id, event.date,
                "Cinéma municipal", "Séance", 24, "14:30", "16:15", 6.5,
                event.advanced_tariff_count,
            )],
        )

        loaded = repo.load_month(7, 2026, 9)
        self.assertIn((dt.date(2026, 9, 3), 1, 11), loaded.openings)
        self.assertEqual(loaded.fillings[(dt.date(2026, 9, 3), 1, 20)], 36)
        self.assertEqual(loaded.events[0].name, "Cinéma municipal")
        self.assertEqual(loaded.events[0].start_time, "14:30")
        self.assertEqual(loaded.events[0].amount, 6.5)

    def test_closing_opening_with_consumption_is_rejected_atomically(self):
        path = self._database()
        connection = sqlite3.connect(path)
        try:
            connection.execute("INSERT INTO ouvertures (IDactivite, IDunite, IDgroupe, date) VALUES (7, 11, 1, '2026-09-04')")
            connection.execute("INSERT INTO consommations (IDactivite, IDunite, IDgroupe, date) VALUES (7, 11, 1, '2026-09-04')")
            connection.commit()
        finally:
            connection.close()

        repo = self._repo(path)
        with self.assertRaises(ValueError):
            repo.save_month(7, 2026, 9, set(), {}, [])

        connection = sqlite3.connect(path)
        try:
            count = connection.execute("SELECT COUNT(*) FROM ouvertures WHERE IDactivite=7").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 1)

    def test_deleting_event_opening_cleans_advanced_tariff_dependencies(self):
        path = self._database()
        connection = sqlite3.connect(path)
        try:
            connection.execute("INSERT INTO ouvertures (IDactivite, IDunite, IDgroupe, date) VALUES (7, 10, 1, '2026-09-05')")
            cursor = connection.execute(
                """INSERT INTO evenements
                   (IDactivite, IDunite, IDgroupe, date, nom, description, capacite_max, heure_debut, heure_fin, montant)
                   VALUES (7, 10, 1, '2026-09-05', 'Yoga', '', NULL, '10:00', '11:00', NULL)"""
            )
            event_id = cursor.lastrowid
            tariff_id = connection.execute("INSERT INTO tarifs (IDevenement, IDactivite) VALUES (?, 7)", (event_id,)).lastrowid
            connection.execute("INSERT INTO tarifs_lignes (IDtarif) VALUES (?)", (tariff_id,))
            connection.execute("INSERT INTO questionnaire_filtres (IDtarif) VALUES (?)", (tariff_id,))
            connection.execute("INSERT INTO combi_tarifs (IDtarif) VALUES (?)", (tariff_id,))
            connection.execute("INSERT INTO combi_tarifs_unites (IDtarif) VALUES (?)", (tariff_id,))
            connection.commit()
        finally:
            connection.close()

        repo = self._repo(path)
        loaded = repo.load_month(7, 2026, 9)
        self.assertEqual(loaded.events[0].advanced_tariff_count, 1)
        repo.save_month(7, 2026, 9, set(), {}, [])

        connection = sqlite3.connect(path)
        try:
            for table in ("evenements", "tarifs", "tarifs_lignes", "questionnaire_filtres", "combi_tarifs", "combi_tarifs_unites", "ouvertures"):
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)
        finally:
            connection.close()

    def test_event_validation_matches_historic_name_and_time_rules(self):
        path = self._database()
        repo = self._repo(path)
        base = CalendarEvent(None, 7, 10, 1, dt.date(2026, 9, 6), "Sortie")
        with self.assertRaises(ValueError):
            repo.validate_event(CalendarEvent(None, 7, 10, 1, dt.date(2026, 9, 6), ""))
        with self.assertRaises(ValueError):
            repo.validate_event(CalendarEvent(None, 7, 10, 1, dt.date(2026, 9, 6), "Sortie", start_time="15:00", end_time="14:00"))
        with self.assertRaises(ValueError):
            repo.validate_event(CalendarEvent(None, 7, 10, 1, dt.date(2026, 9, 6), "Sortie", start_time="25:00"))
        self.assertEqual(repo.validate_event(replace_event(base, start_time="24:59")).start_time, "24:59")

    def test_calendar_page_smoke_displays_real_summary(self):
        path = self._database()
        connection = sqlite3.connect(path)
        try:
            connection.execute("INSERT INTO ouvertures (IDactivite, IDunite, IDgroupe, date) VALUES (7, 11, 1, '2026-09-07')")
            connection.commit()
        finally:
            connection.close()
        page = ActivityCalendarPage(NativeActivityEditorRepository(path), 7)
        self.addCleanup(page.close)
        self.assertEqual(page.tree.topLevelItemCount(), 1)
        self.assertIn("2026", page.tree.topLevelItem(0).text(0))


def replace_event(event: CalendarEvent, **changes) -> CalendarEvent:
    values = {
        "event_id": event.event_id,
        "activity_id": event.activity_id,
        "unit_id": event.unit_id,
        "group_id": event.group_id,
        "date": event.date,
        "name": event.name,
        "description": event.description,
        "capacity_max": event.capacity_max,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "amount": event.amount,
        "advanced_tariff_count": event.advanced_tariff_count,
    }
    values.update(changes)
    return CalendarEvent(**values)


if __name__ == "__main__":
    unittest.main()
