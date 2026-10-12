"""Page Qt « Agréments » de la fiche Activité.

Trois modes historiques sont conservés : aucun agrément, agrément unique
(valide de 1977-01-01 à 2999-01-01) et agréments multiples avec périodes de
validité propres.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from typing import Sequence

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .activity_editor import NativeActivityEditorRepository
from .activity_requirements import (
    ActivityEditorDialog as RequirementsActivityEditorDialog,
    ActivityRequirementsRepository,
)
from .activity_transaction import activity_transaction


UNIQUE_START = dt.date(1977, 1, 1)
UNIQUE_END = dt.date(2999, 1, 1)


@dataclass(frozen=True, slots=True)
class Agreement:
    agreement_id: int | None
    activity_id: int
    number: str
    start_date: dt.date
    end_date: dt.date

    @property
    def is_unique(self) -> bool:
        return self.start_date == UNIQUE_START and self.end_date == UNIQUE_END

    @property
    def period(self) -> str:
        return f"Du {self.start_date:%d/%m/%Y} au {self.end_date:%d/%m/%Y}"


@dataclass(frozen=True, slots=True)
class AgreementState:
    mode: str
    unique_number: str
    multiple: tuple[Agreement, ...]


class ActivityAgreementsRepository:
    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont transitoire volontaire

    def list_agreements(self, activity_id: int) -> list[Agreement]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT IDagrement, IDactivite, agrement, date_debut, date_fin
                    FROM agrements WHERE IDactivite={placeholder}
                    ORDER BY date_fin, IDagrement""",
                (activity_id,),
            )
            return [Agreement(
                int(row[0]), int(row[1]), str(row[2] or ""),
                _as_date(row[3]), _as_date(row[4]),
            ) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def load(self, activity_id: int) -> AgreementState:
        rows = self.list_agreements(activity_id)
        if not rows:
            return AgreementState("none", "", ())
        if len(rows) == 1 and rows[0].is_unique:
            return AgreementState("unique", rows[0].number, ())
        return AgreementState("multiple", "", tuple(row for row in rows if not row.is_unique))

    @staticmethod
    def validate(state: AgreementState) -> None:
        if state.mode not in {"none", "unique", "multiple"}:
            raise ValueError("Mode d'agrément invalide.")
        if state.mode == "unique" and not state.unique_number.strip():
            raise ValueError("Vous avez sélectionné « Agrément unique » sans saisir de numéro d'agrément.")
        if state.mode == "multiple" and not state.multiple:
            raise ValueError("Vous avez sélectionné « Agréments multiples » sans saisir aucun agrément.")
        for agreement in state.multiple:
            if not agreement.number.strip():
                raise ValueError("Chaque agrément doit obligatoirement comporter un numéro.")
            if agreement.end_date < agreement.start_date:
                raise ValueError("La date de fin d'un agrément ne peut pas précéder sa date de début.")

    def save(self, activity_id: int, state: AgreementState) -> None:
        self.validate(state)
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT IDagrement, date_debut, date_fin FROM agrements WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            existing = [(int(row[0]), _as_date(row[1]), _as_date(row[2])) for row in cursor.fetchall()]

            if state.mode == "none":
                cursor.execute(f"DELETE FROM agrements WHERE IDactivite={placeholder}", (activity_id,))

            elif state.mode == "unique":
                unique_ids = [agreement_id for agreement_id, start, end in existing if start == UNIQUE_START and end == UNIQUE_END]
                cursor.execute(
                    f"DELETE FROM agrements WHERE IDactivite={placeholder} AND NOT "
                    f"(date_debut={placeholder} AND date_fin={placeholder})",
                    (activity_id, UNIQUE_START.isoformat(), UNIQUE_END.isoformat()),
                )
                if unique_ids:
                    keep_id = unique_ids[0]
                    cursor.execute(
                        f"UPDATE agrements SET agrement={placeholder}, date_debut={placeholder}, date_fin={placeholder} "
                        f"WHERE IDagrement={placeholder}",
                        (state.unique_number.strip(), UNIQUE_START.isoformat(), UNIQUE_END.isoformat(), keep_id),
                    )
                    for duplicate_id in unique_ids[1:]:
                        cursor.execute(f"DELETE FROM agrements WHERE IDagrement={placeholder}", (duplicate_id,))
                else:
                    cursor.execute(
                        f"INSERT INTO agrements (IDactivite, agrement, date_debut, date_fin) VALUES "
                        f"({placeholder}, {placeholder}, {placeholder}, {placeholder})",
                        (activity_id, state.unique_number.strip(), UNIQUE_START.isoformat(), UNIQUE_END.isoformat()),
                    )

            else:
                # Le mode multiple ne conserve jamais la ligne sentinelle de l'agrément unique.
                cursor.execute(
                    f"DELETE FROM agrements WHERE IDactivite={placeholder} AND date_debut={placeholder} AND date_fin={placeholder}",
                    (activity_id, UNIQUE_START.isoformat(), UNIQUE_END.isoformat()),
                )
                cursor.execute(
                    f"SELECT IDagrement FROM agrements WHERE IDactivite={placeholder}",
                    (activity_id,),
                )
                old_ids = {int(row[0]) for row in cursor.fetchall()}
                kept: set[int] = set()
                for agreement in state.multiple:
                    values = (
                        agreement.number.strip(), agreement.start_date.isoformat(), agreement.end_date.isoformat(),
                    )
                    if agreement.agreement_id is None or agreement.agreement_id not in old_ids:
                        cursor.execute(
                            f"INSERT INTO agrements (IDactivite, agrement, date_debut, date_fin) VALUES "
                            f"({placeholder}, {placeholder}, {placeholder}, {placeholder})",
                            (activity_id, *values),
                        )
                        kept.add(int(cursor.lastrowid))
                    else:
                        cursor.execute(
                            f"UPDATE agrements SET agrement={placeholder}, date_debut={placeholder}, date_fin={placeholder} "
                            f"WHERE IDagrement={placeholder} AND IDactivite={placeholder}",
                            values + (agreement.agreement_id, activity_id),
                        )
                        kept.add(int(agreement.agreement_id))
                for agreement_id in old_ids - kept:
                    cursor.execute(f"DELETE FROM agrements WHERE IDagrement={placeholder}", (agreement_id,))

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()


def _as_date(value: object) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def _qdate(value: dt.date) -> QDate:
    return QDate(value.year, value.month, value.day)


class AgreementEditDialog(QDialog):
    def __init__(self, agreement: Agreement, parent: QWidget | None = None):
        super().__init__(parent)
        self.agreement = agreement
        self.setWindowTitle("Saisie d'un agrément")
        root = QVBoxLayout(self)
        box = QGroupBox("Agrément", self); form = QFormLayout(box)
        self.number_edit = QLineEdit(agreement.number, box)
        self.start_edit = QDateEdit(box); self.start_edit.setCalendarPopup(True); self.start_edit.setDisplayFormat("dd/MM/yyyy"); self.start_edit.setDate(_qdate(agreement.start_date))
        self.end_edit = QDateEdit(box); self.end_edit.setCalendarPopup(True); self.end_edit.setDisplayFormat("dd/MM/yyyy"); self.end_edit.setDate(_qdate(agreement.end_date))
        form.addRow("Numéro :", self.number_edit); form.addRow("Du :", self.start_edit); form.addRow("Au :", self.end_edit)
        root.addWidget(box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Valider"); buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _accept(self) -> None:
        number = self.number_edit.text().strip()
        if not number:
            QMessageBox.warning(self, "Erreur de saisie", "Vous devez obligatoirement donner un numéro d'agrément."); return
        if self.end_edit.date() < self.start_edit.date():
            QMessageBox.warning(self, "Erreur de saisie", "La date de fin ne peut pas précéder la date de début."); return
        self.agreement = replace(
            self.agreement,
            number=number,
            start_date=self.start_edit.date().toPython(),
            end_date=self.end_edit.date().toPython(),
        )
        self.accept()


class ActivityAgreementsPage(QWidget):
    def __init__(
        self,
        editor_repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.activity_id = activity_id
        self.repository = ActivityAgreementsRepository(editor_repository)
        self.initial_rows = self.repository.list_agreements(activity_id)
        self.state = self.repository.load(activity_id)
        self.multiple = list(self.state.multiple)

        root = QVBoxLayout(self); root.setContentsMargins(12, 12, 12, 12)
        box = QGroupBox("Agréments de l'activité", self); layout = QVBoxLayout(box)
        self.none_radio = QRadioButton("Aucun agrément", box)
        self.unique_radio = QRadioButton("Agrément unique", box)
        self.multiple_radio = QRadioButton("Agréments multiples", box)
        group = QButtonGroup(box); group.addButton(self.none_radio); group.addButton(self.unique_radio); group.addButton(self.multiple_radio)
        layout.addWidget(self.none_radio)
        unique_row = QHBoxLayout(); unique_row.addWidget(self.unique_radio); unique_row.addWidget(QLabel("Numéro :", box)); self.unique_edit = QLineEdit(box); unique_row.addWidget(self.unique_edit, 1); layout.addLayout(unique_row)
        layout.addWidget(self.multiple_radio)
        self.table = QTableWidget(box); self.table.setColumnCount(3); self.table.setHorizontalHeaderLabels(("Période de validité", "Agrément", "ID")); self.table.setColumnHidden(2, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout(); self.add_button = QPushButton("Ajouter", box); self.edit_button = QPushButton("Modifier", box); self.delete_button = QPushButton("Supprimer", box); actions.addWidget(self.add_button); actions.addWidget(self.edit_button); actions.addWidget(self.delete_button); actions.addStretch(1); layout.addLayout(actions)
        root.addWidget(box, 1)

        self.none_radio.toggled.connect(self._sync); self.unique_radio.toggled.connect(self._sync); self.multiple_radio.toggled.connect(self._sync)
        self.add_button.clicked.connect(self.add_agreement); self.edit_button.clicked.connect(self.edit_agreement); self.delete_button.clicked.connect(self.delete_agreement); self.table.doubleClicked.connect(self.edit_agreement)
        if self.state.mode == "unique": self.unique_radio.setChecked(True)
        elif self.state.mode == "multiple": self.multiple_radio.setChecked(True)
        else: self.none_radio.setChecked(True)
        self.unique_edit.setText(self.state.unique_number); self._refresh(); self._sync()

    def _sync(self, *_args) -> None:
        self.unique_edit.setEnabled(self.unique_radio.isChecked())
        enabled = self.multiple_radio.isChecked(); self.table.setEnabled(enabled); self.add_button.setEnabled(enabled); self.edit_button.setEnabled(enabled); self.delete_button.setEnabled(enabled)

    def _refresh(self) -> None:
        self.table.setRowCount(len(self.multiple))
        for row, agreement in enumerate(self.multiple):
            self.table.setItem(row, 0, QTableWidgetItem(agreement.period)); self.table.setItem(row, 1, QTableWidgetItem(agreement.number)); self.table.setItem(row, 2, QTableWidgetItem("" if agreement.agreement_id is None else str(agreement.agreement_id)))

    def _selected(self) -> int | None:
        row = self.table.currentRow(); return row if 0 <= row < len(self.multiple) else None

    def add_agreement(self) -> None:
        today = dt.date.today(); dialog = AgreementEditDialog(Agreement(None, self.activity_id, "", today, today), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.multiple.append(dialog.agreement); self._refresh(); self.table.selectRow(len(self.multiple) - 1)

    def edit_agreement(self, *_args) -> None:
        index = self._selected()
        if index is None: return
        dialog = AgreementEditDialog(self.multiple[index], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.multiple[index] = dialog.agreement; self._refresh(); self.table.selectRow(index)

    def delete_agreement(self) -> None:
        index = self._selected()
        if index is None: return
        if QMessageBox.question(self, "Suppression", "Supprimer cet agrément ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        del self.multiple[index]; self._refresh()

    def collect(self, *, confirm_delete: bool = True) -> AgreementState:
        if self.unique_radio.isChecked(): mode = "unique"
        elif self.multiple_radio.isChecked(): mode = "multiple"
        else: mode = "none"
        state = AgreementState(mode, self.unique_edit.text().strip(), tuple(self.multiple))
        self.repository.validate(state)
        if confirm_delete and mode == "none" and self.initial_rows:
            answer = QMessageBox.question(
                self,
                "Suppression d'agréments",
                "Vous avez sélectionné « Aucun agrément ». Supprimer les agréments précédemment saisis ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                raise ValueError("Suppression des agréments annulée.")
        return state

    def save(self, state: AgreementState | None = None) -> None:
        state = state or self.collect()
        self.repository.save(self.activity_id, state)
        self.state = state; self.initial_rows = self.repository.list_agreements(self.activity_id)


class ActivityEditorDialog(RequirementsActivityEditorDialog):
    """Fiche Activité avec Agréments, Renseignements et Calendrier réels."""

    def __init__(
        self,
        repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(1); self.tabs.removeTab(1)
        if old_page is not None: old_page.deleteLater()
        self.agreements_page = ActivityAgreementsPage(repository, activity_id, self)
        self.tabs.insertTab(1, self.agreements_page, "Agréments")

    def _validate_composed_editor(self) -> bool:
        group_page = getattr(self, "group_page", None)
        if group_page is not None and group_page.group_count() == 0:
            self.tabs.setCurrentWidget(group_page)
            QMessageBox.warning(
                self,
                "Erreur de saisie",
                "Vous devez créer au moins un groupe. Si nécessaire, créez simplement « Groupe unique ».",
            )
            return False

        pricing_page = getattr(self, "pricing_page", None)
        if pricing_page is not None and not pricing_page.has_categories():
            answer = QMessageBox.question(
                self,
                "Aucune catégorie de tarif",
                "Vous n'avez saisi aucune catégorie de tarif. Aucun individu ne pourra donc être inscrit à cette activité. Continuer quand même ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.tabs.setCurrentWidget(pricing_page)
                return False

        return True

    def _save(self) -> None:
        if not self._validate_composed_editor():
            return
        try:
            details = self._collect()
            requirements = self.requirements_page.collect()
            agreements = self.agreements_page.collect(confirm_delete=True)
            with activity_transaction(self.repository) as shared_repository:
                NativeActivityEditorRepository.save(
                    shared_repository,
                    details,
                    self._checked_group_ids(),
                )
                ActivityRequirementsRepository(shared_repository).save(
                    self.activity_id,
                    requirements,
                )
                ActivityAgreementsRepository(shared_repository).save(
                    self.activity_id,
                    agreements,
                )
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))
            return
        self.details = details
        self.requirements_page.state = requirements
        self.agreements_page.state = agreements
        self.accept()