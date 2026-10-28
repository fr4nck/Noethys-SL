"""C16 — comptages par états stockés, moteur de lecture indépendant de Qt.

Une consommation = une ligne. Aucun taux de présence, montant, facture,
taux CAF/AFAS, absence justifiée vérifiée ou attestation n'est calculé.
Réutilise les codes et libellés de consumptions_core (contrat déjà testé).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable

from .consumptions_core import ALL_STATES, OTHER, STATES

CONTRACT = "stored-consumption-state-counts/1"
DISPLAY_STATES = (*STATES, (OTHER, "Autres / non renseignés"))
LABELS = dict(DISPLAY_STATES)
CANONICAL = tuple(code for code, _label in STATES)


@dataclass(frozen=True, slots=True)
class StateCount:
    code: str
    label: str
    count: int


@dataclass(frozen=True, slots=True)
class StatusSummary:
    year: int
    activity_id: int | None
    selected: frozenset[str]
    rows: tuple[StateCount, ...]
    total: int


def validate_state_selection(*, year, activity_id=None, states=ALL_STATES):
    if not isinstance(year, int) or isinstance(year, bool) or not 1900 <= year <= 2098:
        raise ValueError("Année d'état invalide.")
    if activity_id is not None and (
        not isinstance(activity_id, int) or isinstance(activity_id, bool)
        or activity_id < 1
    ):
        raise ValueError("Identifiant d'activité invalide.")
    try:
        selected = frozenset(states)
    except TypeError as exc:
        raise ValueError("États sélectionnés invalides.") from exc
    if not selected <= ALL_STATES:
        raise ValueError("État de consommation non reconnu.")
    return selected


def build_state_summary_statement(
    *, year: int, activity_id: int | None = None,
    states: Iterable[str] = ALL_STATES, placeholder: str = "?",
):
    selected = validate_state_selection(
        year=year, activity_id=activity_id, states=states,
    )
    if placeholder not in ("?", "%s"):
        raise ValueError("Marqueur SQL non autorisé.")
    if not selected:
        # Sans états sélectionnés, aucune requête SQL ne doit s'exécuter.
        return None, ()
    known_sql = ", ".join("'" + code + "'" for code in CANONICAL)
    # Groupement borné : les valeurs hors nomenclature et NULL sont
    # réunies dans la seule catégorie "Autres", jamais perdues.
    state_code = (
        "CASE WHEN c.etat IN (" + known_sql + ") "
        "THEN c.etat ELSE '" + OTHER + "' END"
    )
    values = [f"{year:04d}-01-01", f"{year+1:04d}-01-01"]
    where = [f"c.date >= {placeholder}", f"c.date < {placeholder}"]
    if activity_id is not None:
        where.append(f"c.IDactivite = {placeholder}")
        values.append(activity_id)
    if selected != ALL_STATES:
        clauses = []
        included = [code for code in CANONICAL if code in selected]
        if included:
            clauses.append("c.etat IN (" + ", ".join(
                [placeholder] * len(included)
            ) + ")")
            values.extend(included)
        if OTHER in selected:
            clauses.append(
                "(c.etat IS NULL OR c.etat NOT IN (" + known_sql + "))"
            )
        where.append("(" + " OR ".join(clauses) + ")")
    sql = (
        "SELECT " + state_code + " AS state_code, COUNT(*) "
        "FROM consommations c WHERE " + " AND ".join(where)
        + " GROUP BY " + state_code
        + " ORDER BY state_code"
    )
    return sql, tuple(values)


class ConsumptionStatusRepository:
    """Adaptateur SELECT-only réutilisant la connexion Qt existante."""

    def __init__(self, consumption_repository):
        self.consumption_repository = consumption_repository

    def summary(
        self, *, year: int, activity_id: int | None = None,
        states: Iterable[str] = ALL_STATES,
    ) -> StatusSummary:
        selected = validate_state_selection(
            year=year, activity_id=activity_id, states=states
        )
        if not selected:
            return StatusSummary(year, activity_id, selected, (), 0)
        connection, placeholder = self.consumption_repository.editor_repository._connect()
        try:
            if isinstance(connection, sqlite3.Connection):
                connection.execute("PRAGMA query_only=ON")
            statement, params = build_state_summary_statement(
                year=year, activity_id=activity_id,
                states=selected, placeholder=placeholder,
            )
            cursor = connection.cursor()
            try:
                cursor.execute(statement, params)
                values = {str(code): int(count) for code, count in cursor.fetchall()}
            finally:
                cursor.close()
        finally:
            connection.close()
        if not set(values) <= selected:
            raise RuntimeError("Le regroupement d'états a retourné un état exclu.")
        rows = tuple(
            StateCount(code, LABELS[code], values.get(code, 0))
            for code, _label in DISPLAY_STATES if code in selected
        )
        return StatusSummary(
            year=year, activity_id=activity_id, selected=selected,
            rows=rows, total=sum(row.count for row in rows),
        )
