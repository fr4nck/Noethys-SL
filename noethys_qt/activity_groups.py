"""Page Qt « Groupes » de la fiche Activité.

Cette migration reprend le contrat fonctionnel de ``OL_Groupes`` : liste
ordonnée, ajout, modification, suppression protégée et déplacement. Les
opérations de cette page sont enregistrées immédiatement, comme dans le
comportement historique de Noethys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .activity_editor import (
    ActivityEditorDialog as BaseActivityEditorDialog,
    NativeActivityEditorRepository,
)


@dataclass(frozen=True, slots=True)
class ActivityGroup:
    group_id: int
    activity_id: int
    name: str
    order: int
    short_name: str
    max_members: int | None


class ActivityGroupsRepository:
    """Adaptateur minimal autour de la connexion déjà ouverte par l'éditeur."""

    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont transitoire volontaire

    def list(self, activity_id: int) -> list[ActivityGroup]:
        connection, placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"""
                    SELECT IDgroupe, IDactivite, nom, ordre, abrege, nbre_inscrits_max
                    FROM groupes
                    WHERE IDactivite={placeholder}
                    ORDER BY ordre, IDgroupe
                    """,
                    (activity_id,),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return [
            ActivityGroup(
                group_id=int(row[0]),
                activity_id=int(row[1]),
                name=str(row[2] or ""),
                order=int(row[3] or 0),
                short_name=str(row[4] or ""),
                max_members=int(row[5]) if row[5] not in (None, "") else None,
            )
            for row in rows
        ]

    def add(self, activity_id: int, name: str, short_name: str, max_members: int | None) -> int:
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT COALESCE(MAX(ordre), 0) FROM groupes WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            order = int(cursor.fetchone()[0] or 0) + 1
            cursor.execute(
                "INSERT INTO groupes (IDactivite, nom, ordre, abrege, nbre_inscrits_max) "
                f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                (activity_id, name, order, short_name or None, max_members),
            )
            group_id = int(cursor.lastrowid)
            connection.commit()
            return group_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def update(self, group: ActivityGroup, name: str, short_name: str, max_members: int | None) -> None:
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "UPDATE groupes SET "
                f"nom={placeholder}, abrege={placeholder}, nbre_inscrits_max={placeholder} "
                f"WHERE IDgroupe={placeholder} AND IDactivite={placeholder}",
                (name, short_name or None, max_members, group.group_id, group.activity_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def usage(self, group_id: int) -> list[str]:
        """Retourne les dépendances qui interdisent la suppression historique."""
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        dependencies: list[str] = []
        try:
            checks = (
                ("unites_groupes", "IDunite_groupe", "IDgroupe", "unité(s) de consommation"),
                ("ouvertures", "IDouverture", "IDgroupe", "ouverture(s)"),
                ("inscriptions", "IDinscription", "IDgroupe", "inscription(s)"),
                ("consommations", "IDconso", "IDgroupe", "consommation(s)"),
            )
            for table, counted_field, key_field, label in checks:
                cursor.execute(
                    f"SELECT COUNT({counted_field}) FROM {table} WHERE {key_field}={placeholder}",
                    (group_id,),
                )
                count = int(cursor.fetchone()[0] or 0)
                if count:
                    dependencies.append(f"{count} {label}")

            cursor.execute("SELECT groupes FROM tarifs WHERE groupes IS NOT NULL")
            tariff_count = 0
            for (raw_groups,) in cursor.fetchall():
                if raw_groups in (None, ""):
                    continue
                values = {
                    int(value)
                    for value in str(raw_groups).split(";")
                    if str(value).strip().isdigit()
                }
                if group_id in values:
                    tariff_count += 1
            if tariff_count:
                dependencies.append(f"{tariff_count} tarif(s)")
        finally:
            cursor.close()
            connection.close()
        return dependencies

    def delete(self, activity_id: int, group_id: int) -> None:
        dependencies = self.usage(group_id)
        if dependencies:
            raise ValueError("Ce groupe est encore utilisé par : " + ", ".join(dependencies) + ".")

        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"DELETE FROM groupes WHERE IDgroupe={placeholder} AND IDactivite={placeholder}",
                (group_id, activity_id),
            )
            # Le code historique nettoie également le remplissage résiduel.
            cursor.execute(f"DELETE FROM remplissage WHERE IDgroupe={placeholder}", (group_id,))
            self._resequence(cursor, placeholder, activity_id)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def move(self, activity_id: int, group_id: int, delta: int) -> None:
        if delta not in (-1, 1):
            raise ValueError("Le déplacement doit être -1 ou +1.")
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT IDgroupe FROM groupes WHERE IDactivite={placeholder} ORDER BY ordre, IDgroupe",
                (activity_id,),
            )
            ids = [int(row[0]) for row in cursor.fetchall()]
            if group_id not in ids:
                raise ValueError("Groupe introuvable.")
            index = ids.index(group_id)
            target = index + delta
            if target < 0 or target >= len(ids):
                return
            ids[index], ids[target] = ids[target], ids[index]
            for order, current_id in enumerate(ids, start=1):
                cursor.execute(
                    f"UPDATE groupes SET ordre={placeholder} WHERE IDgroupe={placeholder}",
                    (order, current_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _resequence(cursor, placeholder: str, activity_id: int) -> None:
        cursor.execute(
            f"SELECT IDgroupe FROM groupes WHERE IDactivite={placeholder} ORDER BY ordre, IDgroupe",
            (activity_id,),
        )
        for order, (group_id,) in enumerate(cursor.fetchall(), start=1):
            cursor.execute(
                f"UPDATE groupes SET ordre={placeholder} WHERE IDgroupe={placeholder}",
                (order, group_id),
            )


class GroupTableModel(QAbstractTableModel):
    HEADERS = ("Nom", "Abrégé", "Nbre inscrits max.")

    def __init__(self, rows: Iterable[ActivityGroup] = ()):  # noqa: D107
        super().__init__()
        self.rows = list(rows)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or role != int(Qt.ItemDataRole.DisplayRole):
            return None
        row = self.rows[index.row()]
        return (row.name, row.short_name, row.max_members if row.max_members is not None else "")[index.column()]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)):  # noqa: N802,E501
        if orientation == Qt.Orientation.Horizontal and role == int(Qt.ItemDataRole.DisplayRole):
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def replace(self, rows: Iterable[ActivityGroup]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def row_at(self, row: int) -> ActivityGroup:
        return self.rows[row]


class GroupEditDialog(QDialog):
    def __init__(self, group: ActivityGroup | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Modification d'un groupe" if group else "Saisie d'un groupe")
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(self)
        self.short_name_edit = QLineEdit(self)
        self.limit_check = QCheckBox("Limiter le nombre d'inscrits", self)
        self.max_members_spin = QSpinBox(self)
        self.max_members_spin.setRange(1, 99999)
        form.addRow("Nom :", self.name_edit)
        form.addRow("Abrégé :", self.short_name_edit)
        form.addRow(self.limit_check, self.max_members_spin)
        layout.addLayout(form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.accepted.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        if group is not None:
            self.name_edit.setText(group.name)
            self.short_name_edit.setText(group.short_name)
            self.limit_check.setChecked(group.max_members is not None)
            self.max_members_spin.setValue(group.max_members or 1)
        self.limit_check.toggled.connect(self.max_members_spin.setEnabled)
        self.max_members_spin.setEnabled(self.limit_check.isChecked())
        self.name_edit.setFocus()
        self.resize(440, self.sizeHint().height())

    def _accept_if_valid(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Erreur de saisie", "Vous devez obligatoirement saisir un nom de groupe.")
            self.name_edit.setFocus()
            return
        if not self.short_name_edit.text().strip():
            answer = QMessageBox.question(
                self,
                "Confirmation",
                "Aucun nom abrégé n'est saisi pour ce groupe. Continuer quand même ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.short_name_edit.setFocus()
                return
        self.accept()

    def values(self) -> tuple[str, str, int | None]:
        return (
            self.name_edit.text().strip(),
            self.short_name_edit.text().strip(),
            self.max_members_spin.value() if self.limit_check.isChecked() else None,
        )


class ActivityGroupsPage(QWidget):
    """Page Groupes directement exploitable dans la fiche activité Qt."""

    def __init__(
        self,
        editor_repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.activity_id = activity_id
        self.repository = ActivityGroupsRepository(editor_repository)
        self.model = GroupTableModel()

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        intro = QLabel(
            "Au moins un groupe est obligatoire. Si l'activité n'en distingue pas, utilisez « Groupe unique ».",
            self,
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        actions = QHBoxLayout()
        self.add_button = QPushButton("Ajouter", self)
        self.edit_button = QPushButton("Modifier", self)
        self.delete_button = QPushButton("Supprimer", self)
        self.up_button = QPushButton("Monter", self)
        self.down_button = QPushButton("Descendre", self)
        style = self.style()
        self.add_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.edit_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.delete_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.up_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.down_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        for button in (self.add_button, self.edit_button, self.delete_button):
            actions.addWidget(button)
        actions.addSpacing(8)
        actions.addWidget(self.up_button)
        actions.addWidget(self.down_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, self.table.horizontalHeader().ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, self.table.horizontalHeader().ResizeMode.ResizeToContents)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.table, 1)

        note = QLabel("Les ajouts, suppressions et déplacements sont enregistrés immédiatement, comme dans Noethys historique.", self)
        note.setWordWrap(True)
        note.setObjectName("activityGroupsNote")
        root.addWidget(note)

        self.add_button.clicked.connect(self.add_group)
        self.edit_button.clicked.connect(self.edit_group)
        self.delete_button.clicked.connect(self.delete_group)
        self.up_button.clicked.connect(lambda: self.move_group(-1))
        self.down_button.clicked.connect(lambda: self.move_group(1))
        self.table.doubleClicked.connect(lambda _index: self.edit_group())
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._sync_actions)

        self.refresh()
        self._sync_actions()

    def refresh(self, selected_id: int | None = None) -> None:
        rows = self.repository.list(self.activity_id)
        self.model.replace(rows)
        if selected_id is not None:
            for row_index, row in enumerate(rows):
                if row.group_id == selected_id:
                    self.table.selectRow(row_index)
                    self.table.setCurrentIndex(self.model.index(row_index, 0))
                    break
        self._sync_actions()

    def group_count(self) -> int:
        return self.model.rowCount()

    def selected_group(self) -> ActivityGroup | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return self.model.row_at(index.row())

    def add_group(self) -> None:
        dialog = GroupEditDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            group_id = self.repository.add(self.activity_id, *dialog.values())
        except Exception as exc:
            QMessageBox.critical(self, "Ajout impossible", str(exc))
            return
        self.refresh(group_id)

    def edit_group(self) -> None:
        group = self.selected_group()
        if group is None:
            return
        dialog = GroupEditDialog(group, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.update(group, *dialog.values())
        except Exception as exc:
            QMessageBox.critical(self, "Modification impossible", str(exc))
            return
        self.refresh(group.group_id)

    def delete_group(self) -> None:
        group = self.selected_group()
        if group is None:
            return
        dependencies = self.repository.usage(group.group_id)
        if dependencies:
            QMessageBox.warning(
                self,
                "Suppression impossible",
                "Ce groupe est encore utilisé par :\n• " + "\n• ".join(dependencies),
            )
            return
        answer = QMessageBox.question(
            self,
            "Suppression",
            f"Souhaitez-vous vraiment supprimer le groupe « {group.name} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repository.delete(self.activity_id, group.group_id)
        except Exception as exc:
            QMessageBox.critical(self, "Suppression impossible", str(exc))
            return
        self.refresh()

    def move_group(self, delta: int) -> None:
        group = self.selected_group()
        if group is None:
            return
        try:
            self.repository.move(self.activity_id, group.group_id, delta)
        except Exception as exc:
            QMessageBox.critical(self, "Déplacement impossible", str(exc))
            return
        self.refresh(group.group_id)

    def _sync_actions(self, *_args) -> None:
        group = self.selected_group()
        has_selection = group is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        if not has_selection:
            self.up_button.setEnabled(False)
            self.down_button.setEnabled(False)
            return
        row = self.table.currentIndex().row()
        self.up_button.setEnabled(row > 0)
        self.down_button.setEnabled(row >= 0 and row < self.model.rowCount() - 1)


class ActivityEditorDialog(BaseActivityEditorDialog):
    """Éditeur enrichi de la première page structurelle réellement migrée."""

    def __init__(
        self,
        repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(2)
        self.tabs.removeTab(2)
        if old_page is not None:
            old_page.deleteLater()
        self.group_page = ActivityGroupsPage(repository, activity_id, self)
        self.tabs.insertTab(2, self.group_page, "Groupes")

    def _save(self) -> None:
        if self.group_page.group_count() == 0:
            self.tabs.setCurrentWidget(self.group_page)
            QMessageBox.warning(
                self,
                "Erreur de saisie",
                "Vous devez créer au moins un groupe. Si nécessaire, créez simplement « Groupe unique ».",
            )
            return
        super()._save()
