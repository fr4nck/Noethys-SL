import sqlite3
import tempfile
import unittest
from pathlib import Path

from noethys_qt.activity_complete import ActivityGeneralExtrasRepository, ActivityLogoState
from noethys_qt.activity_editor import NativeActivityEditorRepository


class ActivityCompleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "general.sqlite"
        connection = sqlite3.connect(self.path)
        try:
            connection.executescript(
                """
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY,
                    logo_org INTEGER,
                    logo BLOB
                );
                CREATE TABLE responsables_activite (
                    IDresponsable INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER NOT NULL,
                    nom TEXT,
                    fonction TEXT,
                    defaut INTEGER,
                    sexe TEXT
                );
                INSERT INTO activites VALUES (1, 1, NULL);
                INSERT INTO activites VALUES (2, 1, NULL);
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.repository = ActivityGeneralExtrasRepository(NativeActivityEditorRepository(self.path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_responsible_is_default_and_default_can_move(self):
        first = self.repository.save_responsible(1, "Alice", "Directrice", "F")
        second = self.repository.save_responsible(1, "Bob", "Adjoint", "H")
        rows = self.repository.list_responsibles(1)
        self.assertEqual([row.responsible_id for row in rows], [first, second])
        self.assertTrue(rows[0].is_default)
        self.assertFalse(rows[1].is_default)
        self.repository.set_default(1, second)
        by_id = {row.responsible_id: row for row in self.repository.list_responsibles(1)}
        self.assertFalse(by_id[first].is_default)
        self.assertTrue(by_id[second].is_default)

    def test_delete_default_promotes_remaining_responsible(self):
        first = self.repository.save_responsible(1, "Alice", "Directrice", "F")
        second = self.repository.save_responsible(1, "Bob", "Adjoint", "H")
        self.repository.delete_responsible(1, first)
        rows = self.repository.list_responsibles(1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].responsible_id, second)
        self.assertTrue(rows[0].is_default)

    def test_responsible_operations_are_scoped_to_activity(self):
        responsible = self.repository.save_responsible(1, "Alice", "Directrice", "F")
        with self.assertRaises(ValueError):
            self.repository.save_responsible(2, "Intruse", "", "F", responsible)
        with self.assertRaises(ValueError):
            self.repository.set_default(2, responsible)
        with self.assertRaises(ValueError):
            self.repository.delete_responsible(2, responsible)
        self.assertEqual(self.repository.list_responsibles(1)[0].name, "Alice")

    def test_logo_round_trip_and_return_to_organizer(self):
        png_like_bytes = b"\x89PNG\r\n\x1a\nqt-test"
        self.repository.save_logo(1, ActivityLogoState(False, png_like_bytes))
        loaded = self.repository.load_logo(1)
        self.assertFalse(loaded.from_organizer)
        self.assertEqual(loaded.image, png_like_bytes)
        self.repository.save_logo(1, ActivityLogoState(True, png_like_bytes))
        loaded = self.repository.load_logo(1)
        self.assertTrue(loaded.from_organizer)
        self.assertIsNone(loaded.image)

    def test_custom_logo_requires_image(self):
        with self.assertRaises(ValueError):
            self.repository.save_logo(1, ActivityLogoState(False, None))


if __name__ == "__main__":
    unittest.main()
