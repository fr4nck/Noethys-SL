"""Page Qt « Étiquettes » de la fiche Activité.

Les étiquettes de consommations sont historiquement enregistrées immédiatement :
ellles forment un arbre par activité, peuvent être actives ou de regroupement,
être ordonnées entre sœurs et ne peuvent pas être supprimées lorsqu'une
consommation les utilise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .activity_calendar import ActivityEditorDialog as CalendarActivityEditorDialog
from .activity_editor import NativeActivityEditorRepository


@dataclass(frozen=True, slots=True)
class ActivityLabel:
    label_id: int
    activity_id: int
    label: str
    parent_id: int | None
    order: int
    color: str | None
    active: bool


def _parse_label_ids(raw: object) -> tuple[int, ...]:
    if raw in (None, ""):
        return ()
    result: list[int] = []
    for value in str(raw).split(";"):
        text = value.strip()
        if not text:
            continue
        try:
            result.append(int(text))
        except ValueError:
            continue
    return tuple(result)


def _parse_color(raw: str | None) -> QColor:
    if not raw:
        return QColor(255, 255, 255)
    text = raw.strip().strip("()")
    try:
        red, green, blue = (int(part.strip()) for part in text.split(",", 2))
    except (TypeError, ValueError):
        return QColor(255, 255, 255)
    return QColor(red, green, blue)


def _format_color(color: QColor) -> str:
    return f"({color.red()}, {color.green()}, {color.blue()})"


class ActivityLabelsRepository:
    """Accès SQL minimal reproduisant le contrat de ``CTRL_Etiquettes``."""

    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont transitoire volontaire

    def list(self, activity_id: int) -> list[ActivityLabel]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT IDetiquette, IDactivite, label, parent, ordre, couleur, active
                    FROM etiquettes WHERE IDactivite={placeholder}
                    ORDER BY parent, ordre, IDetiquette""",
                (activity_id,),
            )
            return [
                ActivityLabel(
                    label_id=int(row[0]),
                    activity_id=int(row[1]),
                    label=str(row[2] or ""),
                    parent_id=int(row[3]) if row[3] is not None else None,
                    order=int(row[4] or 0),
                    color=str(row[5]) if row[5] not in (None, "") else None,
                    active=bool(row[6]),
                )
                for row in cursor.fetchall()
            ]
        finally:
            cursor.close(); connection.close()

    def _validate_parent(
        self,
        activity_id: int,
        parent_id: int | None,
        label_id: int | None = None,
    ) -> None:
        if parent_id is None:
            return
        rows = self.list(activity_id)
        by_id = {row.label_id: row for row in rows}
        if parent_id not in by_id:
            raise ValueError("L'étiquette parente n'appartient pas à cette activité.")
        if label_id is None:
            return
        if parent_id == label_id:
            raise ValueError("Une étiquette ne peut pas être sa propre parente.")
        current = by_id.get(parent_id)
        seen: set[int] = set()
        while current is not None and current.parent_id is not None:
            if current.label_id in seen:
                raise ValueError("La hiérarchie des étiquettes contient une boucle.")
            seen.add(current.label_id)
            if current.parent_id == label_id:
                raise ValueError("Une étiquette ne peut pas être déplacée sous l'une de ses descendantes.")
            current = by_id.get(current.parent_id)

    def _next_order(self, cursor, placeholder: str, activity_id: int, parent_id: int | None) -> int:
        if parent_id is None:
            cursor.execute(
                f"SELECT COALESCE(MAX(ordre), 0) FROM etiquettes "
                f"WHERE IDactivite={placeholder} AND parent IS NULL",
                (activity_id,),
            )
        else:
            cursor.execute(
                f"SELECT COALESCE(MAX(ordre), 0) FROM etiquettes "
                f"WHERE IDactivite={placeholder} AND parent={placeholder}",
                (activity_id, parent_id),
            )
        return int(cursor.fetchone()[0] or 0) + 1

    def save(
        self,
        activity_id: int,
        label: str,
        parent_id: int | None,
        color: str | None,
        active: bool,
        label_id: int | None = None,
    ) -> int:
        label = label.strip()
        if not label:
            raise ValueError("Vous devez obligatoirement saisir un label pour cette étiquette.")
        self._validate_parent(activity_id, parent_id, label_id)

        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            if label_id is None:
                order = self._next_order(cursor, placeholder, activity_id, parent_id)
                cursor.execute(
                    "INSERT INTO etiquettes (label, IDactivite, parent, couleur, ordre, active) VALUES "
                    f"({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (label, activity_id, parent_id, color, order, 1 if active else 0),
                )
                label_id = int(cursor.lastrowid)
            else:
                cursor.execute(
                    f"SELECT parent, ordre FROM etiquettes WHERE IDetiquette={placeholder} "
                    f"AND IDactivite={placeholder}",
                    (label_id, activity_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Étiquette introuvable.")
                old_parent = int(row[0]) if row[0] is not None else None
                old_order = int(row[1] or 0)
                order = old_order if old_parent == parent_id else self._next_order(
                    cursor, placeholder, activity_id, parent_id
                )
                cursor.execute(
                    f"UPDATE etiquettes SET label={placeholder}, parent={placeholder}, couleur={placeholder}, "
                    f"ordre={placeholder}, active={placeholder} "
                    f"WHERE IDetiquette={placeholder} AND IDactivite={placeholder}",
                    (label, parent_id, color, order, 1 if active else 0, label_id, activity_id),
                )
                if old_parent != parent_id:
                    self._resequence(cursor, placeholder, activity_id, old_parent)
            connection.commit()
            return int(label_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()

    def consumption_usage(self) -> dict[int, int]:
        connection, _placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute("SELECT etiquettes FROM consommations WHERE etiquettes IS NOT NULL AND etiquettes<>''")
            usage: dict[int, int] = {}
            for (raw_ids,) in cursor.fetchall():
                for label_id in _parse_label_ids(raw_ids):
                    usage[label_id] = usage.get(label_id, 0) + 1
            return usage
        finally:
            cursor.close(); connection.close()

    @staticmethod
    def descendants(rows: Iterable[ActivityLabel], label_id: int) -> list[ActivityLabel]:
        children: dict[int | None, list[ActivityLabel]] = {}
        for row in rows:
            children.setdefault(row.parent_id, []).append(row)
        result: list[ActivityLabel] = []

        def collect(parent_id: int) -> None:
            for child in children.get(parent_id, ()):
                result.append(child)
                collect(child.label_id)

        collect(label_id)
        return result

    def delete(self, activity_id: int, label_id: int) -> None:
        rows = self.list(activity_id)
        selected = next((row for row in rows if row.label_id == label_id), None)
        if selected is None:
            raise ValueError("Étiquette introuvable.")
        descendants = self.descendants(rows, label_id)
        usage = self.consumption_usage()
        for row in (selected, *descendants):
            if usage.get(row.label_id, 0):
                raise ValueError(
                    f"L'étiquette « {row.label} » est déjà associée à "
                    f"{usage[row.label_id]} consommation(s)."
                )

        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            for row in reversed(descendants):
                cursor.execute(
                    f"DELETE FROM etiquettes WHERE IDetiquette={placeholder} AND IDactivite={placeholder}",
                    (row.label_id, activity_id),
                )
            cursor.execute(
                f"DELETE FROM etiquettes WHERE IDetiquette={placeholder} AND IDactivite={placeholder}",
                (label_id, activity_id),
            )
            self._resequence(cursor, placeholder, activity_id, selected.parent_id)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()

    def move(self, activity_id: int, label_id: int, delta: int) -> None:
        if delta not in (-1, 1):
            raise ValueError("Le déplacement doit être -1 ou +1.")
        rows = self.list(activity_id)
        selected = next((row for row in rows if row.label_id == label_id), None)
        if selected is None:
            raise ValueError("Étiquette introuvable.")
        siblings = sorted(
            (row for row in rows if row.parent_id == selected.parent_id),
            key=lambda row: (row.order, row.label_id),
        )
        index = next(index for index, row in enumerate(siblings) if row.label_id == label_id)
        target = index + delta
        if target < 0 or target >= len(siblings):
            return
        siblings[index], siblings[target] = siblings[target], siblings[index]
        self._write_order(activity_id, siblings)

    def sort_siblings(self, activity_id: int, label_id: int) -> None:
        rows = self.list(activity_id)
        selected = next((row for row in rows if row.label_id == label_id), None)
        if selected is None:
            raise ValueError("Étiquette introuvable.")
        siblings = sorted(
            (row for row in rows if row.parent_id == selected.parent_id),
            key=lambda row: (row.label.casefold(), row.label_id),
        )
        self._write_order(activity_id, siblings)

    def _write_order(self, activity_id: int, rows: Iterable[ActivityLabel]) -> None:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            for order, row in enumerate(rows, start=1):
                cursor.execute(
                    f"UPDATE etiquettes SET ordre={placeholder} WHERE IDetiquette={placeholder} "
                    f"AND IDactivite={placeholder}",
                    (order, row.label_id, activity_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()

    @staticmethod
    def _resequence(cursor, placeholder: str, activity_id: int, parent_id: int | None) -> None:
        if parent_id is None:
            cursor.execute(
                f"SELECT IDetiquette FROM etiquettes WHERE IDactivite={placeholder} AND parent IS NULL "
                "ORDER BY ordre, IDetiquette",
                (activity_id,),
            )
        else:
            cursor.execute(
                f"SELECT IDetiquette FROM etiquettes WHERE IDactivite={placeholder} AND parent={placeholder} "
                "ORDER BY ordre, IDetiquette",
                (activity_id, parent_id),
            )
        for order, (current_id,) in enumerate(cursor.fetchall(), start=1):
            cursor.execute(
                f"UPDATE etiquettes SET ordre={placeholder} WHERE IDetiquette={placeholder}",
                (order, current_id),
            )


class LabelEditDialog(QDialog):
    def __init__(
        self,
        repository: ActivityLabelsRepository,
        activity_id: int,
        current: ActivityLabel | None = None,
        default_parent_id: int | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.activity_id = activity_id
        self.current = current
        self.color = _parse_color(current.color if current else None)
        self.setWindowTitle("Modifier une étiquette" if current else "Ajouter une étiquette")
        self.resize(520, 260)

        root = QVBoxLayout(self); form = QFormLayout()
        self.label_edit = QLineEdit(current.label if current else "", self)
        self.parent_combo = QComboBox(self)
        self.parent_combo.addItem("Activité", None)
        rows = repository.list(activity_id)
        by_parent: dict[int | None, list[ActivityLabel]] = {}
        for row in rows:
            by_parent.setdefault(row.parent_id, []).append(row)
        for values in by_parent.values():
            values.sort(key=lambda row: (row.order, row.label_id))

        def add_children(parent_id: int | None, depth: int) -> None:
            for row in by_parent.get(parent_id, ()):
                if current is not None and row.label_id == current.label_id:
                    continue
                self.parent_combo.addItem(f"{'  ' * depth}{row.label}", row.label_id)
                add_children(row.label_id, depth + 1)

        add_children(None, 0)
        parent_id = current.parent_id if current else default_parent_id
        index = self.parent_combo.findData(parent_id)
        self.parent_combo.setCurrentIndex(index if index >= 0 else 0)
        self.color_button = QPushButton(self)
        self.color_button.clicked.connect(self._choose_color)
        self.active_check = QCheckBox("Étiquette active", self)
        self.active_check.setChecked(True if current is None else current.active)
        form.addRow("Label :", self.label_edit)
        form.addRow("Parent :", self.parent_combo)
        form.addRow("Couleur :", self.color_button)
        form.addRow("", self.active_check)
        root.addLayout(form)
        self._refresh_color_button()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Valider")
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(self.color, self, "Couleur de l'étiquette")
        if color.isValid():
            self.color = color
            self._refresh_color_button()

    def _refresh_color_button(self) -> None:
        self.color_button.setText(_format_color(self.color))
        self.color_button.setStyleSheet(
            f"background-color: rgb({self.color.red()}, {self.color.green()}, {self.color.blue()});"
        )

    def _accept(self) -> None:
        label = self.label_edit.text().strip()
        if not label:
            QMessageBox.warning(
                self, "Erreur de saisie", "Vous devez obligatoirement saisir un label pour cette étiquette."
            )
            self.label_edit.setFocus(); return
        try:
            self.repository._validate_parent(  # noqa: SLF001 - validation sans écriture
                self.activity_id,
                self.parent_combo.currentData(),
                self.current.label_id if self.current else None,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc)); return
        self.accept()

    def values(self) -> tuple[str, int | None, str, bool]:
        return (
            self.label_edit.text().strip(),
            self.parent_combo.currentData(),
            _format_color(self.color),
            self.active_check.isChecked(),
        )


class ActivityLabelsPage(QWidget):
    """Arbre Qt des étiquettes de consommations de l'activité."""

    def __init__(
        self,
        editor_repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.activity_id = activity_id
        self.repository = ActivityLabelsRepository(editor_repository)
        root = QVBoxLayout(self); root.setContentsMargins(10, 10, 10, 10); root.setSpacing(8)

        intro = QLabel(
            "Les étiquettes sont optionnelles. Elles permettent d'associer aux consommations des actions, "
            "intervenants, salles, états ou regroupements.",
            self,
        )
        intro.setWordWrap(True); root.addWidget(intro)

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(("Étiquette", "État", "Couleur"))
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, self.tree.header().ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, self.tree.header().ResizeMode.ResizeToContents)
        root.addWidget(self.tree, 1)

        actions = QHBoxLayout()
        self.add_button = QPushButton("Ajouter", self)
        self.edit_button = QPushButton("Modifier", self)
        self.delete_button = QPushButton("Supprimer", self)
        self.up_button = QPushButton("Monter", self)
        self.down_button = QPushButton("Descendre", self)
        self.sort_button = QPushButton("Trier A–Z", self)
        style = self.style()
        self.add_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.edit_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.delete_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.up_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.down_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        for button in (
            self.add_button, self.edit_button, self.delete_button,
            self.up_button, self.down_button, self.sort_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1); root.addLayout(actions)

        self.add_button.clicked.connect(self.add_label)
        self.edit_button.clicked.connect(self.edit_label)
        self.delete_button.clicked.connect(self.delete_label)
        self.up_button.clicked.connect(lambda: self.move_label(-1))
        self.down_button.clicked.connect(lambda: self.move_label(1))
        self.sort_button.clicked.connect(self.sort_labels)
        self.tree.itemDoubleClicked.connect(lambda _item, _column: self.edit_label())
        self.tree.itemSelectionChanged.connect(self._sync_actions)
        self.refresh()

    def _selected(self) -> ActivityLabel | None:
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def refresh(self, selected_id: int | None = None) -> None:
        rows = self.repository.list(self.activity_id)
        self.tree.clear()
        items: dict[int, QTreeWidgetItem] = {}
        remaining = list(rows)
        while remaining:
            progressed = False
            for row in list(remaining):
                if row.parent_id is not None and row.parent_id not in items:
                    continue
                parent_item = items.get(row.parent_id)
                item = QTreeWidgetItem(parent_item if parent_item else self.tree)
                item.setText(0, row.label)
                item.setText(1, "Active" if row.active else "Regroupement / inactive")
                item.setText(2, row.color or "")
                item.setData(0, Qt.ItemDataRole.UserRole, row)
                color = _parse_color(row.color)
                item.setBackground(2, color)
                items[row.label_id] = item
                remaining.remove(row)
                progressed = True
            if not progressed:
                # Les données historiques incohérentes restent visibles à la racine.
                for row in remaining:
                    item = QTreeWidgetItem(self.tree)
                    item.setText(0, row.label)
                    item.setText(1, "Active" if row.active else "Regroupement / inactive")
                    item.setText(2, row.color or "")
                    item.setData(0, Qt.ItemDataRole.UserRole, row)
                    items[row.label_id] = item
                break
        self.tree.expandAll()
        if selected_id in items:
            self.tree.setCurrentItem(items[selected_id])
        self._sync_actions()

    def add_label(self) -> None:
        selected = self._selected()
        default_parent_id = selected.label_id if selected else None
        dialog = LabelEditDialog(
            self.repository, self.activity_id, default_parent_id=default_parent_id, parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            label_id = self.repository.save(self.activity_id, *dialog.values())
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self.refresh(label_id)

    def edit_label(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        dialog = LabelEditDialog(self.repository, self.activity_id, selected, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.repository.save(
                self.activity_id, *dialog.values(), label_id=selected.label_id
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc)); return
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self.refresh(selected.label_id)

    def delete_label(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        descendants = self.repository.descendants(self.repository.list(self.activity_id), selected.label_id)
        if descendants:
            text = (
                f"Supprimer « {selected.label} » et ses {len(descendants)} étiquette(s) enfant(s) ?"
            )
        else:
            text = f"Supprimer l'étiquette « {selected.label} » ?"
        if QMessageBox.question(
            self, "Suppression", text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repository.delete(self.activity_id, selected.label_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Suppression impossible", str(exc)); return
        except Exception as exc:
            QMessageBox.critical(self, "Suppression impossible", str(exc)); return
        self.refresh()

    def move_label(self, delta: int) -> None:
        selected = self._selected()
        if selected is None:
            return
        try:
            self.repository.move(self.activity_id, selected.label_id, delta)
        except Exception as exc:
            QMessageBox.critical(self, "Déplacement impossible", str(exc)); return
        self.refresh(selected.label_id)

    def sort_labels(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        try:
            self.repository.sort_siblings(self.activity_id, selected.label_id)
        except Exception as exc:
            QMessageBox.critical(self, "Tri impossible", str(exc)); return
        self.refresh(selected.label_id)

    def _sync_actions(self) -> None:
        selected = self._selected()
        enabled = selected is not None
        for button in (self.edit_button, self.delete_button, self.up_button, self.down_button, self.sort_button):
            button.setEnabled(enabled)


class ActivityEditorDialog(CalendarActivityEditorDialog):
    """Fiche Activité avec page Étiquettes Qt réelle."""

    def __init__(
        self,
        repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(4)
        self.tabs.removeTab(4)
        if old_page is not None:
            old_page.deleteLater()
        self.labels_page = ActivityLabelsPage(repository, activity_id, self)
        self.tabs.insertTab(4, self.labels_page, "Étiquettes")
