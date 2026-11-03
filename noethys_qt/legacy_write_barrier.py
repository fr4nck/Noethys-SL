"""C19d - evaluation conservatrice, NON executable, des controles wx.

Sources lues dans la branche wx du 03/11/2026 :
  Utils/UTILS_Utilisateurs.py : VerificationDroits,
  Utils/UTILS_Gestion.py : Gestion.Verification,
  Ctrl/CTRL_Grille_cases.py : trois implementations de ModifieEtat.

Les valeurs de cette API sont des *declarations fournies par des tests*
et non des habilitations ou verrous de production. Aucune connexion SQL,
aucun utilisateur authentifie, aucun calcul de facture et aucun writer.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Mapping

from .billing_preflight_core import BillingObservation

FINANCIAL = frozenset(("reservation", "present", "absenti"))
NON_FINANCIAL = frozenset(("attente", "refus", "absentj"))
STATES = FINANCIAL | NON_FINANCIAL

_OPERATIONS = frozenset(("consumption_state_change", "invoice_creation"))


@dataclass(frozen=True, slots=True)
class PermissionSnapshot:
    """Capture de declaration, JAMAIS une session authentifiee par Qt."""

    actor_id: int | None
    rules: Mapping[tuple[str, str], str] | None
    complete: bool = False
    group_activities: Mapping[int, tuple[int, ...]] | None = None


@dataclass(frozen=True, slots=True)
class PeriodWindow:
    start: dt.date
    end: dt.date
    lock_consumptions: bool | None
    lock_prestations: bool | None
    lock_invoices: bool | None


@dataclass(frozen=True, slots=True)
class PeriodSnapshot:
    periods: tuple[PeriodWindow, ...] | None
    complete: bool = False


@dataclass(frozen=True, slots=True)
class Check:
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class WriteBarrierReport:
    operation: str
    permission: Check
    period: Check
    financial: Check
    reasons: tuple[str, ...]
    executable: bool = False

    def __post_init__(self):
        if self.executable:
            raise ValueError("Aucune operation metier Qt n'est autorisee par C19d.")

    @property
    def report(self) -> str:
        return "\n".join((
            "QUALIFICATION DES PROTECTIONS - SIMULATION NON EXECUTABLE",
            "Droits : %s - %s" % (self.permission.status, self.permission.detail),
            "Periodes : %s - %s" % (self.period.status, self.period.detail),
            "Prestation/facture : %s - %s" % (
                self.financial.status, self.financial.detail,
            ),
            "VERDICT : BLOQUE (toujours, y compris si les declarations sont favorables)",
            *("- " + code for code in self.reasons),
        ))


def _ids(spec: str) -> tuple[int, ...] | None:
    if not spec or not isinstance(spec, str):
        return None
    result = []
    for part in spec.split(";"):
        if not part.isdecimal() or int(part) < 1:
            return None
        result.append(int(part))
    if len(set(result)) != len(result):
        return None
    return tuple(result)


def _valid_id(value) -> bool:
    return type(value) is int and value > 0


def check_declared_permission(
    evidence: PermissionSnapshot | None,
    *, activity_id: int | None,
    operation: str,
) -> Check:
    """Refuse tout comportement wx implicite de type absence => autorisation."""
    if operation not in _OPERATIONS:
        raise ValueError("Operation inconnue.")
    if operation == "invoice_creation":
        # La cle exacte de creation des factures n'a pas ete qualifiee
        # depuis le code de la generation ; ne pas inventer de droit.
        return Check("INCONNU", "Droit de creation de facture non qualifie.")
    if not _valid_id(activity_id):
        return Check("INCONNU", "Identifiant d'activite absent ou invalide.")
    if (
        not isinstance(evidence, PermissionSnapshot)
        or not evidence.complete
        or not _valid_id(evidence.actor_id)
        or not isinstance(evidence.rules, Mapping)
    ):
        return Check("INCONNU", "Session ou catalogue de droits incomplet.")
    rule = evidence.rules.get(("consommations_conso", "modifier"))
    if rule == "interdiction":
        return Check("REFUSE", "Interdiction explicite sur le droit wx observe.")
    if rule == "autorisation":
        return Check("DECLARE", "Droit presente dans un snapshot non authentifie.")
    if type(rule) is str and rule.startswith("restriction_"):
        spec = rule[len("restriction_"):]
        mode, delim, text = spec.partition(":")
        ids = _ids(text) if delim else None
        if ids is None:
            return Check("INCONNU", "Restriction vide, invalide ou ambigue.")
        if mode == "activites":
            return Check(
                "DECLARE" if activity_id in ids else "REFUSE",
                "Restriction a des identifiants d'activites declares.",
            )
        if mode == "groupes":
            groups = evidence.group_activities
            if not isinstance(groups, Mapping) or any(
                not isinstance(groups.get(group), (tuple, list))
                or any(not _valid_id(v) for v in groups[group])
                for group in ids
            ):
                return Check("INCONNU", "Correspondance des groupes non verifiee.")
            selected = {
                activity for group in ids for activity in groups[group]
            }
            return Check(
                "DECLARE" if activity_id in selected else "REFUSE",
                "Restriction selon un referentiel de groupes declare.",
            )
    return Check("INCONNU", "Regle absente, non explicite ou non reconnue.")


def _as_date(value) -> dt.date | None:
    if type(value) is dt.date:
        return value
    if type(value) is str:
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def check_declared_period(
    evidence: PeriodSnapshot | None,
    *, consumption_date,
    operation: str,
) -> Check:
    """Intervalles inclusifs ; consommation soumise AUSSI au verrou prestations."""
    if operation not in _OPERATIONS:
        raise ValueError("Operation inconnue.")
    day = _as_date(consumption_date)
    if day is None:
        return Check("INCONNU", "Date absente ou non valide.")
    if (
        not isinstance(evidence, PeriodSnapshot)
        or not evidence.complete
        or not isinstance(evidence.periods, tuple)
    ):
        return Check("INCONNU", "Import des periodes non qualifie.")
    applicable = (
        ("lock_consumptions", "lock_prestations")
        if operation == "consumption_state_change"
        else ("lock_invoices", "lock_prestations")
    )
    # La deuxieme combinaison est conservatrice : ce n'est PAS une
    # equivalence prouvee avec les controles du generateur wx.
    for window in evidence.periods:
        if (
            not isinstance(window, PeriodWindow)
            or type(window.start) is not dt.date
            or type(window.end) is not dt.date
            or window.start > window.end
            or any(type(getattr(window, flag)) is not bool for flag in applicable)
        ):
            return Check("INCONNU", "Une periode ou son verrou est non qualifie.")
    for window in evidence.periods:
        if window.start <= day <= window.end:
            if any(getattr(window, flag) for flag in applicable):
                return Check("VERROUILLE", "Periode de gestion verrouillee (borne incluse).")
    return Check("DECLARE_OUVERT", "Aucun verrou trouve dans la capture fournie.")


def check_historical_invoice_boundary(
    *, old_state, target_state, invoice_id, forfait_start,
) -> Check:
    """Une condition de blocage wx ; NE donne pas un droit de changement."""
    if old_state not in STATES or target_state not in STATES:
        return Check("INCONNU", "Etat hors des six etats historiques.")
    if invoice_id is not None and not _valid_id(invoice_id):
        return Check("INCONNU", "Identifiant facture non qualifie.")
    if invoice_id is not None and not forfait_start:
        crosses = (old_state in FINANCIAL) != (target_state in FINANCIAL)
        if crosses:
            return Check(
                "BLOQUE_WX",
                "Prestation deja facturee : frontiere tarifante franchie.",
            )
    return Check(
        "NON_SUFFISANT", "Pas de franchissement interdit identifie ; "
        "droits, recalcul et transaction non qualifies.",
    )


def audit_before_write(
    *, operation: str, permissions: PermissionSnapshot | None = None,
    periods: PeriodSnapshot | None = None, activity_id: int | None = None,
    consumption_date=None, observation: BillingObservation | None = None,
    target_state: str | None = None, forfait_start=None,
) -> WriteBarrierReport:
    if operation not in _OPERATIONS:
        raise ValueError("Operation non qualifiee.")
    rights = check_declared_permission(
        permissions, activity_id=activity_id, operation=operation,
    )
    dates = check_declared_period(
        periods, consumption_date=consumption_date, operation=operation,
    )
    if operation == "consumption_state_change":
        if observation is None:
            finance = Check("INCONNU", "Prestation non relue par le precontrole.")
        else:
            finance = check_historical_invoice_boundary(
                old_state=observation.state, target_state=target_state,
                invoice_id=observation.invoice_id, forfait_start=forfait_start,
            )
    else:
        finance = Check(
            "NON_RACCORDE",
            "Generation, tarifs, cotisations, numeros de factures, "
            "historique et controle transactionnel non homologues.",
        )
    codes = [
        "IDENTITE_ET_DROITS_RUNTIME_NON_RACCORDES",
        "PERIODES_RUNTIME_NON_RACCORDEES",
        "REGLES_TARIFAIRES_ET_ECRITURES_NON_RACCORDEES",
        "AUCUNE_AUTORISATION_DE_FACTURER",
    ]
    if rights.status != "DECLARE":
        codes.append("DROITS_NON_ETABLIS")
    if dates.status != "DECLARE_OUVERT":
        codes.append("PERIODE_NON_ETABLIE_OU_VERROUILLEE")
    if finance.status == "BLOQUE_WX":
        codes.append("FRONTIERE_FACTURATION")
    return WriteBarrierReport(
        operation, rights, dates, finance, tuple(codes),
    )
