"""C19e : lecture de PRESTATIONS fictives C13, puis contrat non executable.

Ce lecteur est volontairement absent de la production Qt :
 - aucun import wx, aucune table utilisateurs/PAI et aucun code writer ;
 - chemin temporaire et marqueurs fictifs verifies AVANT connexion ;
 - SQLite URI mode=ro + query_only, marqueurs reverifies dans la connexion ;
 - perimetre explicite d'activites, familles, payeur et prestations ;
 - aucun partage d'une prestation entre plusieurs activites accepte.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from .c19b_operational_guard import can_demo_inscription_invoices
from .invoice_scope_contract import (
    InvoiceLineEvidence, inspect_invoice_scope,
)

_MARKER_C8 = "NOETHYS_QT_C8_ONLY_FAKE_FIXTURE_20261027"
_MARKER_C13 = "C13_FINANCE_FICTIVE_ONLY"
_MAX_LINES = 64


def _valid_ids(ids, *, label):
    if (
        type(ids) is not tuple or not ids or len(ids) > _MAX_LINES
        or any(type(value) is not int or value <= 0 for value in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("%s : selection exacte non vide et sans doublons exigee" % label)
    return ids


def _id(value, label):
    if type(value) is not int or value <= 0:
        raise ValueError("%s : identifiant non qualifie" % label)


class C19eFictiveInvoiceScopeRepository:
    """Relecture de lignes inventees avant controle, aucune facturation."""

    def __init__(self, sqlite_path):
        self._path = Path(sqlite_path) if sqlite_path is not None else None

    def inspect(
        self, *, activity_ids, prestation_ids, family_id, payer_id,
        permissions=None, periods=None,
    ):
        selected = _valid_ids(activity_ids, label="Activites")
        requested = _valid_ids(prestation_ids, label="Prestations")
        _id(family_id, "Famille")
        _id(payer_id, "Compte payeur")

        if not can_demo_inscription_invoices(
            self._path, read_only_demo=True
        ):
            raise PermissionError("Controle C19e hors fixture fictive interdit.")

        uri = self._path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=3)) as db:
            db.execute("PRAGMA query_only = ON")
            db.execute("BEGIN")
            c8 = db.execute("SELECT token FROM c8_marker").fetchone()
            c13 = db.execute("SELECT token FROM c13_marker").fetchone()
            if c8 != (_MARKER_C8,) or c13 != (_MARKER_C13,):
                raise PermissionError("Fixture modifiee apres verification initiale.")
            placeholders = ",".join("?" for _ in requested)
            # Toutes les consommations liees sont regardees : une prestation
            # attribuee a deux activites n'est jamais reduite a la premiere.
            results = db.execute(
                "SELECT p.IDprestation, p.IDcompte_payeur, cp.IDfamille, "
                "p.date, p.montant, p.IDfacture, c.IDactivite "
                "FROM prestations p "
                "LEFT JOIN comptes_payeurs cp "
                "ON cp.IDcompte_payeur=p.IDcompte_payeur "
                "LEFT JOIN consommations c ON c.IDprestation=p.IDprestation "
                "WHERE p.IDprestation IN (" + placeholders + ") "
                "ORDER BY p.IDprestation, c.IDconso",
                requested,
            ).fetchall()
            db.execute("ROLLBACK")

        by_id: dict[int, list[tuple]] = {}
        for rec in results:
            by_id.setdefault(rec[0], []).append(rec)

        rows: list[InvoiceLineEvidence] = []
        for prestation in requested:
            records = by_id.get(prestation, ())
            if not records:
                # Absente => jamais omise du controle (fail-closed).
                rows.append(InvoiceLineEvidence(
                    prestation, 0, 0, 0, None, None, None,
                ))
                continue
            first = records[0]
            activities = {item[6] for item in records}
            # Toutes les activites sont visibles : ambiguites signalees
            # plutot que rattacher arbitrairement la prestation a une activite.
            activity = next(iter(activities)) if len(activities) == 1 else 0
            if activity is None:
                activity = 0
            rows.append(InvoiceLineEvidence(
                prestation_id=first[0],
                activity_id=activity,
                family_id=first[2],
                payer_id=first[1],
                prestation_date=first[3],
                raw_amount=first[4],
                invoice_id=first[5],
            ))
        return inspect_invoice_scope(
            selected_activities=selected,
            lines=tuple(rows),
            family_id=family_id,
            payer_id=payer_id,
            permissions=permissions,
            periods=periods,
        )
