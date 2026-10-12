"""Page Qt « Unités » de la fiche Activité.

La première passe rend les unités de consommation réellement modifiables et
affiche également les unités de remplissage existantes. Les données avancées
d'auto-génération restent strictement préservées tant que leur éditeur dédié
n'est pas migré.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
import re
from typing import Iterable

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .activity_editor import NativeActivityEditorRepository, UNLIMITED_END, UNLIMITED_START
from .activity_groups import ActivityEditorDialog as GroupsActivityEditorDialog


UNIT_TYPES = (
    ("Unitaire", "Standard"),
    ("Horaire", "Horaire"),
    ("Multihoraires", "Multi-horaires"),
    ("Evenement", "Evènementiel"),
    ("Quantite", "Quantité"),
)
UNIT_TYPE_LABELS = dict(UNIT_TYPES)
SHORTCUTS = (
    (None, "Aucune touche"),
    ("WXK_TAB", "Tabulation"),
    ("WXK_SHIFT", "Shift"),
    ("WXK_ALT", "Alt"),
    ("WXK_CONTROL", "Control"),
    ("WXK_SPACE", "Barre Espace"),
    *((f"WXK_F{number}", f"F{number}") for number in range(1, 13)),
)
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True, slots=True)
class ConsumptionUnit:
    unit_id: int | None
    activity_id: int
    name: str
    short_name: str
    type_code: str
    start_date: dt.date
    end_date: dt.date
    order: int
    auto_gen_active: bool
    hour_start: str | None = None
    hour_end: str | None = None
    meal: bool = False
    restaurateur_id: int | None = None
    shortcut: str | None = None
    hour_start_fixed: bool = False
    hour_end_fixed: bool = False
    auto_gen_conditions: str | None = None
    auto_gen_parameters: str | None = None

    @property
    def period(self) -> str:
        if self.start_date == UNLIMITED_START and self.end_date == UNLIMITED_END:
            return "Illimitée"
        return f"Du {self.start_date:%d/%m/%Y} au {self.end_date:%d/%m/%Y}"


@dataclass(frozen=True, slots=True)
class FillingUnit:
    filling_unit_id: int
    name: str
    short_name: str
    alert_threshold: int
    start_date: dt.date
    end_date: dt.date
    order: int
    hour_min: str | None
    hour_max: str | None

    @property
    def time_range(self) -> str:
        if self.hour_min and self.hour_max:
            return f"{self.hour_min.replace(':', 'h')}-{self.hour_max.replace(':', 'h')}"
        return ""

    @property
    def period(self) -> str:
        if self.start_date == UNLIMITED_START and self.end_date == UNLIMITED_END:
            return "Illimitée"
        return f"Du {self.start_date:%d/%m/%Y} au {self.end_date:%d/%m/%Y}"


def _to_date(value: object) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return UNLIMITED_START


def _qdate(value: dt.date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _normalized_time(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if not _TIME_RE.fullmatch(value):
        raise ValueError(f"L'heure « {value} » n'est pas valide. Utilisez HH:MM.")
    return value


class ActivityUnitsRepository:
    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont transitoire volontaire

    def list_units(self, activity_id: int) -> list[ConsumptionUnit]:
        connection, placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"""
                    SELECT IDunite, IDactivite, nom, abrege, type, date_debut, date_fin,
                           ordre, autogen_active, heure_debut, heure_fin, repas,
                           IDrestaurateur, touche_raccourci, heure_debut_fixe,
                           heure_fin_fixe, autogen_conditions, autogen_parametres
                    FROM unites
                    WHERE IDactivite={placeholder}
                    ORDER BY ordre, IDunite
                    """,
                    (activity_id,),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return [self._row_to_unit(row) for row in rows]

    @staticmethod
    def _row_to_unit(row) -> ConsumptionUnit:
        return ConsumptionUnit(
            unit_id=int(row[0]),
            activity_id=int(row[1]),
            name=str(row[2] or ""),
            short_name=str(row[3] or ""),
            type_code=str(row[4] or "Unitaire"),
            start_date=_to_date(row[5]),
            end_date=_to_date(row[6]),
            order=int(row[7] or 0),
            auto_gen_active=bool(row[8]),
            hour_start=str(row[9]) if row[9] not in (None, "") else None,
            hour_end=str(row[10]) if row[10] not in (None, "") else None,
            meal=bool(row[11]),
            restaurateur_id=int(row[12]) if row[12] not in (None, "") else None,
            shortcut=str(row[13]) if row[13] not in (None, "") else None,
            hour_start_fixed=bool(row[14]),
            hour_end_fixed=bool(row[15]),
            auto_gen_conditions=str(row[16]) if row[16] not in (None, "") else None,
            auto_gen_parameters=str(row[17]) if row[17] not in (None, "") else None,
        )

    def list_filling_units(self, activity_id: int) -> list[FillingUnit]:
        connection, placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"""
                    SELECT IDunite_remplissage, nom, abrege, seuil_alerte,
                           date_debut, date_fin, ordre, heure_min, heure_max
                    FROM unites_remplissage
                    WHERE IDactivite={placeholder}
                    ORDER BY ordre, IDunite_remplissage
                    """,
                    (activity_id,),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return [
            FillingUnit(
                filling_unit_id=int(row[0]),
                name=str(row[1] or ""),
                short_name=str(row[2] or ""),
                alert_threshold=int(row[3] or 0),
                start_date=_to_date(row[4]),
                end_date=_to_date(row[5]),
                order=int(row[6] or 0),
                hour_min=str(row[7]) if row[7] not in (None, "") else None,
                hour_max=str(row[8]) if row[8] not in (None, "") else None,
            )
            for row in rows
        ]

    def list_groups(self, activity_id: int) -> list[tuple[int, str]]:
        connection, placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"SELECT IDgroupe, nom FROM groupes WHERE IDactivite={placeholder} ORDER BY ordre, IDgroupe",
                    (activity_id,),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return [(int(row[0]), str(row[1] or "")) for row in rows]

    def unit_group_ids(self, unit_id: int | None) -> set[int]:
        if unit_id is None:
            return set()
        connection, placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"SELECT IDgroupe FROM unites_groupes WHERE IDunite={placeholder}",
                    (unit_id,),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return {int(row[0]) for row in rows}

    def incompatible_unit_ids(self, unit_id: int | None) -> set[int]:
        if unit_id is None:
            return set()
        connection, placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"SELECT IDunite_incompatible FROM unites_incompat WHERE IDunite={placeholder}",
                    (unit_id,),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return {int(row[0]) for row in rows}

    def list_restaurateurs(self) -> list[tuple[int, str]]:
        connection, _placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT IDrestaurateur, nom FROM restaurateurs ORDER BY nom")
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return [(int(row[0]), str(row[1] or "")) for row in rows]

    def save_unit(
        self,
        unit: ConsumptionUnit,
        *,
        group_ids: Iterable[int] | None,
        incompatible_ids: Iterable[int],
    ) -> int:
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            if unit.unit_id is not None:
                cursor.execute(
                    f"SELECT type FROM unites WHERE IDunite={placeholder}",
                    (unit.unit_id,),
                )
                previous = cursor.fetchone()
                previous_type = str(previous[0]) if previous else unit.type_code
                event_transition = (previous_type == "Evenement") != (unit.type_code == "Evenement")
                if event_transition:
                    for table, field, label in (
                        ("consommations", "IDconso", "consommations"),
                        ("evenements", "IDevenement", "évènements"),
                    ):
                        cursor.execute(
                            f"SELECT COUNT({field}) FROM {table} WHERE IDunite={placeholder}",
                            (unit.unit_id,),
                        )
                        if int(cursor.fetchone()[0] or 0):
                            raise ValueError(
                                f"Impossible de convertir cette unité vers/depuis le type Evènementiel : des {label} existent déjà."
                            )

            fields = (
                "IDactivite", "nom", "abrege", "type", "heure_debut", "heure_fin",
                "repas", "IDrestaurateur", "date_debut", "date_fin", "touche_raccourci",
                "heure_debut_fixe", "heure_fin_fixe", "autogen_active",
                "autogen_conditions", "autogen_parametres",
            )
            values = (
                unit.activity_id,
                unit.name,
                unit.short_name,
                unit.type_code,
                unit.hour_start,
                unit.hour_end,
                1 if unit.meal else 0,
                unit.restaurateur_id if unit.meal else None,
                unit.start_date.isoformat(),
                unit.end_date.isoformat(),
                unit.shortcut,
                1 if unit.hour_start_fixed else 0,
                1 if unit.hour_end_fixed else 0,
                1 if unit.auto_gen_active else 0,
                unit.auto_gen_conditions,
                unit.auto_gen_parameters,
            )

            if unit.unit_id is None:
                cursor.execute(
                    f"SELECT COALESCE(MAX(ordre), 0) FROM unites WHERE IDactivite={placeholder}",
                    (unit.activity_id,),
                )
                order = int(cursor.fetchone()[0] or 0) + 1
                insert_fields = fields + ("ordre",)
                markers = ", ".join(placeholder for _ in insert_fields)
                cursor.execute(
                    f"INSERT INTO unites ({', '.join(insert_fields)}) VALUES ({markers})",
                    values + (order,),
                )
                unit_id = int(cursor.lastrowid)
            else:
                unit_id = unit.unit_id
                assignments = ", ".join(f"{field}={placeholder}" for field in fields)
                cursor.execute(
                    f"UPDATE unites SET {assignments} WHERE IDunite={placeholder}",
                    values + (unit_id,),
                )

            cursor.execute(f"DELETE FROM unites_groupes WHERE IDunite={placeholder}", (unit_id,))
            if group_ids is not None:
                for group_id in sorted(set(int(value) for value in group_ids)):
                    cursor.execute(
                        "INSERT INTO unites_groupes (IDunite, IDgroupe) "
                        f"VALUES ({placeholder}, {placeholder})",
                        (unit_id, group_id),
                    )

            cursor.execute(f"DELETE FROM unites_incompat WHERE IDunite={placeholder}", (unit_id,))
            for incompatible_id in sorted(set(int(value) for value in incompatible_ids if int(value) != unit_id)):
                cursor.execute(
                    "INSERT INTO unites_incompat (IDunite, IDunite_incompatible) "
                    f"VALUES ({placeholder}, {placeholder})",
                    (unit_id, incompatible_id),
                )

            connection.commit()
            return unit_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def usage(self, unit_id: int) -> list[str]:
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        dependencies: list[str] = []
        try:
            checks = (
                ("unites_remplissage_unites", "IDunite_remplissage", "unité(s) de remplissage"),
                ("ouvertures", "IDouverture", "ouverture(s)"),
                ("combi_tarifs_unites", "IDcombi_tarif", "combinaison(s) de tarifs"),
                ("aides_combi_unites", "IDaide_combi_unite", "combinaison(s) d'aides"),
            )
            for table, counted_field, label in checks:
                cursor.execute(
                    f"SELECT COUNT({counted_field}) FROM {table} WHERE IDunite={placeholder}",
                    (unit_id,),
                )
                count = int(cursor.fetchone()[0] or 0)
                if count:
                    dependencies.append(f"{count} {label}")
        finally:
            cursor.close()
            connection.close()
        return dependencies

    def delete_unit(self, activity_id: int, unit_id: int) -> None:
        dependencies = self.usage(unit_id)
        if dependencies:
            raise ValueError("Cette unité est encore utilisée par : " + ", ".join(dependencies) + ".")
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(f"DELETE FROM unites WHERE IDunite={placeholder}", (unit_id,))
            cursor.execute(f"DELETE FROM unites_groupes WHERE IDunite={placeholder}", (unit_id,))
            cursor.execute(f"DELETE FROM unites_incompat WHERE IDunite={placeholder}", (unit_id,))
            self._resequence(cursor, placeholder, activity_id)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def move_unit(self, activity_id: int, unit_id: int, delta: int) -> None:
        if delta not in (-1, 1):
            raise ValueError("Le déplacement doit être -1 ou +1.")
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT IDunite FROM unites WHERE IDactivite={placeholder} ORDER BY ordre, IDunite",
                (activity_id,),
            )
            ids = [int(row[0]) for row in cursor.fetchall()]
            if unit_id not in ids:
                raise ValueError("Unité introuvable.")
            index = ids.index(unit_id)
            target = index + delta
            if target < 0 or target >= len(ids):
                return
            ids[index], ids[target] = ids[target], ids[index]
            for order, current_id in enumerate(ids, start=1):
                cursor.execute(
                    f"UPDATE unites SET ordre={placeholder} WHERE IDunite={placeholder}",
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
            f"SELECT IDunite FROM unites WHERE IDactivite={placeholder} ORDER BY ordre, IDunite",
            (activity_id,),
        )
        for order, (unit_id,) in enumerate(cursor.fetchall(), start=1):
            cursor.execute(
                f"UPDATE unites SET ordre={placeholder} WHERE IDunite={placeholder}",
                (order, unit_id),
            )


class ConsumptionUnitModel(QAbstractTableModel):
    HEADERS = ("Nom", "Abrégé", "Type", "Période de validité", "Auto-gen.")

    def __init__(self, rows: Iterable[ConsumptionUnit] = ()):  # noqa: D107
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
        values = (
            row.name,
            row.short_name,
            UNIT_TYPE_LABELS.get(row.type_code, row.type_code),
            row.period,
            "Oui" if row.auto_gen_active else "",
        )
        return values[index.column()]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)):  # noqa: N802,E501
        if orientation == Qt.Orientation.Horizontal and role == int(Qt.ItemDataRole.DisplayRole):
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def replace(self, rows: Iterable[ConsumptionUnit]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def row_at(self, row: int) -> ConsumptionUnit:
        return self.rows[row]


class FillingUnitModel(QAbstractTableModel):
    HEADERS = ("Nom", "Abrégé", "Seuil", "Plage horaire", "Période de validité")

    def __init__(self, rows: Iterable[FillingUnit] = ()):  # noqa: D107
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
        return (row.name, row.short_name, row.alert_threshold, row.time_range, row.period)[index.column()]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)):  # noqa: N802,E501
        if orientation == Qt.Orientation.Horizontal and role == int(Qt.ItemDataRole.DisplayRole):
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def replace(self, rows: Iterable[FillingUnit]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()


class UnitEditDialog(QDialog):
    def __init__(
        self,
        repository: ActivityUnitsRepository,
        activity_id: int,
        unit: ConsumptionUnit | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.activity_id = activity_id
        self.original = unit
        self.setWindowTitle("Modification d'une unité" if unit else "Saisie d'une unité")
        self.setModal(True)
        self.resize(700, 660)

        root = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        identity = QGroupBox("Nom de l'unité", body)
        identity_form = QFormLayout(identity)
        self.name_edit = QLineEdit(identity)
        self.short_name_edit = QLineEdit(identity)
        identity_form.addRow("Nom :", self.name_edit)
        identity_form.addRow("Abrégé :", self.short_name_edit)
        layout.addWidget(identity)

        characteristics = QGroupBox("Caractéristiques", body)
        form = QGridLayout(characteristics)
        self.type_combo = QComboBox(characteristics)
        for code, label in UNIT_TYPES:
            self.type_combo.addItem(label, code)
        form.addWidget(QLabel("Type d'unité :", characteristics), 0, 0)
        form.addWidget(self.type_combo, 0, 1, 1, 3)

        self.hour_start_edit = QLineEdit(characteristics)
        self.hour_start_edit.setPlaceholderText("HH:MM")
        self.hour_start_fixed = QCheckBox("Fixe", characteristics)
        self.hour_end_edit = QLineEdit(characteristics)
        self.hour_end_edit.setPlaceholderText("HH:MM")
        self.hour_end_fixed = QCheckBox("Fixe", characteristics)
        form.addWidget(QLabel("Amplitude horaire :", characteristics), 1, 0)
        form.addWidget(self.hour_start_edit, 1, 1)
        form.addWidget(self.hour_start_fixed, 1, 2)
        form.addWidget(self.hour_end_edit, 1, 3)
        form.addWidget(self.hour_end_fixed, 1, 4)

        self.all_groups_radio = QRadioButton("Tous les groupes", characteristics)
        self.some_groups_radio = QRadioButton("Uniquement les groupes cochés", characteristics)
        group_buttons = QButtonGroup(characteristics)
        group_buttons.addButton(self.all_groups_radio)
        group_buttons.addButton(self.some_groups_radio)
        self.groups_list = QListWidget(characteristics)
        self.groups_list.setMaximumHeight(130)
        group_box = QVBoxLayout()
        group_box.addWidget(self.all_groups_radio)
        group_box.addWidget(self.some_groups_radio)
        group_box.addWidget(self.groups_list)
        form.addWidget(QLabel("Groupes :", characteristics), 2, 0, Qt.AlignmentFlag.AlignTop)
        form.addLayout(group_box, 2, 1, 1, 4)

        self.meal_check = QCheckBox("Repas inclus", characteristics)
        self.restaurateur_combo = QComboBox(characteristics)
        self.restaurateur_combo.addItem("Aucun restaurateur", None)
        for restaurateur_id, name in repository.list_restaurateurs():
            self.restaurateur_combo.addItem(name, restaurateur_id)
        form.addWidget(QLabel("Repas :", characteristics), 3, 0)
        form.addWidget(self.meal_check, 3, 1)
        form.addWidget(self.restaurateur_combo, 3, 2, 1, 3)

        self.incompat_list = QListWidget(characteristics)
        self.incompat_list.setMaximumHeight(120)
        form.addWidget(QLabel("Incompatibilités :", characteristics), 4, 0, Qt.AlignmentFlag.AlignTop)
        form.addWidget(self.incompat_list, 4, 1, 1, 4)

        self.shortcut_combo = QComboBox(characteristics)
        for code, label in SHORTCUTS:
            self.shortcut_combo.addItem(label, code)
        form.addWidget(QLabel("Touche raccourci :", characteristics), 5, 0)
        form.addWidget(self.shortcut_combo, 5, 1, 1, 4)

        self.auto_gen_check = QCheckBox("Auto-génération active", characteristics)
        self.auto_gen_note = QLabel(
            "Les conditions et paramètres d'auto-génération existants sont préservés à l'identique. "
            "Leur éditeur dédié sera migré séparément.",
            characteristics,
        )
        self.auto_gen_note.setWordWrap(True)
        form.addWidget(QLabel("Auto-génération :", characteristics), 6, 0, Qt.AlignmentFlag.AlignTop)
        form.addWidget(self.auto_gen_check, 6, 1, 1, 4)
        form.addWidget(self.auto_gen_note, 7, 1, 1, 4)
        layout.addWidget(characteristics)

        validity = QGroupBox("Validité", body)
        validity_layout = QGridLayout(validity)
        self.unlimited_radio = QRadioButton("Durant la période de validité de l'activité", validity)
        self.limited_radio = QRadioButton("Période limitée", validity)
        validity_group = QButtonGroup(validity)
        validity_group.addButton(self.unlimited_radio)
        validity_group.addButton(self.limited_radio)
        self.start_date_edit = QDateEdit(validity)
        self.end_date_edit = QDateEdit(validity)
        for editor in (self.start_date_edit, self.end_date_edit):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd/MM/yyyy")
        validity_layout.addWidget(self.unlimited_radio, 0, 0, 1, 4)
        validity_layout.addWidget(self.limited_radio, 1, 0, 1, 4)
        validity_layout.addWidget(QLabel("Du", validity), 2, 0)
        validity_layout.addWidget(self.start_date_edit, 2, 1)
        validity_layout.addWidget(QLabel("au", validity), 2, 2)
        validity_layout.addWidget(self.end_date_edit, 2, 3)
        layout.addWidget(validity)
        layout.addStretch(1)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.accepted.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        selected_groups = repository.unit_group_ids(unit.unit_id if unit else None)
        for group_id, name in repository.list_groups(activity_id):
            item = QListWidgetItem(name, self.groups_list)
            item.setData(Qt.ItemDataRole.UserRole, group_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if group_id in selected_groups else Qt.CheckState.Unchecked)
        self.all_groups_radio.setChecked(not selected_groups)
        self.some_groups_radio.setChecked(bool(selected_groups))

        incompatible = repository.incompatible_unit_ids(unit.unit_id if unit else None)
        for other in repository.list_units(activity_id):
            if unit is not None and other.unit_id == unit.unit_id:
                continue
            item = QListWidgetItem(other.name, self.incompat_list)
            item.setData(Qt.ItemDataRole.UserRole, other.unit_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if other.unit_id in incompatible else Qt.CheckState.Unchecked)

        if unit is None:
            unit = ConsumptionUnit(
                unit_id=None,
                activity_id=activity_id,
                name="",
                short_name="",
                type_code="Unitaire",
                start_date=UNLIMITED_START,
                end_date=UNLIMITED_END,
                order=0,
                auto_gen_active=False,
            )
        self._load(unit)
        self.all_groups_radio.toggled.connect(self._sync_groups)
        self.meal_check.toggled.connect(self._sync_meal)
        self.unlimited_radio.toggled.connect(self._sync_dates)
        self._sync_groups()
        self._sync_meal()
        self._sync_dates()

    def _load(self, unit: ConsumptionUnit) -> None:
        self.name_edit.setText(unit.name)
        self.short_name_edit.setText(unit.short_name)
        index = self.type_combo.findData(unit.type_code)
        self.type_combo.setCurrentIndex(index if index >= 0 else 0)
        self.hour_start_edit.setText(unit.hour_start or "")
        self.hour_end_edit.setText(unit.hour_end or "")
        self.hour_start_fixed.setChecked(unit.hour_start_fixed)
        self.hour_end_fixed.setChecked(unit.hour_end_fixed)
        self.meal_check.setChecked(unit.meal)
        index = self.restaurateur_combo.findData(unit.restaurateur_id)
        self.restaurateur_combo.setCurrentIndex(index if index >= 0 else 0)
        index = self.shortcut_combo.findData(unit.shortcut)
        self.shortcut_combo.setCurrentIndex(index if index >= 0 else 0)
        self.auto_gen_check.setChecked(unit.auto_gen_active)
        # Activation/désactivation conservée ; les chaînes de paramètres ne sont jamais réécrites par l'UI.
        unlimited = unit.start_date == UNLIMITED_START and unit.end_date == UNLIMITED_END
        self.unlimited_radio.setChecked(unlimited)
        self.limited_radio.setChecked(not unlimited)
        today = dt.date.today()
        self.start_date_edit.setDate(_qdate(unit.start_date if not unlimited else today))
        self.end_date_edit.setDate(_qdate(unit.end_date if not unlimited else today))

    def _sync_groups(self, *_args) -> None:
        self.groups_list.setEnabled(self.some_groups_radio.isChecked())

    def _sync_meal(self, *_args) -> None:
        self.restaurateur_combo.setEnabled(self.meal_check.isChecked())

    def _sync_dates(self, *_args) -> None:
        enabled = self.limited_radio.isChecked()
        self.start_date_edit.setEnabled(enabled)
        self.end_date_edit.setEnabled(enabled)

    @staticmethod
    def _checked_ids(widget: QListWidget) -> list[int]:
        ids: list[int] = []
        for index in range(widget.count()):
            item = widget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return ids

    def _accept_if_valid(self) -> None:
        try:
            self.result_values()
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc))
            return
        self.accept()

    def result_values(self) -> tuple[ConsumptionUnit, list[int] | None, list[int]]:
        name = self.name_edit.text().strip()
        short_name = self.short_name_edit.text().strip()
        if not name:
            raise ValueError("Vous devez obligatoirement saisir un nom d'unité.")
        if not short_name:
            raise ValueError("Vous devez obligatoirement saisir un nom abrégé.")
        hour_start = _normalized_time(self.hour_start_edit.text())
        hour_end = _normalized_time(self.hour_end_edit.text())
        type_code = str(self.type_combo.currentData())
        if type_code == "Multihoraires" and (hour_start is None or hour_end is None):
            raise ValueError("Une unité Multi-horaires doit avoir une heure de début et une heure de fin.")

        if self.unlimited_radio.isChecked():
            start_date, end_date = UNLIMITED_START, UNLIMITED_END
        else:
            start_date = self.start_date_edit.date().toPython()
            end_date = self.end_date_edit.date().toPython()
            if start_date > end_date:
                raise ValueError("La date de début doit précéder la date de fin.")

        group_ids: list[int] | None = None
        if self.some_groups_radio.isChecked():
            group_ids = self._checked_ids(self.groups_list)
            if not group_ids:
                raise ValueError("Sélectionnez au moins un groupe ou choisissez « Tous les groupes ».")

        original = self.original
        base = original or ConsumptionUnit(
            unit_id=None,
            activity_id=self.activity_id,
            name="",
            short_name="",
            type_code="Unitaire",
            start_date=UNLIMITED_START,
            end_date=UNLIMITED_END,
            order=0,
            auto_gen_active=False,
        )
        unit = replace(
            base,
            name=name,
            short_name=short_name,
            type_code=type_code,
            start_date=start_date,
            end_date=end_date,
            auto_gen_active=self.auto_gen_check.isChecked(),
            hour_start=hour_start,
            hour_end=hour_end,
            meal=self.meal_check.isChecked(),
            restaurateur_id=self.restaurateur_combo.currentData(),
            shortcut=self.shortcut_combo.currentData(),
            hour_start_fixed=self.hour_start_fixed.isChecked(),
            hour_end_fixed=self.hour_end_fixed.isChecked(),
        )
        return unit, group_ids, self._checked_ids(self.incompat_list)


class ActivityUnitsPage(QWidget):
    def __init__(
        self,
        editor_repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.activity_id = activity_id
        self.repository = ActivityUnitsRepository(editor_repository)
        self.unit_model = ConsumptionUnitModel()
        self.filling_model = FillingUnitModel()

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        root.addWidget(splitter, 1)

        consumption = QGroupBox("Unités de consommation", splitter)
        consumption_layout = QVBoxLayout(consumption)
        actions = QHBoxLayout()
        self.add_button = QPushButton("Ajouter", consumption)
        self.edit_button = QPushButton("Modifier", consumption)
        self.delete_button = QPushButton("Supprimer", consumption)
        self.up_button = QPushButton("Monter", consumption)
        self.down_button = QPushButton("Descendre", consumption)
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
        consumption_layout.addLayout(actions)

        self.unit_table = QTableView(consumption)
        self.unit_table.setModel(self.unit_model)
        self._configure_table(self.unit_table, stretch_column=0)
        consumption_layout.addWidget(self.unit_table, 1)
        splitter.addWidget(consumption)

        filling = QGroupBox("Unités de remplissage", splitter)
        filling_layout = QVBoxLayout(filling)
        note = QLabel(
            "Les unités de remplissage sont déjà lues depuis la vraie base. Leur édition (unités associées, "
            "étiquettes et seuils) constitue la prochaine sous-passe de cet onglet.",
            filling,
        )
        note.setWordWrap(True)
        filling_layout.addWidget(note)
        self.filling_table = QTableView(filling)
        self.filling_table.setModel(self.filling_model)
        self._configure_table(self.filling_table, stretch_column=0)
        filling_layout.addWidget(self.filling_table, 1)
        splitter.addWidget(filling)
        splitter.setSizes([420, 240])

        self.add_button.clicked.connect(self.add_unit)
        self.edit_button.clicked.connect(self.edit_unit)
        self.delete_button.clicked.connect(self.delete_unit)
        self.up_button.clicked.connect(lambda: self.move_unit(-1))
        self.down_button.clicked.connect(lambda: self.move_unit(1))
        self.unit_table.doubleClicked.connect(lambda _index: self.edit_unit())
        selection_model = self.unit_table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self._sync_actions)

        self.refresh()
        self._sync_actions()

    @staticmethod
    def _configure_table(table: QTableView, stretch_column: int) -> None:
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        for column in range(table.model().columnCount()):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch if column == stretch_column else QHeaderView.ResizeMode.ResizeToContents,
            )

    def refresh(self, selected_id: int | None = None) -> None:
        units = self.repository.list_units(self.activity_id)
        self.unit_model.replace(units)
        self.filling_model.replace(self.repository.list_filling_units(self.activity_id))
        if selected_id is not None:
            for row_index, row in enumerate(units):
                if row.unit_id == selected_id:
                    self.unit_table.selectRow(row_index)
                    self.unit_table.setCurrentIndex(self.unit_model.index(row_index, 0))
                    break
        self._sync_actions()

    def selected_unit(self) -> ConsumptionUnit | None:
        index = self.unit_table.currentIndex()
        if not index.isValid():
            return None
        return self.unit_model.row_at(index.row())

    def add_unit(self) -> None:
        dialog = UnitEditDialog(self.repository, self.activity_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            unit, groups, incompatibles = dialog.result_values()
            unit_id = self.repository.save_unit(unit, group_ids=groups, incompatible_ids=incompatibles)
        except Exception as exc:
            QMessageBox.critical(self, "Ajout impossible", str(exc))
            return
        self.refresh(unit_id)

    def edit_unit(self) -> None:
        unit = self.selected_unit()
        if unit is None:
            return
        dialog = UnitEditDialog(self.repository, self.activity_id, unit, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            changed, groups, incompatibles = dialog.result_values()
            unit_id = self.repository.save_unit(changed, group_ids=groups, incompatible_ids=incompatibles)
        except Exception as exc:
            QMessageBox.critical(self, "Modification impossible", str(exc))
            return
        self.refresh(unit_id)

    def delete_unit(self) -> None:
        unit = self.selected_unit()
        if unit is None or unit.unit_id is None:
            return
        dependencies = self.repository.usage(unit.unit_id)
        if dependencies:
            QMessageBox.warning(
                self,
                "Suppression impossible",
                "Cette unité est encore utilisée par :\n• " + "\n• ".join(dependencies),
            )
            return
        answer = QMessageBox.question(
            self,
            "Suppression",
            f"Souhaitez-vous vraiment supprimer l'unité « {unit.name} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repository.delete_unit(self.activity_id, unit.unit_id)
        except Exception as exc:
            QMessageBox.critical(self, "Suppression impossible", str(exc))
            return
        self.refresh()

    def move_unit(self, delta: int) -> None:
        unit = self.selected_unit()
        if unit is None or unit.unit_id is None:
            return
        try:
            self.repository.move_unit(self.activity_id, unit.unit_id, delta)
        except Exception as exc:
            QMessageBox.critical(self, "Déplacement impossible", str(exc))
            return
        self.refresh(unit.unit_id)

    def _sync_actions(self, *_args) -> None:
        unit = self.selected_unit()
        selected = unit is not None
        self.edit_button.setEnabled(selected)
        self.delete_button.setEnabled(selected)
        if not selected:
            self.up_button.setEnabled(False)
            self.down_button.setEnabled(False)
            return
        row = self.unit_table.currentIndex().row()
        self.up_button.setEnabled(row > 0)
        self.down_button.setEnabled(row >= 0 and row < self.unit_model.rowCount() - 1)


class ActivityEditorDialog(GroupsActivityEditorDialog):
    """Éditeur Activité avec Généralités, Groupes et Unités raccordés."""

    def __init__(
        self,
        repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(5)
        self.tabs.removeTab(5)
        if old_page is not None:
            old_page.deleteLater()
        self.units_page = ActivityUnitsPage(repository, activity_id, self)
        self.tabs.insertTab(5, self.units_page, "Unités")
