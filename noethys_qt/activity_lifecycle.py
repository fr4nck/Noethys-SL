"""Cycle de vie Qt des activités : création, duplication et suppression.

Ce module reproduit le périmètre historique de ``OL_Activites`` sans importer
wx/GestionDB :
- une création manuelle commence par une ligne ``activites`` datée ;
- une duplication copie le paramétrage, jamais les inscriptions/consommations ;
- une suppression est interdite dès qu'une inscription existe et l'effacement
  du paramétrage est atomique.

La duplication suit la liste de tables de l'Exporter historique d'activités,
avec remappage explicite des identifiants internes. Les références portail vers
les unités de consommation sont également remappées afin d'éviter qu'une copie
pointe vers l'activité source.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, Mapping

from .activity_editor import NativeActivityEditorRepository


@dataclass(frozen=True, slots=True)
class ActivityDeleteCheck:
    activity_id: int
    registrations: int

    @property
    def allowed(self) -> bool:
        return self.registrations == 0


# Ordre de copie équivalent à OL_Activites.Exporter. Les tables parentes sont
# copiées avant les tables qui portent leurs identifiants.
DIRECT_CLONE_PLAN: tuple[tuple[str, str], ...] = (
    ("responsables_activite", "IDactivite"),
    ("groupes_activites", "IDactivite"),
    ("groupes", "IDactivite"),
    ("agrements", "IDactivite"),
    ("pieces_activites", "IDactivite"),
    ("cotisations_activites", "IDactivite"),
    ("renseignements_activites", "IDactivite"),
    ("unites", "IDactivite"),
    ("etiquettes", "IDactivite"),
    ("unites_remplissage", "IDactivite"),
    ("ouvertures", "IDactivite"),
    ("remplissage", "IDactivite"),
    ("categories_tarifs", "IDactivite"),
    ("noms_tarifs", "IDactivite"),
    ("tarifs", "IDactivite"),
    ("tarifs_lignes", "IDactivite"),
    ("portail_periodes", "IDactivite"),
    ("portail_unites", "IDactivite"),
    ("evenements", "IDactivite"),
)

# Tables reliées par un identifiant d'objet et non directement par IDactivite.
# L'ordre est significatif : la combinaison tarifaire doit être créée avant ses
# unités pour que ``IDcombi_tarif`` puisse être remappé vers la nouvelle ligne.
DEPENDENT_CLONE_PLAN: tuple[tuple[str, str, str], ...] = (
    ("unites_groupes", "IDunite", "unites"),
    ("unites_incompat", "IDunite", "unites"),
    ("unites_remplissage_unites", "IDunite_remplissage", "unites_remplissage"),
    ("categories_tarifs_villes", "IDcategorie_tarif", "categories_tarifs"),
    ("combi_tarifs", "IDtarif", "tarifs"),
    ("combi_tarifs_unites", "IDtarif", "tarifs"),
    ("questionnaire_filtres", "IDtarif", "tarifs"),
)


class ActivityLifecycleRepository:
    """Opérations de cycle de vie sur la base Noethys configurée."""

    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont natif volontaire

    @staticmethod
    def _columns(cursor, table: str) -> list[str]:
        cursor.execute(f"SELECT * FROM {table} WHERE 1=0")
        return [str(item[0]) for item in cursor.description or ()]

    @staticmethod
    def _in_clause(placeholder: str, values: Iterable[int]) -> tuple[str, tuple[int, ...]]:
        ids = tuple(int(value) for value in values)
        if not ids:
            return "(NULL)", ()
        return "(" + ", ".join(placeholder for _ in ids) + ")", ids

    def create_activity(self) -> int:
        """Crée la ligne provisoire historique nécessaire aux sous-pages."""
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"INSERT INTO activites (date_creation) VALUES ({placeholder})",
                (dt.date.today().isoformat(),),
            )
            activity_id = int(cursor.lastrowid)
            if activity_id <= 0:
                raise RuntimeError("La base n'a pas retourné l'identifiant de la nouvelle activité.")
            connection.commit()
            return activity_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()

    def delete_check(self, activity_id: int) -> ActivityDeleteCheck:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT COUNT(*) FROM inscriptions WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            registrations = int(cursor.fetchone()[0] or 0)
            return ActivityDeleteCheck(int(activity_id), registrations)
        finally:
            cursor.close(); connection.close()

    def activity_name(self, activity_id: int) -> str:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT nom FROM activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Activité introuvable.")
            return str(row[0] or "")
        finally:
            cursor.close(); connection.close()

    def delete_activity(self, activity_id: int) -> None:
        """Supprime atomiquement le paramétrage si aucune inscription n'existe."""
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT COUNT(*) FROM inscriptions WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            registrations = int(cursor.fetchone()[0] or 0)
            if registrations:
                raise ValueError(
                    "Vous ne pouvez pas supprimer cette activité car "
                    f"{registrations} individu(s) y sont déjà inscrits."
                )

            cursor.execute(
                f"SELECT 1 FROM activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            if cursor.fetchone() is None:
                raise ValueError("Activité introuvable.")

            unit_ids = self._ids(cursor, placeholder, "unites", "IDunite", activity_id)
            fill_ids = self._ids(
                cursor, placeholder, "unites_remplissage", "IDunite_remplissage", activity_id
            )
            tariff_ids = self._ids(cursor, placeholder, "tarifs", "IDtarif", activity_id)
            category_ids = self._ids(
                cursor, placeholder, "categories_tarifs", "IDcategorie_tarif", activity_id
            )

            # Relations dépendantes : les lignes filles sont effacées avant leur
            # parent afin de rester valides lorsque des clés étrangères existent.
            for table, field, ids in (
                ("questionnaire_filtres", "IDtarif", tariff_ids),
                ("combi_tarifs_unites", "IDtarif", tariff_ids),
                ("combi_tarifs", "IDtarif", tariff_ids),
                ("categories_tarifs_villes", "IDcategorie_tarif", category_ids),
                ("unites_groupes", "IDunite", unit_ids),
                ("unites_incompat", "IDunite", unit_ids),
                ("unites_remplissage_unites", "IDunite_remplissage", fill_ids),
            ):
                self._delete_ids(cursor, placeholder, table, field, ids)

            # Données appartenant directement à l'activité. L'activité elle-même
            # est effacée en dernier pour rester compatible avec d'éventuelles FK.
            direct_tables = (
                "responsables_activite",
                "groupes_activites",
                "agrements",
                "pieces_activites",
                "cotisations_activites",
                "renseignements_activites",
                "remplissage",
                "ouvertures",
                "tarifs_lignes",
                "tarifs",
                "noms_tarifs",
                "categories_tarifs",
                "unites_remplissage",
                "unites",
                "etiquettes",
                "portail_periodes",
                "portail_unites",
                "evenements",
                "groupes",
            )
            for table in direct_tables:
                cursor.execute(
                    f"DELETE FROM {table} WHERE IDactivite={placeholder}",
                    (activity_id,),
                )
            cursor.execute(
                f"DELETE FROM activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("La suppression de l'activité n'a pas été appliquée.")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()

    def discard_new_activity(self, activity_id: int) -> None:
        """Nettoie une création annulée, sans laisser de ligne provisoire."""
        self.delete_activity(activity_id)

    def duplicate_activity(self, activity_id: int, new_name: str | None = None) -> int:
        """Duplique uniquement le paramétrage historique de l'activité."""
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            columns = self._columns(cursor, "activites")
            if not columns or columns[0] != "IDactivite":
                raise RuntimeError("Schéma de la table activites inattendu.")
            cursor.execute(
                f"SELECT * FROM activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            source = cursor.fetchone()
            if source is None:
                raise ValueError("Activité introuvable.")
            source_values = dict(zip(columns, source))
            source_name = str(source_values.get("nom") or "")
            source_values["nom"] = new_name if new_name is not None else f"Copie de {source_name}"
            new_id = self._insert_clone(cursor, placeholder, "activites", columns, source_values)

            table_maps: dict[str, dict[int, int]] = {
                "activites": {int(activity_id): int(new_id)}
            }
            field_maps: dict[str, Mapping[int, int]] = {
                "IDactivite": table_maps["activites"],
            }

            # Première passe : objets directement rattachés à l'activité.
            for table, field in DIRECT_CLONE_PLAN:
                rows_map = self._clone_where(
                    cursor,
                    placeholder,
                    table,
                    f"{field}={placeholder}",
                    (activity_id,),
                    field_maps,
                    table_maps,
                )
                table_maps[table] = rows_map
                self._register_reference_map(table, rows_map, field_maps)

            # Deuxième passe : tables de liaison dépendant des nouveaux objets.
            # Les mappings produits ici peuvent eux-mêmes être requis par la
            # table suivante (combi_tarifs -> combi_tarifs_unites).
            for table, field, source_table in DEPENDENT_CLONE_PLAN:
                source_ids = tuple(table_maps.get(source_table, {}).keys())
                if not source_ids:
                    table_maps[table] = {}
                    continue
                in_sql, params = self._in_clause(placeholder, source_ids)
                rows_map = self._clone_where(
                    cursor,
                    placeholder,
                    table,
                    f"{field} IN {in_sql}",
                    params,
                    field_maps,
                    table_maps,
                )
                table_maps[table] = rows_map
                self._register_reference_map(table, rows_map, field_maps)

            # Références dont le nom de colonne ne suffit pas à déduire la cible.
            self._repair_label_parents(cursor, placeholder, activity_id, new_id, table_maps)
            self._repair_activity_psu(cursor, placeholder, activity_id, new_id, table_maps)
            self._repair_string_references(cursor, placeholder, new_id, table_maps)

            connection.commit()
            return int(new_id)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()

    @staticmethod
    def _register_reference_map(
        table: str,
        rows_map: Mapping[int, int],
        field_maps: dict[str, Mapping[int, int]],
    ) -> None:
        key_by_table = {
            "groupes": "IDgroupe",
            "unites": "IDunite",
            "etiquettes": "IDetiquette",
            "unites_remplissage": "IDunite_remplissage",
            "categories_tarifs": "IDcategorie_tarif",
            "noms_tarifs": "IDnom_tarif",
            "tarifs": "IDtarif",
            "portail_periodes": "IDperiode",
            "combi_tarifs": "IDcombi_tarif",
        }
        key = key_by_table.get(table)
        if key and rows_map:
            field_maps[key] = rows_map
        if table == "unites" and rows_map:
            # Les deux noms existent dans les branches/schémas Noethys observés.
            field_maps["IDunite_incompat"] = rows_map
            field_maps["IDunite_incompatible"] = rows_map

    def _clone_where(
        self,
        cursor,
        placeholder: str,
        table: str,
        condition: str,
        params: tuple[object, ...],
        field_maps: Mapping[str, Mapping[int, int]],
        table_maps: Mapping[str, Mapping[int, int]],
    ) -> dict[int, int]:
        columns = self._columns(cursor, table)
        if not columns:
            raise RuntimeError(f"Table {table} sans colonnes.")
        key = columns[0]
        cursor.execute(f"SELECT * FROM {table} WHERE {condition}", params)
        rows = cursor.fetchall()
        result: dict[int, int] = {}
        for row in rows:
            values = dict(zip(columns, row))
            old_id = int(values[key])
            for field, mapping in field_maps.items():
                if field == key or field not in values or values[field] is None:
                    continue
                try:
                    old_ref = int(values[field])
                except (TypeError, ValueError):
                    continue
                if old_ref in mapping:
                    values[field] = mapping[old_ref]

            if table == "tarifs":
                values["categories_tarifs"] = self._remap_id_string(
                    values.get("categories_tarifs"), table_maps.get("categories_tarifs", {})
                )
                values["groupes"] = self._remap_id_string(
                    values.get("groupes"), table_maps.get("groupes", {})
                )
            new_row_id = self._insert_clone(cursor, placeholder, table, columns, values)
            result[old_id] = new_row_id
        return result

    @staticmethod
    def _insert_clone(cursor, placeholder: str, table: str, columns: list[str], values: Mapping[str, object]) -> int:
        key = columns[0]
        insert_columns = [column for column in columns if column != key]
        sql = (
            f"INSERT INTO {table} ({', '.join(insert_columns)}) VALUES ("
            + ", ".join(placeholder for _ in insert_columns)
            + ")"
        )
        cursor.execute(sql, tuple(values.get(column) for column in insert_columns))
        new_id = int(cursor.lastrowid)
        if new_id <= 0:
            raise RuntimeError(f"La duplication de {table} n'a pas retourné d'identifiant.")
        return new_id

    @staticmethod
    def _remap_id_string(value: object, mapping: Mapping[int, int]) -> object:
        if value in (None, ""):
            return value
        result: list[str] = []
        for raw in str(value).split(";"):
            raw = raw.strip()
            if not raw:
                continue
            try:
                old_id = int(raw)
            except ValueError:
                result.append(raw)
                continue
            result.append(str(mapping.get(old_id, old_id)))
        return ";".join(result)

    def _repair_label_parents(self, cursor, placeholder: str, source_activity: int, new_activity: int,
                              table_maps: Mapping[str, Mapping[int, int]]) -> None:
        mapping = table_maps.get("etiquettes", {})
        if not mapping:
            return
        cursor.execute(
            f"SELECT IDetiquette, parent FROM etiquettes WHERE IDactivite={placeholder}",
            (source_activity,),
        )
        for old_id, old_parent in cursor.fetchall():
            if old_parent is None or int(old_id) not in mapping:
                continue
            new_parent = mapping.get(int(old_parent))
            if new_parent is not None:
                cursor.execute(
                    f"UPDATE etiquettes SET parent={placeholder} WHERE IDetiquette={placeholder} AND IDactivite={placeholder}",
                    (new_parent, mapping[int(old_id)], new_activity),
                )

    def _repair_activity_psu(self, cursor, placeholder: str, source_activity: int, new_activity: int,
                             table_maps: Mapping[str, Mapping[int, int]]) -> None:
        columns = set(self._columns(cursor, "activites"))
        specs = (
            ("psu_unite_prevision", "unites"),
            ("psu_unite_presence", "unites"),
            ("psu_tarif_forfait", "tarifs"),
            ("psu_etiquette_rtt", "etiquettes"),
        )
        available = [(field, table) for field, table in specs if field in columns]
        if not available:
            return
        cursor.execute(
            f"SELECT {', '.join(field for field, _table in available)} FROM activites WHERE IDactivite={placeholder}",
            (source_activity,),
        )
        row = cursor.fetchone()
        updates: list[str] = []; params: list[object] = []
        for value, (field, table) in zip(row, available):
            replacement = None if value is None else table_maps.get(table, {}).get(int(value), value)
            updates.append(f"{field}={placeholder}"); params.append(replacement)
        params.append(new_activity)
        cursor.execute(
            f"UPDATE activites SET {', '.join(updates)} WHERE IDactivite={placeholder}",
            tuple(params),
        )

    def _repair_string_references(self, cursor, placeholder: str, new_activity: int,
                                  table_maps: Mapping[str, Mapping[int, int]]) -> None:
        unit_map = table_maps.get("unites", {})
        if unit_map:
            columns = set(self._columns(cursor, "portail_unites"))
            fields = [name for name in ("unites_principales", "unites_secondaires") if name in columns]
            if fields:
                cursor.execute(
                    f"SELECT IDunite, {', '.join(fields)} FROM portail_unites WHERE IDactivite={placeholder}",
                    (new_activity,),
                )
                for row in cursor.fetchall():
                    updates = [f"{field}={placeholder}" for field in fields]
                    params = [self._remap_id_string(value, unit_map) for value in row[1:]]
                    params.append(int(row[0]))
                    cursor.execute(
                        f"UPDATE portail_unites SET {', '.join(updates)} WHERE IDunite={placeholder}",
                        tuple(params),
                    )

    @staticmethod
    def _ids(cursor, placeholder: str, table: str, key: str, activity_id: int) -> tuple[int, ...]:
        cursor.execute(
            f"SELECT {key} FROM {table} WHERE IDactivite={placeholder}",
            (activity_id,),
        )
        return tuple(int(row[0]) for row in cursor.fetchall())

    def _delete_ids(self, cursor, placeholder: str, table: str, field: str,
                    ids: Iterable[int]) -> None:
        in_sql, params = self._in_clause(placeholder, ids)
        if not params:
            return
        cursor.execute(f"DELETE FROM {table} WHERE {field} IN {in_sql}", params)
