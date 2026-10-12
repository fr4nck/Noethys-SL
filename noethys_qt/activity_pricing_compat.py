"""Compatibilité fine entre la tarification Qt et le comportement wx historique.

Ce module corrige les écarts qui peuvent altérer un tarif existant lors d'un
simple cycle ouverture/enregistrement : forfait daté personnalisé, champs de
durée HH:MM, référence de question pour ``montant_questionnaire`` et valeur
historique NULL du bénéficiaire d'un forfait crédit.
"""

from __future__ import annotations

import re
from typing import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .activity_editor import NativeActivityEditorRepository
from .activity_pricing import (
    ActivityEditorDialog as BaseActivityEditorDialog,
    ActivityPricingPage as BaseActivityPricingPage,
    CalculationTable as BaseCalculationTable,
    TariffEditDialog as BaseTariffEditDialog,
)
from .activity_pricing_core import (
    FIELD_LABELS,
    METHOD_BY_CODE,
    METHOD_FIELDS,
    METHODS,
    NUMERIC_FIELDS,
    TIME_FIELDS,
    ActivityPricingRepository,
    TariffLine,
    UnitCombination,
    as_date,
    parse_date_text,
    parse_number,
)


# Le contrôle wx CTRL_Saisie_heure.Heure accepte 00:00 à 24:59 et stocke
# littéralement la chaîne HH:MM. Les champs ci-dessous utilisaient tous cet
# éditeur, y compris les durées.
LEGACY_HHMM_FIELDS = frozenset(TIME_FIELDS) | {
    "duree_min",
    "duree_max",
    "temps_facture",
    "unite_horaire",
    "duree_seuil",
    "duree_plafond",
}
_HHMM_RE = re.compile(r"^(?:[01]\d|2[0-4]):[0-5]\d$")


def parse_legacy_hhmm(text: str, field: str) -> str | None:
    """Valide une heure/durée avec le même domaine que le contrôle wx."""
    value = text.strip()
    if not value:
        return None
    if not _HHMM_RE.fullmatch(value):
        raise ValueError(
            f"« {FIELD_LABELS.get(field, field)} » doit être au format HH:MM "
            "entre 00:00 et 24:59."
        )
    return value


def historic_credit_beneficiary(value: object) -> str:
    """Reproduit SetBeneficiaire() : seul 'individu' vaut individu, sinon famille."""
    return "individu" if value == "individu" else "famille"


def historic_forfait_mode(options: str | None, combinations: Sequence[UnitCombination]) -> str:
    """Reproduit l'ordre historique de détection du mode du forfait daté."""
    if options and "calendrier" in options:
        return "calendar"
    if combinations:
        return "custom"
    return "none"


def list_amount_questions(repository: ActivityPricingRepository) -> tuple[tuple[int, str], ...]:
    """Questions éligibles au champ historique montant_questionnaire.

    L'ancien RendererChoix n'exposait que les questions dont le contrôle est
    ``montant`` ou ``decimal`` et enregistrait leur IDquestion dans
    ``tarifs_lignes.montant_questionnaire``.
    """
    connection, placeholder = repository._connect()  # noqa: SLF001 - pont transitoire
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""SELECT questionnaire_questions.IDquestion,
                       questionnaire_questions.label,
                       questionnaire_categories.type
                FROM questionnaire_questions
                LEFT JOIN questionnaire_categories
                    ON questionnaire_categories.IDcategorie = questionnaire_questions.IDcategorie
                WHERE questionnaire_questions.controle IN ({placeholder}, {placeholder})
                ORDER BY questionnaire_questions.ordre, questionnaire_questions.IDquestion""",
            ("montant", "decimal"),
        )
        result = []
        for question_id, label, question_type in cursor.fetchall():
            suffix = str(question_type or "").capitalize()
            text = str(label or "")
            if suffix:
                text = f"{text} ({suffix})"
            result.append((int(question_id), text))
        return tuple(result)
    finally:
        cursor.close()
        connection.close()


class LegacyCalculationTable(BaseCalculationTable):
    """Table de calcul qui conserve les types de cellules du wx historique."""

    def __init__(self, question_choices: Sequence[tuple[int, str]], parent: QWidget | None = None):
        self.question_choices = tuple(question_choices)
        super().__init__(parent)

    def add_row(self, line: TariffLine | None = None) -> None:
        maximum = METHOD_BY_CODE.get(self.method_code, {}).get("max_rows")
        if maximum is not None and self.table.rowCount() >= maximum:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.line_ids.append(line.line_id if line else None)
        values = line.values if line else {}
        for column, field in enumerate(self.fields):
            value = values.get(field)
            if field == "montant_questionnaire":
                combo = QComboBox(self.table)
                combo.addItem("— Aucune question —", None)
                for question_id, label in self.question_choices:
                    combo.addItem(label, question_id)
                if value not in (None, ""):
                    try:
                        stored_value: object = int(value)
                    except (TypeError, ValueError):
                        stored_value = value
                    index = combo.findData(stored_value)
                    if index < 0:
                        combo.addItem(f"Question #{stored_value} (indisponible)", stored_value)
                        index = combo.count() - 1
                    combo.setCurrentIndex(index)
                self.table.setCellWidget(row, column, combo)
                continue
            if field == "date" and value not in (None, ""):
                parsed = as_date(value)
                text = parsed.strftime("%d/%m/%Y") if parsed else str(value)
            else:
                text = "" if value is None else str(value)
            self.table.setItem(row, column, QTableWidgetItem(text))
        self._sync_actions()

    def lines(self) -> list[TariffLine]:
        result: list[TariffLine] = []
        for row in range(self.table.rowCount()):
            values: dict[str, object] = {}
            for column, field in enumerate(self.fields):
                if field == "montant_questionnaire":
                    combo = self.table.cellWidget(row, column)
                    values[field] = combo.currentData() if isinstance(combo, QComboBox) else None
                    continue
                item = self.table.item(row, column)
                text = item.text().strip() if item else ""
                if field in LEGACY_HHMM_FIELDS:
                    value = parse_legacy_hhmm(text, field)
                elif field in NUMERIC_FIELDS:
                    value = parse_number(text, field)
                elif field == "date":
                    value = parse_date_text(text, field)
                else:
                    value = text or None
                values[field] = value
            result.append(TariffLine(self.line_ids[row], values))
        return result


class TariffEditDialog(BaseTariffEditDialog):
    """Éditeur tarif avec fidélité de round-trip aux valeurs historiques."""

    def _calculation_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        row = QHBoxLayout()
        row.addWidget(QLabel("Méthode de calcul :", page))
        self.method_combo = QComboBox(page)
        row.addWidget(self.method_combo, 1)
        row.addWidget(QLabel("Type de QF :", page))
        self.quotient_combo = QComboBox(page)
        self.quotient_combo.addItem("Indifférent", None)
        for value, label in self.repository.list_quotient_types():
            self.quotient_combo.addItem(label, value)
        row.addWidget(self.quotient_combo)
        layout.addLayout(row)
        self.calculation_table = LegacyCalculationTable(list_amount_questions(self.repository), page)
        layout.addWidget(self.calculation_table, 1)
        self.method_combo.currentIndexChanged.connect(self._method_changed)
        return page

    def _load(self) -> None:
        super()._load()

        if self.details.type_code == "FORFAIT":
            mode = historic_forfait_mode(
                self.details.options,
                self.combinations.get("FORFAIT", ()),
            )
            self.forfait_mode.blockSignals(True)
            index = self.forfait_mode.findData(mode)
            self.forfait_mode.setCurrentIndex(index if index >= 0 else 0)
            self.forfait_mode.blockSignals(False)

        if self.details.type_code == "CREDIT":
            beneficiary = historic_credit_beneficiary(self.details.forfait_beneficiaire)
            index = self.credit_beneficiary.findData(beneficiary)
            self.credit_beneficiary.setCurrentIndex(index if index >= 0 else 0)

        self._sync_forfait_options()
        self._sync_type()


class ActivityPricingPage(BaseActivityPricingPage):
    """Page activité qui ouvre systématiquement l'éditeur compatible historique."""

    def add_tariff(self) -> None:
        data = self._selected_data()
        name_id = int(data[1] if data and data[0] == "name" else data[2]) if data else None
        if name_id is None:
            QMessageBox.information(self, "Ajouter un tarif", "Sélectionnez d'abord un nom de prestation.")
            return
        dialog = TariffEditDialog(self.repository, self.activity_id, name_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def edit_selected(self) -> None:
        data = self._selected_data()
        if not data:
            return
        if data[0] == "name":
            return super().edit_selected()
        dialog = TariffEditDialog(
            self.repository,
            self.activity_id,
            int(data[2]),
            int(data[1]),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()


class ActivityEditorDialog(BaseActivityEditorDialog):
    """Fiche Activité utilisant la tarification Qt à compatibilité renforcée."""

    def __init__(
        self,
        repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(8)
        self.tabs.removeTab(8)
        if old_page is not None:
            old_page.deleteLater()
        self.pricing_page = ActivityPricingPage(repository, activity_id, self)
        self.tabs.insertTab(8, self.pricing_page, "Tarification")
