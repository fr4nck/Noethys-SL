"""Domaine et accès SQL de la page Qt « Tarification ».

Ce module reprend le contrat des contrôles historiques de tarification sans
importer wx/GestionDB. Il écrit dans les tables Noethys existantes et garde les
validations métier au plus près des opérations SQL.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Iterable, Sequence

from .activity_editor import NativeActivityEditorRepository


TARIFF_TYPES = (
    ("JOURN", "Prestation journalière"),
    ("FORFAIT", "Forfait daté"),
    ("CREDIT", "Forfait crédit"),
    ("BAREME", "Barème de contrat"),
)
TARIFF_TYPE_LABELS = dict(TARIFF_TYPES)
STATE_CHOICES = (
    ("reservation", "Réservation"),
    ("present", "Présent"),
    ("absenti", "Absence injustifiée"),
    ("absentj", "Absence justifiée"),
    ("attente", "Attente"),
    ("refus", "Refus"),
)

# code, libellé, types compatibles, champs obligatoires, nombre max de lignes
METHODS = (
    ("montant_unique", "Montant unique", ("JOURN", "FORFAIT", "CREDIT"), ("montant_unique",), 1),
    ("qf", "En fonction du quotient familial", ("JOURN", "FORFAIT", "CREDIT"), ("qf_min", "qf_max", "montant_unique"), None),
    ("horaire_montant_unique", "Montant unique selon une tranche horaire", ("JOURN",), ("heure_debut_min", "heure_debut_max", "heure_fin_min", "heure_fin_max", "montant_unique"), None),
    ("horaire_qf", "Tranche horaire et quotient familial", ("JOURN",), ("qf_min", "qf_max", "heure_debut_min", "heure_debut_max", "heure_fin_min", "heure_fin_max", "montant_unique"), None),
    ("duree_montant_unique", "Montant unique selon une durée", ("JOURN",), ("duree_min", "duree_max", "montant_unique"), None),
    ("duree_qf", "Durée et quotient familial", ("JOURN",), ("qf_min", "qf_max", "duree_min", "duree_max", "montant_unique"), None),
    ("montant_unique_date", "Montant unique selon la date", ("JOURN",), ("date", "montant_unique"), None),
    ("qf_date", "Date et quotient familial", ("JOURN",), ("date", "qf_min", "qf_max", "montant_unique"), None),
    ("variable", "Tarif libre (saisi par l'utilisateur)", ("JOURN",), (), 0),
    ("choix", "Tarif au choix", ("JOURN", "FORFAIT"), ("montant_unique",), None),
    ("montant_evenement", "Montant de l'évènement", ("JOURN",), (), 0),
    ("montant_unique_nbre_ind", "Montant selon le nombre d'individus présents", ("JOURN",), ("montant_enfant_1",), 1),
    ("qf_nbre_ind", "QF et nombre d'individus présents", ("JOURN",), ("qf_min", "qf_max", "montant_enfant_1"), None),
    ("horaire_montant_unique_nbre_ind", "Nombre d'individus et tranche horaire", ("JOURN",), ("heure_debut_min", "heure_debut_max", "heure_fin_min", "heure_fin_max", "montant_enfant_1"), None),
    ("montant_unique_nbre_ind_degr", "Montant dégressif selon le nombre d'individus", ("JOURN",), ("montant_enfant_1",), 1),
    ("qf_nbre_ind_degr", "Montant dégressif selon QF et individus", ("JOURN",), ("qf_min", "qf_max", "montant_enfant_1"), None),
    ("horaire_montant_unique_nbre_ind_degr", "Montant dégressif et tranche horaire", ("JOURN",), ("heure_debut_min", "heure_debut_max", "heure_fin_min", "heure_fin_max", "montant_enfant_1"), None),
    ("duree_coeff_montant_unique", "Montant au prorata d'une durée", ("JOURN",), ("unite_horaire", "montant_unique"), None),
    ("duree_coeff_qf", "Prorata de durée et QF", ("JOURN",), ("qf_min", "qf_max", "unite_horaire", "montant_unique"), None),
    ("taux_montant_unique", "Par taux d'effort", ("JOURN", "FORFAIT"), ("taux",), 1),
    ("taux_qf", "Taux d'effort et tranches de QF", ("JOURN", "FORFAIT"), ("qf_min", "qf_max", "taux"), None),
    ("taux_date", "Taux d'effort et date", ("JOURN",), ("date", "taux"), None),
    ("duree_taux_montant_unique", "Taux d'effort selon une durée", ("JOURN",), ("duree_min", "duree_max", "taux"), None),
    ("duree_taux_qf", "Taux d'effort, QF et durée", ("JOURN",), ("qf_min", "qf_max", "duree_min", "duree_max", "taux"), None),
    ("forfait_contrat", "Forfait contrat", ("CREDIT",), (), 0),
    ("psu_revenu", "Barème PSU selon revenus", ("BAREME",), ("revenu_min", "revenu_max", "taux"), None),
    ("psu_qf", "Barème PSU selon QF", ("BAREME",), ("qf_min", "qf_max", "taux"), None),
)
METHOD_BY_CODE = {
    code: {"label": label, "types": types, "required": required, "max_rows": max_rows}
    for code, label, types, required, max_rows in METHODS
}

FIELD_LABELS = {
    "qf_min": "QF min", "qf_max": "QF max", "montant_unique": "Montant",
    "montant_questionnaire": "Montant questionnaire", "montant_min": "Montant min",
    "montant_max": "Montant max", "heure_debut_min": "Début min",
    "heure_debut_max": "Début max", "heure_fin_min": "Fin min",
    "heure_fin_max": "Fin max", "duree_min": "Durée min", "duree_max": "Durée max",
    "date": "Date", "label": "Libellé", "temps_facture": "Temps facturé",
    "unite_horaire": "Unité horaire", "duree_seuil": "Durée seuil",
    "duree_plafond": "Durée plafond", "taux": "Taux",
    "ajustement": "Majoration / déduction", "revenu_min": "Revenu min",
    "revenu_max": "Revenu max",
    **{f"montant_enfant_{n}": f"{n}e enfant" if n > 1 else "1er enfant" for n in range(1, 7)},
}
METHOD_FIELDS = {
    "montant_unique": ("montant_unique", "montant_questionnaire"),
    "qf": ("qf_min", "qf_max", "montant_unique"),
    "horaire_montant_unique": ("heure_debut_min", "heure_debut_max", "heure_fin_min", "heure_fin_max", "temps_facture", "montant_unique", "montant_questionnaire", "label"),
    "horaire_qf": ("qf_min", "qf_max", "heure_debut_min", "heure_debut_max", "heure_fin_min", "heure_fin_max", "temps_facture", "montant_unique", "label"),
    "duree_montant_unique": ("duree_min", "duree_max", "temps_facture", "montant_unique", "montant_questionnaire", "label"),
    "duree_qf": ("qf_min", "qf_max", "duree_min", "duree_max", "temps_facture", "montant_unique", "label"),
    "montant_unique_date": ("date", "montant_unique", "label"),
    "qf_date": ("date", "qf_min", "qf_max", "montant_unique", "label"),
    "variable": (), "choix": ("montant_unique", "label"), "montant_evenement": (),
    "montant_unique_nbre_ind": tuple(f"montant_enfant_{n}" for n in range(1, 7)),
    "qf_nbre_ind": ("qf_min", "qf_max", *(f"montant_enfant_{n}" for n in range(1, 7))),
    "horaire_montant_unique_nbre_ind": ("heure_debut_min", "heure_debut_max", "heure_fin_min", "heure_fin_max", "temps_facture", *(f"montant_enfant_{n}" for n in range(1, 7)), "label"),
    "montant_unique_nbre_ind_degr": tuple(f"montant_enfant_{n}" for n in range(1, 7)),
    "qf_nbre_ind_degr": ("qf_min", "qf_max", *(f"montant_enfant_{n}" for n in range(1, 7))),
    "horaire_montant_unique_nbre_ind_degr": ("heure_debut_min", "heure_debut_max", "heure_fin_min", "heure_fin_max", "temps_facture", *(f"montant_enfant_{n}" for n in range(1, 7)), "label"),
    "duree_coeff_montant_unique": ("duree_min", "duree_max", "duree_seuil", "duree_plafond", "unite_horaire", "montant_unique", "montant_min", "montant_max", "montant_questionnaire", "ajustement", "label"),
    "duree_coeff_qf": ("qf_min", "qf_max", "duree_min", "duree_max", "duree_seuil", "duree_plafond", "unite_horaire", "montant_unique", "montant_min", "montant_max", "ajustement", "label"),
    "taux_montant_unique": ("taux", "montant_min", "montant_max", "ajustement", "label"),
    "taux_qf": ("qf_min", "qf_max", "taux", "montant_min", "montant_max", "ajustement", "label"),
    "taux_date": ("date", "taux", "montant_min", "montant_max", "ajustement", "label"),
    "duree_taux_montant_unique": ("duree_min", "duree_max", "temps_facture", "taux", "montant_min", "montant_max", "ajustement", "label"),
    "duree_taux_qf": ("qf_min", "qf_max", "duree_min", "duree_max", "temps_facture", "taux", "montant_min", "montant_max", "ajustement", "label"),
    "forfait_contrat": (),
    "psu_revenu": ("revenu_min", "revenu_max", "taux", "montant_min", "montant_max", "ajustement"),
    "psu_qf": ("qf_min", "qf_max", "taux", "montant_min", "montant_max", "ajustement"),
}

LINE_FIELDS = (
    "IDligne", "IDactivite", "IDtarif", "code", "num_ligne", "tranche",
    "qf_min", "qf_max", "montant_unique", "montant_questionnaire",
    "montant_enfant_1", "montant_enfant_2", "montant_enfant_3", "montant_enfant_4",
    "montant_enfant_5", "montant_enfant_6", "nbre_enfants", "coefficient",
    "montant_min", "montant_max", "heure_debut_min", "heure_debut_max",
    "heure_fin_min", "heure_fin_max", "duree_min", "duree_max", "date", "label",
    "temps_facture", "unite_horaire", "duree_seuil", "duree_plafond", "taux",
    "ajustement", "revenu_min", "revenu_max", "IDmodele",
)
NUMERIC_FIELDS = {
    "qf_min", "qf_max", "montant_unique", "montant_questionnaire", "nbre_enfants",
    "coefficient", "montant_min", "montant_max", "duree_min", "duree_max",
    "temps_facture", "unite_horaire", "duree_seuil", "duree_plafond", "taux",
    "ajustement", "revenu_min", "revenu_max", *(f"montant_enfant_{n}" for n in range(1, 7)),
}
TIME_FIELDS = {"heure_debut_min", "heure_debut_max", "heure_fin_min", "heure_fin_max"}


@dataclass(frozen=True, slots=True)
class PricingCategory:
    category_id: int
    activity_id: int
    name: str
    cities: tuple[tuple[str, str], ...] = ()

    @property
    def cities_label(self) -> str:
        return "; ".join(name for _cp, name in self.cities)


@dataclass(frozen=True, slots=True)
class TariffName:
    name_id: int
    activity_id: int
    name: str


@dataclass(frozen=True, slots=True)
class TariffLine:
    line_id: int | None
    values: dict[str, object]


@dataclass(frozen=True, slots=True)
class UnitCombination:
    combination_id: int | None
    unit_ids: tuple[int, ...]
    date: dt.date | None = None
    quantity_max: int | None = None


@dataclass(frozen=True, slots=True)
class TariffDetails:
    tariff_id: int | None
    activity_id: int
    name_id: int
    date_start: dt.date
    date_end: dt.date | None
    type_code: str
    method_code: str
    category_ids: tuple[int, ...]
    group_ids: tuple[int, ...] | None
    cotisation_ids: tuple[int, ...] | None
    caisse_ids: tuple[int, ...] | None
    school_days: tuple[int, ...]
    vacation_days: tuple[int, ...]
    description: str
    observations: str
    vat: float
    accounting_code: str
    local_product_code: str
    quotient_type_id: int | None
    prestation_label: str
    etats: str | None = None
    date_facturation: str | None = None
    options: str | None = None
    forfait_saisie_manuelle: bool = False
    forfait_saisie_auto: bool = False
    forfait_suppression_auto: bool = False
    forfait_duree: str | None = None
    forfait_beneficiaire: str | None = None
    etiquettes: str | None = None


def as_date(value: object, fallback: dt.date | None = None) -> dt.date | None:
    if value in (None, ""):
        return fallback
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return fallback


def ids_from_text(value: object) -> tuple[int, ...] | None:
    if value in (None, ""):
        return None
    return tuple(int(item) for item in str(value).split(";") if item.strip())


def ids_to_text(values: Iterable[int] | None) -> str | None:
    if values is None:
        return None
    result = tuple(dict.fromkeys(int(value) for value in values))
    return ";".join(str(value) for value in result) if result else None


def parse_number(text: str, field: str) -> float | int | None:
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"« {FIELD_LABELS.get(field, field)} » doit contenir un nombre valide.") from exc
    if field in {"qf_min", "qf_max", "nbre_enfants", "duree_min", "duree_max", "revenu_min", "revenu_max"}:
        return int(value)
    return float(value)


def parse_date_text(text: str, field: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"« {FIELD_LABELS.get(field, field)} » doit être une date valide (JJ/MM/AAAA).")


def parse_time_text(text: str, field: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    try:
        dt.datetime.strptime(text, "%H:%M")
    except ValueError as exc:
        raise ValueError(f"« {FIELD_LABELS.get(field, field)} » doit être une heure valide (HH:MM).") from exc
    return text


def method_label(code: str) -> str:
    return str(METHOD_BY_CODE.get(code, {}).get("label", code or "-- Aucune --"))


class ActivityPricingRepository:
    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont transitoire volontaire

    def _pairs(self, sql_template: str, params: tuple[object, ...] = ()) -> list[tuple[int, str]]:
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(sql_template.format(p=placeholder), params)
            return [(int(row[0]), str(row[1] or "")) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def list_categories(self, activity_id: int) -> list[PricingCategory]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT IDcategorie_tarif, IDactivite, nom FROM categories_tarifs WHERE IDactivite={placeholder} ORDER BY nom", (activity_id,))
            result = []
            for category_id, row_activity, name in cursor.fetchall():
                cursor.execute(f"SELECT cp, nom FROM categories_tarifs_villes WHERE IDcategorie_tarif={placeholder} ORDER BY nom, cp", (category_id,))
                cities = tuple((str(cp or ""), str(city or "")) for cp, city in cursor.fetchall())
                result.append(PricingCategory(int(category_id), int(row_activity), str(name or ""), cities))
            return result
        finally:
            cursor.close(); connection.close()

    def save_category(self, category: PricingCategory) -> int:
        if not category.name.strip():
            raise ValueError("Vous devez obligatoirement saisir un nom pour cette catégorie.")
        if any(not city.strip() for _cp, city in category.cities):
            raise ValueError("Chaque ville rattachée doit avoir un nom.")
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            if category.category_id:
                cursor.execute(f"UPDATE categories_tarifs SET nom={placeholder} WHERE IDcategorie_tarif={placeholder} AND IDactivite={placeholder}", (category.name.strip(), category.category_id, category.activity_id))
                category_id = category.category_id
            else:
                cursor.execute(f"INSERT INTO categories_tarifs (IDactivite, nom) VALUES ({placeholder}, {placeholder})", (category.activity_id, category.name.strip()))
                category_id = int(cursor.lastrowid)
            cursor.execute(f"DELETE FROM categories_tarifs_villes WHERE IDcategorie_tarif={placeholder}", (category_id,))
            for cp, city in category.cities:
                cursor.execute(f"INSERT INTO categories_tarifs_villes (IDcategorie_tarif, cp, nom) VALUES ({placeholder}, {placeholder}, {placeholder})", (category_id, cp.strip() or None, city.strip()))
            connection.commit(); return int(category_id)
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def category_usage(self, category_id: int) -> int:
        connection, _placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute("SELECT categories_tarifs FROM tarifs WHERE categories_tarifs IS NOT NULL")
            return sum(category_id in (ids_from_text(raw) or ()) for (raw,) in cursor.fetchall())
        finally:
            cursor.close(); connection.close()

    def delete_category(self, activity_id: int, category_id: int) -> None:
        usage = self.category_usage(category_id)
        if usage:
            raise ValueError(f"Cette catégorie est utilisée dans {usage} tarif(s) et ne peut pas être supprimée.")
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(f"DELETE FROM categories_tarifs_villes WHERE IDcategorie_tarif={placeholder}", (category_id,))
            cursor.execute(f"DELETE FROM categories_tarifs WHERE IDcategorie_tarif={placeholder} AND IDactivite={placeholder}", (category_id, activity_id))
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def list_names(self, activity_id: int) -> list[TariffName]:
        return [TariffName(value, activity_id, name) for value, name in self._pairs("SELECT IDnom_tarif, nom FROM noms_tarifs WHERE IDactivite={p} ORDER BY nom", (activity_id,))]

    def save_name(self, activity_id: int, name: str, name_id: int | None = None) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Le nom de prestation ne peut pas être vide.")
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            if name_id is None:
                cursor.execute(f"INSERT INTO noms_tarifs (IDactivite, nom) VALUES ({placeholder}, {placeholder})", (activity_id, name)); name_id = int(cursor.lastrowid)
            else:
                cursor.execute(f"UPDATE noms_tarifs SET nom={placeholder} WHERE IDnom_tarif={placeholder} AND IDactivite={placeholder}", (name, name_id, activity_id))
            connection.commit(); return int(name_id)
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def delete_name(self, activity_id: int, name_id: int) -> None:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT COUNT(IDtarif) FROM tarifs WHERE IDnom_tarif={placeholder}", (name_id,)); count = int(cursor.fetchone()[0] or 0)
            if count:
                raise ValueError(f"Ce nom de prestation possède encore {count} tarif(s). Supprimez-les d'abord.")
            cursor.execute(f"DELETE FROM noms_tarifs WHERE IDnom_tarif={placeholder} AND IDactivite={placeholder}", (name_id, activity_id)); connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def list_tariffs(self, activity_id: int) -> list[TariffDetails]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(f"""SELECT IDtarif, IDactivite, IDnom_tarif, date_debut, date_fin, type,
                methode, categories_tarifs, groupes, cotisations, caisses, jours_scolaires,
                jours_vacances, description, observations, tva, code_compta, code_produit_local,
                IDtype_quotient, label_prestation, etats, date_facturation, options,
                forfait_saisie_manuelle, forfait_saisie_auto, forfait_suppression_auto,
                forfait_duree, forfait_beneficiaire, etiquettes
                FROM tarifs WHERE IDactivite={placeholder}
                ORDER BY IDnom_tarif, date_debut DESC, IDtarif DESC""", (activity_id,))
            return [self._tariff(row) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    @staticmethod
    def _tariff(row: Sequence[object]) -> TariffDetails:
        return TariffDetails(
            int(row[0]), int(row[1]), int(row[2]), as_date(row[3], dt.date.today()) or dt.date.today(), as_date(row[4]),
            str(row[5] or "JOURN"), str(row[6] or ""), ids_from_text(row[7]) or (), ids_from_text(row[8]),
            ids_from_text(row[9]), ids_from_text(row[10]), ids_from_text(row[11]) or (), ids_from_text(row[12]) or (),
            str(row[13] or ""), str(row[14] or ""), float(row[15] or 0), str(row[16] or ""), str(row[17] or ""),
            int(row[18]) if row[18] not in (None, "") else None, str(row[19] or "nom_tarif"),
            str(row[20]) if row[20] not in (None, "") else None, str(row[21]) if row[21] not in (None, "") else None,
            str(row[22]) if row[22] not in (None, "") else None, bool(row[23]), bool(row[24]), bool(row[25]),
            str(row[26]) if row[26] not in (None, "") else None, str(row[27]) if row[27] not in (None, "") else None,
            str(row[28]) if row[28] not in (None, "") else None,
        )

    def load_tariff(self, activity_id: int, tariff_id: int) -> TariffDetails:
        for tariff in self.list_tariffs(activity_id):
            if tariff.tariff_id == tariff_id:
                return tariff
        raise ValueError("Tarif introuvable.")

    def list_lines(self, tariff_id: int) -> list[TariffLine]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT {', '.join(LINE_FIELDS)} FROM tarifs_lignes WHERE IDtarif={placeholder} ORDER BY num_ligne, IDligne", (tariff_id,))
            return [TariffLine(int(row[0]), dict(zip(LINE_FIELDS, row))) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def validate_tariff(self, details: TariffDetails, lines: Sequence[TariffLine]) -> None:
        if details.date_end is not None and details.date_end < details.date_start:
            raise ValueError("La date de fin doit être supérieure ou égale à la date de début.")
        if not 0 <= details.vat <= 100:
            raise ValueError("Le taux de TVA doit être compris entre 0 et 100 %.")
        if details.prestation_label.startswith("autre:") and not details.prestation_label[6:].strip():
            raise ValueError("Le label de prestation personnalisé ne peut pas être vide.")
        if details.group_ids is not None and not details.group_ids:
            raise ValueError("Vous avez activé le filtre de groupes sans cocher aucun groupe.")
        if details.cotisation_ids is not None and not details.cotisation_ids:
            raise ValueError("Vous avez activé le filtre de cotisations sans cocher aucune cotisation.")
        if details.caisse_ids is not None and not details.caisse_ids:
            raise ValueError("Vous avez activé le filtre de caisses sans cocher aucune caisse.")
        method = METHOD_BY_CODE.get(details.method_code)
        if method is None:
            raise ValueError("Vous devez obligatoirement sélectionner une méthode de calcul.")
        if details.type_code not in method["types"]:
            raise ValueError("La méthode de calcul sélectionnée n'est pas compatible avec le type de tarif sélectionné.")
        max_rows = method["max_rows"]
        if max_rows is not None and len(lines) > max_rows:
            raise ValueError(f"Cette méthode accepte au maximum {max_rows} ligne(s) de calcul.")
        if method["required"] and not lines:
            raise ValueError("Cette méthode nécessite au moins une ligne de paramètres.")
        for index, line in enumerate(lines, 1):
            for field in method["required"]:
                if line.values.get(field) in (None, ""):
                    raise ValueError(f"Vous devez renseigner « {FIELD_LABELS.get(field, field)} » à la ligne {index}.")
            for low, high, label in (("qf_min", "qf_max", "QF"), ("revenu_min", "revenu_max", "revenu")):
                if line.values.get(low) is not None and line.values.get(high) is not None and float(line.values[low]) > float(line.values[high]):
                    raise ValueError(f"Ligne {index} : le {label} minimum est supérieur au maximum.")
        if details.type_code == "CREDIT" and details.forfait_duree:
            parts = {part[0]: int(part[1:]) for part in details.forfait_duree.split("-") if len(part) > 1 and part[0] in "jma" and part[1:].isdigit()}
            if not any(parts.get(key, 0) for key in "jma"):
                raise ValueError("La durée limitée du forfait crédit doit contenir au moins un jour, un mois ou une année.")
        if details.date_facturation and details.date_facturation.startswith("date:") and as_date(details.date_facturation[5:]) is None:
            raise ValueError("La date de facturation personnalisée n'est pas valide.")

    def save_tariff(self, details: TariffDetails, lines: Sequence[TariffLine]) -> int:
        self.validate_tariff(details, lines)
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            fields = ("IDactivite", "IDnom_tarif", "date_debut", "date_fin", "type", "methode", "categories_tarifs", "groupes", "cotisations", "caisses", "jours_scolaires", "jours_vacances", "description", "observations", "tva", "code_compta", "code_produit_local", "IDtype_quotient", "label_prestation", "etats", "date_facturation", "options", "forfait_saisie_manuelle", "forfait_saisie_auto", "forfait_suppression_auto", "forfait_duree", "forfait_beneficiaire", "etiquettes")
            values = (details.activity_id, details.name_id, details.date_start.isoformat(), details.date_end.isoformat() if details.date_end else None, details.type_code, details.method_code, ids_to_text(details.category_ids), ids_to_text(details.group_ids), ids_to_text(details.cotisation_ids), ids_to_text(details.caisse_ids), ids_to_text(details.school_days), ids_to_text(details.vacation_days), details.description or None, details.observations or None, details.vat, details.accounting_code or None, details.local_product_code or None, details.quotient_type_id, details.prestation_label, details.etats, details.date_facturation, details.options, int(details.forfait_saisie_manuelle), int(details.forfait_saisie_auto), int(details.forfait_suppression_auto), details.forfait_duree, details.forfait_beneficiaire, details.etiquettes)
            if details.tariff_id is None:
                cursor.execute(f"INSERT INTO tarifs ({', '.join(fields)}) VALUES ({', '.join(placeholder for _ in fields)})", values); tariff_id = int(cursor.lastrowid)
            else:
                tariff_id = details.tariff_id
                cursor.execute(f"UPDATE tarifs SET {', '.join(f'{field}={placeholder}' for field in fields)} WHERE IDtarif={placeholder} AND IDactivite={placeholder}", values + (tariff_id, details.activity_id))
            cursor.execute(f"SELECT IDligne FROM tarifs_lignes WHERE IDtarif={placeholder}", (tariff_id,)); old_ids = {int(row[0]) for row in cursor.fetchall()}; kept = set()
            insert_fields = LINE_FIELDS[1:]
            for num_line, line in enumerate(lines, 1):
                row = dict(line.values); row.update(IDactivite=details.activity_id, IDtarif=tariff_id, code=details.method_code, num_ligne=num_line)
                payload = tuple(row.get(field) for field in insert_fields)
                if line.line_id is None:
                    cursor.execute(f"INSERT INTO tarifs_lignes ({', '.join(insert_fields)}) VALUES ({', '.join(placeholder for _ in insert_fields)})", payload); kept.add(int(cursor.lastrowid))
                else:
                    kept.add(line.line_id); cursor.execute(f"UPDATE tarifs_lignes SET {', '.join(f'{field}={placeholder}' for field in insert_fields)} WHERE IDligne={placeholder}", payload + (line.line_id,))
            for line_id in old_ids - kept:
                cursor.execute(f"DELETE FROM tarifs_lignes WHERE IDligne={placeholder}", (line_id,))
            connection.commit(); return int(tariff_id)
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def tariff_usage(self, tariff_id: int) -> int:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT COUNT(IDprestation) FROM prestations WHERE IDtarif={placeholder}", (tariff_id,)); return int(cursor.fetchone()[0] or 0)
        finally:
            cursor.close(); connection.close()

    def delete_tariff(self, tariff_id: int) -> None:
        count = self.tariff_usage(tariff_id)
        if count:
            raise ValueError(f"Ce tarif est utilisé par {count} prestation(s) et ne peut pas être supprimé.")
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            for table in ("questionnaire_filtres", "tarifs_lignes", "combi_tarifs_unites", "combi_tarifs"):
                cursor.execute(f"DELETE FROM {table} WHERE IDtarif={placeholder}", (tariff_id,))
            cursor.execute(f"DELETE FROM tarifs WHERE IDtarif={placeholder}", (tariff_id,)); connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def duplicate_tariff(self, activity_id: int, tariff_id: int) -> int:
        original = self.load_tariff(activity_id, tariff_id)
        new_id = self.save_tariff(replace(original, tariff_id=None), [TariffLine(None, dict(line.values)) for line in self.list_lines(tariff_id)])
        for type_code in ("JOURN", "FORFAIT", "CREDIT"):
            copied = [replace(combination, combination_id=None) for combination in self.list_combinations(tariff_id, type_code)]
            if copied:
                self.save_combinations(new_id, type_code, copied)
        return new_id

    def list_groups(self, activity_id: int) -> list[tuple[int, str]]:
        return self._pairs("SELECT IDgroupe, nom FROM groupes WHERE IDactivite={p} ORDER BY ordre, nom", (activity_id,))

    def list_cotisations(self) -> list[tuple[int, str]]:
        return self._pairs("SELECT IDtype_cotisation, nom FROM types_cotisations ORDER BY nom")

    def list_caisses(self) -> list[tuple[int, str]]:
        return [(0, "Caisse non spécifiée"), *self._pairs("SELECT IDcaisse, nom FROM caisses ORDER BY nom")]

    def list_quotient_types(self) -> list[tuple[int, str]]:
        return self._pairs("SELECT IDtype_quotient, nom FROM types_quotients ORDER BY nom")

    def list_units(self, activity_id: int) -> list[tuple[int, str]]:
        return self._pairs("SELECT IDunite, nom FROM unites WHERE IDactivite={p} ORDER BY ordre, nom", (activity_id,))

    def list_combinations(self, tariff_id: int, type_code: str) -> list[UnitCombination]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT IDcombi_tarif, date, quantite_max FROM combi_tarifs WHERE IDtarif={placeholder} AND type={placeholder} ORDER BY IDcombi_tarif", (tariff_id, type_code))
            result = []
            for combination_id, raw_date, quantity_max in cursor.fetchall():
                cursor.execute(f"SELECT IDunite FROM combi_tarifs_unites WHERE IDcombi_tarif={placeholder} ORDER BY IDunite", (combination_id,))
                result.append(UnitCombination(int(combination_id), tuple(int(row[0]) for row in cursor.fetchall()), as_date(raw_date), int(quantity_max) if quantity_max not in (None, "") else None))
            return result
        finally:
            cursor.close(); connection.close()

    def validate_combination(self, activity_id: int, unit_ids: Iterable[int], existing: Sequence[UnitCombination] = (), date: dt.date | None = None, type_code: str = "JOURN") -> tuple[int, ...]:
        ids = tuple(sorted(set(int(value) for value in unit_ids)))
        if not ids:
            raise ValueError("Vous devez sélectionner au moins une unité.")
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            marks = ", ".join(placeholder for _ in ids)
            cursor.execute(f"SELECT IDunite FROM unites WHERE IDactivite={placeholder} AND IDunite IN ({marks})", (activity_id, *ids))
            if {int(row[0]) for row in cursor.fetchall()} != set(ids):
                raise ValueError("Une unité sélectionnée n'appartient plus à cette activité.")
            cursor.execute(f"SELECT IDunite, IDunite_incompatible FROM unites_incompat WHERE IDunite IN ({marks})", ids)
            selected = set(ids)
            for _unit_id, incompatible in cursor.fetchall():
                if int(incompatible) in selected:
                    raise ValueError("Vous ne pouvez pas combiner des unités déclarées incompatibles entre elles.")
            if date is not None:
                for unit_id in ids:
                    cursor.execute(f"SELECT COUNT(IDouverture) FROM ouvertures WHERE IDactivite={placeholder} AND IDunite={placeholder} AND date={placeholder}", (activity_id, unit_id, date.isoformat()))
                    if int(cursor.fetchone()[0] or 0) == 0:
                        raise ValueError("Une unité sélectionnée n'est pas ouverte à la date choisie.")
        finally:
            cursor.close(); connection.close()
        if type_code == "JOURN" and any(tuple(sorted(item.unit_ids)) == ids for item in existing):
            raise ValueError("Cette combinaison existe déjà.")
        return ids

    def save_combinations(self, tariff_id: int, type_code: str, combinations: Sequence[UnitCombination]) -> None:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(f"SELECT IDcombi_tarif FROM combi_tarifs WHERE IDtarif={placeholder} AND type={placeholder}", (tariff_id, type_code)); old_ids = {int(row[0]) for row in cursor.fetchall()}; kept = set()
            for combination in combinations:
                if combination.combination_id is None:
                    cursor.execute(f"INSERT INTO combi_tarifs (IDtarif, type, date, quantite_max) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})", (tariff_id, type_code, combination.date.isoformat() if combination.date else None, combination.quantity_max)); combination_id = int(cursor.lastrowid)
                else:
                    combination_id = combination.combination_id; cursor.execute(f"UPDATE combi_tarifs SET date={placeholder}, quantite_max={placeholder} WHERE IDcombi_tarif={placeholder}", (combination.date.isoformat() if combination.date else None, combination.quantity_max, combination_id))
                kept.add(combination_id); cursor.execute(f"DELETE FROM combi_tarifs_unites WHERE IDcombi_tarif={placeholder}", (combination_id,))
                for unit_id in combination.unit_ids:
                    cursor.execute(f"INSERT INTO combi_tarifs_unites (IDcombi_tarif, IDtarif, IDunite) VALUES ({placeholder}, {placeholder}, {placeholder})", (combination_id, tariff_id, unit_id))
            for combination_id in old_ids - kept:
                cursor.execute(f"DELETE FROM combi_tarifs_unites WHERE IDcombi_tarif={placeholder}", (combination_id,)); cursor.execute(f"DELETE FROM combi_tarifs WHERE IDcombi_tarif={placeholder}", (combination_id,))
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()
