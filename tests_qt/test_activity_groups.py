import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.activity_groups import (
    ActivityEditorDialog,
    ActivityGroupsPage,
    ActivityGroupsRepository,
)


class ActivityGroupsTests(unittest.TestCase):
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
                    nom TEXT, abrege TEXT, coords_org INTEGER, rue TEXT, cp TEXT,
                    ville TEXT, tel TEXT, fax TEXT, mail TEXT, site TEXT,
                    date_debut TEXT, date_fin TEXT, nbre_inscrits_max INTEGER,
                    code_comptable TEXT, regie INTEGER, code_produit_local TEXT,
                    inscriptions_multiples INTEGER, code_service TEXT, code_analytique TEXT
                );
                CREATE TABLE factures_regies (IDregie INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE types_groupes_activites (
                    IDtype_groupe_activite INTEGER PRIMARY KEY, nom TEXT, observations TEXT
                );
                CREATE TABLE groupes_activites (IDtype_groupe_activite INTEGER, IDactivite INTEGER);
                CREATE TABLE groupes (
                    IDgroupe INTEGER PRIMARY KEY AUTOINCREMENT,
                    IDactivite INTEGER,
                    nom TEXT,
                    ordre INTEGER,
                    abrege TEXT,
                    nbre_inscrits_max INTEGER
                );
                CREATE TABLE unites_groupes (IDunite_groupe INTEGER PRIMARY KEY, IDunite INTEGER, IDgroupe INTEGER);
                CREATE TABLE ouvertures (IDouverture INTEGER PRIMARY KEY, IDgroupe INTEGER);
                CREATE TABLE inscriptions (IDinscription INTEGER PRIMARY KEY, IDgroupe INTEGER);
                CREATE TABLE consommations (IDconso INTEGER PRIMARY KEY, IDgroupe INTEGER);
                CREATE TABLE tarifs (IDtarif INTEGER PRIMARY KEY, groupes TEXT);
                CREATE TABLE remplissage (IDremplissage INTEGER PRIMARY KEY, IDgroupe INTEGER);
                """
            )
            connection.execute(
                "INSERT INTO activites VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    7, "École Multisports", "EMS", 1, None, None, None, None, None,
                    None, None, "1977-01-01", "2999-01-01", None, "706", None,
                    "SPORT", 0, "EMS", "A1",
                ),
            )
            connection.execute(
                "INSERT INTO groupes (IDactivite, nom, ordre, abrege, nbre_inscrits_max) VALUES (7, 'Petits', 1, 'P', 20)"
            )
            connection.execute(
                "INSERT INTO groupes (IDactivite, nom, ordre, abrege, nbre_inscrits_max) VALUES (7, 'Grands', 2, 'G', NULL)"
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(database.unlink, missing_ok=True)
        return database

    def test_repository_crud_and_order(self):
        database = self._make_database()
        editor_repository = NativeActivityEditorRepository(database)
        repository = ActivityGroupsRepository(editor_repository)

        rows = repository.list(7)
        self.assertEqual([row.name for row in rows], ["Petits", "Grands"])

        new_id = repository.add(7, "Ados", "A", 12)
        rows = repository.list(7)
        self.assertEqual([row.name for row in rows], ["Petits", "Grands", "Ados"])
        self.assertEqual(rows[-1].max_members, 12)

        repository.move(7, new_id, -1)
        self.assertEqual([row.name for row in repository.list(7)], ["Petits", "Ados", "Grands"])

        group = next(row for row in repository.list(7) if row.group_id == new_id)
        repository.update(group, "Adolescents", "ADOS", 16)
        updated = next(row for row in repository.list(7) if row.group_id == new_id)
        self.assertEqual((updated.name, updated.short_name, updated.max_members), ("Adolescents", "ADOS", 16))

        repository.delete(7, new_id)
        self.assertEqual([row.order for row in repository.list(7)], [1, 2])

    def test_delete_is_blocked_when_group_is_used(self):
        database = self._make_database()
        editor_repository = NativeActivityEditorRepository(database)
        repository = ActivityGroupsRepository(editor_repository)
        group = repository.list(7)[0]

        connection = sqlite3.connect(database)
        try:
            connection.execute("INSERT INTO inscriptions VALUES (1, ?)", (group.group_id,))
            connection.execute("INSERT INTO tarifs VALUES (1, ?)", (str(group.group_id),))
            connection.commit()
        finally:
            connection.close()

        dependencies = repository.usage(group.group_id)
        self.assertIn("1 inscription(s)", dependencies)
        self.assertIn("1 tarif(s)", dependencies)
        with self.assertRaises(ValueError):
            repository.delete(7, group.group_id)

    def test_groups_page_smoke_loads_real_rows(self):
        editor_repository = NativeActivityEditorRepository(self._make_database())
        page = ActivityGroupsPage(editor_repository, 7)
        self.addCleanup(page.close)

        self.assertEqual(page.group_count(), 2)
        self.assertEqual(page.model.row_at(0).name, "Petits")
        self.assertFalse(page.edit_button.isEnabled())
        page.table.selectRow(0)
        self.assertEqual(page.selected_group().name, "Petits")

    def test_activity_editor_replaces_groups_placeholder(self):
        editor_repository = NativeActivityEditorRepository(self._make_database())
        dialog = ActivityEditorDialog(editor_repository, 7)
        self.addCleanup(dialog.close)

        self.assertEqual(dialog.tabs.tabText(2), "Groupes")
        self.assertIs(dialog.tabs.widget(2), dialog.group_page)
        self.assertEqual(dialog.group_page.group_count(), 2)


if __name__ == "__main__":
    unittest.main()
