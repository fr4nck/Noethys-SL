"""Adaptateur Qt/SQL vers le moteur commun d'états C17.

Aucun calcul de présence réglementaire, de facture ou de montant.
La normalisation et la requête SQL vivent dans noethys/Utils, sans UI.
"""
from __future__ import annotations

import sqlite3
from typing import Iterable

from noethys.Utils.UTILS_Consumption_StateCounts import (
    CONTRACT, STATES, OTHER, ALL_STATES, DISPLAY_STATES, LABELS, CANONICAL,
    StateCount, StatusSummary, validate_state_selection,
    build_state_summary_statement, make_status_summary,
)


class ConsumptionStatusRepository:
    """Connexion Qt gardée ; requêtes et résultats du moteur partagé."""

    def __init__(self, consumption_repository):
        self.consumption_repository = consumption_repository

    def summary(
        self, *, year: int, activity_id: int | None = None,
        states: Iterable[str] = ALL_STATES,
    ) -> StatusSummary:
        selected = validate_state_selection(
            year=year, activity_id=activity_id, states=states,
        )
        if not selected:
            # Barrière ancienne C16 : aucune connexion pour une sélection vide.
            return make_status_summary(
                year=year, activity_id=activity_id, states=selected,
            )
        connection, placeholder = (
            self.consumption_repository.editor_repository._connect()
        )
        try:
            if isinstance(connection, sqlite3.Connection):
                connection.execute("PRAGMA query_only=ON")
            sql, params = build_state_summary_statement(
                year=year, activity_id=activity_id, states=selected,
                placeholder=placeholder,
            )
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                grouped = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return make_status_summary(
            year=year, activity_id=activity_id, states=selected,
            grouped_rows=grouped,
        )
