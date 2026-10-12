"""Page Qt « Calendrier » de la fiche Activité.

Cette migration reprend le contrat fonctionnel du calendrier wx historique sans
importer wx/GestionDB : ouvertures par date/groupe/unité, capacités des unités de
remplissage et évènements des unités de type ``Evenement``. Les modifications
restent tamponnées dans le dialogue puis sont écrites dans une transaction.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .activity_editor import NativeActivityEditorRepository
from .activity_pricing_parity import ActivityEditorDialog as PricingActivityEditorDialog


MONTH_NAMES = (
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
)
_HHMM_RE = re.compile(r"^(?:[01]\d|2[0-4]):[0-5]\d$")


@dataclass(frozen=True, slots=True)
class CalendarUnit:
    unit_id: int
    name: str
    short_name: str
    type_code: str
    start_date: dt.date
    end_date: dt.date
    order: int
    group_ids: frozenset[int]


@dataclass(frozen=True, slots=True)
class CalendarFillingUnit:
    filling_unit_id: int
    name: str
    short_name: str
    start_date: dt.date
    end_date: dt.date
    order: int


@dataclass(frozen=True, slots=True)
class CalendarOpening:
    opening_id: int
    date: dt.date
    group_id: int | None
    unit_id: int


@dataclass(frozen=True, slots=True)
class CalendarFilling:
    filling_id: int
    date: dt.date
    group_id: int | None
    filling_unit_id: int
    places: int


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    event_id: int | None
    activity_id: int
    unit_id: int
    group_id: int
    date: dt.date
    name: str
    description: str = ""
    capacity_max: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    amount: float | None = None
    advanced_tariff_count: int = 0


@dataclass(frozen=True, slots=True)
class MonthData:
    openings: frozenset[tuple[dt.date, int | None, int]]
    fillings: dict[tuple[dt.date, int | None, int], int]
    events: tuple[CalendarEvent, ...]
    consumption_counts: dict[tuple[dt.date, int | None, int], int]


def _event_counts_by_cell(
    events: Iterable[CalendarEvent],
) -> dict[tuple[dt.date, int | None, int], int]:
    counts: dict[tuple[dt.date, int | None, int], int] = {}
    for event in events:
        key = (event.date, event.group_id, event.unit_id)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _event_counts_by_period(
    events: Iterable[CalendarEvent],
) -> dict[tuple[int, int, int | None, int], int]:
    counts: dict[tuple[int, int, int | None, int], int] = {}
    for event in events:
        key = (event.date.year, event.date.month, event.group_id, event.unit_id)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _to_date(value: object) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def _valid_hhmm(value: str | None, field: str) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not _HHMM_RE.fullmatch(text):
        raise ValueError(f"{field} doit être au format HH:MM entre 00:00 et 24:59.")
    return text


class ActivityCalendarRepository:
    """Accès SQL du calendrier avec protections métier historiques."""

    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont transitoire volontaire

    def activity_period(self, activity_id: int) -> tuple[dt.date, dt.date]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT date_debut, date_fin FROM activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Activité introuvable.")
            return _to_date(row[0]), _to_date(row[1])
        finally:
            cursor.close(); connection.close()

    def list_groups(self, activity_id: int) -> list[tuple[int, str]]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT IDgroupe, nom FROM groupes WHERE IDactivite={placeholder} ORDER BY ordre, IDgroupe",
                (activity_id,),
            )
            return [(int(row[0]), str(row[1] or "")) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def list_units(self, activity_id: int) -> list[CalendarUnit]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT IDunite, nom, abrege, type, date_debut, date_fin, ordre
                    FROM unites WHERE IDactivite={placeholder} ORDER BY ordre, IDunite""",
                (activity_id,),
            )
            rows = cursor.fetchall()
            result: list[CalendarUnit] = []
            for unit_id, name, short_name, type_code, date_start, date_end, order in rows:
                cursor.execute(
                    f"SELECT IDgroupe FROM unites_groupes WHERE IDunite={placeholder}",
                    (unit_id,),
                )
                group_ids = frozenset(int(row[0]) for row in cursor.fetchall())
                result.append(CalendarUnit(
                    int(unit_id), str(name or ""), str(short_name or name or ""),
                    str(type_code or "Unitaire"), _to_date(date_start), _to_date(date_end),
                    int(order or 0), group_ids,
                ))
            return result
        finally:
            cursor.close(); connection.close()

    def list_filling_units(self, activity_id: int) -> list[CalendarFillingUnit]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT IDunite_remplissage, nom, abrege, date_debut, date_fin, ordre
                    FROM unites_remplissage WHERE IDactivite={placeholder}
                    ORDER BY ordre, IDunite_remplissage""",
                (activity_id,),
            )
            return [CalendarFillingUnit(
                int(row[0]), str(row[1] or ""), str(row[2] or row[1] or ""),
                _to_date(row[3]), _to_date(row[4]), int(row[5] or 0),
            ) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def list_openings(self, activity_id: int, start: dt.date, end: dt.date) -> list[CalendarOpening]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT IDouverture, date, IDgroupe, IDunite FROM ouvertures
                    WHERE IDactivite={placeholder} AND date>={placeholder} AND date<={placeholder}
                    ORDER BY date, IDgroupe, IDunite""",
                (activity_id, start.isoformat(), end.isoformat()),
            )
            return [CalendarOpening(
                int(row[0]), _to_date(row[1]), int(row[2]) if row[2] is not None else None, int(row[3])
            ) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def list_fillings(self, activity_id: int, start: dt.date, end: dt.date) -> list[CalendarFilling]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT IDremplissage, date, IDgroupe, IDunite_remplissage, places
                    FROM remplissage WHERE IDactivite={placeholder}
                    AND date>={placeholder} AND date<={placeholder}
                    ORDER BY date, IDgroupe, IDunite_remplissage""",
                (activity_id, start.isoformat(), end.isoformat()),
            )
            return [CalendarFilling(
                int(row[0]), _to_date(row[1]), int(row[2]) if row[2] is not None else None,
                int(row[3]), int(row[4] or 0),
            ) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def list_events(self, activity_id: int, start: dt.date, end: dt.date) -> list[CalendarEvent]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT e.IDevenement, e.IDactivite, e.IDunite, e.IDgroupe, e.date,
                           e.nom, e.description, e.capacite_max, e.heure_debut, e.heure_fin,
                           e.montant, COUNT(t.IDtarif)
                    FROM evenements e
                    LEFT JOIN tarifs t ON t.IDevenement=e.IDevenement
                    WHERE e.IDactivite={placeholder} AND e.date>={placeholder} AND e.date<={placeholder}
                    GROUP BY e.IDevenement, e.IDactivite, e.IDunite, e.IDgroupe, e.date,
                             e.nom, e.description, e.capacite_max, e.heure_debut, e.heure_fin, e.montant
                    ORDER BY e.date, e.IDgroupe, e.IDunite, e.IDevenement""",
                (activity_id, start.isoformat(), end.isoformat()),
            )
            return [CalendarEvent(
                event_id=int(row[0]), activity_id=int(row[1]), unit_id=int(row[2]),
                group_id=int(row[3]), date=_to_date(row[4]), name=str(row[5] or ""),
                description=str(row[6] or ""), capacity_max=int(row[7]) if row[7] not in (None, "") else None,
                start_time=str(row[8]) if row[8] not in (None, "") else None,
                end_time=str(row[9]) if row[9] not in (None, "") else None,
                amount=float(row[10]) if row[10] not in (None, "") else None,
                advanced_tariff_count=int(row[11] or 0),
            ) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def consumption_counts(self, activity_id: int, start: dt.date, end: dt.date) -> dict[tuple[dt.date, int | None, int], int]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT date, IDgroupe, IDunite, COUNT(IDconso)
                    FROM consommations WHERE IDactivite={placeholder}
                    AND date>={placeholder} AND date<={placeholder}
                    GROUP BY date, IDgroupe, IDunite""",
                (activity_id, start.isoformat(), end.isoformat()),
            )
            return {
                (_to_date(row[0]), int(row[1]) if row[1] is not None else None, int(row[2])): int(row[3] or 0)
                for row in cursor.fetchall()
            }
        finally:
            cursor.close(); connection.close()

    def event_consumption_count(self, event_id: int) -> int:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT COUNT(IDconso) FROM consommations WHERE IDevenement={placeholder}",
                (event_id,),
            )
            return int(cursor.fetchone()[0] or 0)
        finally:
            cursor.close(); connection.close()

    def load_month(self, activity_id: int, year: int, month: int) -> MonthData:
        start = dt.date(year, month, 1)
        end = dt.date(year, month, calendar.monthrange(year, month)[1])
        openings = self.list_openings(activity_id, start, end)
        fillings = self.list_fillings(activity_id, start, end)
        return MonthData(
            openings=frozenset((row.date, row.group_id, row.unit_id) for row in openings),
            fillings={(row.date, row.group_id, row.filling_unit_id): row.places for row in fillings if row.places > 0},
            events=tuple(self.list_events(activity_id, start, end)),
            consumption_counts=self.consumption_counts(activity_id, start, end),
        )

    def _delete_event(self, cursor, placeholder: str, event_id: int) -> None:
        cursor.execute(
            f"SELECT COUNT(IDconso) FROM consommations WHERE IDevenement={placeholder}",
            (event_id,),
        )
        count = int(cursor.fetchone()[0] or 0)
        if count:
            raise ValueError(
                f"Impossible de supprimer l'évènement : {count} consommation(s) y sont déjà associée(s)."
            )
        cursor.execute(f"SELECT IDtarif FROM tarifs WHERE IDevenement={placeholder}", (event_id,))
        tariff_ids = [int(row[0]) for row in cursor.fetchall()]
        for tariff_id in tariff_ids:
            for table in ("questionnaire_filtres", "tarifs_lignes", "combi_tarifs_unites", "combi_tarifs"):
                cursor.execute(f"DELETE FROM {table} WHERE IDtarif={placeholder}", (tariff_id,))
            cursor.execute(f"DELETE FROM tarifs WHERE IDtarif={placeholder}", (tariff_id,))
        cursor.execute(f"DELETE FROM evenements WHERE IDevenement={placeholder}", (event_id,))

    def validate_event(self, event: CalendarEvent) -> CalendarEvent:
        name = event.name.strip()
        if not name:
            raise ValueError("Vous devez obligatoirement saisir un nom pour cet évènement.")
        start_time = _valid_hhmm(event.start_time, "L'heure de début")
        end_time = _valid_hhmm(event.end_time, "L'heure de fin")
        if start_time and end_time and start_time > end_time:
            raise ValueError("L'heure de début ne peut pas être supérieure à l'heure de fin.")
        if event.capacity_max is not None and event.capacity_max < 1:
            raise ValueError("La capacité maximale doit être supérieure à zéro.")
        return replace(event, name=name, description=event.description.strip(), start_time=start_time, end_time=end_time)

    def save_month(
        self,
        activity_id: int,
        year: int,
        month: int,
        openings: Iterable[tuple[dt.date, int | None, int]],
        fillings: dict[tuple[dt.date, int | None, int], int],
        events: Sequence[CalendarEvent],
    ) -> None:
        start = dt.date(year, month, 1)
        end = dt.date(year, month, calendar.monthrange(year, month)[1])
        final_openings = set(openings)
        final_fillings = {key: int(value) for key, value in fillings.items() if int(value) > 0}
        final_events = [self.validate_event(event) for event in events]

        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            # Vérifie que les évènements sont sur une unité évènementielle ouverte.
            cursor.execute(
                f"SELECT IDunite, type FROM unites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            unit_types = {int(row[0]): str(row[1] or "") for row in cursor.fetchall()}
            for event in final_events:
                if event.activity_id != activity_id or event.date < start or event.date > end:
                    raise ValueError("Un évènement ne correspond pas au mois ou à l'activité en cours.")
                if unit_types.get(event.unit_id) != "Evenement":
                    raise ValueError("Les évènements ne peuvent être rattachés qu'à une unité évènementielle.")
                if (event.date, event.group_id, event.unit_id) not in final_openings:
                    raise ValueError("L'unité doit être ouverte avant d'y associer un évènement.")

            # Évènements supprimés / modifiés / ajoutés.
            cursor.execute(
                f"SELECT IDevenement FROM evenements WHERE IDactivite={placeholder} "
                f"AND date>={placeholder} AND date<={placeholder}",
                (activity_id, start.isoformat(), end.isoformat()),
            )
            old_event_ids = {int(row[0]) for row in cursor.fetchall()}
            kept_event_ids = {int(event.event_id) for event in final_events if event.event_id is not None}
            for event_id in sorted(old_event_ids - kept_event_ids):
                self._delete_event(cursor, placeholder, event_id)

            for event in final_events:
                values = (
                    event.activity_id, event.unit_id, event.group_id, event.date.isoformat(),
                    event.name, event.description or None, event.capacity_max, event.start_time,
                    event.end_time, event.amount,
                )
                fields = (
                    "IDactivite", "IDunite", "IDgroupe", "date", "nom", "description",
                    "capacite_max", "heure_debut", "heure_fin", "montant",
                )
                if event.event_id is None:
                    cursor.execute(
                        f"INSERT INTO evenements ({', '.join(fields)}) VALUES "
                        f"({', '.join(placeholder for _ in fields)})",
                        values,
                    )
                else:
                    cursor.execute(
                        f"UPDATE evenements SET {', '.join(f'{field}={placeholder}' for field in fields)} "
                        f"WHERE IDevenement={placeholder} AND IDactivite={placeholder}",
                        values + (event.event_id, activity_id),
                    )

            # Ouvertures : fermeture interdite s'il reste des consommations.
            cursor.execute(
                f"SELECT IDouverture, date, IDgroupe, IDunite FROM ouvertures "
                f"WHERE IDactivite={placeholder} AND date>={placeholder} AND date<={placeholder}",
                (activity_id, start.isoformat(), end.isoformat()),
            )
            existing_openings = {
                (_to_date(row[1]), int(row[2]) if row[2] is not None else None, int(row[3])): int(row[0])
                for row in cursor.fetchall()
            }
            for cell, opening_id in existing_openings.items():
                if cell in final_openings:
                    continue
                date_value, group_id, unit_id = cell
                if group_id is None:
                    group_clause = "IDgroupe IS NULL"
                    params = (activity_id, date_value.isoformat(), unit_id)
                else:
                    group_clause = f"IDgroupe={placeholder}"
                    params = (activity_id, date_value.isoformat(), group_id, unit_id)
                cursor.execute(
                    f"SELECT COUNT(IDconso) FROM consommations WHERE IDactivite={placeholder} "
                    f"AND date={placeholder} AND {group_clause} AND IDunite={placeholder}",
                    params,
                )
                count = int(cursor.fetchone()[0] or 0)
                if count:
                    raise ValueError(
                        f"Impossible de fermer une ouverture : {count} consommation(s) existent déjà."
                    )
                cursor.execute(f"DELETE FROM ouvertures WHERE IDouverture={placeholder}", (opening_id,))

            for date_value, group_id, unit_id in sorted(final_openings - set(existing_openings), key=lambda item: (item[0], item[1] or -1, item[2])):
                cursor.execute(
                    f"INSERT INTO ouvertures (IDactivite, IDunite, IDgroupe, date) VALUES "
                    f"({placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (activity_id, unit_id, group_id, date_value.isoformat()),
                )

            # Unités de remplissage : 0 équivaut à absence de ligne.
            cursor.execute(
                f"SELECT IDremplissage, date, IDgroupe, IDunite_remplissage FROM remplissage "
                f"WHERE IDactivite={placeholder} AND date>={placeholder} AND date<={placeholder}",
                (activity_id, start.isoformat(), end.isoformat()),
            )
            existing_fillings = {
                (_to_date(row[1]), int(row[2]) if row[2] is not None else None, int(row[3])): int(row[0])
                for row in cursor.fetchall()
            }
            for key, filling_id in existing_fillings.items():
                if key not in final_fillings:
                    cursor.execute(f"DELETE FROM remplissage WHERE IDremplissage={placeholder}", (filling_id,))
                else:
                    cursor.execute(
                        f"UPDATE remplissage SET places={placeholder} WHERE IDremplissage={placeholder}",
                        (final_fillings[key], filling_id),
                    )
            for key, places in final_fillings.items():
                if key in existing_fillings:
                    continue
                date_value, group_id, filling_unit_id = key
                cursor.execute(
                    f"INSERT INTO remplissage (IDactivite, IDunite_remplissage, IDgroupe, date, places) "
                    f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (activity_id, filling_unit_id, group_id, date_value.isoformat(), places),
                )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()


class EventEditDialog(QDialog):
    def __init__(self, event: CalendarEvent, parent: QWidget | None = None):
        super().__init__(parent)
        self.event = event
        self.setWindowTitle("Modifier un évènement" if event.event_id is not None else "Ajouter un évènement")
        self.setMinimumWidth(520)
        root = QVBoxLayout(self)

        general = QGroupBox("Généralités", self); form = QFormLayout(general)
        self.name_edit = QLineEdit(event.name, general)
        self.description_edit = QPlainTextEdit(event.description, general); self.description_edit.setMaximumHeight(100)
        self.start_edit = QLineEdit(event.start_time or "", general); self.start_edit.setPlaceholderText("HH:MM")
        self.end_edit = QLineEdit(event.end_time or "", general); self.end_edit.setPlaceholderText("HH:MM")
        self.capacity_check = QCheckBox("Limiter le nombre d'inscrits", general)
        self.capacity_spin = QSpinBox(general); self.capacity_spin.setRange(1, 99999)
        self.capacity_check.setChecked(event.capacity_max is not None); self.capacity_spin.setValue(event.capacity_max or 1)
        self.capacity_spin.setEnabled(self.capacity_check.isChecked()); self.capacity_check.toggled.connect(self.capacity_spin.setEnabled)
        form.addRow("Nom :", self.name_edit); form.addRow("Description :", self.description_edit)
        times = QWidget(general); times_layout = QHBoxLayout(times); times_layout.setContentsMargins(0, 0, 0, 0)
        times_layout.addWidget(self.start_edit); times_layout.addWidget(QLabel("à", times)); times_layout.addWidget(self.end_edit)
        form.addRow("Horaires :", times); form.addRow(self.capacity_check, self.capacity_spin)
        root.addWidget(general)

        pricing = QGroupBox("Tarification spécifique", self); pricing_form = QFormLayout(pricing)
        self.amount_check = QCheckBox("Montant fixe", pricing)
        self.amount_spin = QDoubleSpinBox(pricing); self.amount_spin.setRange(0.0, 999999.0); self.amount_spin.setDecimals(2); self.amount_spin.setSuffix(" €")
        self.amount_check.setChecked(event.amount is not None); self.amount_spin.setValue(event.amount or 0.0)
        self.amount_spin.setEnabled(self.amount_check.isChecked()); self.amount_check.toggled.connect(self.amount_spin.setEnabled)
        pricing_form.addRow(self.amount_check, self.amount_spin)
        if event.advanced_tariff_count:
            warning = QLabel(
                f"{event.advanced_tariff_count} tarif(s) avancé(s) historique(s) sont rattachés à cet évènement. "
                "Ils sont conservés sans modification par cette fenêtre Qt.",
                pricing,
            )
            warning.setWordWrap(True); pricing_form.addRow(warning)
            self.amount_check.setEnabled(False); self.amount_spin.setEnabled(False)
        root.addWidget(pricing)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Valider")
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _accept(self) -> None:
        try:
            updated = replace(
                self.event,
                name=self.name_edit.text().strip(),
                description=self.description_edit.toPlainText().strip(),
                start_time=_valid_hhmm(self.start_edit.text(), "L'heure de début"),
                end_time=_valid_hhmm(self.end_edit.text(), "L'heure de fin"),
                capacity_max=self.capacity_spin.value() if self.capacity_check.isChecked() else None,
                amount=(self.amount_spin.value() if self.amount_check.isChecked() else None)
                if not self.event.advanced_tariff_count else self.event.amount,
            )
            if not updated.name:
                raise ValueError("Vous devez obligatoirement saisir un nom pour cet évènement.")
            if updated.start_time and updated.end_time and updated.start_time > updated.end_time:
                raise ValueError("L'heure de début ne peut pas être supérieure à l'heure de fin.")
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc)); return
        self.event = updated; self.accept()


class EventsDialog(QDialog):
    def __init__(self, repository: ActivityCalendarRepository, events: Sequence[CalendarEvent], template: CalendarEvent, parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository; self.events = list(events); self.template = template
        self.setWindowTitle(f"Évènements du {template.date:%d/%m/%Y}")
        self.resize(720, 420)
        root = QVBoxLayout(self)
        self.table = QTableWidget(self); self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(("Nom", "Début", "Fin", "Montant", "Capacité", "Tarifs avancés"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6): self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self.edit_selected); root.addWidget(self.table, 1)
        actions = QHBoxLayout(); self.add_button = QPushButton("Ajouter", self); self.edit_button = QPushButton("Modifier", self); self.delete_button = QPushButton("Supprimer", self)
        actions.addWidget(self.add_button); actions.addWidget(self.edit_button); actions.addWidget(self.delete_button); actions.addStretch(1); root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.add_button.clicked.connect(self.add_event); self.edit_button.clicked.connect(self.edit_selected); self.delete_button.clicked.connect(self.delete_selected)
        self._refresh()

    def _selected_index(self) -> int | None:
        row = self.table.currentRow(); return row if 0 <= row < len(self.events) else None

    def _refresh(self) -> None:
        self.table.setRowCount(len(self.events))
        for row, event in enumerate(self.events):
            values = (
                event.name, event.start_time or "", event.end_time or "",
                "" if event.amount is None else f"{event.amount:.2f} €",
                "" if event.capacity_max is None else str(event.capacity_max),
                "" if not event.advanced_tariff_count else str(event.advanced_tariff_count),
            )
            for column, value in enumerate(values): self.table.setItem(row, column, QTableWidgetItem(value))

    def add_event(self) -> None:
        dialog = EventEditDialog(self.template, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.events.append(dialog.event); self._refresh(); self.table.selectRow(len(self.events) - 1)

    def edit_selected(self, *_args) -> None:
        index = self._selected_index()
        if index is None: return
        event = self.events[index]
        if event.event_id is not None:
            count = self.repository.event_consumption_count(event.event_id)
            if count:
                answer = QMessageBox.question(
                    self, "Modification", f"Cet évènement est déjà associé à {count} consommation(s). Le modifier quand même ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes: return
        dialog = EventEditDialog(event, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.events[index] = dialog.event; self._refresh(); self.table.selectRow(index)

    def delete_selected(self) -> None:
        index = self._selected_index()
        if index is None: return
        event = self.events[index]
        if event.event_id is not None:
            count = self.repository.event_consumption_count(event.event_id)
            if count:
                QMessageBox.warning(self, "Suppression impossible", f"{count} consommation(s) sont déjà associée(s) à cet évènement."); return
        if QMessageBox.question(self, "Suppression", "Supprimer cet évènement ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        del self.events[index]; self._refresh()


class CalendarEditorDialog(QDialog):
    """Éditeur mensuel dense des ouvertures, remplissages et évènements."""

    def __init__(self, repository: ActivityCalendarRepository, activity_id: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository; self.activity_id = activity_id
        self.units = repository.list_units(activity_id); self.filling_units = repository.list_filling_units(activity_id); self.groups = repository.list_groups(activity_id)
        self.activity_start, self.activity_end = repository.activity_period(activity_id)
        today = dt.date.today(); self.year = today.year; self.month = today.month
        self.data = MonthData(frozenset(), {}, (), {})
        self.openings: set[tuple[dt.date, int | None, int]] = set(); self.fillings: dict[tuple[dt.date, int | None, int], int] = {}; self.events: list[CalendarEvent] = []
        self._loading = False; self._dirty = False
        self.setWindowTitle("Calendrier des ouvertures et des évènements"); self.resize(1180, 760); self.setMinimumSize(900, 580)
        root = QVBoxLayout(self)

        controls = QHBoxLayout(); controls.addWidget(QLabel("Mois :", self))
        self.month_combo = QComboBox(self)
        for index, name in enumerate(MONTH_NAMES, 1): self.month_combo.addItem(name, index)
        self.month_combo.setCurrentIndex(today.month - 1); controls.addWidget(self.month_combo)
        controls.addWidget(QLabel("Année :", self)); self.year_spin = QSpinBox(self); self.year_spin.setRange(1977, 2999); self.year_spin.setValue(today.year); controls.addWidget(self.year_spin); controls.addStretch(1)
        legend = QLabel("Coche = ouvert · nombre = effectif max. · Év. = évènements", self); controls.addWidget(legend); root.addLayout(controls)

        self.table = QTableWidget(self); self.table.setAlternatingRowColors(True); self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionsMovable(False); self.table.verticalHeader().setVisible(False); root.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer le mois"); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Fermer")
        buttons.accepted.connect(self._save); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.month_combo.currentIndexChanged.connect(self._change_period); self.year_spin.valueChanged.connect(self._change_period)
        self._load_month()

    def _change_period(self, *_args) -> None:
        if self._loading: return
        new_month = int(self.month_combo.currentData()); new_year = self.year_spin.value()
        if (new_year, new_month) == (self.year, self.month): return
        if self._dirty:
            answer = QMessageBox.question(self, "Modifications non enregistrées", "Abandonner les modifications du mois affiché ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                self._loading = True; self.month_combo.setCurrentIndex(self.month - 1); self.year_spin.setValue(self.year); self._loading = False; return
        self.year, self.month = new_year, new_month; self._load_month()

    def _load_month(self) -> None:
        self._loading = True
        self.data = self.repository.load_month(self.activity_id, self.year, self.month)
        self.openings = set(self.data.openings); self.fillings = dict(self.data.fillings); self.events = list(self.data.events); self._dirty = False
        self._build_table(); self._loading = False

    def _active_unit(self, unit: CalendarUnit, date_value: dt.date, group_id: int | None) -> bool:
        if group_id is None: return False
        if not (self.activity_start <= date_value <= self.activity_end and unit.start_date <= date_value <= unit.end_date): return False
        return not unit.group_ids or group_id in unit.group_ids

    def _active_filling(self, unit: CalendarFillingUnit, date_value: dt.date) -> bool:
        return self.activity_start <= date_value <= self.activity_end and unit.start_date <= date_value <= unit.end_date

    def _build_table(self) -> None:
        days = calendar.monthrange(self.year, self.month)[1]
        groups: list[tuple[int | None, str]] = list(self.groups)
        if any(group_id is None for _date, group_id, _unit in self.fillings): groups.append((None, "Tous les groupes"))
        headers = ["Date", "Groupe", *[unit.short_name for unit in self.units], *[f"Max. {unit.short_name}" for unit in self.filling_units]]
        self.table.clear(); self.table.setColumnCount(len(headers)); self.table.setHorizontalHeaderLabels(headers); self.table.setRowCount(days * len(groups))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(2, len(headers)): self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        event_counts = _event_counts_by_cell(self.events)
        row = 0
        for day in range(1, days + 1):
            date_value = dt.date(self.year, self.month, day)
            for group_id, group_name in groups:
                date_item = QTableWidgetItem(date_value.strftime("%a %d/%m")); date_item.setData(Qt.ItemDataRole.UserRole, date_value); date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable); self.table.setItem(row, 0, date_item)
                group_item = QTableWidgetItem(group_name); group_item.setData(Qt.ItemDataRole.UserRole, group_id); group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsEditable); self.table.setItem(row, 1, group_item)
                column = 2
                for unit in self.units:
                    cell = QWidget(self.table); layout = QHBoxLayout(cell); layout.setContentsMargins(3, 0, 3, 0); layout.setSpacing(3)
                    check = QCheckBox(cell); key = (date_value, group_id, unit.unit_id); check.setChecked(key in self.openings); check.setEnabled(self._active_unit(unit, date_value, group_id)); check.setProperty("calendar_key", key); check.toggled.connect(self._opening_toggled); layout.addWidget(check)
                    if unit.type_code == "Evenement":
                        button = QPushButton("Év.", cell); button.setEnabled(check.isChecked() and check.isEnabled()); button.setProperty("calendar_key", key); button.clicked.connect(self._edit_events)
                        count = event_counts.get(key, 0)
                        if count: button.setText(f"Év. {count}")
                        check.toggled.connect(button.setEnabled); layout.addWidget(button)
                    layout.addStretch(1); self.table.setCellWidget(row, column, cell); column += 1
                for filling_unit in self.filling_units:
                    spin = QSpinBox(self.table); spin.setRange(0, 999); spin.setSpecialValueText("—"); key = (date_value, group_id, filling_unit.filling_unit_id); spin.setValue(self.fillings.get(key, 0)); spin.setEnabled(self._active_filling(filling_unit, date_value)); spin.setProperty("calendar_key", key); spin.valueChanged.connect(self._filling_changed); self.table.setCellWidget(row, column, spin); column += 1
                row += 1

    def _opening_toggled(self, checked: bool) -> None:
        if self._loading: return
        check = self.sender(); key = check.property("calendar_key")
        if not isinstance(key, tuple): return
        if not checked:
            count = int(self.data.consumption_counts.get(key, 0))
            if count:
                QMessageBox.warning(self, "Fermeture impossible", f"{count} consommation(s) existent déjà pour cette ouverture.")
                self._loading = True; check.setChecked(True); self._loading = False; return
            cell_events = [event for event in self.events if (event.date, event.group_id, event.unit_id) == key]
            if cell_events:
                if QMessageBox.question(self, "Évènements associés", f"{len(cell_events)} évènement(s) sont associés. Les supprimer avec l'ouverture ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    self._loading = True; check.setChecked(True); self._loading = False; return
                for event in cell_events:
                    if event.event_id is not None and self.repository.event_consumption_count(event.event_id):
                        QMessageBox.warning(self, "Fermeture impossible", "Un évènement possède déjà des consommations.")
                        self._loading = True; check.setChecked(True); self._loading = False; return
                self.events = [event for event in self.events if (event.date, event.group_id, event.unit_id) != key]
            self.openings.discard(key)
        else:
            self.openings.add(key)
        self._dirty = True

    def _filling_changed(self, value: int) -> None:
        if self._loading: return
        spin = self.sender(); key = spin.property("calendar_key")
        if not isinstance(key, tuple): return
        if value > 0: self.fillings[key] = int(value)
        else: self.fillings.pop(key, None)
        self._dirty = True

    def _edit_events(self) -> None:
        button = self.sender(); key = button.property("calendar_key")
        if not isinstance(key, tuple): return
        date_value, group_id, unit_id = key
        if group_id is None: return
        current = [event for event in self.events if (event.date, event.group_id, event.unit_id) == key]
        template = CalendarEvent(None, self.activity_id, unit_id, group_id, date_value, "")
        dialog = EventsDialog(self.repository, current, template, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.events = [event for event in self.events if (event.date, event.group_id, event.unit_id) != key] + dialog.events
            self._dirty = True; self._loading = True; self._build_table(); self._loading = False

    def _save(self) -> None:
        try:
            self.repository.save_month(self.activity_id, self.year, self.month, self.openings, self.fillings, self.events)
        except ValueError as exc:
            QMessageBox.warning(self, "Enregistrement impossible", str(exc)); return
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self._dirty = False; self.accept()


class ActivityCalendarPage(QWidget):
    """Résumé historique par année/mois/groupe et accès à l'éditeur mensuel."""

    def __init__(self, editor_repository: NativeActivityEditorRepository, activity_id: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.activity_id = activity_id; self.repository = ActivityCalendarRepository(editor_repository)
        root = QVBoxLayout(self); root.setContentsMargins(8, 10, 8, 10)
        top = QHBoxLayout(); intro = QLabel("Calendrier des ouvertures et des évènements", self); intro.setStyleSheet("font-weight: 600;"); top.addWidget(intro); top.addStretch(1)
        self.edit_button = QPushButton("Modifier le calendrier", self); self.edit_button.clicked.connect(self.edit_calendar); top.addWidget(self.edit_button); root.addLayout(top)
        self.tree = QTreeWidget(self); self.tree.setAlternatingRowColors(True); root.addWidget(self.tree, 1)
        self.refresh()

    def refresh(self) -> None:
        units = self.repository.list_units(self.activity_id); groups = dict(self.repository.list_groups(self.activity_id))
        openings = self.repository.list_openings(self.activity_id, dt.date(1977, 1, 1), dt.date(2999, 1, 1))
        events = self.repository.list_events(self.activity_id, dt.date(1977, 1, 1), dt.date(2999, 1, 1))
        event_counts = _event_counts_by_period(events)
        data: dict[int, dict[int, dict[int | None, dict[int, int]]]] = {}
        year_dates: dict[int, set[dt.date]] = {}; year_unit_dates: dict[tuple[int, int], set[dt.date]] = {}
        for opening in openings:
            data.setdefault(opening.date.year, {}).setdefault(opening.date.month, {}).setdefault(opening.group_id, {}).setdefault(opening.unit_id, 0)
            data[opening.date.year][opening.date.month][opening.group_id][opening.unit_id] += 1
            year_dates.setdefault(opening.date.year, set()).add(opening.date); year_unit_dates.setdefault((opening.date.year, opening.unit_id), set()).add(opening.date)
        self.tree.clear(); self.tree.setColumnCount(1 + len(units)); self.tree.setHeaderLabels(["Périodes / Groupes", *[unit.short_name for unit in units]])
        unit_columns = {unit.unit_id: index + 1 for index, unit in enumerate(units)}
        current_year = dt.date.today().year
        for year in sorted(data):
            year_item = QTreeWidgetItem(self.tree, [f"Année {year} ({len(year_dates.get(year, ())) } dates)"])
            for unit in units:
                count = len(year_unit_dates.get((year, unit.unit_id), ()))
                if count: year_item.setText(unit_columns[unit.unit_id], f"{count} dates")
            for month in sorted(data[year]):
                month_item = QTreeWidgetItem(year_item, [MONTH_NAMES[month - 1]])
                for group_id, unit_counts in sorted(data[year][month].items(), key=lambda item: (groups.get(item[0], "") if item[0] is not None else "")):
                    group_item = QTreeWidgetItem(month_item, [groups.get(group_id, "Sans groupe")])
                    for unit_id, count in unit_counts.items():
                        column = unit_columns.get(unit_id)
                        if column is None: continue
                        event_total = event_counts.get((year, month, group_id, unit_id), 0)
                        text = "1 date" if count == 1 else f"{count} dates"
                        if event_total: text += f" · {event_total} év."
                        group_item.setText(column, text)
                month_item.setExpanded(True)
            year_item.setExpanded(year >= current_year)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, self.tree.columnCount()): self.tree.header().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

    def edit_calendar(self) -> None:
        dialog = CalendarEditorDialog(self.repository, self.activity_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.refresh()


class ActivityEditorDialog(PricingActivityEditorDialog):
    """Fiche Activité avec page Calendrier Qt réelle."""

    def __init__(self, repository: NativeActivityEditorRepository, activity_id: int, parent: QWidget | None = None):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(6); self.tabs.removeTab(6)
        if old_page is not None: old_page.deleteLater()
        self.calendar_page = ActivityCalendarPage(repository, activity_id, self)
        self.tabs.insertTab(6, self.calendar_page, "Calendrier")
