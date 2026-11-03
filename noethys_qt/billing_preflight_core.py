"""C19c : precontrole de facturation sur fixture ephemere fictive uniquement.

Ne facture rien, ne somme rien, ne qualifie aucun droit utilisateur.
Les montants proviennent des prestations deja enregistrees et sont
affiches BRUTS (sans arrondi, distribution ou tarification automatique).
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .c19b_operational_guard import can_demo_inscription_invoices


def _positive_id(value, label):
    if type(value) is not int or value <= 0:
        raise ValueError("Identifiant %s invalide." % label)
    return value


@dataclass(frozen=True, slots=True)
class BillingObservation:
    consumption_id: int
    inscription_id: int
    individual_id: int
    family_id: int
    state: str | None
    prestation_id: int | None
    raw_amount: str | None
    invoice_id: int | None
    consumption_references: int
    allocation_rows: int
    alerts: tuple[str, ...]
    executable: bool = False

    def __post_init__(self):
        if self.executable:
            raise ValueError("Aucune facturation executable dans le prototype Qt.")

    @property
    def report(self):
        lines = [
            "CONTROLE AVANT FACTURATION - CONSULTATION UNIQUEMENT",
            "Famille #%s | inscription #%s | individu #%s | consommation #%s" % (
                self.family_id, self.inscription_id,
                self.individual_id, self.consumption_id,
            ),
            "Etat constate : %s" % (self.state or "non renseigne"),
            "Prestation enregistree : %s" % (
                "#%s" % self.prestation_id
                if self.prestation_id is not None else "aucune",
            ),
            "Montant BRUT de cette prestation : %s" % (
                self.raw_amount if self.raw_amount is not None
                else "non renseigne",
            ),
            "Facture liee a la prestation : %s" % (
                "#%s" % self.invoice_id
                if self.invoice_id is not None else "aucune identifiee",
            ),
            "Autres usages de cette prestation : %s reference(s) au total" %
            self.consumption_references,
            "Ventilations enregistrees : %s" % self.allocation_rows,
        ]
        if self.alerts:
            lines.append("CONTROLES A TRAITER :")
            lines.extend("- " + alert for alert in self.alerts)
        lines.extend([
            "Aucun montant par seance ni total de facture n'est calcule.",
            "AUCUNE FACTURATION AUTORISEE - droits, regles wx et periodes "
            "de gestion non qualifies.",
        ])
        return "\n".join(lines)


class BillingPreflightRepository:
    """Une seule consommation, JOIN sur les identifiants SQL exacts, mode=ro."""

    def __init__(self, sqlite_path):
        self._source = Path(sqlite_path) if sqlite_path is not None else None

    def inspect(
        self, *, consumption_id, inscription_id, individual_id, family_id,
        displayed_state=None, displayed_prestation_id=None,
    ):
        # Refuser toutes les cles invalides AVANT la moindre connexion.
        _positive_id(consumption_id, "consommation")
        _positive_id(inscription_id, "inscription")
        _positive_id(individual_id, "individu")
        _positive_id(family_id, "famille")
        if displayed_prestation_id is not None:
            _positive_id(displayed_prestation_id, "prestation")
        if displayed_state is not None and type(displayed_state) is not str:
            raise ValueError("Etat affiche invalide.")

        # Ne jamais utiliser ce module sur une base PMSL ni une copie
        # arbitraire. On revalide le garde a CHAQUE clic.
        if not can_demo_inscription_invoices(
            self._source, read_only_demo=True
        ):
            raise PermissionError("Controle financier reserve a la fixture C13 fictive.")

        uri = self._source.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=3)) as db:
            db.execute("PRAGMA query_only = ON")
            row = db.execute(
                "SELECT c.IDconso, c.IDinscription, c.IDindividu, "
                "c.IDprestation, c.etat, i.IDfamille, i.IDindividu, "
                "p.IDprestation, p.montant, p.IDfacture, cp.IDfamille, "
                "f.IDfacture, fcp.IDfamille, "
                "(SELECT COUNT(*) FROM consommations c2 "
                " WHERE c2.IDprestation = c.IDprestation), "
                "(SELECT COUNT(*) FROM ventilation v "
                " WHERE v.IDprestation = c.IDprestation) "
                "FROM consommations c "
                "LEFT JOIN inscriptions i ON i.IDinscription=c.IDinscription "
                "LEFT JOIN prestations p ON p.IDprestation=c.IDprestation "
                "LEFT JOIN comptes_payeurs cp "
                " ON cp.IDcompte_payeur=p.IDcompte_payeur "
                "LEFT JOIN factures f ON f.IDfacture=p.IDfacture "
                "LEFT JOIN comptes_payeurs fcp "
                " ON fcp.IDcompte_payeur=f.IDcompte_payeur "
                "WHERE c.IDconso=?",
                (consumption_id,),
            ).fetchone()

        if row is None:
            raise LookupError("Consommation inexistante : actualiser.")

        # Pas de repli vers la famille de l'individu ni vers la prestation.
        if (
            row[0] != consumption_id
            or row[1] != inscription_id
            or row[2] != individual_id
            or row[5] != family_id
            or row[6] != individual_id
        ):
            raise PermissionError(
                "Dossier, inscription ou individu modifie : actualiser."
            )
        if row[3] != displayed_prestation_id or row[4] != displayed_state:
            raise ValueError(
                "Consommation ou prestation modifiee depuis l'affichage : actualiser."
            )

        prestation_id = row[3]
        raw_amount = None if row[8] is None else str(row[8])
        invoice_id = row[9]
        count = int(row[13])
        allocation_rows = int(row[14])
        alerts = []

        if prestation_id is None:
            alerts.append("Aucune prestation rattachee a la consommation.")
        elif row[7] is None:
            alerts.append("Prestation referencee introuvable.")
        else:
            if row[10] != family_id:
                alerts.append(
                    "Compte payeur de la prestation absent ou d'une autre famille."
                )
            if count > 1:
                alerts.append(
                    "Prestation commune a plusieurs consommations : ne pas "
                    "repartir ni additionner son montant par presence."
                )
            if allocation_rows:
                alerts.append(
                    "Ventilations de reglement deja enregistrees : "
                    "aucune regularisation automatique."
                )
            if raw_amount is None:
                alerts.append("Montant de prestation non renseigne.")
            else:
                try:
                    if not Decimal(raw_amount).is_finite():
                        raise ValueError("non fini")
                except (InvalidOperation, ValueError):
                    alerts.append("Montant brut non numerique ou non fini.")
            if invoice_id is not None:
                if row[11] != invoice_id:
                    alerts.append("Facture referencee introuvable.")
                elif row[12] != family_id:
                    alerts.append(
                        "Compte payeur de la facture absent ou d'une autre famille."
                    )
                else:
                    alerts.append(
                        "Prestation deja liee a une facture : "
                        "aucune nouvelle facturation automatique."
                    )

        if row[4] != "present":
            alerts.append(
                "Etat different de present : aucune conclusion tarifaire "
                "sans les regles wx."
            )

        return BillingObservation(
            consumption_id, inscription_id, individual_id, family_id,
            row[4], prestation_id, raw_amount, invoice_id,
            count, allocation_rows, tuple(alerts),
        )
