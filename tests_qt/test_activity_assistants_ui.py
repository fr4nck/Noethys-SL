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

from noethys_qt.activities_native import NativeActivitiesWindow
from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.activity_assistants import ActivityAssistantChoiceDialog, ActivityAssistantDialog
from noethys_qt.activity_assistants_core import ActivityAssistantRepository
from noethys_qt.activity_editor import NativeActivityEditorRepository


class ActivityAssistantsUiTests(unittest.TestCase):
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
            # Windows peut conserver brièvement un handle SQLite après la
            # destruction différée d'un widget Qt. Ce détail de nettoyage ne
            # doit pas transformer un smoke UI réussi en échec fonctionnel.
            pass

    def _database(self) -> Path:
        handle, filename = tempfile.mkstemp(suffix="_DATA.dat")
        os.close(handle)
        database = Path(filename)
        connection = sqlite3.connect(database)
        try:
            connection.executescript(
                """
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT, abrege TEXT, date_debut TEXT, date_fin TEXT
                );
                CREATE TABLE types_groupes_activites (
                    IDtype_groupe_activite INTEGER PRIMARY KEY, nom TEXT
                );
                CREATE TABLE types_pieces (IDtype_piece INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE types_cotisations (IDtype_cotisation INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE responsables_activite (
                    IDresponsable INTEGER PRIMARY KEY AUTOINCREMENT,
                    sexe TEXT, nom TEXT, fonction TEXT
                );
                """
            )
            connection.execute("INSERT INTO types_groupes_activites VALUES (1, 'Sports')")
            connection.execute("INSERT INTO types_pieces VALUES (1, 'Certificat')")
            connection.execute("INSERT INTO types_cotisations VALUES (1, 'Adhésion')")
            connection.execute(
                "INSERT INTO responsables_activite (sexe, nom, fonction) VALUES ('F', 'Direction', 'Directrice')"
            )
            connection.execute(
                "INSERT INTO activites (nom, abrege, date_debut, date_fin) "
                "VALUES ('Test', 'TEST', '1977-01-01', '2999-01-01')"
            )
            connection.commit()
        finally:
            connection.close()
        self.addCleanup(self._safe_unlink, database)
        return database

    def test_choice_dialog_exposes_historic_six_choices(self) -> None:
        dialog = ActivityAssistantChoiceDialog()
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.list.count(), 6)
        codes = [
            dialog.list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(dialog.list.count())
        ]
        self.assertEqual(codes, ["nouveau", "annuelle", "sejour", "stage", "cantine", "sorties"])

    def test_cantine_wizard_builds_without_wx_and_prefills_last_responsible(self) -> None:
        database = self._database()
        repository = ActivityAssistantRepository(NativeActivityEditorRepository(database))
        wizard = ActivityAssistantDialog(repository, "cantine")
        self.addCleanup(wizard.close)
        self.assertEqual(wizard.name_edit.text(), "Cantine")
        self.assertEqual(wizard.responsible_name.text(), "Direction")
        wizard.groups_edit.setPlainText("Service 1\nService 2")
        configuration = wizard.configuration()
        self.assertEqual(configuration.group_names, ("Service 1", "Service 2"))
        self.assertIsNone(configuration.start_date)
        self.assertFalse(configuration.track_sessions)

    def test_simulation_toggle_disables_modify_but_keeps_preview_actions(self) -> None:
        database = self._database()
        window = NativeActivitiesWindow(
            SqliteActivityRepository(database),
            editor_sqlite_path=database,
        )
        self.addCleanup(window.close)
        window.table.selectRow(0)
        window._sync_lifecycle_actions()
        self.assertTrue(window.modify_action.isEnabled())
        window.simulation_action.setChecked(True)
        self.assertTrue(window.simulation_mode)
        self.assertFalse(window.modify_action.isEnabled())
        self.assertTrue(window.add_action.isEnabled())
        self.assertTrue(window.duplicate_action.isEnabled())
        self.assertTrue(window.delete_action.isEnabled())


if __name__ == "__main__":
    unittest.main()
