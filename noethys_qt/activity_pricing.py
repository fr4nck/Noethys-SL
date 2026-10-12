"""Page Qt « Tarification » de la fiche Activité.

L'interface conserve l'organisation historique : catégories, prestations et
leurs tarifs, puis Généralités / Conditions / Type / Calcul. Les opérations de
cette page sont enregistrées immédiatement, comme dans Noethys historique.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import Iterable, Sequence

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .activity_editor import NativeActivityEditorRepository
from .activity_pricing_core import (
    ActivityPricingRepository,
    FIELD_LABELS,
    METHOD_BY_CODE,
    METHOD_FIELDS,
    METHODS,
    NUMERIC_FIELDS,
    PricingCategory,
    STATE_CHOICES,
    TIME_FIELDS,
    TARIFF_TYPES,
    TariffDetails,
    TariffLine,
    UnitCombination,
    as_date,
    method_label,
    parse_date_text,
    parse_number,
    parse_time_text,
)
from .activity_units import ActivityEditorDialog as UnitsActivityEditorDialog


DAY_LABELS = ("L", "M", "M", "J", "V", "S", "D")
DAY_NAMES = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")


def _qdate(value: dt.date) -> QDate:
    return QDate(value.year, value.month, value.day)


class CheckList(QListWidget):
    def __init__(self, choices: Sequence[tuple[int, str]], selected: Iterable[int] = (), parent: QWidget | None = None):
        super().__init__(parent)
        selected = set(int(value) for value in selected)
        for value, label in choices:
            item = QListWidgetItem(label, self)
            item.setData(Qt.ItemDataRole.UserRole, int(value))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if int(value) in selected else Qt.CheckState.Unchecked)

    def checked_ids(self) -> tuple[int, ...]:
        return tuple(
            int(self.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.count())
            if self.item(index).checkState() == Qt.CheckState.Checked
        )

    def set_checked(self, values: Iterable[int]) -> None:
        wanted = set(int(value) for value in values)
        for index in range(self.count()):
            item = self.item(index)
            item.setCheckState(Qt.CheckState.Checked if int(item.data(Qt.ItemDataRole.UserRole)) in wanted else Qt.CheckState.Unchecked)


class CategoryDialog(QDialog):
    def __init__(self, activity_id: int, category: PricingCategory | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.activity_id = activity_id
        self.category = category
        self.setWindowTitle("Modifier une catégorie de tarif" if category else "Ajouter une catégorie de tarif")
        self.setModal(True)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(self)
        form.addRow("Nom :", self.name_edit)
        root.addLayout(form)

        city_box = QGroupBox("Attribution automatique par ville", self)
        city_layout = QVBoxLayout(city_box)
        self.city_enabled = QCheckBox("Attribuer cette catégorie selon la ville de résidence", city_box)
        self.city_list = QListWidget(city_box)
        city_layout.addWidget(self.city_enabled)
        city_layout.addWidget(self.city_list, 1)
        row = QHBoxLayout()
        self.add_city_button = QPushButton("Ajouter une ville", city_box)
        self.remove_city_button = QPushButton("Retirer", city_box)
        row.addWidget(self.add_city_button); row.addWidget(self.remove_city_button); row.addStretch(1)
        city_layout.addLayout(row)
        root.addWidget(city_box, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer")
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.city_enabled.toggled.connect(self._sync_cities)
        self.add_city_button.clicked.connect(self._add_city)
        self.remove_city_button.clicked.connect(self._remove_city)
        if category:
            self.name_edit.setText(category.name)
            for cp, name in category.cities:
                self._append_city(cp, name)
            self.city_enabled.setChecked(bool(category.cities))
        self._sync_cities()
        self.resize(520, 420)

    def _append_city(self, cp: str, name: str) -> None:
        item = QListWidgetItem(f"{name} ({cp})" if cp else name, self.city_list)
        item.setData(Qt.ItemDataRole.UserRole, (cp, name))

    def _add_city(self) -> None:
        city, ok = QInputDialog.getText(self, "Ville", "Nom de la ville :")
        if not ok or not city.strip():
            return
        cp, ok = QInputDialog.getText(self, "Code postal", "Code postal :")
        if ok:
            self._append_city(cp.strip(), city.strip())

    def _remove_city(self) -> None:
        if self.city_list.currentRow() >= 0:
            self.city_list.takeItem(self.city_list.currentRow())

    def _sync_cities(self, *_args) -> None:
        enabled = self.city_enabled.isChecked()
        self.city_list.setEnabled(enabled); self.add_city_button.setEnabled(enabled); self.remove_city_button.setEnabled(enabled)

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Erreur de saisie", "Vous devez obligatoirement saisir un nom pour cette catégorie.")
            return
        if self.city_enabled.isChecked() and self.city_list.count() == 0:
            QMessageBox.warning(self, "Erreur de saisie", "Vous avez activé l'attribution par ville sans saisir aucune ville.")
            return
        self.accept()

    def value(self) -> PricingCategory:
        cities = tuple(self.city_list.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.city_list.count())) if self.city_enabled.isChecked() else ()
        return PricingCategory(self.category.category_id if self.category else 0, self.activity_id, self.name_edit.text().strip(), cities)


class CalculationTable(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.method_code = ""
        self.fields: tuple[str, ...] = ()
        self.line_ids: list[int | None] = []
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(self)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.add_button = QPushButton("Ajouter une ligne", self)
        self.remove_button = QPushButton("Supprimer la ligne", self)
        actions.addWidget(self.add_button); actions.addWidget(self.remove_button); actions.addStretch(1)
        root.addLayout(actions)
        self.add_button.clicked.connect(self.add_row); self.remove_button.clicked.connect(self.remove_row)

    def set_method(self, code: str, lines: Sequence[TariffLine] = ()) -> None:
        self.method_code = code
        self.fields = tuple(METHOD_FIELDS.get(code, ()))
        self.table.clear(); self.table.setColumnCount(len(self.fields)); self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels([FIELD_LABELS.get(field, field) for field in self.fields])
        self.line_ids = []
        for line in lines:
            self.add_row(line)
        maximum = METHOD_BY_CODE.get(code, {}).get("max_rows")
        if maximum == 1 and not lines:
            self.add_row()
        self._sync_actions()

    def add_row(self, line: TariffLine | None = None) -> None:
        maximum = METHOD_BY_CODE.get(self.method_code, {}).get("max_rows")
        if maximum is not None and self.table.rowCount() >= maximum:
            return
        row = self.table.rowCount(); self.table.insertRow(row); self.line_ids.append(line.line_id if line else None)
        values = line.values if line else {}
        for column, field in enumerate(self.fields):
            value = values.get(field)
            if field == "date" and value not in (None, ""):
                parsed = as_date(value); text = parsed.strftime("%d/%m/%Y") if parsed else str(value)
            else:
                text = "" if value is None else str(value)
            self.table.setItem(row, column, QTableWidgetItem(text))
        self._sync_actions()

    def remove_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row); self.line_ids.pop(row)
        self._sync_actions()

    def _sync_actions(self) -> None:
        maximum = METHOD_BY_CODE.get(self.method_code, {}).get("max_rows")
        self.add_button.setEnabled(maximum != 0 and (maximum is None or self.table.rowCount() < maximum))
        self.remove_button.setEnabled(maximum != 0 and self.table.rowCount() > 0)

    def lines(self) -> list[TariffLine]:
        result = []
        for row in range(self.table.rowCount()):
            values: dict[str, object] = {}
            for column, field in enumerate(self.fields):
                item = self.table.item(row, column); text = item.text().strip() if item else ""
                if field in NUMERIC_FIELDS:
                    value = parse_number(text, field)
                elif field == "date":
                    value = parse_date_text(text, field)
                elif field in TIME_FIELDS:
                    value = parse_time_text(text, field)
                else:
                    value = text or None
                values[field] = value
            result.append(TariffLine(self.line_ids[row], values))
        return result


class CombinationDialog(QDialog):
    def __init__(self, repository: ActivityPricingRepository, activity_id: int, type_code: str, existing: Sequence[UnitCombination], combination: UnitCombination | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository; self.activity_id = activity_id; self.type_code = type_code; self.combination = combination
        self.existing = [item for item in existing if combination is None or item.combination_id != combination.combination_id]
        self.setWindowTitle("Combinaison d'unités")
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Unités à combiner :", self))
        self.units = CheckList(repository.list_units(activity_id), combination.unit_ids if combination else (), self)
        root.addWidget(self.units, 1)
        self.date_edit = QDateEdit(self); self.date_edit.setCalendarPopup(True); self.date_edit.setDisplayFormat("dd/MM/yyyy"); self.date_edit.setDate(_qdate(combination.date if combination and combination.date else dt.date.today()))
        if type_code == "FORFAIT":
            form = QFormLayout(); form.addRow("Date :", self.date_edit); root.addLayout(form)
        self.quantity_check = QCheckBox("Limiter le nombre de consommations", self)
        self.quantity_spin = QSpinBox(self); self.quantity_spin.setRange(1, 99999)
        if combination and combination.quantity_max:
            self.quantity_check.setChecked(True); self.quantity_spin.setValue(combination.quantity_max)
        if type_code == "CREDIT":
            row = QHBoxLayout(); row.addWidget(self.quantity_check); row.addWidget(self.quantity_spin); row.addStretch(1); root.addLayout(row)
        self.quantity_check.toggled.connect(self.quantity_spin.setEnabled); self.quantity_spin.setEnabled(self.quantity_check.isChecked())
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.resize(470, 460)

    def _accept(self) -> None:
        date = self.date_edit.date().toPython() if self.type_code == "FORFAIT" else None
        try:
            self.repository.validate_combination(self.activity_id, self.units.checked_ids(), self.existing, date, self.type_code)
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc)); return
        self.accept()

    def value(self) -> UnitCombination:
        return UnitCombination(
            self.combination.combination_id if self.combination else None,
            tuple(sorted(self.units.checked_ids())),
            self.date_edit.date().toPython() if self.type_code == "FORFAIT" else None,
            self.quantity_spin.value() if self.type_code == "CREDIT" and self.quantity_check.isChecked() else None,
        )


class TariffEditDialog(QDialog):
    def __init__(self, repository: ActivityPricingRepository, activity_id: int, name_id: int, tariff_id: int | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository; self.activity_id = activity_id; self.name_id = name_id; self.tariff_id = tariff_id; self._loading = True
        self.details = repository.load_tariff(activity_id, tariff_id) if tariff_id is not None else TariffDetails(
            None, activity_id, name_id, dt.date.today(), None, "JOURN", "montant_unique", (), None, None, None,
            tuple(range(7)), tuple(range(7)), "", "", 0.0, "", "", None, "nom_tarif",
            etats="reservation;present;absenti", forfait_beneficiaire="individu",
        )
        self.initial_lines = repository.list_lines(tariff_id) if tariff_id is not None else []
        self.combinations = {code: repository.list_combinations(tariff_id, code) if tariff_id is not None else [] for code in ("JOURN", "FORFAIT", "CREDIT")}
        name = next((item.name for item in repository.list_names(activity_id) if item.name_id == name_id), "")
        self.setWindowTitle(f"Paramétrage du tarif — {name}"); self.setModal(True)
        root = QVBoxLayout(self)
        title = QLabel(name, self); title.setObjectName("pricingEditorTitle"); root.addWidget(title)
        self.tabs = QTabWidget(self); root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._general_page(), "Généralités")
        self.tabs.addTab(self._conditions_page(), "Conditions d'application")
        self.tabs.addTab(self._type_page(), "Type de tarif")
        self.tabs.addTab(self._calculation_page(), "Calcul du tarif")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer"); buttons.accepted.connect(self._save); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._load(); self.resize(940, 730)

    def _general_page(self) -> QWidget:
        page = QWidget(self); layout = QFormLayout(page)
        validity = QWidget(page); row = QHBoxLayout(validity); row.setContentsMargins(0, 0, 0, 0)
        self.start_date = QDateEdit(validity); self.start_date.setCalendarPopup(True); self.start_date.setDisplayFormat("dd/MM/yyyy")
        self.end_check = QCheckBox("Jusqu'au", validity); self.end_date = QDateEdit(validity); self.end_date.setCalendarPopup(True); self.end_date.setDisplayFormat("dd/MM/yyyy")
        row.addWidget(self.start_date); row.addWidget(self.end_check); row.addWidget(self.end_date); row.addStretch(1); layout.addRow("À partir du :", validity)
        self.description = QLineEdit(page); self.observations = QPlainTextEdit(page); self.observations.setMaximumHeight(90)
        layout.addRow("Description :", self.description); layout.addRow("Observations :", self.observations)
        choices = [(item.category_id, item.name) for item in self.repository.list_categories(self.activity_id)]
        self.categories = CheckList(choices, parent=page); self.categories.setMaximumHeight(110); layout.addRow("Catégories :", self.categories)
        label_widget = QWidget(page); label_row = QHBoxLayout(label_widget); label_row.setContentsMargins(0, 0, 0, 0)
        self.label_combo = QComboBox(label_widget); self.label_combo.addItem("Nom du tarif", "nom_tarif"); self.label_combo.addItem("Description du tarif", "description_tarif"); self.label_combo.addItem("Label personnalisé", "autre:")
        self.custom_label = QLineEdit(label_widget); label_row.addWidget(self.label_combo); label_row.addWidget(self.custom_label, 1); layout.addRow("Label prestation :", label_widget)
        codes = QWidget(page); codes_row = QHBoxLayout(codes); codes_row.setContentsMargins(0, 0, 0, 0)
        self.accounting_code = QLineEdit(codes); self.local_product_code = QLineEdit(codes)
        codes_row.addWidget(QLabel("Compta", codes)); codes_row.addWidget(self.accounting_code); codes_row.addWidget(QLabel("Produit local", codes)); codes_row.addWidget(self.local_product_code); layout.addRow("Codes :", codes)
        self.vat = QDoubleSpinBox(page); self.vat.setRange(0, 100); self.vat.setDecimals(2); self.vat.setSuffix(" %"); layout.addRow("TVA :", self.vat)
        self.end_check.toggled.connect(self.end_date.setEnabled); self.label_combo.currentIndexChanged.connect(self._sync_custom_label)
        return page

    def _conditions_page(self) -> QWidget:
        page = QWidget(self); layout = QGridLayout(page)
        self.group_filter = QCheckBox("Activer ce filtre", page); self.groups = CheckList(self.repository.list_groups(self.activity_id), parent=page)
        self.cotisation_filter = QCheckBox("Activer ce filtre", page); self.cotisations = CheckList(self.repository.list_cotisations(), parent=page)
        self.caisse_filter = QCheckBox("Activer ce filtre", page); self.caisses = CheckList(self.repository.list_caisses(), parent=page)
        for column, (title, check, widget) in enumerate((("Groupes", self.group_filter, self.groups), ("Cotisations", self.cotisation_filter, self.cotisations), ("Caisses", self.caisse_filter, self.caisses))):
            box = QGroupBox(title, page); box_layout = QVBoxLayout(box); box_layout.addWidget(check); box_layout.addWidget(widget, 1); layout.addWidget(box, 0, column); check.toggled.connect(widget.setEnabled)
        days = QGroupBox("Jours d'application", page); days_layout = QGridLayout(days); days_layout.addWidget(QLabel("Scolaire", days), 0, 0); days_layout.addWidget(QLabel("Vacances", days), 1, 0)
        self.school_checks = []; self.vacation_checks = []
        for index, label in enumerate(DAY_LABELS):
            school = QCheckBox(label, days); vacation = QCheckBox(label, days); school.setToolTip(DAY_NAMES[index]); vacation.setToolTip(DAY_NAMES[index]); self.school_checks.append(school); self.vacation_checks.append(vacation); days_layout.addWidget(school, 0, index + 1); days_layout.addWidget(vacation, 1, index + 1)
        layout.addWidget(days, 1, 0, 1, 3)
        note = QLabel("Les filtres Étiquettes et Questionnaire existants sont conservés à l'identique tant que leur éditeur dédié n'est pas migré.", page); note.setWordWrap(True); layout.addWidget(note, 2, 0, 1, 3); layout.setRowStretch(0, 1)
        return page

    def _type_page(self) -> QWidget:
        page = QWidget(self); layout = QVBoxLayout(page); form = QFormLayout(); self.type_combo = QComboBox(page)
        for code, label in TARIFF_TYPES: self.type_combo.addItem(label, code)
        form.addRow("Type de tarif :", self.type_combo); layout.addLayout(form)
        self.type_stack = QTabWidget(page); self.type_stack.tabBar().hide(); layout.addWidget(self.type_stack)

        journ = QWidget(page); journ_layout = QVBoxLayout(journ); journ_layout.addWidget(QLabel("États de consommation associés :", journ)); self.state_list = QListWidget(journ)
        for code, label in STATE_CHOICES:
            item = QListWidgetItem(label, self.state_list); item.setData(Qt.ItemDataRole.UserRole, code); item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Unchecked)
        journ_layout.addWidget(self.state_list); self.type_stack.addTab(journ, "JOURN")

        forfait = QWidget(page); forfait_form = QFormLayout(forfait); self.forfait_mode = QComboBox(forfait); self.forfait_mode.addItem("Sans consommations", "none"); self.forfait_mode.addItem("Selon le calendrier des ouvertures", "calendar"); self.forfait_mode.addItem("Combinaisons personnalisées", "custom"); forfait_form.addRow("Consommations :", self.forfait_mode)
        self.forfait_manual = QCheckBox("Saisie manuelle autorisée", forfait); self.forfait_auto = QCheckBox("Création automatique à l'inscription", forfait); self.forfait_delete_auto = QCheckBox("Suppression uniquement à la désinscription", forfait)
        forfait_form.addRow(self.forfait_manual); forfait_form.addRow(self.forfait_auto); forfait_form.addRow(self.forfait_delete_auto); self.type_stack.addTab(forfait, "FORFAIT")

        credit = QWidget(page); credit_form = QFormLayout(credit); self.credit_duration = QCheckBox("Durée limitée", credit); duration = QWidget(credit); duration_row = QHBoxLayout(duration); duration_row.setContentsMargins(0, 0, 0, 0)
        self.credit_days = QSpinBox(duration); self.credit_months = QSpinBox(duration); self.credit_years = QSpinBox(duration)
        for spin in (self.credit_days, self.credit_months, self.credit_years): spin.setRange(0, 500)
        for label, spin in (("Jours", self.credit_days), ("Mois", self.credit_months), ("Années", self.credit_years)): duration_row.addWidget(QLabel(label, duration)); duration_row.addWidget(spin)
        duration_row.addStretch(1); credit_form.addRow(self.credit_duration, duration)
        self.credit_ceiling = QCheckBox("Bloquer quand la quantité maximale est atteinte", credit); credit_form.addRow(self.credit_ceiling)
        self.credit_beneficiary = QComboBox(credit); self.credit_beneficiary.addItem("Forfait individuel", "individu"); self.credit_beneficiary.addItem("Forfait familial", "famille"); credit_form.addRow("Bénéficiaire :", self.credit_beneficiary); self.type_stack.addTab(credit, "CREDIT")
        bareme = QWidget(page); bareme_layout = QVBoxLayout(bareme); bareme_layout.addWidget(QLabel("Le barème est défini par la méthode de calcul.", bareme)); bareme_layout.addStretch(1); self.type_stack.addTab(bareme, "BAREME")

        self.combinations_box = QGroupBox("Combinaisons d'unités", page); combinations_layout = QVBoxLayout(self.combinations_box); self.combination_list = QListWidget(self.combinations_box); combinations_layout.addWidget(self.combination_list, 1)
        combi_row = QHBoxLayout(); self.add_combination_button = QPushButton("Ajouter", self.combinations_box); self.edit_combination_button = QPushButton("Modifier", self.combinations_box); self.remove_combination_button = QPushButton("Supprimer", self.combinations_box)
        for button in (self.add_combination_button, self.edit_combination_button, self.remove_combination_button): combi_row.addWidget(button)
        combi_row.addStretch(1); combinations_layout.addLayout(combi_row); layout.addWidget(self.combinations_box, 1)

        self.billing_box = QGroupBox("Date de facturation", page); billing_row = QHBoxLayout(self.billing_box); self.billing_combo = QComboBox(self.billing_box); self.billing_date = QDateEdit(self.billing_box); self.billing_date.setCalendarPopup(True); self.billing_date.setDisplayFormat("dd/MM/yyyy"); self.billing_date.setDate(_qdate(dt.date.today())); billing_row.addWidget(self.billing_combo); billing_row.addWidget(self.billing_date); billing_row.addStretch(1); layout.addWidget(self.billing_box)
        self.type_combo.currentIndexChanged.connect(self._sync_type); self.forfait_mode.currentIndexChanged.connect(self._sync_type); self.billing_combo.currentIndexChanged.connect(self._sync_billing); self.credit_duration.toggled.connect(self._sync_credit_duration); self.forfait_manual.toggled.connect(self._sync_forfait_options); self.forfait_auto.toggled.connect(self._sync_forfait_options)
        self.add_combination_button.clicked.connect(self._add_combination); self.edit_combination_button.clicked.connect(self._edit_combination); self.remove_combination_button.clicked.connect(self._remove_combination)
        return page

    def _calculation_page(self) -> QWidget:
        page = QWidget(self); layout = QVBoxLayout(page); row = QHBoxLayout(); row.addWidget(QLabel("Méthode de calcul :", page)); self.method_combo = QComboBox(page); row.addWidget(self.method_combo, 1); row.addWidget(QLabel("Type de QF :", page)); self.quotient_combo = QComboBox(page); self.quotient_combo.addItem("Indifférent", None)
        for value, label in self.repository.list_quotient_types(): self.quotient_combo.addItem(label, value)
        row.addWidget(self.quotient_combo); layout.addLayout(row); self.calculation_table = CalculationTable(page); layout.addWidget(self.calculation_table, 1); self.method_combo.currentIndexChanged.connect(self._method_changed); return page

    def _load(self) -> None:
        d = self.details; self.start_date.setDate(_qdate(d.date_start)); self.end_check.setChecked(d.date_end is not None); self.end_date.setDate(_qdate(d.date_end or d.date_start)); self.end_date.setEnabled(self.end_check.isChecked()); self.description.setText(d.description); self.observations.setPlainText(d.observations); self.categories.set_checked(d.category_ids)
        if d.prestation_label.startswith("autre:"):
            self.label_combo.setCurrentIndex(self.label_combo.findData("autre:")); self.custom_label.setText(d.prestation_label[6:])
        else:
            index = self.label_combo.findData(d.prestation_label); self.label_combo.setCurrentIndex(index if index >= 0 else 0)
        self._sync_custom_label(); self.accounting_code.setText(d.accounting_code); self.local_product_code.setText(d.local_product_code); self.vat.setValue(d.vat)
        for check, widget, values in ((self.group_filter, self.groups, d.group_ids), (self.cotisation_filter, self.cotisations, d.cotisation_ids), (self.caisse_filter, self.caisses, d.caisse_ids)):
            check.setChecked(values is not None); widget.set_checked(values or ()); widget.setEnabled(check.isChecked())
        for index, check in enumerate(self.school_checks): check.setChecked(index in d.school_days)
        for index, check in enumerate(self.vacation_checks): check.setChecked(index in d.vacation_days)
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(d.type_code)))
        selected_states = set((d.etats or "").split(";"))
        for index in range(self.state_list.count()):
            item = self.state_list.item(index); item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in selected_states else Qt.CheckState.Unchecked)
        self.forfait_manual.setChecked(d.forfait_saisie_manuelle); self.forfait_auto.setChecked(d.forfait_saisie_auto); self.forfait_delete_auto.setChecked(d.forfait_suppression_auto); self.forfait_mode.setCurrentIndex(self.forfait_mode.findData("calendar") if d.options and "calendrier" in d.options else 0)
        if d.forfait_duree:
            parts = {part[0]: int(part[1:]) for part in d.forfait_duree.split("-") if len(part) > 1 and part[0] in "jma" and part[1:].isdigit()}; self.credit_duration.setChecked(True); self.credit_days.setValue(parts.get("j", 0)); self.credit_months.setValue(parts.get("m", 0)); self.credit_years.setValue(parts.get("a", 0))
        self.credit_ceiling.setChecked(bool(d.options and "blocage_plafond" in d.options)); beneficiary = self.credit_beneficiary.findData(d.forfait_beneficiaire or "individu"); self.credit_beneficiary.setCurrentIndex(beneficiary if beneficiary >= 0 else 0)
        self._populate_billing(d.type_code, d.date_facturation)
        if d.date_facturation and d.date_facturation.startswith("date:"):
            custom = as_date(d.date_facturation[5:]); self.billing_combo.setCurrentIndex(self.billing_combo.findData("date:"));
            if custom: self.billing_date.setDate(_qdate(custom))
        elif d.date_facturation:
            index = self.billing_combo.findData(d.date_facturation); self.billing_combo.setCurrentIndex(index if index >= 0 else 0)
        self._populate_methods(d.type_code, d.method_code); method_index = self.method_combo.findData(d.method_code); self.method_combo.setCurrentIndex(method_index if method_index >= 0 else 0); self.calculation_table.set_method(d.method_code, self.initial_lines); quotient = self.quotient_combo.findData(d.quotient_type_id); self.quotient_combo.setCurrentIndex(quotient if quotient >= 0 else 0); self.quotient_combo.setEnabled("qf" in d.method_code)
        self._loading = False; self._sync_credit_duration(); self._sync_forfait_options(); self._sync_type(); self._refresh_combinations()

    def _sync_custom_label(self, *_args) -> None:
        self.custom_label.setEnabled(self.label_combo.currentData() == "autre:")

    def _populate_methods(self, type_code: str, preferred: str | None = None) -> None:
        self.method_combo.blockSignals(True); self.method_combo.clear()
        for code, label, types, _required, _maximum in METHODS:
            if type_code in types: self.method_combo.addItem(label, code)
        index = self.method_combo.findData(preferred) if preferred else -1; self.method_combo.setCurrentIndex(index if index >= 0 else 0); self.method_combo.blockSignals(False)

    def _populate_billing(self, type_code: str, preferred: str | None = None) -> None:
        choices = {
            "FORFAIT": (("Date de début du forfait", "date_debut_forfait"), ("Date de saisie", "date_saisie"), ("Date de début de l'activité", "date_debut_activite"), ("Date personnalisée", "date:")),
            "CREDIT": (("Date de début du forfait", "date_debut_forfait"), ("Date de fin du forfait", "date_fin_forfait"), ("Date de saisie", "date_saisie"), ("Date personnalisée", "date:")),
        }.get(type_code, ())
        self.billing_combo.blockSignals(True); self.billing_combo.clear()
        for label, code in choices: self.billing_combo.addItem(label, code)
        index = self.billing_combo.findData(preferred) if preferred else -1; self.billing_combo.setCurrentIndex(index if index >= 0 else (0 if choices else -1)); self.billing_combo.blockSignals(False)

    def _sync_type(self, *_args) -> None:
        code = self.type_combo.currentData() or "JOURN"; self.type_stack.setCurrentIndex({"JOURN": 0, "FORFAIT": 1, "CREDIT": 2, "BAREME": 3}.get(code, 0)); old_billing = self.billing_combo.currentData(); self._populate_billing(code, old_billing); self.billing_box.setVisible(code in {"FORFAIT", "CREDIT"})
        self.combinations_box.setVisible(code in {"JOURN", "FORFAIT", "CREDIT"}); self.combinations_box.setEnabled(code != "FORFAIT" or self.forfait_mode.currentData() == "custom")
        if hasattr(self, "method_combo"):
            current = self.method_combo.currentData(); self._populate_methods(code, current)
            if not self._loading and self.calculation_table.method_code != self.method_combo.currentData(): self._method_changed()
        self._sync_billing()
        if not self._loading: self._refresh_combinations()

    def _method_changed(self, *_args) -> None:
        code = self.method_combo.currentData() or ""
        if self.calculation_table.method_code == code:
            self.quotient_combo.setEnabled("qf" in code); return
        old = self.calculation_table.method_code; old_compatible = self.method_combo.findData(old) >= 0
        if self.calculation_table.table.rowCount() and self.isVisible() and old_compatible:
            answer = QMessageBox.question(self, "Changer de méthode", "Changer de méthode réinitialisera les lignes de calcul affichées. Continuer ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                self.method_combo.blockSignals(True); self.method_combo.setCurrentIndex(self.method_combo.findData(old)); self.method_combo.blockSignals(False); return
        self.calculation_table.set_method(code); self.quotient_combo.setEnabled("qf" in code)

    def _sync_billing(self, *_args) -> None:
        self.billing_date.setVisible(self.billing_combo.currentData() == "date:")

    def _sync_credit_duration(self, *_args) -> None:
        enabled = self.credit_duration.isChecked()
        for spin in (self.credit_days, self.credit_months, self.credit_years): spin.setEnabled(enabled)

    def _sync_forfait_options(self, *_args) -> None:
        if self.sender() is self.forfait_manual and self.forfait_manual.isChecked(): self.forfait_auto.setChecked(False); self.forfait_delete_auto.setChecked(False)
        if self.sender() is self.forfait_auto and self.forfait_auto.isChecked(): self.forfait_manual.setChecked(False)
        self.forfait_delete_auto.setEnabled(self.forfait_auto.isChecked())
        if not self.forfait_auto.isChecked(): self.forfait_delete_auto.setChecked(False)

    def _current_combinations(self) -> list[UnitCombination]:
        return self.combinations.setdefault(self.type_combo.currentData() or "JOURN", [])

    def _refresh_combinations(self) -> None:
        self.combination_list.clear(); names = dict(self.repository.list_units(self.activity_id))
        for combination in self._current_combinations():
            label = " + ".join(names.get(unit_id, f"#{unit_id}") for unit_id in combination.unit_ids)
            if combination.date: label = f"{combination.date:%d/%m/%Y} — {label}"
            if combination.quantity_max: label += f" ({combination.quantity_max} max)"
            item = QListWidgetItem(label, self.combination_list); item.setData(Qt.ItemDataRole.UserRole, combination)

    def _add_combination(self) -> None:
        code = self.type_combo.currentData() or "JOURN"; current = self._current_combinations(); dialog = CombinationDialog(self.repository, self.activity_id, code, current, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted: current.append(dialog.value()); self._refresh_combinations()

    def _edit_combination(self) -> None:
        row = self.combination_list.currentRow(); current = self._current_combinations()
        if row < 0: return
        dialog = CombinationDialog(self.repository, self.activity_id, self.type_combo.currentData() or "JOURN", current, current[row], self)
        if dialog.exec() == QDialog.DialogCode.Accepted: current[row] = dialog.value(); self._refresh_combinations()

    def _remove_combination(self) -> None:
        row = self.combination_list.currentRow()
        if row >= 0: self._current_combinations().pop(row); self._refresh_combinations()

    def _billing_code(self) -> str | None:
        if self.type_combo.currentData() not in {"FORFAIT", "CREDIT"}: return None
        code = self.billing_combo.currentData() or "date_debut_forfait"
        return f"date:{self.billing_date.date().toPython().isoformat()}" if code == "date:" else str(code)

    def _collect(self) -> tuple[TariffDetails, list[TariffLine]]:
        type_code = self.type_combo.currentData() or "JOURN"; prestation = self.label_combo.currentData() or "nom_tarif"
        if prestation == "autre:": prestation = f"autre:{self.custom_label.text().strip()}"
        options = None; manual = auto = delete_auto = False; duration = None; beneficiary = self.details.forfait_beneficiaire
        if type_code == "FORFAIT":
            options = "calendrier" if self.forfait_mode.currentData() == "calendar" else None; manual = self.forfait_manual.isChecked(); auto = self.forfait_auto.isChecked(); delete_auto = self.forfait_delete_auto.isChecked()
        elif type_code == "CREDIT":
            options = "blocage_plafond" if self.credit_ceiling.isChecked() else None; beneficiary = self.credit_beneficiary.currentData() or "individu"
            if self.credit_duration.isChecked(): duration = f"j{self.credit_days.value()}-m{self.credit_months.value()}-a{self.credit_years.value()}"
        states = ";".join(str(self.state_list.item(index).data(Qt.ItemDataRole.UserRole)) for index in range(self.state_list.count()) if self.state_list.item(index).checkState() == Qt.CheckState.Checked) or None
        details = TariffDetails(
            self.tariff_id, self.activity_id, self.name_id, self.start_date.date().toPython(), self.end_date.date().toPython() if self.end_check.isChecked() else None,
            type_code, self.method_combo.currentData() or "", self.categories.checked_ids(), self.groups.checked_ids() if self.group_filter.isChecked() else None,
            self.cotisations.checked_ids() if self.cotisation_filter.isChecked() else None, self.caisses.checked_ids() if self.caisse_filter.isChecked() else None,
            tuple(index for index, check in enumerate(self.school_checks) if check.isChecked()), tuple(index for index, check in enumerate(self.vacation_checks) if check.isChecked()),
            self.description.text().strip(), self.observations.toPlainText().strip(), self.vat.value(), self.accounting_code.text().strip(), self.local_product_code.text().strip(), self.quotient_combo.currentData(), prestation,
            states, self._billing_code(), options, manual, auto, delete_auto, duration, beneficiary, self.details.etiquettes,
        )
        return details, self.calculation_table.lines()

    def _save(self) -> None:
        try:
            details, lines = self._collect(); current = self._current_combinations()
            if details.type_code == "FORFAIT" and self.forfait_mode.currentData() == "custom" and not current: raise ValueError("Vous avez choisi des consommations personnalisées sans saisir aucune combinaison.")
            if details.type_code == "JOURN" and not current:
                answer = QMessageBox.question(self, "Aucune combinaison", "Aucune combinaison conditionnelle n'a été indiquée. Confirmer ce tarif sans combinaison ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes: return
            tariff_id = self.repository.save_tariff(details, lines)
            if details.type_code in {"JOURN", "FORFAIT", "CREDIT"}:
                saved = () if details.type_code == "FORFAIT" and self.forfait_mode.currentData() != "custom" else current; self.repository.save_combinations(tariff_id, details.type_code, saved)
            for other in {"JOURN", "FORFAIT", "CREDIT"} - {details.type_code}: self.repository.save_combinations(tariff_id, other, ())
            self.tariff_id = tariff_id; self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))


class ActivityPricingPage(QWidget):
    def __init__(self, editor_repository: NativeActivityEditorRepository, activity_id: int, parent: QWidget | None = None):
        super().__init__(parent); self.activity_id = activity_id; self.repository = ActivityPricingRepository(editor_repository)
        root = QVBoxLayout(self); splitter = QSplitter(Qt.Orientation.Vertical, self); root.addWidget(splitter, 1)
        categories_box = QGroupBox("Catégories de tarifs", splitter); categories_layout = QVBoxLayout(categories_box); self.category_table = QTableWidget(categories_box); self.category_table.setColumnCount(2); self.category_table.setHorizontalHeaderLabels(("Nom", "Villes rattachées")); self.category_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.category_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.category_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.category_table.horizontalHeader().setStretchLastSection(True); categories_layout.addWidget(self.category_table, 1)
        cat_actions = QHBoxLayout(); self.add_category_button = QPushButton("Ajouter", categories_box); self.edit_category_button = QPushButton("Modifier", categories_box); self.delete_category_button = QPushButton("Supprimer", categories_box)
        for button in (self.add_category_button, self.edit_category_button, self.delete_category_button): cat_actions.addWidget(button)
        cat_actions.addStretch(1); categories_layout.addLayout(cat_actions)
        tariffs_box = QGroupBox("Prestations / Tarifs", splitter); tariffs_layout = QVBoxLayout(tariffs_box); self.tree = QTreeWidget(tariffs_box); self.tree.setColumnCount(4); self.tree.setHeaderLabels(("Prestations / Tarifs", "Description", "Catégories", "Méthode de calcul")); self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.tree.setAlternatingRowColors(True); tariffs_layout.addWidget(self.tree, 1)
        actions = QHBoxLayout(); self.add_name_button = QPushButton("Nouvelle prestation", tariffs_box); self.add_tariff_button = QPushButton("Ajouter un tarif", tariffs_box); self.edit_tariff_button = QPushButton("Modifier", tariffs_box); self.delete_tariff_button = QPushButton("Supprimer", tariffs_box); self.duplicate_tariff_button = QPushButton("Dupliquer", tariffs_box)
        for button in (self.add_name_button, self.add_tariff_button, self.edit_tariff_button, self.delete_tariff_button, self.duplicate_tariff_button): actions.addWidget(button)
        actions.addStretch(1); tariffs_layout.addLayout(actions)
        style = self.style(); self.add_category_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder)); self.add_tariff_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder)); self.delete_category_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon)); self.delete_tariff_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.add_category_button.clicked.connect(self.add_category); self.edit_category_button.clicked.connect(self.edit_category); self.delete_category_button.clicked.connect(self.delete_category); self.add_name_button.clicked.connect(self.add_name); self.add_tariff_button.clicked.connect(self.add_tariff); self.edit_tariff_button.clicked.connect(self.edit_selected); self.delete_tariff_button.clicked.connect(self.delete_selected); self.duplicate_tariff_button.clicked.connect(self.duplicate_selected); self.tree.itemDoubleClicked.connect(lambda _item, _column: self.edit_selected()); self.tree.itemSelectionChanged.connect(self._sync_actions); self.category_table.itemSelectionChanged.connect(self._sync_actions); self.refresh()

    def refresh(self) -> None:
        self.categories = self.repository.list_categories(self.activity_id); self.category_table.setRowCount(len(self.categories))
        for row, category in enumerate(self.categories): self.category_table.setItem(row, 0, QTableWidgetItem(category.name)); self.category_table.setItem(row, 1, QTableWidgetItem(category.cities_label))
        self.names = self.repository.list_names(self.activity_id); self.tariffs = self.repository.list_tariffs(self.activity_id); category_names = {item.category_id: item.name for item in self.categories}; self.tree.clear(); grouped: dict[int, list[TariffDetails]] = {}
        for tariff in self.tariffs: grouped.setdefault(tariff.name_id, []).append(tariff)
        for name in self.names:
            parent = QTreeWidgetItem((name.name, "", "", "")); parent.setData(0, Qt.ItemDataRole.UserRole, ("name", name.name_id)); self.tree.addTopLevelItem(parent)
            for tariff in grouped.get(name.name_id, []):
                period = f"À partir du {tariff.date_start:%d/%m/%Y}" if not tariff.date_end else f"Du {tariff.date_start:%d/%m/%Y} au {tariff.date_end:%d/%m/%Y}"; categories = "; ".join(category_names.get(value, f"#{value}") for value in tariff.category_ids); child = QTreeWidgetItem((period, tariff.description, categories, method_label(tariff.method_code))); child.setData(0, Qt.ItemDataRole.UserRole, ("tariff", tariff.tariff_id, tariff.name_id)); parent.addChild(child)
            parent.setExpanded(True)
        self.tree.resizeColumnToContents(0); self._sync_actions()

    def has_categories(self) -> bool:
        return bool(self.repository.list_categories(self.activity_id))

    def _selected_category(self) -> PricingCategory | None:
        row = self.category_table.currentRow(); return self.categories[row] if 0 <= row < len(self.categories) else None

    def _selected_data(self):
        item = self.tree.currentItem(); return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def add_category(self) -> None:
        dialog = CategoryDialog(self.activity_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try: self.repository.save_category(dialog.value()); self.refresh()
            except Exception as exc: QMessageBox.critical(self, "Enregistrement impossible", str(exc))

    def edit_category(self) -> None:
        category = self._selected_category()
        if not category: return
        dialog = CategoryDialog(self.activity_id, category, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try: self.repository.save_category(dialog.value()); self.refresh()
            except Exception as exc: QMessageBox.critical(self, "Enregistrement impossible", str(exc))

    def delete_category(self) -> None:
        category = self._selected_category()
        if not category: return
        if QMessageBox.question(self, "Suppression", f"Supprimer la catégorie « {category.name} » ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        try: self.repository.delete_category(self.activity_id, category.category_id); self.refresh()
        except ValueError as exc: QMessageBox.warning(self, "Suppression impossible", str(exc))
        except Exception as exc: QMessageBox.critical(self, "Suppression impossible", str(exc))

    def add_name(self) -> None:
        name, ok = QInputDialog.getText(self, "Nouvelle prestation", "Nom de la prestation :")
        if not ok: return
        try: self.repository.save_name(self.activity_id, name); self.refresh()
        except ValueError as exc: QMessageBox.warning(self, "Erreur de saisie", str(exc))

    def add_tariff(self) -> None:
        data = self._selected_data(); name_id = int(data[1] if data and data[0] == "name" else data[2]) if data else None
        if name_id is None: QMessageBox.information(self, "Ajouter un tarif", "Sélectionnez d'abord un nom de prestation."); return
        dialog = TariffEditDialog(self.repository, self.activity_id, name_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.refresh()

    def edit_selected(self) -> None:
        data = self._selected_data()
        if not data: return
        if data[0] == "name":
            name_id = int(data[1]); current = next((item.name for item in self.names if item.name_id == name_id), ""); name, ok = QInputDialog.getText(self, "Modifier la prestation", "Nom :", text=current)
            if ok:
                try: self.repository.save_name(self.activity_id, name, name_id); self.refresh()
                except ValueError as exc: QMessageBox.warning(self, "Erreur de saisie", str(exc))
            return
        dialog = TariffEditDialog(self.repository, self.activity_id, int(data[2]), int(data[1]), self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.refresh()

    def delete_selected(self) -> None:
        data = self._selected_data()
        if not data: return
        if QMessageBox.question(self, "Suppression", "Confirmer la suppression ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        try:
            self.repository.delete_name(self.activity_id, int(data[1])) if data[0] == "name" else self.repository.delete_tariff(int(data[1])); self.refresh()
        except ValueError as exc: QMessageBox.warning(self, "Suppression impossible", str(exc))
        except Exception as exc: QMessageBox.critical(self, "Suppression impossible", str(exc))

    def duplicate_selected(self) -> None:
        data = self._selected_data()
        if not data or data[0] != "tariff": return
        try: self.repository.duplicate_tariff(self.activity_id, int(data[1])); self.refresh()
        except Exception as exc: QMessageBox.critical(self, "Duplication impossible", str(exc))

    def _sync_actions(self) -> None:
        category = self._selected_category() is not None; self.edit_category_button.setEnabled(category); self.delete_category_button.setEnabled(category); data = self._selected_data(); self.add_tariff_button.setEnabled(bool(data)); self.edit_tariff_button.setEnabled(bool(data)); self.delete_tariff_button.setEnabled(bool(data)); self.duplicate_tariff_button.setEnabled(bool(data and data[0] == "tariff"))


class ActivityEditorDialog(UnitsActivityEditorDialog):
    """Éditeur Activité avec Généralités, Groupes, Unités et Tarification Qt."""

    def __init__(self, repository: NativeActivityEditorRepository, activity_id: int, parent: QWidget | None = None):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(8); self.tabs.removeTab(8)
        if old_page is not None: old_page.deleteLater()
        self.pricing_page = ActivityPricingPage(repository, activity_id, self); self.tabs.insertTab(8, self.pricing_page, "Tarification")

    def _save(self) -> None:
        if not self.pricing_page.has_categories():
            answer = QMessageBox.question(self, "Aucune catégorie de tarif", "Vous n'avez saisi aucune catégorie de tarif. Aucun individu ne pourra donc être inscrit à cette activité. Continuer quand même ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes: self.tabs.setCurrentIndex(8); return
        super()._save()
