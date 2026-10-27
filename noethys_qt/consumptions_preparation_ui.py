"""Panneau Qt de simulation avant toute future saisie de consommation.

Ce panneau ne contient volontairement aucun bouton Enregistrer et aucun
appel SQL modifiant la base ; il matérialise les protections encore absentes.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from .consumptions_core import Consumption, STATES
from .consumptions_preparation_core import (
    ConsumptionPreflightRepository, TransitionPreview,
)


class _PreviewSignals(QObject):
    completed = Signal(int, object, str)


class _PreviewWorker(QRunnable):
    def __init__(self, repository, token: int, displayed: Consumption, target: str):
        super().__init__()
        self.setAutoDelete(False)
        self.repository = repository
        self.token = token
        self.displayed = displayed
        self.target = target
        self.signals = _PreviewSignals()

    def run(self):
        try:
            preview = self.repository.inspect(self.displayed, self.target)
        except Exception as exc:
            self.signals.completed.emit(self.token, None, str(exc))
        else:
            self.signals.completed.emit(self.token, preview, "")


class ConsumptionPreparationPanel(QGroupBox):
    """Présentation bloquante d'une proposition, jamais un éditeur actif."""

    def __init__(self, consumption_repository, parent=None, *, background=True):
        super().__init__("Préparer un changement d'état — simulation", parent)
        self.preflight_repository = ConsumptionPreflightRepository(consumption_repository)
        self.background = background
        self._selected: Consumption | None = None
        self._token = 0
        self._queued = None
        self._worker = None
        self.last_preview: TransitionPreview | None = None

        root = QVBoxLayout(self)
        root.setSpacing(4)
        controls = QHBoxLayout()
        self.target_combo = QComboBox(self)
        self.target_combo.setAccessibleName("Nouvel état envisagé pour la simulation")
        self.target_combo.addItem("Choisir un état cible…", None)
        for code, label in STATES:
            self.target_combo.addItem(label, code)
        controls.addWidget(self.target_combo, 1)
        self.preview_button = QPushButton("Vérifier les protections", self)
        controls.addWidget(self.preview_button)
        root.addLayout(controls)
        self.selection_label = QLabel("Sélectionnez une consommation dans la liste.", self)
        self.selection_label.setWordWrap(True)
        root.addWidget(self.selection_label)
        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(100)
        self.output.setMaximumHeight(130)
        self.output.setPlaceholderText("Les contrôles disponibles seront affichés ici.")
        root.addWidget(self.output)
        self.warning = QLabel(
            "ÉCRITURE DÉSACTIVÉE — droits, période de gestion et facturation à qualifier.",
            self,
        )
        self.warning.setWordWrap(True)
        root.addWidget(self.warning)

        self.target_combo.currentIndexChanged.connect(self._target_changed)
        self.preview_button.clicked.connect(self.inspect)
        self.set_row(None)

    def set_row(self, row: Consumption | None) -> None:
        self._token += 1
        self._queued = None
        self._selected = row
        self.last_preview = None
        self.output.clear()
        self.selection_label.setText(
            f"Consommation #{row.consumption_id} — état actuel : {row.state or 'non renseigné'}"
            if row else "Sélectionnez une consommation dans la liste."
        )
        self._sync_enabled()

    def _target_changed(self, *_args) -> None:
        self._token += 1
        self._queued = None
        self.last_preview = None
        self.output.clear()
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        self.preview_button.setEnabled(
            self._selected is not None and self.target_combo.currentData() is not None
        )

    def inspect(self, *_args) -> None:
        row = self._selected
        target = self.target_combo.currentData()
        if row is None or target is None:
            return
        self._token += 1
        token = self._token
        self.output.setPlainText("Relecture des protections en cours…")
        if not self.background:
            try:
                preview = self.preflight_repository.inspect(row, target)
            except Exception as exc:
                self._apply_error(str(exc))
            else:
                self._apply_result(preview)
            return
        self._queued = (token, row, target)
        self._launch()

    def _launch(self) -> None:
        if self._worker is not None or self._queued is None:
            return
        token, row, target = self._queued
        self._queued = None
        worker = _PreviewWorker(self.preflight_repository, token, row, target)
        self._worker = worker
        worker.signals.completed.connect(self._completed)
        QThreadPool.globalInstance().start(worker)

    def _completed(self, token, result, error) -> None:
        self._worker = None
        self._launch()  # Coalescence ; seule la sélection courante compte.
        if token != self._token:
            return
        if error:
            self._apply_error(error)
        elif isinstance(result, TransitionPreview):
            self._apply_result(result)
        else:
            self._apply_error("Résultat de simulation inattendu.")

    def _apply_error(self, error: str) -> None:
        self.last_preview = None
        self.output.setPlainText(
            "CONSULTATION IMPOSSIBLE — aucune action autorisée.\n" + error
        )

    def _apply_result(self, preview: TransitionPreview) -> None:
        self.last_preview = preview
        self.output.setPlainText(preview.report)
