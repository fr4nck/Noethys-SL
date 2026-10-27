"""Précontrôle de changement d'état de consommation, sans écriture SQL.

La grille wx historique contrôle droits, périodes, forfaits, prestations,
factures et ventilation. Ce module **ne** reproduit **pas** ces traitements :
il expose les risques et produit toujours une simulation non exécutable.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass

from .consumptions_core import Consumption, LABEL_BY_STATE, state_label

# Référence observée dans CTRL_Grille_cases.ModifieEtat : deux familles
# dont le franchissement peut modifier le statut tarifant d'une consommation.
# Cela ne signifie PAS que les transitions internes sont autorisées.
FINANCIAL_FAMILY = frozenset(("reservation", "present", "absenti"))
NON_FINANCIAL_FAMILY = frozenset(("attente", "refus", "absentj"))
SUPPORTED_STATES = FINANCIAL_FAMILY | NON_FINANCIAL_FAMILY


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class PreflightSnapshot:
    consumption_id: int
    date: str
    state: str | None
    locked: int | None
    forfait: int | None
    prestation_id: int | None
    individual_id: int | None
    activity_id: int | None
    inscription_id: int | None
    event_id: int | None
    prestation_exists: bool
    invoice_id: int | None
    forfait_start: str | None
    ventilation_rows: int


@dataclass(frozen=True, slots=True)
class TransitionPreview:
    consumption_id: int
    source_state: str | None
    target_state: str
    snapshot: PreflightSnapshot | None
    issues: tuple[Issue, ...]
    executable: bool = False

    def __post_init__(self) -> None:
        # Sécurité structurelle : aucune réponse ne doit devenir "prête"
        # tant que le moteur métier, droits et transaction ne sont pas raccordés.
        if self.executable:
            raise ValueError("Aucun adaptateur d'écriture Qt n'est homologué.")

    @property
    def report(self) -> str:
        lines = [
            "SIMULATION UNIQUEMENT — aucune consommation ne sera modifiée.",
            f"Consommation #{self.consumption_id}",
            f"État affiché : {state_label(self.source_state)}",
            f"État demandé : {state_label(self.target_state)}",
        ]
        if self.snapshot is not None:
            lines.append(
                f"État relu en base : {state_label(self.snapshot.state)} "
                f"· date {self.snapshot.date}"
            )
        lines.append("ENREGISTREMENT BLOQUÉ :")
        lines.extend(f"• [{issue.code}] {issue.message}" for issue in self.issues)
        return "\n".join(lines)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _iso_date(value: object) -> str:
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value or "")[:10]


def _issue(code: str, message: str) -> Issue:
    return Issue(code, message)


def assess_transition(
    displayed: Consumption,
    target: str,
    snapshot: PreflightSnapshot | None,
) -> TransitionPreview:
    """Analyse conservatrice, indépendante du toolkit et de tout writer."""
    if not isinstance(displayed, Consumption):
        raise TypeError("Une consommation issue de la liste est requise.")
    if target not in SUPPORTED_STATES:
        raise ValueError("L'état cible n'appartient pas aux six états historiques.")

    issues: list[Issue] = []
    if snapshot is None:
        issues.append(_issue("DISPARUE", "La consommation est introuvable en base."))
    else:
        # La sélection peut avoir vieilli entre le chargement et le clic.
        # Recontrôler les identifiants métier et l'état du serveur.
        displayed_fingerprint = (
            displayed.consumption_id, _iso_date(displayed.date),
            displayed.state, displayed.individual_id, displayed.activity_id,
            displayed.prestation_id, displayed.event_id,
        )
        observed_fingerprint = (
            snapshot.consumption_id, snapshot.date,
            snapshot.state, snapshot.individual_id, snapshot.activity_id,
            snapshot.prestation_id, snapshot.event_id,
        )
        if displayed_fingerprint != observed_fingerprint:
            issues.append(_issue(
                "SELECTION_PERIMEE",
                "La consommation a changé depuis l'affichage : actualisation obligatoire.",
            ))
        if snapshot.state not in SUPPORTED_STATES:
            issues.append(_issue(
                "ETAT_INCONNU", "État actuel non reconnu : traitement administratif requis."
            ))
        if snapshot.locked not in (None, 0):
            issues.append(_issue("VERROUILLAGE", "Consommation verrouillée dans la grille."))
        if snapshot.forfait not in (None, 0):
            issues.append(_issue(
                "FORFAIT", "Consommation liée à un forfait ; gestion globale à qualifier."
            ))
        if snapshot.inscription_id is None:
            issues.append(_issue(
                "INSCRIPTION", "Aucune inscription identifiée : contexte métier incomplet."
            ))
        if snapshot.prestation_id is not None and not snapshot.prestation_exists:
            issues.append(_issue(
                "PRESTATION_ABSENTE", "La prestation référencée est introuvable."
            ))
        if snapshot.invoice_id is not None:
            issues.append(_issue(
                "FACTURE", "La prestation est liée à une facture : blocage conservateur."
            ))
        if snapshot.ventilation_rows:
            issues.append(_issue(
                "VENTILATION",
                "Des ventilations de règlements existent sur cette prestation ; "
                "aucune suppression ou régularisation implicite.",
            ))
        if snapshot.state == target:
            issues.append(_issue("AUCUN_CHANGEMENT", "L'état demandé est déjà enregistré."))
        if (
            snapshot.state in SUPPORTED_STATES
            and ((snapshot.state in FINANCIAL_FAMILY) != (target in FINANCIAL_FAMILY))
        ):
            issues.append(_issue(
                "FRONTIERE_FACTURATION",
                "Changement de famille tarifante : calcul des prestations et facture "
                "à requalifier selon les règles wx.",
            ))

    # Barrières systématiques : les contrôles wx historiques ne sont pas
    # implicitement assurés par la présence d'une ligne SQL.
    issues.extend((
        _issue(
            "DROITS_NON_VERIFIES",
            "Droits utilisateur 'consommations_conso/modifier' non raccordés à Qt.",
        ),
        _issue(
            "PERIODE_NON_VERIFIEE",
            "Période de gestion et éventuelles clôtures non contrôlées.",
        ),
        _issue(
            "FACTURATION_NON_RACCORDEE",
            "Recalcul tarifaire, cotisations et historique non raccordés au moteur wx.",
        ),
        _issue(
            "AUCUNE_ECRITURE",
            "Aucune opération UPDATE/INSERT/DELETE ni confirmation d'enregistrement "
            "n'est proposée par ce lot.",
        ),
    ))
    return TransitionPreview(
        displayed.consumption_id, displayed.state, target, snapshot,
        tuple(issues),
    )


class ConsumptionPreflightRepository:
    """Snapshot SQL au clic : connexion Qt gardée, SELECT seulement."""

    def __init__(self, consumption_repository):
        self.consumption_repository = consumption_repository

    def inspect(self, displayed: Consumption, target: str) -> TransitionPreview:
        if not isinstance(displayed, Consumption) or displayed.consumption_id <= 0:
            raise ValueError("Sélection de consommation invalide.")
        if target not in LABEL_BY_STATE:
            raise ValueError("État cible non reconnu.")

        connection, placeholder = self.consumption_repository.editor_repository._connect()
        try:
            if isinstance(connection, sqlite3.Connection):
                connection.execute("PRAGMA query_only = ON")
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "SELECT c.IDconso, c.date, c.etat, c.verrouillage, c.forfait, "
                    "c.IDprestation, c.IDindividu, c.IDactivite, c.IDinscription, "
                    "c.IDevenement, p.IDprestation, p.IDfacture, p.forfait_date_debut "
                    "FROM consommations c "
                    "LEFT JOIN prestations p ON p.IDprestation=c.IDprestation "
                    f"WHERE c.IDconso={placeholder}",
                    (displayed.consumption_id,),
                )
                row = cursor.fetchone()
                snapshot = None
                if row is not None:
                    prestation_id = _optional_int(row[5])
                    ventilation_rows = 0
                    if prestation_id is not None:
                        cursor.execute(
                            f"SELECT COUNT(*) FROM ventilation WHERE IDprestation={placeholder}",
                            (prestation_id,),
                        )
                        ventilation_rows = int(cursor.fetchone()[0])
                    snapshot = PreflightSnapshot(
                        consumption_id=int(row[0]),
                        date=_iso_date(row[1]),
                        state=None if row[2] is None else str(row[2]),
                        locked=_optional_int(row[3]),
                        forfait=_optional_int(row[4]),
                        prestation_id=prestation_id,
                        individual_id=_optional_int(row[6]),
                        activity_id=_optional_int(row[7]),
                        inscription_id=_optional_int(row[8]),
                        event_id=_optional_int(row[9]),
                        prestation_exists=row[10] is not None,
                        invoice_id=_optional_int(row[11]),
                        forfait_start=None if row[12] is None else _iso_date(row[12]),
                        ventilation_rows=ventilation_rows,
                    )
            finally:
                cursor.close()
        finally:
            connection.close()
        return assess_transition(displayed, target, snapshot)
