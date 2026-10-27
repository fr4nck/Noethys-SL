"""Consultation pure et lecture SQL bornees des consommations Noethys.

Aucun import wx/Qt, aucune ecriture SQL, aucune addition de montants :
une prestation peut etre partagee par plusieurs consommations.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

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
LABEL_BY_STATE = dict(STATES)
MAX_RESULTS = 300


def state_label(value: str | None) -> str:
    if not value:
        return "Non renseigné"
    return LABEL_BY_STATE.get(value, f"Autre : {value}")


def format_date(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%d/%m/%Y")
    text = str(value)
    try:
        return dt.date.fromisoformat(text[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return text


def format_time(value: object) -> str:
    if value in (None, ""):
        return ""
    text = str(value)
    if len(text) >= 5 and text[2:3] == ":":
        return text[:5]
    return text


@dataclass(frozen=True, slots=True)
class Consumption:
    consumption_id: int
    date: object
    state: str | None
    activity: str
    unit: str
    group: str
    last_name: str
    first_name: str
    start_time: object
    end_time: object
    prestation_id: int | None
    amount: Decimal | None
    individual_id: int | None
    activity_id: int | None
    event_id: int | None = None
    event_name: str = ""

    @property
    def hours_label(self) -> str:
        start, end = format_time(self.start_time), format_time(self.end_time)
        return f"{start}–{end}" if start and end else start or end

    @property
    def amount_label(self) -> str:
        if self.amount is None:
            return ""
        rounded = self.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{rounded:,.2f}".replace(",", " ").replace(".", ",") + " €"


@dataclass(frozen=True, slots=True)
class ConsumptionResult:
    rows: tuple[Consumption, ...]
    has_more: bool


def _escape_like(value: str) -> str:
    return "%" + value.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def build_statement(
    *,
    year: int,
    states: Iterable[str],
    text: str = "",
    activity_id: int | None = None,
    day: dt.date | None = None,
    limit: int = MAX_RESULTS,
    placeholder: str = "?",
) -> tuple[str, tuple[object, ...]]:
    """Requete parametree SQLite/MySQL. Limitation appliquee AVANT le chargement."""
    if not 1900 <= year <= 2098:
        raise ValueError("Année de recherche hors limites (1900–2098).")
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError("Limite de consultation invalide.")
    if placeholder not in ("?", "%s"):
        raise ValueError("Marqueur SQL non autorisé.")
    chosen = set(states)
    if not chosen <= ALL_STATES:
        raise ValueError("État de consommation non reconnu.")
    if not chosen:
        raise ValueError("Aucun état sélectionné.")
    if activity_id is not None and (not isinstance(activity_id, int) or activity_id <= 0):
        raise ValueError("Identifiant d'activité invalide.")
    if day is not None and (
        not isinstance(day, dt.date) or isinstance(day, dt.datetime) or day.year != year
    ):
        raise ValueError("Le jour doit appartenir à l'année sélectionnée.")

    conditions = [f"c.date >= {placeholder}", f"c.date < {placeholder}"]
    values: list[object] = [f"{year:04d}-01-01", f"{year + 1:04d}-01-01"]
    if day is not None:
        conditions.append(f"c.date = {placeholder}")
        values.append(day.isoformat())

    if chosen != ALL_STATES:
        parts: list[str] = []
        known = [code for code, _label in STATES if code in chosen]
        if known:
            parts.append("c.etat IN (" + ", ".join([placeholder] * len(known)) + ")")
            values.extend(known)
        if OTHER in chosen:
            canonical = [code for code, _label in STATES]
            parts.append(
                "(c.etat IS NULL OR c.etat NOT IN ("
                + ", ".join([placeholder] * len(canonical))
                + "))"
            )
            values.extend(canonical)
        conditions.append("(" + " OR ".join(parts) + ")")

    if activity_id is not None:
        conditions.append(f"c.IDactivite = {placeholder}")
        values.append(activity_id)

    query = text.strip()
    if query:
        pattern = _escape_like(query)
        parts = [
            f"{column} LIKE {placeholder} ESCAPE '!'"
            for column in ("i.nom", "i.prenom", "a.nom", "u.nom", "g.nom")
        ]
        values.extend([pattern] * len(parts))
        if query.isdecimal() and len(query) <= 18:
            parts.extend((f"c.IDconso = {placeholder}", f"c.IDindividu = {placeholder}"))
            values.extend((int(query), int(query)))
        conditions.append("(" + " OR ".join(parts) + ")")

    sql = (
        "SELECT c.IDconso, c.date, c.etat, a.nom, u.nom, g.nom, "
        "i.nom, i.prenom, c.heure_debut, c.heure_fin, "
        "c.IDprestation, p.montant, c.IDindividu, c.IDactivite, "
        "c.IDevenement, e.nom "
        "FROM consommations c "
        "LEFT JOIN individus i ON i.IDindividu = c.IDindividu "
        "LEFT JOIN activites a ON a.IDactivite = c.IDactivite "
        "LEFT JOIN unites u ON u.IDunite = c.IDunite "
        "LEFT JOIN groupes g ON g.IDgroupe = c.IDgroupe "
        "LEFT JOIN evenements e ON e.IDevenement = c.IDevenement "
        "LEFT JOIN prestations p ON p.IDprestation = c.IDprestation "
        "WHERE " + " AND ".join(conditions)
        + " ORDER BY c.date DESC, c.IDconso DESC "
        + f"LIMIT {placeholder}"
    )
    values.append(limit + 1)
    return sql, tuple(values)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _amount(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("Montant de prestation non numérique.") from exc
    if not amount.is_finite():
        raise ValueError("Montant de prestation non fini.")
    return amount


class ConsumptionRepository:
    """SELECT sur une connexion distincte par appel, issue du pont natif existant."""

    def __init__(self, editor_repository):
        self.editor_repository = editor_repository

    def search(
        self,
        *,
        year: int,
        states: Iterable[str] = ALL_STATES,
        text: str = "",
        activity_id: int | None = None,
        day: dt.date | None = None,
        limit: int = MAX_RESULTS,
    ) -> ConsumptionResult:
        chosen = frozenset(states)
        if not chosen:
            return ConsumptionResult((), False)  # Aucun acces a la base.
        if not chosen <= ALL_STATES:
            raise ValueError("État de consommation non reconnu.")
        connection, placeholder = self.editor_repository._connect()
        try:
            if isinstance(connection, sqlite3.Connection):
                connection.execute("PRAGMA query_only = ON")
            sql, params = build_statement(
                year=year, states=chosen, text=text,
                activity_id=activity_id, day=day,
                limit=limit, placeholder=placeholder,
            )
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                raw_rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        rows = tuple(
            Consumption(
                consumption_id=int(raw[0]),
                date=raw[1],
                state=None if raw[2] is None else str(raw[2]),
                activity=str(raw[3] or ""),
                unit=str(raw[4] or ""),
                group=str(raw[5] or ""),
                last_name=str(raw[6] or ""),
                first_name=str(raw[7] or ""),
                start_time=raw[8],
                end_time=raw[9],
                prestation_id=_optional_int(raw[10]),
                amount=_amount(raw[11]),
                individual_id=_optional_int(raw[12]),
                activity_id=_optional_int(raw[13]),
                event_id=_optional_int(raw[14]),
                event_name=str(raw[15] or ""),
            )
            for raw in raw_rows[:limit]
        )
        return ConsumptionResult(rows, len(raw_rows) > limit)
