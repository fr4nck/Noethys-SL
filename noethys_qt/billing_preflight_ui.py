"""Panneau de controle financier C19c : uniquement en demonstration fictive."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .billing_preflight_core import BillingObservation, BillingPreflightRepository
from .legacy_write_barrier import audit_before_write
from .consumptions_core import Consumption


class BillingPreflightPanel(QGroupBox):
    """Une constatation par clic ; jamais une commande de facturation."""

    def __init__(self, sqlite_path, parent=None):
        super().__init__("Contrôle avant facturation — démonstration", parent)
        self.repository = BillingPreflightRepository(sqlite_path)
        self._context = None
        self._row = None
        self.last_observation: BillingObservation | None = None
        self.last_barrier = None

        layout = QVBoxLayout(self)
        self.notice = QLabel(
            "Lecture seule : prix enregistré, facture liée et alertes. "
            "Aucun tarif ni solde calculé.", self,
        )
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.check_button = QPushButton(
            "Contrôler cette consommation avant facturation", self
        )
        layout.addWidget(self.check_button)
        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(165)
        self.output.setPlaceholderText(
            "Sélectionnez une consommation d'une inscription fictive."
        )
        layout.addWidget(self.output)
        self.check_button.clicked.connect(self.inspect)
        self.set_context()

    def set_context(self, *, individual_id=None, inscription_id=None, family_id=None):
        values = (individual_id, inscription_id, family_id)
        self._context = values if all(
            type(value) is int and value > 0 for value in values
        ) else None
        self._row = None
        self.last_observation = None
        self.last_barrier = None
        self.output.clear()
        self._update_button()

    def set_row(self, row: Consumption | None):
        self._row = row if isinstance(row, Consumption) else None
        self.last_observation = None
        self.last_barrier = None
        self.output.clear()
        self._update_button()

    def _update_button(self):
        self.check_button.setEnabled(
            self._context is not None
            and self._row is not None
            and self._row.individual_id == self._context[0]
        )

    def inspect(self):
        self.last_observation = None
        self.last_barrier = None
        self.output.clear()
        if not self.check_button.isEnabled() or self._context is None:
            return
        row = self._row
        individual_id, inscription_id, family_id = self._context
        try:
            result = self.repository.inspect(
                consumption_id=row.consumption_id,
                inscription_id=inscription_id,
                individual_id=individual_id,
                family_id=family_id,
                displayed_state=row.state,
                displayed_prestation_id=row.prestation_id,
            )
        except (PermissionError, ValueError, LookupError, OSError) as exc:
            self.output.setPlainText(
                "CONTROLE IMPOSSIBLE — aucune facturation autorisée.\n" + str(exc)
            )
            return
        self.last_observation = result
        # C19d : aucune identite authentifiee, aucun verrou certifie, aucun
        # writer. Afficher explicitement les refus, meme si les donnees
        # brutes de la prestation sont disponibles dans cette fixture.
        self.last_barrier = audit_before_write(
            operation="invoice_creation", activity_id=row.activity_id,
            consumption_date=row.date, observation=result,
        )
        self.output.setPlainText(result.report + "\n\n" + self.last_barrier.report)
