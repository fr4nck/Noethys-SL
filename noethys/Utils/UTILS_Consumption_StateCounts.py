# -*- coding: utf-8 -*-
"""Contrat partagé d'agrégation des états STOCKÉS des consommations.

Ce module ne connaît ni wxPython, ni Qt, ni GestionDB, ni famille, ni
écriture métier. Une consommation = une ligne stockée, pas une heure
CAF/AFAS, un paiement, un tarif ou une présence réglementaire.

Contrat de lecture : stored-consumption-state-counts/1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

CONTRACT = "stored-consumption-state-counts/1"
STATES = (
    ("reservation", "Réservation"),
    ("attente", "Attente"),
    ("refus", "Refus"),
    ("present", "Présent"),
    ("absentj", "Absence justifiée"),
    ("absenti", "Absence injustifiée"),
)
OTHER = "__autres__"
ALL_STATES = frozenset(code for code, _label in STATES) | {OTHER}
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


def validate_state_selection(
    *, year: int, activity_id: int | None = None,
    states: Iterable[str] = ALL_STATES,
) -> frozenset[str]:
    """Rejette les paramètres erronés AVANT toute connexion SQL."""
    if not isinstance(year, int) or isinstance(year, bool) or not 1900 <= year <= 2098:
        raise ValueError("Année d'état invalide.")
    if activity_id is not None and (
        not isinstance(activity_id, int) or isinstance(activity_id, bool)
        or activity_id < 1
    ):
        raise ValueError("Identifiant d'activité invalide.")
    try:
        chosen = frozenset(states)
    except TypeError as exc:
        raise ValueError("États sélectionnés invalides.") from exc
    if not chosen <= ALL_STATES:
        raise ValueError("État de consommation non reconnu.")
    return chosen


def build_state_summary_statement(
    *, year: int, activity_id: int | None = None,
    states: Iterable[str] = ALL_STATES, placeholder: str = "?",
) -> tuple[str | None, tuple[object, ...]]:
    """SQL SQLite/MySQL paramétré, résultats limités à sept catégories.

    Aucun nom de colonne ou de table ne vient de l'utilisateur ; les codes
    de classification sont des constantes de cette version du contrat.
    Aucun SELECT n'est émis lorsque la sélection est vide.
    """
    selected = validate_state_selection(
        year=year, activity_id=activity_id, states=states,
    )
    if placeholder not in ("?", "%s"):
        raise ValueError("Marqueur SQL non autorisé.")
    if not selected:
        return None, ()

    known_sql = ", ".join("'" + code + "'" for code in CANONICAL)
    state_code = (
        "CASE WHEN c.etat IN (" + known_sql + ") "
        "THEN c.etat ELSE '" + OTHER + "' END"
    )
    values: list[object] = [f"{year:04d}-01-01", f"{year + 1:04d}-01-01"]
    where = [f"c.date >= {placeholder}", f"c.date < {placeholder}"]

    if activity_id is not None:
        where.append(f"c.IDactivite = {placeholder}")
        values.append(activity_id)

    if selected != ALL_STATES:
        predicates = []
        known_selected = [code for code in CANONICAL if code in selected]
        if known_selected:
            predicates.append(
                "c.etat IN (" + ", ".join([placeholder] * len(known_selected)) + ")"
            )
            values.extend(known_selected)
        if OTHER in selected:
            predicates.append(
                "(c.etat IS NULL OR c.etat NOT IN (" + known_sql + "))"
            )
        where.append("(" + " OR ".join(predicates) + ")")

    sql = (
        "SELECT " + state_code + " AS state_code, COUNT(*) "
        "FROM consommations c WHERE " + " AND ".join(where)
        + " GROUP BY " + state_code
        + " ORDER BY state_code"
    )
    return sql, tuple(values)


def make_status_summary(
    *, year: int, activity_id: int | None = None,
    states: Iterable[str] = ALL_STATES,
    grouped_rows: Iterable[tuple[object, object]] = (),
) -> StatusSummary:
    """Formate les comptes renvoyés par le SQL, de manière déterministe.

    Rejette les doublons, codes inattendus et comptes non entiers ou négatifs
    au lieu d'afficher une synthèse partiellement corrompue.
    """
    selected = validate_state_selection(
        year=year, activity_id=activity_id, states=states,
    )
    counts: dict[str, int] = {}
    for code, count in grouped_rows:
        if not isinstance(code, str) or code not in selected or code in counts:
            raise ValueError("Ligne de regroupement d'états non conforme.")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("Comptage des consommations invalide.")
        counts[code] = count

    rows = tuple(
        StateCount(code, LABELS[code], counts.get(code, 0))
        for code, _label in DISPLAY_STATES if code in selected
    )
    return StatusSummary(
        year=year,
        activity_id=activity_id,
        selected=selected,
        rows=rows,
        total=sum(item.count for item in rows),
    )
