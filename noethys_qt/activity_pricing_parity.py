"""Parité de round-trip de la tarification Qt avec Noethys historique.

Cette couche resserre trois écarts encore sensibles après la première passe de
compatibilité : précision décimale QF/revenus, indexation historique des lignes
de calcul et duplication des filtres Questionnaire.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Sequence

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .activity_editor import NativeActivityEditorRepository
from .activity_pricing_compat import (
    ActivityEditorDialog as CompatActivityEditorDialog,
    ActivityPricingPage as CompatActivityPricingPage,
    LEGACY_HHMM_FIELDS,
    LegacyCalculationTable,
    TariffEditDialog as CompatTariffEditDialog,
    list_amount_questions,
    parse_legacy_hhmm,
)
from .activity_pricing_core import (
    FIELD_LABELS,
    LINE_FIELDS,
    METHOD_BY_CODE,
    METHODS,
    NUMERIC_FIELDS,
    ActivityPricingRepository,
    TariffDetails,
    TariffLine,
    as_date,
    ids_to_text,
    parse_date_text,
)


LEGACY_INTEGER_FIELDS = frozenset({"nbre_enfants"})


def parse_legacy_number(text: str, field: str) -> float | int | None:
    """Reproduit les éditeurs numériques historiques sans tronquer QF/revenus.

    Les colonnes QF et revenus utilisaient un éditeur décimal dans wx. Seul le
    nombre d'enfants est intrinsèquement entier parmi les champs encore gérés
    ici.
    """
    value_text = text.strip().replace(",", ".")
    if not value_text:
        return None
    try:
        value = Decimal(value_text)
    except InvalidOperation as exc:
        raise ValueError(
            f"« {FIELD_LABELS.get(field, field)} » doit contenir un nombre valide."
        ) from exc
    if field in LEGACY_INTEGER_FIELDS:
        return int(value)
    return float(value)


class HistoricalCalculationTable(LegacyCalculationTable):
    """Table compatible wx jusque dans la précision et les types de cellules."""

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
                    value = parse_legacy_number(text, field)
                elif field == "date":
                    value = parse_date_text(text, field)
                else:
                    value = text or None
                values[field] = value
            result.append(TariffLine(self.line_ids[row], values))
        return result


class HistoricalActivityPricingRepository(ActivityPricingRepository):
    """Accès SQL avec convention de lignes et duplication identiques au wx."""

    def save_tariff(self, details: TariffDetails, lines: Sequence[TariffLine]) -> int:
        self.validate_tariff(details, lines)
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            fields = (
                "IDactivite", "IDnom_tarif", "date_debut", "date_fin", "type", "methode",
                "categories_tarifs", "groupes", "cotisations", "caisses", "jours_scolaires",
                "jours_vacances", "description", "observations", "tva", "code_compta",
                "code_produit_local", "IDtype_quotient", "label_prestation", "etats",
                "date_facturation", "options", "forfait_saisie_manuelle", "forfait_saisie_auto",
                "forfait_suppression_auto", "forfait_duree", "forfait_beneficiaire", "etiquettes",
            )
            values = (
                details.activity_id,
                details.name_id,
                details.date_start.isoformat(),
                details.date_end.isoformat() if details.date_end else None,
                details.type_code,
                details.method_code,
                ids_to_text(details.category_ids),
                ids_to_text(details.group_ids),
                ids_to_text(details.cotisation_ids),
                ids_to_text(details.caisse_ids),
                ids_to_text(details.school_days),
                ids_to_text(details.vacation_days),
                details.description or None,
                details.observations or None,
                details.vat,
                details.accounting_code or None,
                details.local_product_code or None,
                details.quotient_type_id,
                details.prestation_label,
                details.etats,
                details.date_facturation,
                details.options,
                int(details.forfait_saisie_manuelle),
                int(details.forfait_saisie_auto),
                int(details.forfait_suppression_auto),
                details.forfait_duree,
                details.forfait_beneficiaire,
                details.etiquettes,
            )
            if details.tariff_id is None:
                cursor.execute(
                    f"INSERT INTO tarifs ({', '.join(fields)}) VALUES "
                    f"({', '.join(placeholder for _ in fields)})",
                    values,
                )
                tariff_id = int(cursor.lastrowid)
            else:
                tariff_id = details.tariff_id
                cursor.execute(
                    f"UPDATE tarifs SET {', '.join(f'{field}={placeholder}' for field in fields)} "
                    f"WHERE IDtarif={placeholder} AND IDactivite={placeholder}",
                    values + (tariff_id, details.activity_id),
                )

            cursor.execute(
                f"SELECT IDligne FROM tarifs_lignes WHERE IDtarif={placeholder}",
                (tariff_id,),
            )
            old_ids = {int(row[0]) for row in cursor.fetchall()}
            kept: set[int] = set()
            insert_fields = LINE_FIELDS[1:]

            # Convention wx : num_ligne commence à 0 et tranche contient 1, 2, 3...
            for num_line, line in enumerate(lines):
                row = dict(line.values)
                row.update(
                    IDactivite=details.activity_id,
                    IDtarif=tariff_id,
                    code=details.method_code,
                    num_ligne=num_line,
                    tranche=str(num_line + 1),
                )
                payload = tuple(row.get(field) for field in insert_fields)
                if line.line_id is None:
                    cursor.execute(
                        f"INSERT INTO tarifs_lignes ({', '.join(insert_fields)}) VALUES "
                        f"({', '.join(placeholder for _ in insert_fields)})",
                        payload,
                    )
                    kept.add(int(cursor.lastrowid))
                else:
                    kept.add(line.line_id)
                    cursor.execute(
                        f"UPDATE tarifs_lignes SET "
                        f"{', '.join(f'{field}={placeholder}' for field in insert_fields)} "
                        f"WHERE IDligne={placeholder}",
                        payload + (line.line_id,),
                    )

            for line_id in old_ids - kept:
                cursor.execute(
                    f"DELETE FROM tarifs_lignes WHERE IDligne={placeholder}",
                    (line_id,),
                )
            connection.commit()
            return int(tariff_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def _duplicate_questionnaire_filters(self, source_tariff_id: int, target_tariff_id: int) -> None:
        """Copie toute la ligne de filtre sans connaître son schéma exact.

        Le schéma historique a évolué. On se base donc sur ``cursor.description``
        et on exclut uniquement la clé auto-incrémentée ``IDfiltre``.
        """
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT * FROM questionnaire_filtres WHERE IDtarif={placeholder}",
                (source_tariff_id,),
            )
            rows = cursor.fetchall()
            columns = [str(info[0]) for info in (cursor.description or ())]
            if not rows or "IDtarif" not in columns:
                connection.commit()
                return
            copied_columns = [column for column in columns if column != "IDfiltre"]
            sql = (
                f"INSERT INTO questionnaire_filtres ({', '.join(copied_columns)}) VALUES "
                f"({', '.join(placeholder for _ in copied_columns)})"
            )
            for source_row in rows:
                source = dict(zip(columns, source_row))
                source["IDtarif"] = target_tariff_id
                cursor.execute(sql, tuple(source[column] for column in copied_columns))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def duplicate_tariff(self, activity_id: int, tariff_id: int) -> int:
        new_id = super().duplicate_tariff(activity_id, tariff_id)
        try:
            self._duplicate_questionnaire_filters(tariff_id, new_id)
        except Exception:
            # Ne jamais laisser une copie silencieusement incomplète.
            try:
                self.delete_tariff(new_id)
            except Exception:
                pass
            raise
        return new_id


class TariffEditDialog(CompatTariffEditDialog):
    """Éditeur utilisant la table de calcul à parité décimale."""

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
        self.calculation_table = HistoricalCalculationTable(
            list_amount_questions(self.repository),
            page,
        )
        layout.addWidget(self.calculation_table, 1)
        self.method_combo.currentIndexChanged.connect(self._method_changed)
        return page


class ActivityPricingPage(CompatActivityPricingPage):
    """Page Tarification branchée sur le repository à parité historique."""

    def __init__(
        self,
        editor_repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(editor_repository, activity_id, parent)
        self.repository = HistoricalActivityPricingRepository(editor_repository)
        self.refresh()

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


class ActivityEditorDialog(CompatActivityEditorDialog):
    """Fiche Activité utilisant la tarification à parité de round-trip."""

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
