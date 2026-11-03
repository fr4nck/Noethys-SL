"""C19e: perimetre de creation de factures, declaration non habilitante.

Ce module est purement descriptif : aucun acces BDD/Qt, aucun writer,
aucune cle d'authentification. Il n'etablit pas le droit de facturer.
La cle 'facturation_factures'/'creer' est observee dans le generateur wx.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .legacy_write_barrier import (
    Check, PermissionSnapshot, PeriodSnapshot, check_declared_period,
)

_INVOICE_RIGHT = ("facturation_factures", "creer")


def _id(value: object) -> bool:
    return type(value) is int and value > 0


def _ids(value: object) -> tuple[int, ...] | None:
    if not isinstance(value, str) or not value:
        return None
    parts = value.split(";")
    if not parts or any(not p.isascii() or not p.isdecimal() for p in parts):
        return None
    ids = tuple(int(p) for p in parts)
    if any(not _id(i) for i in ids) or len(ids) != len(set(ids)):
        return None
    return ids


@dataclass(frozen=True, slots=True)
class InvoiceLineEvidence:
    prestation_id: int
    activity_id: int
    family_id: int
    payer_id: int
    prestation_date: dt.date
    raw_amount: str | None
    invoice_id: int | None = None


@dataclass(frozen=True, slots=True)
class InvoiceScopeReport:
    selected_activity_ids: tuple[int, ...]
    checked_prestation_ids: tuple[int, ...]
    permissions: tuple[tuple[int, Check], ...]
    periods: tuple[tuple[int, Check], ...]
    findings: tuple[str, ...]
    executable: bool = False

    def __post_init__(self):
        if self.executable:
            raise ValueError("C19e ne peut creer aucune facture.")

    @property
    def summary(self) -> str:
        lines = [
            "C19e - VALIDATION DE PERIMETRE, AUCUNE ECRITURE",
            "Activites demandees : %s" % (
                ", ".join(str(i) for i in self.selected_activity_ids)
                or "AUCUNE"
            ),
            "Prestations controlees : %s" % len(self.checked_prestation_ids),
        ]
        lines.extend(
            "Droit declare activite #%s : %s" % (activity, check.status)
            for activity, check in self.permissions
        )
        lines.extend(
            "Periode prestation #%s : %s" % (prestation, check.status)
            for prestation, check in self.periods
        )
        lines.extend("- " + finding for finding in self.findings)
        lines.append("DECISION : BLOQUE - AUCUNE AUTORISATION D'ECRITURE")
        return "\n".join(lines)


def _check_one_declared_right(
    evidence: PermissionSnapshot | None, activity_id: int
) -> Check:
    """La declaration est un indice, JAMAIS une session authentifiee."""
    if not _id(activity_id):
        return Check("INCONNU", "Activite invalide.")
    if (
        not isinstance(evidence, PermissionSnapshot)
        or not evidence.complete
        or not _id(evidence.actor_id)
        or not isinstance(evidence.rules, Mapping)
    ):
        return Check("INCONNU", "Session authentifiee absente.")
    right = evidence.rules.get(_INVOICE_RIGHT)
    if right == "interdiction":
        return Check("REFUSE", "Interdiction explicite.")
    if right == "autorisation":
        return Check("DECLARE", "Autorisation declaree, non authentifiee.")
    if type(right) is not str or not right.startswith("restriction_"):
        return Check("INCONNU", "Droit absent ou non reconnu.")

    mode, sep, raw_ids = right[len("restriction_"):].partition(":")
    ids = _ids(raw_ids) if sep else None
    if ids is None:
        return Check("INCONNU", "Restriction vide ou mal formee.")
    if mode == "activites":
        return Check(
            "DECLARE" if activity_id in ids else "REFUSE",
            "Activites declarees dans le profil non authentifie.",
        )
    if mode == "groupes":
        groups = evidence.group_activities
        if not isinstance(groups, Mapping):
            return Check("INCONNU", "Groupes non resolus.")
        resolved = set()
        for group in ids:
            members = groups.get(group)
            if (
                not isinstance(members, (tuple, list))
                or not members
                or any(not _id(x) for x in members)
            ):
                return Check("INCONNU", "Groupe absent ou incomplet.")
            resolved.update(members)
        return Check(
            "DECLARE" if activity_id in resolved else "REFUSE",
            "Groupes declares dans le profil non authentifie.",
        )
    return Check("INCONNU", "Mode de restriction inconnu.")


def inspect_invoice_scope(
    *, selected_activities: tuple[int, ...] | None,
    lines: tuple[InvoiceLineEvidence, ...] | None,
    family_id: int | None, payer_id: int | None,
    permissions: PermissionSnapshot | None = None,
    periods: PeriodSnapshot | None = None,
) -> InvoiceScopeReport:
    """Qualifie une proposition fournie, pas des donnees SQL de production.

    Aucune signature, provenance, session, transaction ou droits serveur
    n'est verifie ici. Meme une proposition integralement favorable reste
    INEXECUTABLE.
    """
    findings: list[str] = [
        "SESSION_AUTHENTIFIEE_NON_RACCORDEE",
        "PERIMETRE_SQL_TRANSACTIONNEL_NON_RACCORDE",
        "RECALCUL_ET_NUMEROTATION_WX_NON_RACCORDES",
        "AUCUNE_FACTURATION_POSSIBLE",
    ]
    scope_valid = (
        type(selected_activities) is tuple
        and bool(selected_activities)
        and all(_id(x) for x in selected_activities)
        and len(set(selected_activities)) == len(selected_activities)
    )
    scope = selected_activities if scope_valid else ()
    if not scope_valid:
        findings.append("PERIMETRE_ACTIVITES_VIDE_OU_INVALIDE")
    if not _id(family_id) or not _id(payer_id):
        findings.append("FAMILLE_OU_COMPTE_PAYEUR_NON_QUALIFIE")

    checks = tuple(
        (activity, _check_one_declared_right(permissions, activity))
        for activity in scope
    )
    if any(check.status == "REFUSE" for _, check in checks):
        findings.append("DROIT_INTERDIT_POUR_AU_MOINS_UNE_ACTIVITE")
    if not checks or any(check.status != "DECLARE" for _, check in checks):
        findings.append("DROITS_NON_COMPLETS_SUR_TOUTES_LES_ACTIVITES")

    lines_valid = type(lines) is tuple and bool(lines) and all(
        isinstance(line, InvoiceLineEvidence) for line in lines
    )
    entries = lines if lines_valid else ()
    if not lines_valid:
        findings.append("PRESTATIONS_ABSENTES_OU_INVALIDES")
    seen: set[int] = set()
    actual_activities: set[int] = set()
    dates = []
    for line in entries:
        if not _id(line.prestation_id) or line.prestation_id in seen:
            findings.append("PRESTATION_INVALIDE_OU_DOUBLON")
        else:
            seen.add(line.prestation_id)
        if not _id(line.activity_id):
            findings.append("ACTIVITE_PRESTATION_INVALIDE")
        else:
            actual_activities.add(line.activity_id)
        if (
            not _id(line.family_id) or line.family_id != family_id
            or not _id(line.payer_id) or line.payer_id != payer_id
        ):
            findings.append("COMPTE_PAYEUR_OU_FAMILLE_INCOHERENT")
        if line.invoice_id is not None:
            if _id(line.invoice_id):
                findings.append("PRESTATION_DEJA_FACTUREE")
            else:
                findings.append("ID_FACTURE_INVALIDE")
        if type(line.raw_amount) is not str:
            findings.append("MONTANT_BRUT_NON_QUALIFIE")
        else:
            try:
                if not Decimal(line.raw_amount).is_finite():
                    findings.append("MONTANT_BRUT_NON_FINI")
            except InvalidOperation:
                findings.append("MONTANT_BRUT_NON_NUMERIQUE")
        dates.append(
            (line.prestation_id, check_declared_period(
                periods, consumption_date=line.prestation_date,
                operation="invoice_creation",
            ))
        )
    if scope_valid and actual_activities != set(scope):
        findings.append("ACTIVITES_PRESTATIONS_NON_EXHAUSTIVES")
    if any(check.status != "DECLARE_OUVERT" for _, check in dates):
        findings.append("PERIODES_MANQUANTES_OU_VERROUILLEES")
    return InvoiceScopeReport(
        selected_activity_ids=tuple(scope),
        checked_prestation_ids=tuple(
            line.prestation_id for line in entries if _id(line.prestation_id)
        ),
        permissions=checks, periods=tuple(dates),
        findings=tuple(dict.fromkeys(findings)),
    )
