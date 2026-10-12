import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.activity_requirements import (
    ActivityRequirementsPage,
    ActivityRequirementsRepository,
    RequirementsState,
)


class ActivityRequirementsTests(unittest.TestCase):
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
                    vaccins_obligatoires INTEGER
                );
                CREATE TABLE types_pieces (
                    IDtype_piece INTEGER PRIMARY KEY,
                    nom TEXT
                );
                CREATE TABLE pieces_activites (
                    IDpiece_activite INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    IDtype_piece INTEGER
                );
                CREATE TABLE types_cotisations (
                    IDtype_cotisation INTEGER PRIMARY KEY,
                    nom TEXT
                );
                CREATE TABLE cotisations_activites (
                    IDcotisation_activite INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    IDtype_cotisation INTEGER
                );
                CREATE TABLE renseignements_activites (
                    IDrenseignement INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    IDtype_renseignement INTEGER
                );

                INSERT INTO activites VALUES (7, 1);
                INSERT INTO activites VALUES (8, 0);
                INSERT INTO types_pieces VALUES (1, 'Attestation');
                INSERT INTO types_pieces VALUES (2, 'Certificat médical');
                INSERT INTO types_cotisations VALUES (10, 'Adhésion');
                INSERT INTO types_cotisations VALUES (11, 'Licence');
                INSERT INTO pieces_activites (IDactivite, IDtype_piece) VALUES (7, 1);
                INSERT INTO pieces_activites (IDactivite, IDtype_piece) VALUES (8, 2);
                INSERT INTO cotisations_activites (IDactivite, IDtype_cotisation) VALUES (7, 10);
                INSERT INTO cotisations_activites (IDactivite, IDtype_cotisation) VALUES (8, 11);
                INSERT INTO renseignements_activites (IDactivite, IDtype_renseignement) VALUES (7, 1);
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def _repo(self, path: Path) -> ActivityRequirementsRepository:
        return ActivityRequirementsRepository(NativeActivityEditorRepository(path))

    def test_load_reproduces_historic_obligations(self):
        path = self._database()
        state = self._repo(path).load(7)
        self.assertEqual(state.piece_ids, frozenset({1}))
        self.assertTrue(state.cotisation_required)
        self.assertEqual(state.cotisation_ids, frozenset({10}))
        self.assertTrue(state.vaccines_required)
        self.assertEqual(state.information_ids, frozenset({1}))

    def test_required_cotisation_without_selection_is_rejected(self):
        path = self._database()
        repo = self._repo(path)
        with self.assertRaises(ValueError):
            repo.save(
                7,
                RequirementsState(
                    piece_ids=frozenset(),
                    cotisation_required=True,
                    cotisation_ids=frozenset(),
                    vaccines_required=False,
                    information_ids=frozenset(),
                ),
            )

    def test_save_is_scoped_to_activity_and_roundtrips(self):
        path = self._database()
        repo = self._repo(path)
        target = RequirementsState(
            piece_ids=frozenset({2}),
            cotisation_required=True,
            cotisation_ids=frozenset({10, 11}),
            vaccines_required=False,
            information_ids=frozenset({2, 12}),
        )
        repo.save(7, target)
        self.assertEqual(repo.load(7), target)

        connection = sqlite3.connect(path)
        try:
            self.assertEqual(
                connection.execute("SELECT IDtype_piece FROM pieces_activites WHERE IDactivite=8").fetchall(),
                [(2,)],
            )
            self.assertEqual(
                connection.execute("SELECT IDtype_cotisation FROM cotisations_activites WHERE IDactivite=8").fetchall(),
                [(11,)],
            )
        finally:
            connection.close()

    def test_disabling_cotisation_requirement_removes_links(self):
        path = self._database()
        repo = self._repo(path)
        repo.save(
            7,
            RequirementsState(
                piece_ids=frozenset({1}),
                cotisation_required=False,
                cotisation_ids=frozenset({10}),
                vaccines_required=True,
                information_ids=frozenset({1}),
            ),
        )
        loaded = repo.load(7)
        self.assertFalse(loaded.cotisation_required)
        self.assertEqual(loaded.cotisation_ids, frozenset())

    def test_page_smoke_loads_existing_catalogues(self):
        path = self._database()
        page = ActivityRequirementsPage(NativeActivityEditorRepository(path), 7)
        self.addCleanup(page.close)
        self.assertEqual(page.pieces.count(), 2)
        self.assertEqual(page.cotisations.count(), 2)
        self.assertGreater(page.informations.count(), 5)
        self.assertTrue(page.vaccines_required.isChecked())


if __name__ == "__main__":
    unittest.main()
