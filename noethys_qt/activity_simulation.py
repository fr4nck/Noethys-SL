"""Prévisualisation sans écriture des opérations de cycle de vie Activités.

Le mode simulation est un garde-fou supplémentaire du rail Qt : il interroge la
base réellement configurée, calcule ce qui serait créé/copier/supprimé et ne
lance aucune instruction INSERT/UPDATE/DELETE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .activity_editor import NativeActivityEditorRepository


@dataclass(frozen=True, slots=True)
class SimulationReport:
    title: str
    lines: tuple[str, ...]
    blocked: bool = False

    def as_text(self) -> str:
        prefix = "OPÉRATION BLOQUÉE\n\n" if self.blocked else "AUCUNE ÉCRITURE NE SERA EFFECTUÉE\n\n"
        return prefix + self.title + "\n\n" + "\n".join(f"• {line}" for line in self.lines)


class ActivitySimulationRepository:
    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001

    @staticmethod
    def _columns(cursor, table: str) -> set[str]:
        try:
            cursor.execute(f"SELECT * FROM {table} WHERE 1=0")
        except Exception:
            return set()
        return {str(item[0]) for item in cursor.description or ()}

    @classmethod
    def _count(cls, cursor, placeholder: str, table: str, field: str,
               values: Iterable[int]) -> int:
        if field not in cls._columns(cursor, table):
            return 0
        ids = tuple(dict.fromkeys(int(value) for value in values))
        if not ids:
            return 0
        marks = ", ".join(placeholder for _ in ids)
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {field} IN ({marks})", ids)
        return int(cursor.fetchone()[0] or 0)

    @classmethod
    def _ids(cls, cursor, placeholder: str, table: str, key: str,
             activity_id: int) -> tuple[int, ...]:
        columns = cls._columns(cursor, table)
        if key not in columns or "IDactivite" not in columns:
            return ()
        cursor.execute(
            f"SELECT {key} FROM {table} WHERE IDactivite={placeholder}",
            (activity_id,),
        )
        return tuple(int(row[0]) for row in cursor.fetchall())

    @classmethod
    def _direct_count(cls, cursor, placeholder: str, table: str, activity_id: int) -> int:
        if "IDactivite" not in cls._columns(cursor, table):
            return 0
        cursor.execute(
            f"SELECT COUNT(*) FROM {table} WHERE IDactivite={placeholder}",
            (activity_id,),
        )
        return int(cursor.fetchone()[0] or 0)

    def _activity_name(self, cursor, placeholder: str, activity_id: int) -> str:
        cursor.execute(f"SELECT nom FROM activites WHERE IDactivite={placeholder}", (activity_id,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Activité introuvable.")
        return str(row[0] or "")

    def _configuration_counts(self, cursor, placeholder: str, activity_id: int) -> list[tuple[str, int]]:
        direct_tables = (
            ("responsables_activite", "responsable(s)"),
            ("groupes_activites", "lien(s) de groupe d'activités"),
            ("groupes", "groupe(s)"),
            ("agrements", "agrément(s)"),
            ("pieces_activites", "pièce(s) obligatoire(s)"),
            ("cotisations_activites", "cotisation(s) obligatoire(s)"),
            ("renseignements_activites", "renseignement(s)"),
            ("unites", "unité(s)"),
            ("etiquettes", "étiquette(s)"),
            ("unites_remplissage", "unité(s) de remplissage"),
            ("ouvertures", "ouverture(s)"),
            ("remplissage", "ligne(s) de remplissage"),
            ("categories_tarifs", "catégorie(s) tarifaire(s)"),
            ("noms_tarifs", "nom(s) de prestation"),
            ("tarifs", "tarif(s)"),
            ("tarifs_lignes", "ligne(s) tarifaire(s)"),
            ("portail_periodes", "période(s) portail"),
            ("portail_unites", "unité(s) portail"),
            ("evenements", "évènement(s)"),
        )
        result = [
            (label, self._direct_count(cursor, placeholder, table, activity_id))
            for table, label in direct_tables
        ]

        unit_ids = self._ids(cursor, placeholder, "unites", "IDunite", activity_id)
        fill_ids = self._ids(cursor, placeholder, "unites_remplissage", "IDunite_remplissage", activity_id)
        tariff_ids = self._ids(cursor, placeholder, "tarifs", "IDtarif", activity_id)
        category_ids = self._ids(cursor, placeholder, "categories_tarifs", "IDcategorie_tarif", activity_id)
        combo_ids: tuple[int, ...] = ()
        combo_columns = self._columns(cursor, "combi_tarifs")
        if "IDcombi_tarif" in combo_columns and "IDtarif" in combo_columns and tariff_ids:
            marks = ", ".join(placeholder for _ in tariff_ids)
            cursor.execute(f"SELECT IDcombi_tarif FROM combi_tarifs WHERE IDtarif IN ({marks})", tariff_ids)
            combo_ids = tuple(int(row[0]) for row in cursor.fetchall())

        dependent = (
            ("unites_groupes", "IDunite", unit_ids, "lien(s) unité/groupe"),
            ("unites_incompat", "IDunite", unit_ids, "incompatibilité(s) d'unités"),
            ("unites_remplissage_unites", "IDunite_remplissage", fill_ids, "lien(s) remplissage/unité"),
            ("categories_tarifs_villes", "IDcategorie_tarif", category_ids, "ville(s) tarifaire(s)"),
            ("combi_tarifs", "IDtarif", tariff_ids, "combinaison(s) tarifaire(s)"),
            ("questionnaire_filtres", "IDtarif", tariff_ids, "filtre(s) questionnaire"),
        )
        result.extend(
            (label, self._count(cursor, placeholder, table, field, ids))
            for table, field, ids, label in dependent
        )
        combo_unit_columns = self._columns(cursor, "combi_tarifs_unites")
        if "IDtarif" in combo_unit_columns:
            count = self._count(cursor, placeholder, "combi_tarifs_unites", "IDtarif", tariff_ids)
        else:
            count = self._count(cursor, placeholder, "combi_tarifs_unites", "IDcombi_tarif", combo_ids)
        result.append(("unité(s) de combinaison tarifaire", count))
        return [(label, count) for label, count in result if count]

    def manual_create_report(self) -> SimulationReport:
        return SimulationReport(
            "Création manuelle",
            (
                "Créerait une ligne provisoire dans activites avec la date du jour.",
                "Ouvrirait ensuite la fiche Qt complète.",
                "Une annulation supprimerait intégralement cette ligne provisoire.",
            ),
        )

    def duplicate_report(self, activity_id: int) -> SimulationReport:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            name = self._activity_name(cursor, placeholder, activity_id)
            counts = self._configuration_counts(cursor, placeholder, activity_id)
            total = 1 + sum(count for _label, count in counts)
            lines = [
                f"Créerait « Copie de {name} » avec un nouvel identifiant.",
                f"Copierait environ {total} ligne(s) de paramétrage avec remappage des identifiants internes.",
                "Ne copierait aucune inscription ni consommation.",
                *[f"{count} {label}" for label, count in counts],
            ]
            return SimulationReport("Duplication", tuple(lines))
        finally:
            cursor.close(); connection.close()

    def delete_report(self, activity_id: int) -> SimulationReport:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            name = self._activity_name(cursor, placeholder, activity_id)
            registrations = self._direct_count(cursor, placeholder, "inscriptions", activity_id)
            if registrations:
                return SimulationReport(
                    "Suppression",
                    (
                        f"« {name} » possède {registrations} inscription(s).",
                        "Le garde-fou historique interdit donc toute suppression.",
                    ),
                    blocked=True,
                )
            counts = self._configuration_counts(cursor, placeholder, activity_id)
            total = 1 + sum(count for _label, count in counts)
            return SimulationReport(
                "Suppression",
                (
                    f"Supprimerait « {name} ».",
                    f"Supprimerait environ {total} ligne(s) de paramétrage dans une transaction unique.",
                    "Les deux confirmations historiques resteraient requises en mode réel.",
                    *[f"{count} {label}" for label, count in counts],
                ),
            )
        finally:
            cursor.close(); connection.close()
