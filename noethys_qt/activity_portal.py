"""Page Qt « Portail » de la fiche Activité.

Cette migration conserve le modèle historique : droits d'inscription et de
réservation portails, périodes de réservation, unités de réservation et options
de délai. Les données sont écrites dans les tables/colonnes Noethys existantes,
sans conversion de schéma et sans dépendance wxPython.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QDate, QDateTime, QTime, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .activity_agreements import ActivityAgreementsRepository
from .activity_editor import NativeActivityEditorRepository
from .activity_full import ActivityEditorDialog as FullActivityEditorDialog
from .activity_requirements import ActivityRequirementsRepository
from .activity_transaction import activity_transaction


DATE_LIMIT_CHOICES = (
    *((1000 + day, f"{label} précédent") for day, label in enumerate(
        ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")
    )),
    *((2000 + day, f"{label} de la semaine précédente") for day, label in enumerate(
        ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")
    )),
    (0, "Jour J"),
    *((day, f"Jour J-{day}") for day in range(1, 31)),
)


def _to_date(value: object) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _to_datetime(value: object) -> dt.datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time())
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(text[:19], fmt)
            return parsed
        except ValueError:
            continue
    return None


def _qdate(value: dt.date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _qdatetime(value: dt.datetime) -> QDateTime:
    return QDateTime(
        QDate(value.year, value.month, value.day),
        QTime(value.hour, value.minute, value.second),
    )


def _datetime_text(value: dt.datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value is not None else None


def _ids_text(values: Iterable[int]) -> str:
    return ";".join(str(int(value)) for value in values)


def _text_ids(value: object) -> tuple[int, ...]:
    if value in (None, ""):
        return ()
    result: list[int] = []
    for raw in str(value).split(";"):
        raw = raw.strip()
        if raw:
            try:
                result.append(int(raw))
            except ValueError:
                continue
    return tuple(result)


def _valid_hhmm(value: str) -> bool:
    try:
        dt.datetime.strptime(value, "%H:%M")
        return len(value) == 5
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class PortalSettings:
    registrations_enabled: bool
    registration_start: dt.datetime | None
    registration_end: dt.datetime | None
    reservations_enabled: bool
    multiple_units: bool
    reservation_limit: str | None
    unjustified_absence_limit: str | None


@dataclass(frozen=True, slots=True)
class ReservationPeriod:
    period_id: int | None
    activity_id: int
    name: str
    start_date: dt.date
    end_date: dt.date
    display: bool
    display_start: dt.datetime | None
    display_end: dt.datetime | None
    model_id: int | None
    introduction: str
    prefacturation: bool

    @property
    def period_label(self) -> str:
        return f"Du {self.start_date:%d/%m/%Y} au {self.end_date:%d/%m/%Y}"

    @property
    def display_label(self) -> str:
        if not self.display:
            return "Ne pas afficher"
        if self.display_start is None:
            return "Toujours afficher"
        return (
            f"Du {self.display_start:%d/%m/%Y-%Hh%M} "
            f"au {self.display_end:%d/%m/%Y-%Hh%M}"
        )


@dataclass(frozen=True, slots=True)
class PortalReservationUnit:
    unit_id: int | None
    activity_id: int
    name: str
    primary_unit_ids: tuple[int, ...]
    secondary_unit_ids: tuple[int, ...]
    order: int


class ActivityPortalRepository:
    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont transitoire volontaire

    def load_settings(self, activity_id: int) -> PortalSettings:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT portail_inscriptions_affichage, portail_inscriptions_date_debut,
                           portail_inscriptions_date_fin, portail_reservations_affichage,
                           portail_unites_multiples, portail_reservations_limite,
                           portail_reservations_absenti
                    FROM activites WHERE IDactivite={placeholder}""",
                (activity_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Activité introuvable.")
            return PortalSettings(
                registrations_enabled=bool(row[0]),
                registration_start=_to_datetime(row[1]),
                registration_end=_to_datetime(row[2]),
                reservations_enabled=bool(row[3]),
                multiple_units=bool(row[4]),
                reservation_limit=str(row[5]) if row[5] not in (None, "") else None,
                unjustified_absence_limit=str(row[6]) if row[6] not in (None, "") else None,
            )
        finally:
            cursor.close(); connection.close()

    def save_settings(self, activity_id: int, settings: PortalSettings) -> None:
        self.validate_settings(settings)
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""UPDATE activites SET
                    portail_inscriptions_affichage={placeholder},
                    portail_inscriptions_date_debut={placeholder},
                    portail_inscriptions_date_fin={placeholder},
                    portail_reservations_affichage={placeholder},
                    portail_unites_multiples={placeholder},
                    portail_reservations_limite={placeholder},
                    portail_reservations_absenti={placeholder}
                    WHERE IDactivite={placeholder}""",
                (
                    1 if settings.registrations_enabled else 0,
                    _datetime_text(settings.registration_start),
                    _datetime_text(settings.registration_end),
                    1 if settings.reservations_enabled else 0,
                    1 if settings.multiple_units else 0,
                    settings.reservation_limit,
                    settings.unjustified_absence_limit,
                    activity_id,
                ),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    f"SELECT 1 FROM activites WHERE IDactivite={placeholder}",
                    (activity_id,),
                )
                if cursor.fetchone() is None:
                    raise ValueError("Activité introuvable.")
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    @staticmethod
    def validate_settings(settings: PortalSettings) -> None:
        if settings.registrations_enabled and settings.registration_start is not None:
            if settings.registration_end is None:
                raise ValueError("Vous devez saisir une date de fin pour la période d'inscription sur le portail.")
            if settings.registration_start > settings.registration_end:
                raise ValueError("La fin de la période d'inscription doit être postérieure à son début.")
        if settings.reservation_limit:
            parts = settings.reservation_limit.split("#")
            if len(parts) < 2 or not _valid_hhmm(parts[1]):
                raise ValueError("L'heure limite de modification des réservations est invalide.")
            try:
                code = int(parts[0])
            except ValueError as exc:
                raise ValueError("La date limite de modification des réservations est invalide.") from exc
            if code not in {choice[0] for choice in DATE_LIMIT_CHOICES}:
                raise ValueError("La date limite de modification des réservations est inconnue.")
        if settings.unjustified_absence_limit:
            parts = settings.unjustified_absence_limit.split("#")
            if len(parts) != 2 or not _valid_hhmm(parts[1]):
                raise ValueError("L'heure de bascule en absence injustifiée est invalide.")
            try:
                day = int(parts[0])
            except ValueError as exc:
                raise ValueError("La date de bascule en absence injustifiée est invalide.") from exc
            if day < 0 or day > 30:
                raise ValueError("La date de bascule en absence injustifiée est invalide.")

    def list_periods(self, activity_id: int) -> list[ReservationPeriod]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT IDperiode, IDactivite, nom, date_debut, date_fin, affichage,
                           affichage_date_debut, affichage_date_fin, IDmodele,
                           introduction, prefacturation
                    FROM portail_periodes WHERE IDactivite={placeholder}
                    ORDER BY date_debut, date_fin, IDperiode""",
                (activity_id,),
            )
            result: list[ReservationPeriod] = []
            for row in cursor.fetchall():
                start = _to_date(row[3]); end = _to_date(row[4])
                if start is None or end is None:
                    continue
                result.append(
                    ReservationPeriod(
                        period_id=int(row[0]), activity_id=int(row[1]), name=str(row[2] or ""),
                        start_date=start, end_date=end, display=bool(row[5]),
                        display_start=_to_datetime(row[6]), display_end=_to_datetime(row[7]),
                        model_id=int(row[8]) if row[8] not in (None, "") else None,
                        introduction=str(row[9] or ""), prefacturation=bool(row[10]),
                    )
                )
            return result
        finally:
            cursor.close(); connection.close()

    def list_email_models(self) -> list[tuple[int, str, bool]]:
        connection, _placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT IDmodele, nom, defaut FROM modeles_emails "
                "WHERE categorie='portail_demande_reservation' ORDER BY nom"
            )
            return [(int(row[0]), str(row[1] or ""), bool(row[2])) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def save_period(self, period: ReservationPeriod) -> int:
        self.validate_period(period)
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            if period.model_id is not None:
                cursor.execute(
                    f"SELECT 1 FROM modeles_emails WHERE IDmodele={placeholder} "
                    "AND categorie='portail_demande_reservation'",
                    (period.model_id,),
                )
                if cursor.fetchone() is None:
                    raise ValueError("Le modèle d'Email sélectionné n'existe plus.")
            fields = (
                "IDactivite", "nom", "date_debut", "date_fin", "affichage",
                "affichage_date_debut", "affichage_date_fin", "IDmodele",
                "introduction", "prefacturation",
            )
            values = (
                period.activity_id, period.name.strip(), period.start_date.isoformat(),
                period.end_date.isoformat(), 1 if period.display else 0,
                _datetime_text(period.display_start), _datetime_text(period.display_end),
                period.model_id, period.introduction or None, 1 if period.prefacturation else 0,
            )
            if period.period_id is None:
                cursor.execute(
                    f"INSERT INTO portail_periodes ({', '.join(fields)}) VALUES "
                    f"({', '.join(placeholder for _ in fields)})",
                    values,
                )
                period_id = int(cursor.lastrowid)
            else:
                cursor.execute(
                    f"UPDATE portail_periodes SET "
                    f"{', '.join(f'{field}={placeholder}' for field in fields)} "
                    f"WHERE IDperiode={placeholder} AND IDactivite={placeholder}",
                    values + (period.period_id, period.activity_id),
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        f"SELECT 1 FROM portail_periodes WHERE IDperiode={placeholder} "
                        f"AND IDactivite={placeholder}",
                        (period.period_id, period.activity_id),
                    )
                    if cursor.fetchone() is None:
                        raise ValueError("Période de réservation introuvable.")
                period_id = period.period_id
            connection.commit(); return int(period_id)
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    @staticmethod
    def validate_period(period: ReservationPeriod) -> None:
        if not period.name.strip():
            raise ValueError("Vous devez obligatoirement saisir un nom pour cette période de réservations.")
        if period.start_date > period.end_date:
            raise ValueError("La fin de la période de réservations doit être postérieure à son début.")
        if period.display and period.display_start is not None:
            if period.display_end is None:
                raise ValueError("Vous devez saisir une fin de période d'affichage sur le portail.")
            if period.display_start > period.display_end:
                raise ValueError("La fin de la période d'affichage doit être postérieure à son début.")
        if not period.display and (period.display_start is not None or period.display_end is not None):
            raise ValueError("Une période masquée ne doit pas conserver de dates d'affichage.")

    def delete_period(self, activity_id: int, period_id: int) -> None:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"DELETE FROM portail_periodes WHERE IDperiode={placeholder} AND IDactivite={placeholder}",
                (period_id, activity_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Période de réservation introuvable.")
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def list_consumption_units(self, activity_id: int) -> list[tuple[int, str]]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT IDunite, nom FROM unites WHERE IDactivite={placeholder} ORDER BY ordre, IDunite",
                (activity_id,),
            )
            return [(int(row[0]), str(row[1] or "")) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def list_reservation_units(self, activity_id: int) -> list[PortalReservationUnit]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT IDunite, IDactivite, nom, unites_principales, unites_secondaires, ordre
                    FROM portail_unites WHERE IDactivite={placeholder}
                    ORDER BY ordre, IDunite""",
                (activity_id,),
            )
            return [
                PortalReservationUnit(
                    unit_id=int(row[0]), activity_id=int(row[1]), name=str(row[2] or ""),
                    primary_unit_ids=_text_ids(row[3]), secondary_unit_ids=_text_ids(row[4]),
                    order=int(row[5] or 0),
                )
                for row in cursor.fetchall()
            ]
        finally:
            cursor.close(); connection.close()

    def _validate_reservation_unit(self, unit: PortalReservationUnit) -> None:
        if not unit.name.strip():
            raise ValueError("Vous devez obligatoirement saisir un nom pour cette unité de réservation.")
        if not unit.primary_unit_ids:
            raise ValueError("Vous devez cocher au moins une unité de consommation principale.")
        overlap = set(unit.primary_unit_ids) & set(unit.secondary_unit_ids)
        if overlap:
            raise ValueError("Une unité de consommation ne peut pas être à la fois principale et secondaire.")
        allowed = {unit_id for unit_id, _name in self.list_consumption_units(unit.activity_id)}
        unknown = (set(unit.primary_unit_ids) | set(unit.secondary_unit_ids)) - allowed
        if unknown:
            raise ValueError("Une unité de consommation sélectionnée n'appartient pas à cette activité.")

    def save_reservation_unit(self, unit: PortalReservationUnit) -> int:
        self._validate_reservation_unit(unit)
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            if unit.unit_id is None:
                cursor.execute(
                    f"SELECT COALESCE(MAX(ordre), 0) FROM portail_unites WHERE IDactivite={placeholder}",
                    (unit.activity_id,),
                )
                order = int(cursor.fetchone()[0] or 0) + 1
                cursor.execute(
                    "INSERT INTO portail_unites "
                    "(IDactivite, nom, unites_principales, unites_secondaires, ordre) VALUES "
                    f"({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (unit.activity_id, unit.name.strip(), _ids_text(unit.primary_unit_ids),
                     _ids_text(unit.secondary_unit_ids), order),
                )
                unit_id = int(cursor.lastrowid)
            else:
                cursor.execute(
                    f"UPDATE portail_unites SET nom={placeholder}, unites_principales={placeholder}, "
                    f"unites_secondaires={placeholder} WHERE IDunite={placeholder} AND IDactivite={placeholder}",
                    (unit.name.strip(), _ids_text(unit.primary_unit_ids), _ids_text(unit.secondary_unit_ids),
                     unit.unit_id, unit.activity_id),
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        f"SELECT 1 FROM portail_unites WHERE IDunite={placeholder} AND IDactivite={placeholder}",
                        (unit.unit_id, unit.activity_id),
                    )
                    if cursor.fetchone() is None:
                        raise ValueError("Unité de réservation introuvable.")
                unit_id = unit.unit_id
            connection.commit(); return int(unit_id)
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def delete_reservation_unit(self, activity_id: int, unit_id: int) -> None:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"DELETE FROM portail_unites WHERE IDunite={placeholder} AND IDactivite={placeholder}",
                (unit_id, activity_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("Unité de réservation introuvable.")
            self._resequence_units(cursor, placeholder, activity_id)
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def move_reservation_unit(self, activity_id: int, unit_id: int, delta: int) -> None:
        if delta not in (-1, 1):
            raise ValueError("Le déplacement doit être -1 ou +1.")
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT IDunite FROM portail_unites WHERE IDactivite={placeholder} ORDER BY ordre, IDunite",
                (activity_id,),
            )
            ids = [int(row[0]) for row in cursor.fetchall()]
            if unit_id not in ids:
                raise ValueError("Unité de réservation introuvable.")
            source = ids.index(unit_id); target = source + delta
            if target < 0 or target >= len(ids):
                return
            ids[source], ids[target] = ids[target], ids[source]
            for order, current_id in enumerate(ids, start=1):
                cursor.execute(
                    f"UPDATE portail_unites SET ordre={placeholder} WHERE IDunite={placeholder} AND IDactivite={placeholder}",
                    (order, current_id, activity_id),
                )
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    @staticmethod
    def _resequence_units(cursor, placeholder: str, activity_id: int) -> None:
        cursor.execute(
            f"SELECT IDunite FROM portail_unites WHERE IDactivite={placeholder} ORDER BY ordre, IDunite",
            (activity_id,),
        )
        for order, (unit_id,) in enumerate(cursor.fetchall(), start=1):
            cursor.execute(
                f"UPDATE portail_unites SET ordre={placeholder} WHERE IDunite={placeholder} AND IDactivite={placeholder}",
                (order, unit_id, activity_id),
            )


class ReservationPeriodDialog(QDialog):
    def __init__(self, repository: ActivityPortalRepository, activity_id: int,
                 period: ReservationPeriod | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository; self.activity_id = activity_id; self.period = period
        self.setWindowTitle("Période de réservations")
        root = QVBoxLayout(self)
        form = QFormLayout(); root.addLayout(form)
        self.name_edit = QLineEdit(self); form.addRow("Nom :", self.name_edit)
        self.intro_edit = QPlainTextEdit(self); self.intro_edit.setMaximumHeight(90)
        form.addRow("Introduction :", self.intro_edit)
        dates = QHBoxLayout(); self.start_edit = QDateEdit(self); self.end_edit = QDateEdit(self)
        for control in (self.start_edit, self.end_edit): control.setCalendarPopup(True); control.setDisplayFormat("dd/MM/yyyy")
        dates.addWidget(QLabel("Du", self)); dates.addWidget(self.start_edit); dates.addWidget(QLabel("au", self)); dates.addWidget(self.end_edit)
        form.addRow("Période :", dates)

        display_box = QGroupBox("Affichage sur le portail", self); display_layout = QVBoxLayout(display_box)
        self.always_radio = QRadioButton("Toujours afficher", display_box)
        self.dates_radio = QRadioButton("Afficher uniquement sur une période", display_box)
        self.never_radio = QRadioButton("Ne pas afficher", display_box)
        group = QButtonGroup(display_box)
        for radio in (self.always_radio, self.dates_radio, self.never_radio): group.addButton(radio); display_layout.addWidget(radio)
        display_dates = QHBoxLayout(); self.display_start = QDateTimeEdit(display_box); self.display_end = QDateTimeEdit(display_box)
        for control in (self.display_start, self.display_end):
            control.setCalendarPopup(True); control.setDisplayFormat("dd/MM/yyyy HH:mm")
        display_dates.addWidget(QLabel("Du", display_box)); display_dates.addWidget(self.display_start)
        display_dates.addWidget(QLabel("au", display_box)); display_dates.addWidget(self.display_end)
        display_layout.addLayout(display_dates); root.addWidget(display_box)
        self.dates_radio.toggled.connect(self._sync_display)

        self.model_combo = __import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox(self)
        self.model_combo.addItem("Modèle d'Email par défaut", None)
        for model_id, name, _default in repository.list_email_models(): self.model_combo.addItem(name, model_id)
        form.addRow("Modèle d'Email :", self.model_combo)
        self.prefacturation_check = QCheckBox("Activer la préfacturation pour cette période", self)
        root.addWidget(self.prefacturation_check)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer")
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._load()

    def _load(self) -> None:
        today = dt.date.today(); now = dt.datetime.now().replace(second=0, microsecond=0)
        period = self.period
        self.name_edit.setText(period.name if period else "")
        self.intro_edit.setPlainText(period.introduction if period else "")
        self.start_edit.setDate(_qdate(period.start_date if period else today))
        self.end_edit.setDate(_qdate(period.end_date if period else today))
        self.display_start.setDateTime(_qdatetime(period.display_start if period and period.display_start else now))
        self.display_end.setDateTime(_qdatetime(period.display_end if period and period.display_end else now))
        if period and not period.display: self.never_radio.setChecked(True)
        elif period and period.display_start is not None: self.dates_radio.setChecked(True)
        else: self.always_radio.setChecked(True)
        if period and period.model_id is not None:
            index = self.model_combo.findData(period.model_id)
            if index >= 0: self.model_combo.setCurrentIndex(index)
        self.prefacturation_check.setChecked(bool(period and period.prefacturation)); self._sync_display()

    def _sync_display(self, *_args) -> None:
        enabled = self.dates_radio.isChecked(); self.display_start.setEnabled(enabled); self.display_end.setEnabled(enabled)

    def collect(self) -> ReservationPeriod:
        display = not self.never_radio.isChecked()
        display_start = self.display_start.dateTime().toPython() if self.dates_radio.isChecked() else None
        display_end = self.display_end.dateTime().toPython() if self.dates_radio.isChecked() else None
        result = ReservationPeriod(
            period_id=self.period.period_id if self.period else None, activity_id=self.activity_id,
            name=self.name_edit.text().strip(), start_date=self.start_edit.date().toPython(),
            end_date=self.end_edit.date().toPython(), display=display, display_start=display_start,
            display_end=display_end, model_id=self.model_combo.currentData(),
            introduction=self.intro_edit.toPlainText(), prefacturation=self.prefacturation_check.isChecked(),
        )
        self.repository.validate_period(result); return result

    def _accept(self) -> None:
        try: self.repository.save_period(self.collect())
        except ValueError as exc: QMessageBox.warning(self, "Erreur de saisie", str(exc)); return
        except Exception as exc: QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self.accept()


class ReservationUnitDialog(QDialog):
    def __init__(self, repository: ActivityPortalRepository, activity_id: int,
                 unit: PortalReservationUnit | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository; self.activity_id = activity_id; self.unit = unit
        self.setWindowTitle("Unité de réservation")
        root = QVBoxLayout(self); form = QFormLayout(); root.addLayout(form)
        self.name_edit = QLineEdit(self); form.addRow("Nom :", self.name_edit)
        row = QHBoxLayout(); self.primary_list = QListWidget(self); self.secondary_list = QListWidget(self)
        row.addWidget(self._list_box("Unités principales", self.primary_list)); row.addWidget(self._list_box("Unités secondaires", self.secondary_list)); root.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer")
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._load()

    def _list_box(self, title: str, control: QListWidget) -> QGroupBox:
        box = QGroupBox(title, self); layout = QVBoxLayout(box); layout.addWidget(control); return box

    def _load(self) -> None:
        primary = set(self.unit.primary_unit_ids if self.unit else ()); secondary = set(self.unit.secondary_unit_ids if self.unit else ())
        self.name_edit.setText(self.unit.name if self.unit else "")
        for unit_id, name in self.repository.list_consumption_units(self.activity_id):
            for control, selected in ((self.primary_list, primary), (self.secondary_list, secondary)):
                item = QListWidgetItem(name, control); item.setData(Qt.ItemDataRole.UserRole, unit_id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if unit_id in selected else Qt.CheckState.Unchecked)

    @staticmethod
    def _checked(control: QListWidget) -> tuple[int, ...]:
        return tuple(int(control.item(index).data(Qt.ItemDataRole.UserRole)) for index in range(control.count()) if control.item(index).checkState() == Qt.CheckState.Checked)

    def collect(self) -> PortalReservationUnit:
        result = PortalReservationUnit(
            unit_id=self.unit.unit_id if self.unit else None, activity_id=self.activity_id,
            name=self.name_edit.text().strip(), primary_unit_ids=self._checked(self.primary_list),
            secondary_unit_ids=self._checked(self.secondary_list), order=self.unit.order if self.unit else 0,
        )
        self.repository._validate_reservation_unit(result); return result  # noqa: SLF001

    def _accept(self) -> None:
        try: self.repository.save_reservation_unit(self.collect())
        except ValueError as exc: QMessageBox.warning(self, "Erreur de saisie", str(exc)); return
        except Exception as exc: QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self.accept()


class ActivityPortalPage(QWidget):
    def __init__(self, editor_repository: NativeActivityEditorRepository, activity_id: int,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = ActivityPortalRepository(editor_repository); self.activity_id = activity_id
        self.state = self.repository.load_settings(activity_id)
        root = QVBoxLayout(self)
        root.addWidget(self._registrations_box())
        reservations = QGroupBox("Réservations sur le portail", self); reservations_layout = QVBoxLayout(reservations)
        radio_row = QHBoxLayout(); self.reservations_no = QRadioButton("Ne pas autoriser", reservations); self.reservations_yes = QRadioButton("Autoriser", reservations)
        reservation_group = QButtonGroup(reservations); reservation_group.addButton(self.reservations_no); reservation_group.addButton(self.reservations_yes)
        radio_row.addWidget(self.reservations_no); radio_row.addWidget(self.reservations_yes); radio_row.addStretch(1); reservations_layout.addLayout(radio_row)
        self.reservation_tabs = QTabWidget(reservations); self.periods_page = self._periods_page(); self.units_page = self._units_page(); self.options_page = self._options_page()
        self.reservation_tabs.addTab(self.periods_page, "Périodes"); self.reservation_tabs.addTab(self.units_page, "Unités"); self.reservation_tabs.addTab(self.options_page, "Options")
        reservations_layout.addWidget(self.reservation_tabs, 1); root.addWidget(reservations, 1)
        self._load_settings(); self.refresh_periods(); self.refresh_units()

    def _registrations_box(self) -> QGroupBox:
        box = QGroupBox("Inscriptions sur le portail", self); layout = QVBoxLayout(box)
        row = QHBoxLayout(); self.reg_no = QRadioButton("Ne pas autoriser", box); self.reg_yes = QRadioButton("Autoriser", box); self.reg_dates = QRadioButton("Autoriser uniquement sur une période", box)
        group = QButtonGroup(box)
        for radio in (self.reg_no, self.reg_yes, self.reg_dates): group.addButton(radio); row.addWidget(radio)
        row.addStretch(1); layout.addLayout(row)
        dates = QHBoxLayout(); self.reg_start = QDateTimeEdit(box); self.reg_end = QDateTimeEdit(box)
        for control in (self.reg_start, self.reg_end): control.setCalendarPopup(True); control.setDisplayFormat("dd/MM/yyyy HH:mm")
        dates.addWidget(QLabel("Du", box)); dates.addWidget(self.reg_start); dates.addWidget(QLabel("au", box)); dates.addWidget(self.reg_end); dates.addStretch(1); layout.addLayout(dates)
        self.reg_dates.toggled.connect(self._sync_registration_dates); return box

    def _periods_page(self) -> QWidget:
        page = QWidget(self); layout = QHBoxLayout(page); self.periods_table = QTableWidget(0, 3, page)
        self.periods_table.setHorizontalHeaderLabels(("Période", "Nom", "Affichage")); self.periods_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.periods_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.periods_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.periods_table.doubleClicked.connect(self.edit_period)
        layout.addWidget(self.periods_table, 1); buttons = QVBoxLayout()
        for label, slot in (("Ajouter", self.add_period), ("Modifier", self.edit_period), ("Supprimer", self.delete_period)):
            button = QPushButton(label, page); button.clicked.connect(slot); buttons.addWidget(button)
        buttons.addStretch(1); layout.addLayout(buttons); return page

    def _units_page(self) -> QWidget:
        page = QWidget(self); outer = QVBoxLayout(page); row = QHBoxLayout(); self.units_table = QTableWidget(0, 4, page)
        self.units_table.setHorizontalHeaderLabels(("Ordre", "Nom", "Unités principales", "Unités secondaires")); self.units_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.units_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.units_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.units_table.doubleClicked.connect(self.edit_unit)
        row.addWidget(self.units_table, 1); buttons = QVBoxLayout()
        for label, slot in (("Ajouter", self.add_unit), ("Modifier", self.edit_unit), ("Supprimer", self.delete_unit), ("Monter", lambda: self.move_unit(-1)), ("Descendre", lambda: self.move_unit(1))):
            button = QPushButton(label, page); button.clicked.connect(slot); buttons.addWidget(button)
        buttons.addStretch(1); row.addLayout(buttons); outer.addLayout(row, 1)
        self.multiple_check = QCheckBox("Sélection multiple d'unités de réservations autorisée", page); outer.addWidget(self.multiple_check); return page

    def _options_page(self) -> QWidget:
        page = QWidget(self); layout = QVBoxLayout(page)
        limit = QGroupBox("Limite de modification", page); form = QFormLayout(limit); self.limit_check = QCheckBox("Activer une date limite", limit); form.addRow(self.limit_check)
        from PySide6.QtWidgets import QComboBox
        self.limit_day = QComboBox(limit)
        for code, label in DATE_LIMIT_CHOICES: self.limit_day.addItem(label, code)
        self.limit_time = QTimeEdit(limit); self.limit_time.setDisplayFormat("HH:mm"); self.limit_weekends = QCheckBox("Exclure les week-ends", limit); self.limit_holidays = QCheckBox("Exclure les jours fériés", limit)
        limit_row = QHBoxLayout(); limit_row.addWidget(self.limit_day); limit_row.addWidget(self.limit_time); limit_row.addStretch(1); form.addRow("Jusqu'à :", limit_row); form.addRow(self.limit_weekends); form.addRow(self.limit_holidays); self.limit_check.toggled.connect(self._sync_limit); layout.addWidget(limit)
        absence = QGroupBox("Absence injustifiée", page); absence_form = QFormLayout(absence); self.absence_check = QCheckBox("Appliquer l'état après la limite", absence); absence_form.addRow(self.absence_check); self.absence_day = QComboBox(absence)
        for day in range(31): self.absence_day.addItem("Jour J" if day == 0 else f"Jour J-{day}", day)
        self.absence_time = QTimeEdit(absence); self.absence_time.setDisplayFormat("HH:mm"); absence_row = QHBoxLayout(); absence_row.addWidget(self.absence_day); absence_row.addWidget(self.absence_time); absence_row.addStretch(1); absence_form.addRow("Après :", absence_row); self.absence_check.toggled.connect(self._sync_absence); layout.addWidget(absence); layout.addStretch(1); return page

    def _load_settings(self) -> None:
        state = self.state; now = dt.datetime.now().replace(second=0, microsecond=0)
        if not state.registrations_enabled: self.reg_no.setChecked(True)
        elif state.registration_start is None: self.reg_yes.setChecked(True)
        else: self.reg_dates.setChecked(True)
        self.reg_start.setDateTime(_qdatetime(state.registration_start or now)); self.reg_end.setDateTime(_qdatetime(state.registration_end or now))
        self.reservations_yes.setChecked(state.reservations_enabled); self.reservations_no.setChecked(not state.reservations_enabled); self.multiple_check.setChecked(state.multiple_units)
        self.limit_time.setTime(QTime(9, 0)); self.limit_day.setCurrentIndex(max(0, self.limit_day.findData(0)))
        if state.reservation_limit:
            parts = state.reservation_limit.split("#"); self.limit_check.setChecked(True)
            try: self.limit_day.setCurrentIndex(max(0, self.limit_day.findData(int(parts[0]))))
            except (ValueError, IndexError): pass
            if len(parts) > 1 and _valid_hhmm(parts[1]): self.limit_time.setTime(QTime.fromString(parts[1], "HH:mm"))
            options = parts[2] if len(parts) > 2 else ""; self.limit_weekends.setChecked("weekends" in options); self.limit_holidays.setChecked("feries" in options)
        self.absence_time.setTime(QTime(23, 59)); self.absence_day.setCurrentIndex(self.absence_day.findData(3))
        if state.unjustified_absence_limit:
            parts = state.unjustified_absence_limit.split("#"); self.absence_check.setChecked(True)
            try: self.absence_day.setCurrentIndex(max(0, self.absence_day.findData(int(parts[0]))))
            except (ValueError, IndexError): pass
            if len(parts) > 1 and _valid_hhmm(parts[1]): self.absence_time.setTime(QTime.fromString(parts[1], "HH:mm"))
        self._sync_registration_dates(); self._sync_limit(); self._sync_absence()

    def _sync_registration_dates(self, *_args) -> None:
        enabled = self.reg_dates.isChecked(); self.reg_start.setEnabled(enabled); self.reg_end.setEnabled(enabled)

    def _sync_limit(self, *_args) -> None:
        enabled = self.limit_check.isChecked()
        for control in (self.limit_day, self.limit_time, self.limit_weekends, self.limit_holidays): control.setEnabled(enabled)

    def _sync_absence(self, *_args) -> None:
        enabled = self.absence_check.isChecked(); self.absence_day.setEnabled(enabled); self.absence_time.setEnabled(enabled)

    def collect(self) -> PortalSettings:
        registrations = not self.reg_no.isChecked(); start = self.reg_start.dateTime().toPython() if self.reg_dates.isChecked() else None; end = self.reg_end.dateTime().toPython() if self.reg_dates.isChecked() else None
        limit = None
        if self.limit_check.isChecked():
            options = []
            if self.limit_weekends.isChecked(): options.append("weekends")
            if self.limit_holidays.isChecked(): options.append("feries")
            limit = f"{int(self.limit_day.currentData())}#{self.limit_time.time().toString('HH:mm')}#{','.join(options)}"
        absence = None
        if self.absence_check.isChecked(): absence = f"{int(self.absence_day.currentData())}#{self.absence_time.time().toString('HH:mm')}"
        state = PortalSettings(registrations, start, end, self.reservations_yes.isChecked(), self.multiple_check.isChecked(), limit, absence)
        self.repository.validate_settings(state); return state

    def refresh_periods(self) -> None:
        self.period_rows = self.repository.list_periods(self.activity_id); self.periods_table.setRowCount(len(self.period_rows))
        for row_index, period in enumerate(self.period_rows):
            values = (period.period_label, period.name, period.display_label)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole, period.period_id); self.periods_table.setItem(row_index, column, item)
        self.periods_table.resizeColumnsToContents()

    def _selected_period(self) -> ReservationPeriod | None:
        row = self.periods_table.currentRow(); return self.period_rows[row] if 0 <= row < len(self.period_rows) else None

    def add_period(self, *_args) -> None:
        if ReservationPeriodDialog(self.repository, self.activity_id, parent=self).exec() == QDialog.DialogCode.Accepted: self.refresh_periods()

    def edit_period(self, *_args) -> None:
        period = self._selected_period()
        if period and ReservationPeriodDialog(self.repository, self.activity_id, period, self).exec() == QDialog.DialogCode.Accepted: self.refresh_periods()

    def delete_period(self, *_args) -> None:
        period = self._selected_period()
        if period is None: return
        if QMessageBox.question(self, "Suppression", f"Supprimer la période « {period.name} » ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        try: self.repository.delete_period(self.activity_id, int(period.period_id))
        except Exception as exc: QMessageBox.critical(self, "Suppression impossible", str(exc)); return
        self.refresh_periods()

    def refresh_units(self) -> None:
        self.unit_rows = self.repository.list_reservation_units(self.activity_id); names = dict(self.repository.list_consumption_units(self.activity_id)); self.units_table.setRowCount(len(self.unit_rows))
        for row_index, unit in enumerate(self.unit_rows):
            values = (str(unit.order), unit.name, " + ".join(names.get(value, str(value)) for value in unit.primary_unit_ids), " + ".join(names.get(value, str(value)) for value in unit.secondary_unit_ids))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole, unit.unit_id); self.units_table.setItem(row_index, column, item)
        self.units_table.resizeColumnsToContents()

    def _selected_unit(self) -> PortalReservationUnit | None:
        row = self.units_table.currentRow(); return self.unit_rows[row] if 0 <= row < len(self.unit_rows) else None

    def add_unit(self, *_args) -> None:
        if ReservationUnitDialog(self.repository, self.activity_id, parent=self).exec() == QDialog.DialogCode.Accepted: self.refresh_units()

    def edit_unit(self, *_args) -> None:
        unit = self._selected_unit()
        if unit and ReservationUnitDialog(self.repository, self.activity_id, unit, self).exec() == QDialog.DialogCode.Accepted: self.refresh_units()

    def delete_unit(self, *_args) -> None:
        unit = self._selected_unit()
        if unit is None: return
        if QMessageBox.question(self, "Suppression", f"Supprimer l'unité de réservation « {unit.name} » ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        try: self.repository.delete_reservation_unit(self.activity_id, int(unit.unit_id))
        except Exception as exc: QMessageBox.critical(self, "Suppression impossible", str(exc)); return
        self.refresh_units()

    def move_unit(self, delta: int) -> None:
        unit = self._selected_unit()
        if unit is None: return
        try: self.repository.move_reservation_unit(self.activity_id, int(unit.unit_id), delta)
        except Exception as exc: QMessageBox.critical(self, "Déplacement impossible", str(exc)); return
        self.refresh_units()
        for row, current in enumerate(self.unit_rows):
            if current.unit_id == unit.unit_id: self.units_table.selectRow(row); break


class ActivityEditorDialog(FullActivityEditorDialog):
    """Fiche Activité complète avec page Portail réellement éditable."""

    def __init__(self, repository: NativeActivityEditorRepository, activity_id: int,
                 parent: QWidget | None = None):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(7); self.tabs.removeTab(7)
        if old_page is not None: old_page.deleteLater()
        self.portal_page = ActivityPortalPage(repository, activity_id, self)
        self.tabs.insertTab(7, self.portal_page, "Portail")

    def _save(self) -> None:
        if not self._validate_composed_editor():
            return
        try:
            details = self._collect(); requirements = self.requirements_page.collect(); agreements = self.agreements_page.collect(confirm_delete=True); portal = self.portal_page.collect()
            with activity_transaction(self.repository) as shared_repository:
                NativeActivityEditorRepository.save(shared_repository, details, self._checked_group_ids())
                ActivityRequirementsRepository(shared_repository).save(self.activity_id, requirements)
                ActivityAgreementsRepository(shared_repository).save(self.activity_id, agreements)
                ActivityPortalRepository(shared_repository).save_settings(self.activity_id, portal)
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc)); return
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self.details = details; self.requirements_page.state = requirements; self.agreements_page.state = agreements; self.portal_page.state = portal; self.accept()
