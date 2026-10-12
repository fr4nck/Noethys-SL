from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository


class PeopleSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _safe_unlink(database: Path) -> None:
        QApplication.processEvents()
        gc.collect()
        try:
            database.unlink(missing_ok=True)
        except PermissionError:
            pass

    def _database(self) -> Path:
        handle, filename = tempfile.mkstemp(suffix="_DATA.dat")
        os.close(handle)
        database = Path(filename)
        connection = sqlite3.connect(database)
        try:
            connection.executescript(
                """
                CREATE TABLE individus (
                    IDindividu INTEGER PRIMARY KEY,
                    nom TEXT, prenom TEXT, date_naiss TEXT, adresse_auto INTEGER,
                    rue_resid TEXT, cp_resid TEXT, ville_resid TEXT,
                    tel_domicile TEXT, tel_mobile TEXT, travail_tel TEXT,
                    mail TEXT, travail_mail TEXT, profession TEXT, employeur TEXT,
                    etat TEXT
                );
                CREATE TABLE rattachements (
                    IDrattachement INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDindividu INTEGER, IDfamille INTEGER, IDcategorie INTEGER, titulaire INTEGER
                );
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT, abrege TEXT, date_debut TEXT, date_fin TEXT
                );
                """
            )
            connection.executemany(
                """INSERT INTO individus (
                    IDindividu, nom, prenom, date_naiss, adresse_auto,
                    rue_resid, cp_resid, ville_resid, tel_domicile, tel_mobile,
                    travail_tel, mail, travail_mail, profession, employeur, etat
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (1, "DUPONT", "Élodie", "1985-03-12", None, "1 rue Test", "35000", "Rennes", None, "06 12 34 56 78", None, "elodie@example.org", None, "Paysagiste", "Atelier", None),
                    (2, "MARTIN", "Léa", "2015-08-20", 1, "", "", "", None, None, None, None, None, "", "", None),
                    (3, "DURAND", "Paul", "1970-01-01", None, "2 rue Archive", "35000", "Rennes", None, None, None, None, None, "", "", "archive"),
                ),
            )
            connection.executemany(
                "INSERT INTO rattachements (IDindividu, IDfamille, IDcategorie, titulaire) VALUES (?, ?, ?, ?)",
                ((1, 10, 1, 1), (2, 10, 2, 0)),
            )
            connection.execute(
                "INSERT INTO activites (nom, abrege, date_debut, date_fin) VALUES ('Test', 'TEST', '2026-01-01', '2026-12-31')"
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(self._safe_unlink, database)
        return database

    def _repository(self, database: Path) -> PeopleSearchRepository:
        return PeopleSearchRepository(NativeActivityEditorRepository(database))

    def test_search_preserves_auto_address_and_family_label(self) -> None:
        database = self._database()
        repository = self._repository(database)
        result = repository.search("MARTIN")
        self.assertEqual(result.total, 1)
        row = result.rows[0]
        self.assertEqual(row.city, "Rennes")
        self.assertEqual(row.street, "1 rue Test")
        self.assertEqual(row.families[0].family_id, 10)
        self.assertIn("DUPONT", row.families[0].family_label)
        self.assertEqual(row.families[0].role_label, "enfant")

    def test_search_is_accent_insensitive_and_searches_family_and_phone(self) -> None:
        database = self._database()
        repository = self._repository(database)
        by_representative = repository.search("elodie")
        self.assertEqual({row.individual_id for row in by_representative.rows}, {1, 2})
        self.assertEqual(repository.search("0612345678").rows[0].individual_id, 1)
        family = repository.search("dupont")
        self.assertEqual({row.individual_id for row in family.rows}, {1, 2})

    def test_archives_are_hidden_by_default(self) -> None:
        database = self._database()
        repository = self._repository(database)
        self.assertEqual(repository.search("DURAND").total, 0)
        archived = repository.search("DURAND", include_archived=True)
        self.assertEqual(archived.total, 1)
        self.assertEqual(archived.rows[0].state_label, "Archivé")

    def test_shell_opens_on_real_navigation_with_people_search(self) -> None:
        database = self._database()
        people = self._repository(database)
        window = NoethysQtWindow(
            people,
            SqliteActivityRepository(database),
            editor_sqlite_path=database,
            requested_theme="dark",
            source_label="copie de test",
        )
        self.addCleanup(window.close)
        self.assertEqual(window.navigation.count(), 7)
        window.navigate("people")
        self.assertIs(window.stack.currentWidget(), window.people_page)
        window.people_page.search_edit.setText("Dupont")
        window.people_page.search_now()
        self.assertEqual(window.people_page.model.rowCount(), 2)
        pending = window.navigation.item(3)
        self.assertFalse(bool(pending.flags() & Qt.ItemFlag.ItemIsEnabled))


if __name__ == "__main__":
    unittest.main()
