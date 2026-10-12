import datetime as dt
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.activity_portal import (
    ActivityPortalPage,
    ActivityPortalRepository,
    PortalReservationUnit,
    PortalSettings,
    ReservationPeriod,
)


APP = QApplication.instance() or QApplication([])


class ActivityPortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "portal.sqlite"
        connection = sqlite3.connect(self.path)
        try:
            connection.executescript(
                """
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY,
                    portail_inscriptions_affichage INTEGER,
                    portail_inscriptions_date_debut TEXT,
                    portail_inscriptions_date_fin TEXT,
                    portail_reservations_affichage INTEGER,
                    portail_unites_multiples INTEGER,
                    portail_reservations_limite TEXT,
                    portail_reservations_absenti TEXT
                );
                CREATE TABLE portail_periodes (
                    IDperiode INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER NOT NULL,
                    nom TEXT,
                    date_debut TEXT,
                    date_fin TEXT,
                    affichage INTEGER,
                    affichage_date_debut TEXT,
                    affichage_date_fin TEXT,
                    IDmodele INTEGER,
                    introduction TEXT,
                    prefacturation INTEGER
                );
                CREATE TABLE portail_unites (
                    IDunite INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER NOT NULL,
                    nom TEXT,
                    unites_principales TEXT,
                    unites_secondaires TEXT,
                    ordre INTEGER
                );
                CREATE TABLE unites (
                    IDunite INTEGER PRIMARY KEY,
                    IDactivite INTEGER NOT NULL,
                    nom TEXT,
                    ordre INTEGER
                );
                CREATE TABLE modeles_emails (
                    IDmodele INTEGER PRIMARY KEY,
                    nom TEXT,
                    categorie TEXT,
                    defaut INTEGER
                );
                INSERT INTO activites VALUES (1, 1, NULL, NULL, 1, 0, NULL, NULL);
                INSERT INTO activites VALUES (2, 0, NULL, NULL, 0, 0, NULL, NULL);
                INSERT INTO unites VALUES (10, 1, 'Journée', 1);
                INSERT INTO unites VALUES (11, 1, 'Repas', 2);
                INSERT INTO unites VALUES (20, 2, 'Autre activité', 1);
                INSERT INTO modeles_emails VALUES (5, 'Réponse portail', 'portail_demande_reservation', 1);
                INSERT INTO modeles_emails VALUES (6, 'Autre catégorie', 'facture', 0);
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.editor = NativeActivityEditorRepository(self.path)
        self.repository = ActivityPortalRepository(self.editor)

    def tearDown(self):
        self.tmp.cleanup()

    def test_settings_round_trip_preserves_legacy_encoding(self):
        state = PortalSettings(
            registrations_enabled=True,
            registration_start=dt.datetime(2026, 9, 1, 8, 30),
            registration_end=dt.datetime(2026, 9, 15, 18, 0),
            reservations_enabled=True,
            multiple_units=True,
            reservation_limit="1004#09:00#weekends,feries",
            unjustified_absence_limit="3#23:59",
        )
        self.repository.save_settings(1, state)
        loaded = self.repository.load_settings(1)
        self.assertEqual(loaded, state)

    def test_period_crud_and_scope(self):
        period = ReservationPeriod(
            None, 1, "Toussaint", dt.date(2026, 10, 17), dt.date(2026, 11, 2),
            True, dt.datetime(2026, 9, 1, 8, 0), dt.datetime(2026, 10, 10, 23, 59),
            5, "Réservez ici", True,
        )
        period_id = self.repository.save_period(period)
        loaded = self.repository.list_periods(1)[0]
        self.assertEqual(loaded.period_id, period_id)
        self.assertEqual(loaded.name, "Toussaint")
        self.assertTrue(loaded.prefacturation)
        with self.assertRaises(ValueError):
            self.repository.delete_period(2, period_id)
        self.repository.delete_period(1, period_id)
        self.assertEqual(self.repository.list_periods(1), [])

    def test_period_rejects_invalid_ranges_and_wrong_model(self):
        with self.assertRaises(ValueError):
            self.repository.save_period(ReservationPeriod(
                None, 1, "Inversée", dt.date(2026, 10, 2), dt.date(2026, 10, 1),
                True, None, None, None, "", False,
            ))
        with self.assertRaises(ValueError):
            self.repository.save_period(ReservationPeriod(
                None, 1, "Modèle", dt.date(2026, 10, 1), dt.date(2026, 10, 2),
                True, None, None, 6, "", False,
            ))

    def test_reservation_unit_validates_membership_and_overlap(self):
        with self.assertRaises(ValueError):
            self.repository.save_reservation_unit(PortalReservationUnit(None, 1, "Vide", (), (), 0))
        with self.assertRaises(ValueError):
            self.repository.save_reservation_unit(PortalReservationUnit(None, 1, "Conflit", (10,), (10,), 0))
        with self.assertRaises(ValueError):
            self.repository.save_reservation_unit(PortalReservationUnit(None, 1, "Étrangère", (20,), (), 0))

    def test_reservation_unit_order_move_and_delete(self):
        first = self.repository.save_reservation_unit(PortalReservationUnit(None, 1, "Journée", (10,), (), 0))
        second = self.repository.save_reservation_unit(PortalReservationUnit(None, 1, "Journée + repas", (10,), (11,), 0))
        self.assertEqual([row.unit_id for row in self.repository.list_reservation_units(1)], [first, second])
        self.repository.move_reservation_unit(1, second, -1)
        moved = self.repository.list_reservation_units(1)
        self.assertEqual([row.unit_id for row in moved], [second, first])
        self.assertEqual([row.order for row in moved], [1, 2])
        with self.assertRaises(ValueError):
            self.repository.delete_reservation_unit(2, second)
        self.repository.delete_reservation_unit(1, second)
        remaining = self.repository.list_reservation_units(1)
        self.assertEqual([(row.unit_id, row.order) for row in remaining], [(first, 1)])

    def test_page_collects_legacy_option_strings(self):
        page = ActivityPortalPage(self.editor, 1)
        try:
            page.reg_dates.setChecked(True)
            page.reg_start.setDateTime(dt.datetime(2026, 9, 1, 8, 0))
            page.reg_end.setDateTime(dt.datetime(2026, 9, 30, 18, 0))
            page.limit_check.setChecked(True)
            page.limit_day.setCurrentIndex(page.limit_day.findData(1004))
            page.limit_time.setTime(dt.time(9, 15))
            page.limit_weekends.setChecked(True)
            page.limit_holidays.setChecked(True)
            page.absence_check.setChecked(True)
            page.absence_day.setCurrentIndex(page.absence_day.findData(2))
            page.absence_time.setTime(dt.time(23, 45))
            state = page.collect()
            self.assertEqual(state.reservation_limit, "1004#09:15#weekends,feries")
            self.assertEqual(state.unjustified_absence_limit, "2#23:45")
        finally:
            page.close(); page.deleteLater(); APP.processEvents()


if __name__ == "__main__":
    unittest.main()
