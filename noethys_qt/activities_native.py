"""Lance la ligne Qt Activités sans importer wx/GestionDB.

Le pont lit la configuration Noethys historique, ouvre SQLite ou MySQL avec
les pilotes Python modernes puis présente la liste et les pages Qt déjà
migrées de la fiche activité.
"""

from __future__ import annotations

import base64
import configparser
import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Sequence

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QStyle, QToolBar

from .activities_prototype import (
    ActivitiesWindow,
    ActivityRepository,
    ActivityRow,
    _parse_args,
)
from .activity_visuals import apply_activity_visuals


ROOT = Path(__file__).resolve().parents[1]
NOETHYS_DIR = ROOT / "noethys"


def _user_config_dir() -> Path:
    portable = NOETHYS_DIR / "Portable"
    if portable.is_dir():
        return portable
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("Variable APPDATA introuvable : impossible de localiser Config.json.")
    return Path(appdata) / "noethys"


def _load_config() -> dict:
    from .activities_prototype import VerifierAccesBaseConfiguree

    VerifierAccesBaseConfiguree()
    path = _user_config_dir() / "Config.json"
    if not path.is_file():
        raise RuntimeError(f"Configuration Noethys introuvable : {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Impossible de lire {path} : {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Configuration Noethys invalide : {path}")
    return data


def _custom_data_dir() -> Path | None:
    path = _user_config_dir() / "Customize.ini"
    if not path.is_file():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
        value = parser.get("repertoire_donnees", "chemin", fallback="").strip()
    except Exception:
        return None
    if value and Path(value).is_dir():
        return Path(value)
    return None


def _data_database_name(name: str) -> str:
    """Reproduit le suffixe ``DATA`` ajouté par ``GestionDB.DB()``."""
    normalized = name.strip()
    if normalized.lower().endswith("_data"):
        return normalized
    return f"{normalized}_DATA"


def _local_database_path(name: str) -> Path:
    filename = f"{_data_database_name(name)}.dat"
    portable_data = NOETHYS_DIR / "Portable" / "Data" / filename
    if portable_data.is_file():
        return portable_data

    custom = _custom_data_dir()
    if custom is not None:
        candidate = custom / filename
        if candidate.is_file():
            return candidate

    program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "noethys" / filename
    if program_data.is_file():
        return program_data

    raise RuntimeError(
        "Base locale Noethys introuvable. Chemins testés :\n"
        f"- {portable_data}\n"
        f"- {custom / filename if custom else '(aucun répertoire personnalisé)'}\n"
        f"- {program_data}"
    )


def _decode_network_password(password: str) -> str:
    """Reproduit DecodeMdpReseau sans importer GestionDB/wx."""
    if not password.startswith("#64#"):
        return password
    try:
        return base64.b64decode(password[4:]).decode("utf-8")
    except Exception as exc:
        raise RuntimeError("Le mot de passe réseau enregistré par Noethys est illisible.") from exc


def _query(only_open: bool, placeholder: str) -> tuple[str, tuple[object, ...]]:
    sql = "SELECT IDactivite, nom, abrege, date_debut, date_fin FROM activites"
    params: tuple[object, ...] = ()
    if only_open:
        sql += f" WHERE date_fin >= {placeholder}"
        params = (dt.date.today().isoformat(),)
    sql += " ORDER BY date_fin, nom"
    return sql, params


class NativeConfiguredActivityRepository(ActivityRepository):
    """Lecture de la base configurée, sans importer le runtime wx."""

    def fetch(self, only_open: bool = False) -> list[ActivityRow]:
        config = _load_config()
        name = str(config.get("nomFichier") or "").strip()
        if not name:
            raise RuntimeError("Config.json ne contient aucun 'nomFichier' actif.")

        if "[RESEAU]" in name:
            rows = self._fetch_mysql(name, only_open)
        else:
            rows = self._fetch_sqlite(name, only_open)
        return [ActivityRow.from_db_row(row) for row in rows]

    def _fetch_sqlite(self, name: str, only_open: bool) -> Sequence[Sequence[object]]:
        database = _local_database_path(name)
        sql, params = _query(only_open, "?")
        with sqlite3.connect(database) as connection:
            return connection.execute(sql, params).fetchall()

    def _fetch_mysql(self, descriptor: str, only_open: bool) -> Sequence[Sequence[object]]:
        try:
            import mysql.connector
        except ImportError as exc:
            raise RuntimeError(
                "mysql-connector-python manque dans l'environnement Qt. "
                "Relancez : .\\.venv\\Scripts\\python.exe -m pip install -r requirements-qt.txt"
            ) from exc

        before, database = descriptor.split("[RESEAU]", 1)
        try:
            port, host, user, encoded_password = before.split(";", 3)
        except ValueError as exc:
            raise RuntimeError("Descripteur réseau Noethys invalide dans Config.json.") from exc

        sql, params = _query(only_open, "%s")
        connect_params = {
            "host": host,
            "port": int(port),
            "user": user,
            "password": _decode_network_password(encoded_password),
            "database": _data_database_name(database).lower(),
            "use_unicode": True,
        }
        ca_path = _user_config_dir() / "ca-cert.pem"
        if ca_path.is_file():
            connect_params["ssl_ca"] = str(ca_path)

        connection = mysql.connector.connect(**connect_params)
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                return cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()


class NativeActivitiesWindow(ActivitiesWindow):
    """Liste Qt enrichie des pages, assistants et commandes déjà migrés."""

    def __init__(
        self,
        repository: ActivityRepository,
        *,
        editor_sqlite_path: Path | None = None,
        initial_open_only: bool = False,
        requested_theme: str | None = None,
    ):
        self.editor_sqlite_path = editor_sqlite_path
        self.simulation_mode = False
        super().__init__(
            repository,
            initial_open_only=initial_open_only,
            requested_theme=requested_theme,
        )

        self.add_action = self.deferred_actions[0]
        self.modify_action = self.deferred_actions[1]
        self.delete_action = self.deferred_actions[2]
        self.duplicate_action = self.deferred_actions[3]

        self.add_action.setEnabled(True)
        self.add_action.setToolTip("Créer une activité")
        self.modify_action.setToolTip("Modifier l'activité sélectionnée")
        self.delete_action.setToolTip("Supprimer l'activité sélectionnée")
        self.duplicate_action.setToolTip("Dupliquer l'activité sélectionnée")

        self.add_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder)
        )
        self.modify_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self.delete_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        self.duplicate_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        )

        self.add_action.triggered.connect(self._add_activity)
        self.modify_action.triggered.connect(self._edit_selected)
        self.delete_action.triggered.connect(self._delete_selected)
        self.duplicate_action.triggered.connect(self._duplicate_selected)

        self.simulation_action = QAction("Simulation", self)
        self.simulation_action.setCheckable(True)
        self.simulation_action.setToolTip(
            "Prévisualiser Ajouter / Dupliquer / Supprimer sans aucune écriture"
        )
        self.simulation_action.toggled.connect(self._set_simulation_mode)

        toolbar = self.findChild(QToolBar)
        if toolbar is not None:
            for action in (
                self.add_action,
                self.modify_action,
                self.delete_action,
                self.duplicate_action,
            ):
                toolbar.insertAction(self.export_text_action, action)
            toolbar.insertSeparator(self.export_text_action)
            toolbar.insertAction(self.export_text_action, self.simulation_action)
            toolbar.insertSeparator(self.export_text_action)

        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._sync_lifecycle_actions)
        self.table.doubleClicked.connect(self._edit_selected)
        self._sync_lifecycle_actions()

    def _selected_activity(self) -> ActivityRow | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        source_index = self.proxy.mapToSource(index)
        if not source_index.isValid():
            return None
        return self.model.row_at(source_index.row())

    def _selected_activity_id(self) -> int | None:
        row = self._selected_activity()
        return row.activity_id if row is not None else None

    def _sync_lifecycle_actions(self, *_args) -> None:
        selected = self._selected_activity() is not None
        self.add_action.setEnabled(True)
        self.modify_action.setEnabled(selected and not self.simulation_mode)
        self.delete_action.setEnabled(selected)
        self.duplicate_action.setEnabled(selected)
        if self.simulation_mode:
            self.modify_action.setToolTip("Modification désactivée en mode simulation")
        else:
            self.modify_action.setToolTip("Modifier l'activité sélectionnée")

    # Compatibilité avec les tests/appels précédents du POC.
    def _sync_modify_action(self, *_args) -> None:
        self._sync_lifecycle_actions(*_args)

    def _editor_and_lifecycle(self):
        from .activity_editor import NativeActivityEditorRepository
        from .activity_lifecycle import ActivityLifecycleRepository

        editor = NativeActivityEditorRepository(self.editor_sqlite_path)
        return editor, ActivityLifecycleRepository(editor)

    def _simulation_repository(self):
        from .activity_editor import NativeActivityEditorRepository
        from .activity_simulation import ActivitySimulationRepository

        return ActivitySimulationRepository(NativeActivityEditorRepository(self.editor_sqlite_path))

    def _set_simulation_mode(self, enabled: bool) -> None:
        self.simulation_mode = bool(enabled)
        self._sync_lifecycle_actions()
        if self.simulation_mode:
            self.statusBar().showMessage(
                "MODE SIMULATION — aucune écriture via Ajouter / Modifier / Dupliquer / Supprimer"
            )
        else:
            self.statusBar().showMessage("Mode réel réactivé", 3500)

    def _select_activity_id(self, activity_id: int) -> None:
        for proxy_row in range(self.proxy.rowCount()):
            proxy_index = self.proxy.index(proxy_row, 0)
            source_index = self.proxy.mapToSource(proxy_index)
            if not source_index.isValid():
                continue
            row = self.model.row_at(source_index.row())
            if row.activity_id == activity_id:
                self.table.setCurrentIndex(self.proxy.index(proxy_row, 1))
                self.table.selectRow(proxy_row)
                break
        self._sync_lifecycle_actions()

    def _add_activity(self, *_args) -> None:
        try:
            from .activity_assistants import ActivityAssistantChoiceDialog

            choice = ActivityAssistantChoiceDialog(self)
        except Exception as exc:
            QMessageBox.critical(self, "Création impossible", str(exc))
            return
        if choice.exec() != QDialog.DialogCode.Accepted:
            return
        code = choice.selected_code()
        if code == "nouveau":
            if self.simulation_mode:
                try:
                    report = self._simulation_repository().manual_create_report()
                    QMessageBox.information(self, "Simulation — création", report.as_text())
                except Exception as exc:
                    QMessageBox.critical(self, "Simulation impossible", str(exc))
                return
            self._add_manual_activity()
            return
        self._run_creation_assistant(code)

    def _add_manual_activity(self) -> None:
        try:
            editor_repository, lifecycle = self._editor_and_lifecycle()
            activity_id = lifecycle.create_activity()
        except Exception as exc:
            QMessageBox.critical(self, "Création impossible", str(exc))
            return

        try:
            from .activity_complete import ActivityEditorDialog

            dialog = ActivityEditorDialog(editor_repository, activity_id, self)
            dialog.setWindowTitle("Nouvelle activité")
            result = dialog.exec()
        except Exception as exc:
            try:
                lifecycle.discard_new_activity(activity_id)
            except Exception as cleanup_exc:
                QMessageBox.critical(
                    self,
                    "Création impossible",
                    f"{exc}\n\nLe nettoyage de l'activité provisoire a aussi échoué : {cleanup_exc}",
                )
                return
            QMessageBox.critical(self, "Création impossible", str(exc))
            self.reload()
            return

        if result == QDialog.DialogCode.Accepted:
            self.reload()
            self._select_activity_id(activity_id)
            return

        try:
            lifecycle.discard_new_activity(activity_id)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Annulation incomplète",
                "L'activité provisoire n'a pas pu être supprimée :\n" + str(exc),
            )
        self.reload()

    def _run_creation_assistant(self, code: str) -> None:
        try:
            from .activity_assistants import ActivityAssistantDialog
            from .activity_assistants_core import ActivityAssistantRepository
            from .activity_editor import NativeActivityEditorRepository

            repository = ActivityAssistantRepository(
                NativeActivityEditorRepository(self.editor_sqlite_path)
            )
            dialog = ActivityAssistantDialog(repository, code, self)
        except Exception as exc:
            QMessageBox.critical(self, "Assistant impossible", str(exc))
            return
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        configuration = dialog.configuration()
        try:
            plan = repository.preview(configuration)
        except Exception as exc:
            QMessageBox.critical(self, "Assistant impossible", str(exc))
            return
        if self.simulation_mode:
            QMessageBox.information(self, "Simulation — assistant", plan.as_text())
            return
        confirm = QMessageBox.question(
            self,
            "Générer l'activité",
            plan.as_text() + "\n\nConfirmer la génération ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            activity_id = repository.generate(configuration)
        except Exception as exc:
            QMessageBox.critical(self, "Génération impossible", str(exc))
            return
        self.reload()
        self._select_activity_id(activity_id)
        self.statusBar().showMessage("Activité générée par l'assistant Qt", 5000)

    def _edit_selected(self, *_args) -> None:
        activity_id = self._selected_activity_id()
        if activity_id is None:
            return
        if self.simulation_mode:
            QMessageBox.information(
                self,
                "Mode simulation",
                "La modification est désactivée en mode simulation afin de garantir zéro écriture.",
            )
            return

        try:
            from .activity_complete import ActivityEditorDialog
            from .activity_editor import NativeActivityEditorRepository

            editor_repository = NativeActivityEditorRepository(self.editor_sqlite_path)
            dialog = ActivityEditorDialog(editor_repository, activity_id, self)
        except Exception as exc:
            QMessageBox.critical(self, "Modification impossible", str(exc))
            return

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.reload()
            self._select_activity_id(activity_id)

    def _duplicate_selected(self, *_args) -> None:
        row = self._selected_activity()
        if row is None:
            return
        if self.simulation_mode:
            try:
                report = self._simulation_repository().duplicate_report(row.activity_id)
                QMessageBox.information(self, "Simulation — duplication", report.as_text())
            except Exception as exc:
                QMessageBox.critical(self, "Simulation impossible", str(exc))
            return

        answer = QMessageBox.question(
            self,
            "Duplication",
            f"Confirmez-vous la duplication de l'activité « {row.name} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            _editor, lifecycle = self._editor_and_lifecycle()
            new_id = lifecycle.duplicate_activity(row.activity_id, f"Copie de {row.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Duplication impossible", str(exc))
            return
        self.reload()
        self._select_activity_id(new_id)

    def _delete_selected(self, *_args) -> None:
        row = self._selected_activity()
        if row is None:
            return
        if self.simulation_mode:
            try:
                report = self._simulation_repository().delete_report(row.activity_id)
                if report.blocked:
                    QMessageBox.warning(self, "Simulation — suppression", report.as_text())
                else:
                    QMessageBox.information(self, "Simulation — suppression", report.as_text())
            except Exception as exc:
                QMessageBox.critical(self, "Simulation impossible", str(exc))
            return

        try:
            _editor, lifecycle = self._editor_and_lifecycle()
            check = lifecycle.delete_check(row.activity_id)
        except Exception as exc:
            QMessageBox.critical(self, "Suppression impossible", str(exc))
            return

        if not check.allowed:
            QMessageBox.critical(
                self,
                "Suppression impossible",
                "Vous ne pouvez pas supprimer cette activité car "
                f"{check.registrations} individu(s) y sont déjà inscrits.",
            )
            return

        first = QMessageBox.question(
            self,
            "Suppression",
            f"Souhaitez-vous vraiment supprimer l'activité « {row.name} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No,
        )
        if first != QMessageBox.StandardButton.Yes:
            return

        second = QMessageBox.warning(
            self,
            "Suppression",
            "Vous êtes vraiment sûr de vouloir supprimer cette activité ?\n\n"
            "Toute suppression sera irréversible !",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No,
        )
        if second != QMessageBox.StandardButton.Yes:
            return

        try:
            # Le contrôle des inscriptions est répété dans delete_activity afin
            # de fermer la fenêtre de course entre confirmation et suppression.
            lifecycle.delete_activity(row.activity_id)
        except Exception as exc:
            QMessageBox.critical(self, "Suppression impossible", str(exc))
            return
        self.reload()
        self._sync_lifecycle_actions()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Noethys Qt — Activités")
    app.setOrganizationName("Noethys")

    if args.sqlite:
        from .activities_prototype import SqliteActivityRepository

        repository: ActivityRepository = SqliteActivityRepository(args.sqlite)
    else:
        repository = NativeConfiguredActivityRepository()

    window = NativeActivitiesWindow(
        repository,
        editor_sqlite_path=args.sqlite,
        initial_open_only=args.open_only,
        requested_theme=args.theme,
    )
    apply_activity_visuals(window)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
