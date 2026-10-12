"""Moteur Qt des assistants historiques de création d'activités.

Le module ne dépend ni de wx ni de GestionDB. Il reprend les cinq familles
proposées historiquement par ``CTRL_Assistants_liste`` et génère leur squelette
métier directement dans les tables Noethys existantes, en une transaction.

La passe Qt volontairement prudente conserve les invariants structurants :
activité + groupes, responsable et obligations facultatifs, agrément du séjour,
unités/ouvertures adaptées au modèle, catégorie tarifaire et tarification
simple lorsqu'elle est demandée. Les méthodes tarifaires avancées restent
ensuite modifiables dans l'onglet Tarification déjà migré.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .activity_editor import NativeActivityEditorRepository, UNLIMITED_END, UNLIMITED_START


ASSISTANT_CHOICES: tuple[tuple[str, str, str], ...] = (
    (
        "nouveau",
        "Créer une nouvelle activité",
        "Personnalisez votre nouvelle activité de A à Z dans la fiche Qt complète.",
    ),
    (
        "annuelle",
        "Une activité culturelle ou sportive annuelle",
        "Club de gym, danse, couture, sport… avec groupes/séances et pointage facultatif.",
    ),
    (
        "sejour",
        "Un séjour",
        "Séjour, camp ou mini-camp avec journées ouvertes sur toute la période.",
    ),
    (
        "stage",
        "Un stage",
        "Stage culturel ou sportif avec journées ouvertes sur toute la période.",
    ),
    (
        "cantine",
        "Une cantine",
        "Cantine avec un ou plusieurs services et une unité Repas.",
    ),
    (
        "sorties",
        "Des sorties familiales",
        "Activité événementielle avec unité Sortie et tarif porté par l'évènement.",
    ),
)

INFORMATION_TYPES: tuple[tuple[int, str], ...] = (
    (1, "Date de naissance"),
    (2, "Lieu de naissance"),
    (3, "Numéro de sécurité sociale"),
    (6, "Médecin traitant"),
    (12, "Quotient familial"),
    (7, "Caisse d'allocations"),
    (8, "Numéro d'allocataire"),
    (9, "Titulaire allocataire"),
    (10, "Titulaire Hélios"),
    (11, "Code comptable"),
)


@dataclass(frozen=True, slots=True)
class AssistantConfiguration:
    code: str
    name: str
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    max_members: int | None = None
    activity_group_type_ids: tuple[int, ...] = ()
    group_names: tuple[str, ...] = ()
    group_capacities: tuple[int | None, ...] = ()
    session_weekdays: tuple[int, ...] = ()  # 0=lundi … 6=dimanche
    track_sessions: bool = False
    agreement_number: str = ""
    responsible_name: str = ""
    responsible_function: str = ""
    responsible_gender: str = "H"
    piece_ids: tuple[int, ...] = ()
    cotisation_ids: tuple[int, ...] = ()
    information_ids: tuple[int, ...] = ()
    pricing_mode: str = "later"  # later | free | fixed
    pricing_categories: tuple[str, ...] = ()
    amount: float | None = None


@dataclass(frozen=True, slots=True)
class AssistantPlan:
    code: str
    title: str
    effects: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def as_text(self) -> str:
        sections = [self.title, "", *[f"• {line}" for line in self.effects]]
        if self.warnings:
            sections.extend(("", "Points d'attention :", *[f"• {line}" for line in self.warnings]))
        return "\n".join(sections)


def create_abbreviation(name: str) -> str:
    """Reprend ``CreationAbrege`` de l'assistant historique."""
    result = str(name or "")
    for character in " 0123456789/*-+.,;:_'()":
        result = result.replace(character, "")
    return result[:5].upper()


class ActivityAssistantRepository:
    """Génération atomique des cinq assistants historiques."""

    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont natif volontaire

    @staticmethod
    def _columns(cursor, table: str) -> list[str]:
        cursor.execute(f"SELECT * FROM {table} WHERE 1=0")
        return [str(item[0]) for item in cursor.description or ()]

    @classmethod
    def _insert(cls, cursor, placeholder: str, table: str, values: Mapping[str, object]) -> int:
        columns = cls._columns(cursor, table)
        if not columns:
            raise RuntimeError(f"Table {table} sans colonnes.")
        primary_key = columns[0]
        fields = [field for field in values if field in columns and field != primary_key]
        if not fields:
            cursor.execute(f"INSERT INTO {table} DEFAULT VALUES")
        else:
            marks = ", ".join(placeholder for _ in fields)
            cursor.execute(
                f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({marks})",
                tuple(values[field] for field in fields),
            )
        new_id = int(cursor.lastrowid or 0)
        if new_id <= 0:
            raise RuntimeError(f"L'insertion dans {table} n'a pas retourné d'identifiant.")
        return new_id

    @classmethod
    def _insert_no_id(cls, cursor, placeholder: str, table: str, values: Mapping[str, object]) -> None:
        columns = cls._columns(cursor, table)
        fields = [field for field in values if field in columns]
        if not fields:
            return
        marks = ", ".join(placeholder for _ in fields)
        cursor.execute(
            f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({marks})",
            tuple(values[field] for field in fields),
        )

    @staticmethod
    def _pair_rows(cursor, sql: str) -> list[tuple[int, str]]:
        cursor.execute(sql)
        return [(int(row[0]), str(row[1] or "")) for row in cursor.fetchall()]

    def list_activity_group_types(self) -> list[tuple[int, str]]:
        connection, _placeholder = self._connect(); cursor = connection.cursor()
        try:
            return self._pair_rows(
                cursor,
                "SELECT IDtype_groupe_activite, nom FROM types_groupes_activites ORDER BY nom",
            )
        finally:
            cursor.close(); connection.close()

    def list_pieces(self) -> list[tuple[int, str]]:
        connection, _placeholder = self._connect(); cursor = connection.cursor()
        try:
            return self._pair_rows(cursor, "SELECT IDtype_piece, nom FROM types_pieces ORDER BY nom")
        finally:
            cursor.close(); connection.close()

    def list_cotisations(self) -> list[tuple[int, str]]:
        connection, _placeholder = self._connect(); cursor = connection.cursor()
        try:
            return self._pair_rows(
                cursor,
                "SELECT IDtype_cotisation, nom FROM types_cotisations ORDER BY nom",
            )
        finally:
            cursor.close(); connection.close()

    def last_responsible(self) -> tuple[str, str, str] | None:
        connection, _placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT sexe, nom, fonction FROM responsables_activite "
                "ORDER BY IDresponsable DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return str(row[0] or "H"), str(row[1] or ""), str(row[2] or "")
        finally:
            cursor.close(); connection.close()

    @staticmethod
    def validate(configuration: AssistantConfiguration) -> None:
        valid_codes = {code for code, _name, _description in ASSISTANT_CHOICES if code != "nouveau"}
        if configuration.code not in valid_codes:
            raise ValueError("Assistant de création inconnu.")
        if not configuration.name.strip():
            raise ValueError("Vous devez obligatoirement saisir le nom de l'activité.")
        if configuration.code in {"annuelle", "sejour", "stage"}:
            if configuration.start_date is None or configuration.end_date is None:
                raise ValueError("Les dates de début et de fin sont obligatoires pour cet assistant.")
            if configuration.end_date < configuration.start_date:
                raise ValueError("La date de fin doit être supérieure ou égale à la date de début.")
        if configuration.max_members is not None and configuration.max_members < 0:
            raise ValueError("Le nombre maximal d'inscrits ne peut pas être négatif.")
        if configuration.responsible_gender not in {"H", "F"}:
            raise ValueError("Le genre du responsable doit être H ou F.")
        group_names = tuple(name.strip() for name in configuration.group_names if name.strip())
        if len(set(name.casefold() for name in group_names)) != len(group_names):
            raise ValueError("Deux groupes ou services portent le même nom.")
        if configuration.pricing_mode not in {"later", "free", "fixed"}:
            raise ValueError("Mode de tarification inconnu.")
        if configuration.code == "sorties" and configuration.pricing_mode == "free":
            raise ValueError("L'assistant Sorties utilise un tarif événementiel ; choisissez 'à finaliser' ou 'fixe'.")
        if configuration.pricing_mode == "fixed":
            if configuration.amount is None or configuration.amount < 0:
                raise ValueError("Vous devez saisir un montant positif ou nul pour le tarif fixe.")
        categories = tuple(name.strip() for name in configuration.pricing_categories if name.strip())
        if len(set(name.casefold() for name in categories)) != len(categories):
            raise ValueError("Deux catégories tarifaires portent le même nom.")
        for weekday in configuration.session_weekdays:
            if weekday not in range(7):
                raise ValueError("Jour de séance invalide.")

    @staticmethod
    def _effective_period(configuration: AssistantConfiguration) -> tuple[dt.date, dt.date]:
        return (
            configuration.start_date or UNLIMITED_START,
            configuration.end_date or UNLIMITED_END,
        )

    @staticmethod
    def _effective_groups(configuration: AssistantConfiguration) -> tuple[str, ...]:
        groups = tuple(name.strip() for name in configuration.group_names if name.strip())
        return groups or ("Groupe unique",)

    @staticmethod
    def _date_range(start: dt.date, end: dt.date) -> Iterable[dt.date]:
        current = start
        while current <= end:
            yield current
            current += dt.timedelta(days=1)

    def preview(self, configuration: AssistantConfiguration) -> AssistantPlan:
        self.validate(configuration)
        start, end = self._effective_period(configuration)
        groups = self._effective_groups(configuration)
        effects: list[str] = [
            f"Créerait l'activité « {configuration.name.strip()} ».",
            f"Créerait {len(groups)} groupe(s) : {', '.join(groups)}.",
        ]
        if configuration.responsible_name.strip():
            effects.append(f"Ajouterait le responsable « {configuration.responsible_name.strip()} ».")
        obligations = len(configuration.piece_ids) + len(configuration.cotisation_ids) + len(configuration.information_ids)
        if obligations:
            effects.append(f"Créerait {obligations} lien(s) d'obligation/renseignement.")
        if configuration.agreement_number.strip():
            effects.append(f"Ajouterait l'agrément « {configuration.agreement_number.strip()} ».")

        openings = 0
        if configuration.code in {"sejour", "stage"}:
            openings = (end - start).days + 1
            openings *= len(groups)
            unit_label = "Journée Camp" if configuration.code == "sejour" else "Journée Stage"
            effects.append(f"Créerait l'unité et le remplissage « {unit_label} ».")
        elif configuration.code == "annuelle" and configuration.track_sessions:
            weekdays = set(configuration.session_weekdays)
            openings = sum(1 for day in self._date_range(start, end) if day.weekday() in weekdays) * len(groups)
            effects.append("Créerait l'unité et le remplissage « Séance ».")
        elif configuration.code == "cantine":
            effects.append("Créerait l'unité et le remplissage « Repas » ; le calendrier resterait à compléter.")
        elif configuration.code == "sorties":
            effects.append("Créerait l'unité événementielle et le remplissage « Sortie » ; les sorties resteraient à saisir au calendrier.")
        if openings:
            effects.append(f"Créerait {openings} ouverture(s) de calendrier.")

        categories = tuple(name.strip() for name in configuration.pricing_categories if name.strip()) or ("Catégorie unique",)
        effects.append(f"Créerait {len(categories)} catégorie(s) tarifaire(s).")
        if configuration.code == "sorties":
            effects.append("Créerait un tarif journalier basé sur le montant de l'évènement.")
        elif configuration.pricing_mode == "fixed":
            effects.append(f"Créerait un tarif simple de {configuration.amount:.2f} € par catégorie.")
        elif configuration.pricing_mode == "free":
            effects.append("L'activité serait déclarée gratuite : aucune ligne tarifaire ne serait créée.")
        else:
            effects.append("La tarification détaillée resterait à finaliser dans l'onglet Tarification.")

        warnings: list[str] = []
        if configuration.code == "annuelle" and configuration.track_sessions and not configuration.session_weekdays:
            warnings.append("Le pointage est activé mais aucun jour de séance n'est coché : aucune ouverture ne sera créée.")
        if configuration.code in {"cantine", "sorties"}:
            warnings.append("Comme dans l'assistant historique, les dates d'ouverture doivent ensuite être renseignées dans le calendrier.")
        if configuration.pricing_mode == "later" and configuration.code != "sorties":
            warnings.append("Une catégorie tarifaire sera créée, mais aucun tarif ne sera facturable avant finalisation.")
        return AssistantPlan(configuration.code, "Simulation de l'assistant", tuple(effects), tuple(warnings))

    def generate(self, configuration: AssistantConfiguration) -> int:
        """Génère l'activité en une transaction réelle et retourne son ID."""
        self.validate(configuration)
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            start, end = self._effective_period(configuration)
            activity_id = self._insert(
                cursor,
                placeholder,
                "activites",
                {
                    "date_creation": dt.date.today().isoformat(),
                    "nom": configuration.name.strip(),
                    "abrege": create_abbreviation(configuration.name),
                    "date_debut": start.isoformat(),
                    "date_fin": end.isoformat(),
                    "nbre_inscrits_max": configuration.max_members or None,
                },
            )

            for type_id in sorted(set(int(value) for value in configuration.activity_group_type_ids)):
                self._insert_no_id(
                    cursor,
                    placeholder,
                    "groupes_activites",
                    {"IDtype_groupe_activite": type_id, "IDactivite": activity_id},
                )

            if configuration.agreement_number.strip():
                self._insert(
                    cursor,
                    placeholder,
                    "agrements",
                    {
                        "IDactivite": activity_id,
                        "agrement": configuration.agreement_number.strip(),
                        "date_debut": UNLIMITED_START.isoformat(),
                        "date_fin": UNLIMITED_END.isoformat(),
                    },
                )

            if configuration.responsible_name.strip():
                self._insert(
                    cursor,
                    placeholder,
                    "responsables_activite",
                    {
                        "IDactivite": activity_id,
                        "sexe": configuration.responsible_gender,
                        "nom": configuration.responsible_name.strip(),
                        "fonction": configuration.responsible_function.strip() or None,
                        "defaut": 1,
                    },
                )

            for piece_id in sorted(set(int(value) for value in configuration.piece_ids)):
                self._insert_no_id(
                    cursor,
                    placeholder,
                    "pieces_activites",
                    {"IDactivite": activity_id, "IDtype_piece": piece_id},
                )
            for cotisation_id in sorted(set(int(value) for value in configuration.cotisation_ids)):
                self._insert_no_id(
                    cursor,
                    placeholder,
                    "cotisations_activites",
                    {"IDactivite": activity_id, "IDtype_cotisation": cotisation_id},
                )
            for information_id in sorted(set(int(value) for value in configuration.information_ids)):
                self._insert_no_id(
                    cursor,
                    placeholder,
                    "renseignements_activites",
                    {"IDactivite": activity_id, "IDtype_renseignement": information_id},
                )

            group_ids = self._create_groups(cursor, placeholder, activity_id, configuration)
            unit_ids: list[int] = []
            filling_ids: list[int] = []
            if configuration.code == "annuelle" and configuration.track_sessions:
                unit_id, filling_id = self._create_unit_pair(
                    cursor, placeholder, activity_id, "Séance", "SEANCE", "Unitaire", 1
                )
                unit_ids.append(unit_id); filling_ids.append(filling_id)
                self._create_annual_openings(
                    cursor, placeholder, activity_id, group_ids, unit_id, configuration
                )
            elif configuration.code in {"sejour", "stage"}:
                label, short = ("Journée Camp", "JC") if configuration.code == "sejour" else ("Journée Stage", "JS")
                unit_id, filling_id = self._create_unit_pair(
                    cursor, placeholder, activity_id, label, short, "Unitaire", 1
                )
                unit_ids.append(unit_id); filling_ids.append(filling_id)
                self._create_daily_openings_and_fill(
                    cursor,
                    placeholder,
                    activity_id,
                    group_ids,
                    unit_id,
                    filling_id,
                    start,
                    end,
                    configuration.max_members,
                )
            elif configuration.code == "cantine":
                unit_id, filling_id = self._create_unit_pair(
                    cursor, placeholder, activity_id, "Repas", "R", "Unitaire", 1
                )
                unit_ids.append(unit_id); filling_ids.append(filling_id)
            elif configuration.code == "sorties":
                unit_id, filling_id = self._create_unit_pair(
                    cursor, placeholder, activity_id, "Sortie", "SORTIE", "Evenement", 1
                )
                unit_ids.append(unit_id); filling_ids.append(filling_id)

            self._create_pricing(
                cursor,
                placeholder,
                activity_id,
                group_ids,
                unit_ids,
                start,
                configuration,
            )
            connection.commit()
            return int(activity_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()

    def _create_groups(self, cursor, placeholder: str, activity_id: int,
                       configuration: AssistantConfiguration) -> list[int]:
        names = self._effective_groups(configuration)
        capacities = tuple(configuration.group_capacities)
        ids: list[int] = []
        for index, name in enumerate(names, start=1):
            max_members = capacities[index - 1] if index - 1 < len(capacities) else None
            ids.append(
                self._insert(
                    cursor,
                    placeholder,
                    "groupes",
                    {
                        "IDactivite": activity_id,
                        "nom": name,
                        "ordre": index,
                        "abrege": "UNIQ" if len(names) == 1 and name == "Groupe unique" else create_abbreviation(name),
                        "nbre_inscrits_max": max_members or None,
                    },
                )
            )
        return ids

    def _create_unit_pair(self, cursor, placeholder: str, activity_id: int, name: str,
                          short_name: str, type_code: str, order: int) -> tuple[int, int]:
        unit_id = self._insert(
            cursor,
            placeholder,
            "unites",
            {
                "IDactivite": activity_id,
                "nom": name,
                "abrege": short_name,
                "type": type_code,
                "date_debut": UNLIMITED_START.isoformat(),
                "date_fin": UNLIMITED_END.isoformat(),
                "repas": 0,
                "ordre": order,
            },
        )
        filling_id = self._insert(
            cursor,
            placeholder,
            "unites_remplissage",
            {
                "IDactivite": activity_id,
                "nom": name,
                "abrege": short_name,
                "seuil_alerte": 5,
                "date_debut": UNLIMITED_START.isoformat(),
                "date_fin": UNLIMITED_END.isoformat(),
                "afficher_page_accueil": 1,
                "afficher_grille_conso": 1,
                "ordre": order,
            },
        )
        self._insert_no_id(
            cursor,
            placeholder,
            "unites_remplissage_unites",
            {"IDunite_remplissage": filling_id, "IDunite": unit_id},
        )
        return unit_id, filling_id

    def _create_annual_openings(self, cursor, placeholder: str, activity_id: int,
                                group_ids: Sequence[int], unit_id: int,
                                configuration: AssistantConfiguration) -> None:
        if configuration.start_date is None or configuration.end_date is None:
            return
        weekdays = set(configuration.session_weekdays)
        if not weekdays:
            return
        for day in self._date_range(configuration.start_date, configuration.end_date):
            if day.weekday() not in weekdays:
                continue
            for group_id in group_ids:
                self._insert_no_id(
                    cursor,
                    placeholder,
                    "ouvertures",
                    {
                        "IDactivite": activity_id,
                        "IDunite": unit_id,
                        "IDgroupe": group_id,
                        "date": day.isoformat(),
                    },
                )

    def _create_daily_openings_and_fill(self, cursor, placeholder: str, activity_id: int,
                                        group_ids: Sequence[int], unit_id: int, filling_id: int,
                                        start: dt.date, end: dt.date,
                                        max_members: int | None) -> None:
        for day in self._date_range(start, end):
            for group_id in group_ids:
                self._insert_no_id(
                    cursor,
                    placeholder,
                    "ouvertures",
                    {
                        "IDactivite": activity_id,
                        "IDunite": unit_id,
                        "IDgroupe": group_id,
                        "date": day.isoformat(),
                    },
                )
                if max_members:
                    self._insert_no_id(
                        cursor,
                        placeholder,
                        "remplissage",
                        {
                            "IDactivite": activity_id,
                            "IDunite_remplissage": filling_id,
                            "IDgroupe": group_id,
                            "date": day.isoformat(),
                            "places": max_members,
                        },
                    )

    def _create_pricing(self, cursor, placeholder: str, activity_id: int,
                        group_ids: Sequence[int], unit_ids: Sequence[int], start: dt.date,
                        configuration: AssistantConfiguration) -> None:
        categories = tuple(name.strip() for name in configuration.pricing_categories if name.strip()) or ("Catégorie unique",)
        category_ids = [
            self._insert(
                cursor,
                placeholder,
                "categories_tarifs",
                {"IDactivite": activity_id, "nom": name},
            )
            for name in categories
        ]

        # L'assistant historique Sorties crée toujours un tarif évènementiel.
        event_pricing = configuration.code == "sorties"
        if configuration.pricing_mode in {"later", "free"} and not event_pricing:
            return

        tariff_name = "Repas" if configuration.code == "cantine" else "Sortie" if event_pricing else configuration.name.strip()
        tariff_name_id = self._insert(
            cursor,
            placeholder,
            "noms_tarifs",
            {"IDactivite": activity_id, "nom": tariff_name},
        )
        tariff_type = "JOURN" if configuration.code in {"cantine", "sorties"} else "FORFAIT"
        method = "montant_evenement" if event_pricing else "montant_unique"
        for category_id in category_ids:
            tariff_id = self._insert(
                cursor,
                placeholder,
                "tarifs",
                {
                    "IDactivite": activity_id,
                    "IDnom_tarif": tariff_name_id,
                    "date_debut": start.isoformat(),
                    "date_fin": None,
                    "type": tariff_type,
                    "methode": method,
                    "categories_tarifs": str(category_id),
                    "groupes": None,
                    "jours_scolaires": "0;1;2;3;4;5;6",
                    "jours_vacances": "0;1;2;3;4;5;6",
                    "tva": 0.0,
                    "label_prestation": "nom_tarif",
                    "etats": "reservation;present;absenti" if tariff_type == "JOURN" else None,
                    "options": "calendrier" if tariff_type == "FORFAIT" and bool(unit_ids) else None,
                    "forfait_saisie_manuelle": 0,
                    "forfait_saisie_auto": 1 if tariff_type == "FORFAIT" else 0,
                    "forfait_suppression_auto": 1 if tariff_type == "FORFAIT" else 0,
                },
            )
            if method == "montant_unique":
                self._insert(
                    cursor,
                    placeholder,
                    "tarifs_lignes",
                    {
                        "IDactivite": activity_id,
                        "IDtarif": tariff_id,
                        "code": method,
                        "num_ligne": 0,
                        "tranche": "1",
                        "montant_unique": float(configuration.amount or 0.0),
                    },
                )
            if tariff_type == "JOURN" and unit_ids:
                combination_id = self._insert(
                    cursor,
                    placeholder,
                    "combi_tarifs",
                    {"IDtarif": tariff_id, "type": "JOURN", "date": None, "quantite_max": None},
                )
                for unit_id in unit_ids:
                    self._insert_no_id(
                        cursor,
                        placeholder,
                        "combi_tarifs_unites",
                        {
                            "IDcombi_tarif": combination_id,
                            "IDtarif": tariff_id,
                            "IDunite": unit_id,
                        },
                    )
