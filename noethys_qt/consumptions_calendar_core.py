"""Synthese mensuelle de consommations Qt : agrégation SQL indépendante du tableau.

Une consommation = une ligne; aucune somme de prestations, aucun compte
financier. Les résultats ne proviennent jamais des 300 lignes plafonnées.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from typing import Iterable

from .consumptions_core import ALL_STATES, OTHER, STATES, _escape_like


@dataclass(frozen=True, slots=True)
class DayCount:
    date: dt.date
    count: int


def build_month_statement(
    *, year: int, month: int, states: Iterable[str] = ALL_STATES,
    activity_id: int | None = None, individual_id: int | None = None,
    inscription_id: int | None = None, text: str = "", placeholder: str = "?",
) -> tuple[str, tuple[object, ...]]:
    """COUNT(*) groupé par date avec les mêmes filtres que la liste annuelle."""
    if not isinstance(year, int) or not 1900 <= year <= 2098:
        raise ValueError("Année de calendrier hors limites.")
    if not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("Mois de calendrier invalide.")
    if placeholder not in ("?", "%s"):
        raise ValueError("Marqueur SQL non autorisé.")
    if activity_id is not None and (
        not isinstance(activity_id, int) or isinstance(activity_id, bool) or activity_id <= 0
    ):
        raise ValueError("Identifiant d'activité invalide.")
    for name, value in (("individu", individual_id), ("inscription", inscription_id)):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
        ):
            raise ValueError(f"Identifiant {name} invalide.")
    chosen = set(states)
    if not chosen or not chosen <= ALL_STATES:
        raise ValueError("Sélection d'états invalide.")

    first = dt.date(year, month, 1)
    next_month = dt.date(year + (month == 12), month % 12 + 1, 1)
    conditions = [f"c.date >= {placeholder}", f"c.date < {placeholder}"]
    values: list[object] = [first.isoformat(), next_month.isoformat()]

    if chosen != ALL_STATES:
        parts = []
        canonical = [code for code, _label in STATES]
        selected = [code for code in canonical if code in chosen]
        if selected:
            parts.append("c.etat IN (" + ", ".join([placeholder] * len(selected)) + ")")
            values.extend(selected)
        if OTHER in chosen:
            parts.append(
                "(c.etat IS NULL OR c.etat NOT IN ("
                + ", ".join([placeholder] * len(canonical)) + "))"
            )
            values.extend(canonical)
        conditions.append("(" + " OR ".join(parts) + ")")

    if activity_id is not None:
        conditions.append(f"c.IDactivite = {placeholder}")
        values.append(activity_id)
    if individual_id is not None:
        conditions.append(f"c.IDindividu = {placeholder}")
        values.append(individual_id)
    if inscription_id is not None:
        conditions.append(f"c.IDinscription = {placeholder}")
        values.append(inscription_id)

    query = text.strip()
    joins = ""
    if query:
        joins = (
            " LEFT JOIN individus i ON i.IDindividu = c.IDindividu"
            " LEFT JOIN activites a ON a.IDactivite = c.IDactivite"
            " LEFT JOIN unites u ON u.IDunite = c.IDunite"
            " LEFT JOIN groupes g ON g.IDgroupe = c.IDgroupe"
        )
        columns = ("i.nom", "i.prenom", "a.nom", "u.nom", "g.nom")
        patterns = [f"{col} LIKE {placeholder} ESCAPE '!'" for col in columns]
        values.extend([_escape_like(query)] * len(patterns))
        if query.isdecimal() and len(query) <= 18:
            patterns.extend((f"c.IDconso = {placeholder}", f"c.IDindividu = {placeholder}"))
            values.extend((int(query), int(query)))
        conditions.append("(" + " OR ".join(patterns) + ")")

    sql = (
        "SELECT c.date, COUNT(*) FROM consommations c" + joins
        + " WHERE " + " AND ".join(conditions)
        + " GROUP BY c.date ORDER BY c.date ASC"
    )
    return sql, tuple(values)


class ConsumptionCalendarRepository:
    """Lectures par connexion propre, sur le connecteur Qt déjà gardé."""

    def __init__(self, consumption_repository):
        self.consumption_repository = consumption_repository

    def _connect(self):
        return self.consumption_repository.editor_repository._connect()

    def list_activities(self) -> tuple[tuple[int, str], ...]:
        connection, _placeholder = self._connect()
        try:
            if isinstance(connection, sqlite3.Connection):
                connection.execute("PRAGMA query_only = ON")
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT IDactivite, nom FROM activites ORDER BY nom, IDactivite")
                return tuple(
                    (int(row[0]), str(row[1] or f"Activité #{row[0]}"))
                    for row in cursor.fetchall()
                )
            finally:
                cursor.close()
        finally:
            connection.close()

    def month_counts(
        self, *, year: int, month: int, states: Iterable[str] = ALL_STATES,
        activity_id: int | None = None, individual_id: int | None = None,
        inscription_id: int | None = None, text: str = "",
    ) -> tuple[DayCount, ...]:
        chosen = frozenset(states)
        if not chosen:
            return ()  # Rien à lire lorsque les sept cases sont décochées.
        connection, placeholder = self._connect()
        try:
            if isinstance(connection, sqlite3.Connection):
                connection.execute("PRAGMA query_only = ON")
            sql, params = build_month_statement(
                year=year, month=month, states=chosen,
                activity_id=activity_id, individual_id=individual_id,
                inscription_id=inscription_id, text=text, placeholder=placeholder,
            )
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return tuple(
            DayCount(
                date=raw[0] if isinstance(raw[0], dt.date)
                else dt.date.fromisoformat(str(raw[0])[:10]),
                count=int(raw[1]),
            )
            for raw in rows
        )
