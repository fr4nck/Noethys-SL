import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.activity_labels import ActivityLabelsPage, ActivityLabelsRepository


class ActivityLabelsTests(unittest.TestCase):
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
                CREATE TABLE etiquettes (
                    IDetiquette INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT,
                    IDactivite INTEGER,
                    parent INTEGER,
                    ordre INTEGER,
                    couleur TEXT,
                    active INTEGER
                );
                CREATE TABLE consommations (
                    IDconso INTEGER PRIMARY KEY AUTOINCREMENT,
                    etiquettes TEXT
                );
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(database.unlink, missing_ok=True)
        return database

    def test_repository_roundtrip_hierarchy_and_order(self) -> None:
        database = self._make_database()
        repository = ActivityLabelsRepository(NativeActivityEditorRepository(database))

        room_id = repository.save(7, "Salle", None, "(10, 20, 30)", False)
        coach_id = repository.save(7, "Intervenant", None, "(255, 255, 255)", True)
        child_id = repository.save(7, "Salle rouge", room_id, "(255, 0, 0)", True)

        rows = repository.list(7)
        by_id = {row.label_id: row for row in rows}
        self.assertEqual(by_id[child_id].parent_id, room_id)
        self.assertFalse(by_id[room_id].active)
        self.assertEqual(by_id[coach_id].order, 2)

        repository.move(7, coach_id, -1)
        roots = [row for row in repository.list(7) if row.parent_id is None]
        self.assertEqual([row.label for row in roots], ["Intervenant", "Salle"])

    def test_parent_delete_is_blocked_when_descendant_is_used(self) -> None:
        database = self._make_database()
        repository = ActivityLabelsRepository(NativeActivityEditorRepository(database))
        parent_id = repository.save(7, "Salles", None, None, False)
        child_id = repository.save(7, "Gymnase", parent_id, None, True)
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "INSERT INTO consommations (etiquettes) VALUES (?)",
                (f"{child_id};999",),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(ValueError, "Gymnase"):
            repository.delete(7, parent_id)

        self.assertEqual(len(repository.list(7)), 2)

    def test_parent_delete_removes_unused_descendants_and_resequences(self) -> None:
        database = self._make_database()
        repository = ActivityLabelsRepository(NativeActivityEditorRepository(database))
        first_id = repository.save(7, "Premier", None, None, True)
        parent_id = repository.save(7, "Parent", None, None, False)
        repository.save(7, "Enfant", parent_id, None, True)
        last_id = repository.save(7, "Dernier", None, None, True)

        repository.delete(7, parent_id)

        roots = [row for row in repository.list(7) if row.parent_id is None]
        self.assertEqual([row.label_id for row in roots], [first_id, last_id])
        self.assertEqual([row.order for row in roots], [1, 2])

    def test_page_smoke_displays_hierarchy(self) -> None:
        database = self._make_database()
        editor_repository = NativeActivityEditorRepository(database)
        repository = ActivityLabelsRepository(editor_repository)
        parent_id = repository.save(7, "Actions", None, "(1, 2, 3)", False)
        repository.save(7, "Sortie", parent_id, "(4, 5, 6)", True)

        page = ActivityLabelsPage(editor_repository, 7)

        self.assertEqual(page.tree.topLevelItemCount(), 1)
        self.assertEqual(page.tree.topLevelItem(0).text(0), "Actions")
        self.assertEqual(page.tree.topLevelItem(0).childCount(), 1)
        self.assertEqual(page.tree.topLevelItem(0).child(0).text(0), "Sortie")
        page.deleteLater()


if __name__ == "__main__":
    unittest.main()
