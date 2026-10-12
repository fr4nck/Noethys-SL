import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_editor import (
    ActivityEditorDialog,
    NativeActivityEditorRepository,
    UNLIMITED_END,
    UNLIMITED_START,
)


class ActivityEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_database(self) -> Path:
        handle, filename = tempfile.mkstemp(suffix="_DATA.dat")
        os.close(handle)
        database = Path(filename)
        connection = sqlite3.connect(database)
        try:
            connection.executescript(
                """
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY,
                    nom TEXT,
                    abrege TEXT,
                    coords_org INTEGER,
                    rue TEXT,
                    cp TEXT,
                    ville TEXT,
                    tel TEXT,
                    fax TEXT,
                    mail TEXT,
                    site TEXT,
                    date_debut TEXT,
                    date_fin TEXT,
                    nbre_inscrits_max INTEGER,
                    code_comptable TEXT,
                    regie INTEGER,
                    code_produit_local TEXT,
                    inscriptions_multiples INTEGER,
                    code_service TEXT,
                    code_analytique TEXT
                );
                CREATE TABLE factures_regies (
                    IDregie INTEGER PRIMARY KEY,
                    nom TEXT
                );
                CREATE TABLE types_groupes_activites (
                    IDtype_groupe_activite INTEGER PRIMARY KEY,
                    nom TEXT,
                    observations TEXT
                );
                CREATE TABLE groupes_activites (
                    IDtype_groupe_activite INTEGER,
                    IDactivite INTEGER
                );
                """
            )
            connection.execute(
                "INSERT INTO activites VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    7,
                    "École Multisports",
                    "EMS",
                    1,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "1977-01-01",
                    "2999-01-01",
                    None,
                    "706",
                    1,
                    "SPORT",
                    0,
                    "EMS",
                    "A1",
                ),
            )
            connection.execute("INSERT INTO factures_regies VALUES (1, 'Régie principale')")
            connection.executemany(
                "INSERT INTO types_groupes_activites VALUES (?, ?, ?)",
                [(10, "Sports", ""), (20, "Jeunesse", "")],
            )
            connection.execute("INSERT INTO groupes_activites VALUES (10, 7)")
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(database.unlink, missing_ok=True)
        return database

    def test_repository_loads_historic_generalities(self):
        repository = NativeActivityEditorRepository(self._make_database())
        details = repository.load(7)

        self.assertEqual(details.name, "École Multisports")
        self.assertEqual(details.short_name, "EMS")
        self.assertEqual(details.start_date, UNLIMITED_START)
        self.assertEqual(details.end_date, UNLIMITED_END)
        self.assertTrue(details.coords_from_organizer)
        self.assertEqual(details.regie_id, 1)
        self.assertEqual(repository.list_group_types(7), [(20, "Jeunesse", False), (10, "Sports", True)])

    def test_repository_saves_generalities_and_groups_atomically(self):
        database = self._make_database()
        repository = NativeActivityEditorRepository(database)
        details = repository.load(7)
        details.name = "EMS 2026"
        details.short_name = "EMS26"
        details.coords_from_organizer = False
        details.street = "1 rue du Test"
        details.postal_code = "35130"
        details.city = "La Guerche-de-Bretagne"
        details.multiple_registrations = True
        details.max_members = 80

        repository.save(details, [20])
        reloaded = repository.load(7)

        self.assertEqual(reloaded.name, "EMS 2026")
        self.assertEqual(reloaded.city, "La Guerche-de-Bretagne")
        self.assertTrue(reloaded.multiple_registrations)
        self.assertEqual(reloaded.max_members, 80)
        self.assertEqual(repository.list_group_types(7), [(20, "Jeunesse", True), (10, "Sports", False)])

    def test_dialog_smoke_builds_historic_page_order(self):
        repository = NativeActivityEditorRepository(self._make_database())
        dialog = ActivityEditorDialog(repository, 7)
        self.addCleanup(dialog.close)

        self.assertEqual(dialog.tabs.count(), 9)
        self.assertEqual(dialog.tabs.tabText(0), "Généralités")
        self.assertEqual(dialog.tabs.tabText(8), "Tarification")
        self.assertEqual(dialog.name_edit.text(), "École Multisports")
        self.assertTrue(dialog.unlimited_radio.isChecked())
        self.assertFalse(dialog.start_date_edit.isEnabled())


if __name__ == "__main__":
    unittest.main()
