"""C16 — aperçu autonome des consommations par états, pure consultation.

Sélection des états par clic ; les totaux sont des COUNT(*) des lignes,
pas les heures CAF/AFAS ni les montants à facturer.
"""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, QObject, QRunnable,
    QSignalBlocker, QThreadPool, Qt, Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QGridLayout, QGroupBox,
    QHeaderView, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QTableView, QVBoxLayout, QWidget,
)

from .consumptions_core import ALL_STATES
from .consumptions_status_core import (
    DISPLAY_STATES, ConsumptionStatusRepository, StatusSummary,
    validate_state_selection,
)


class StateCountModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = ()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 3

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ("État stocké", "Code source", "Lignes enregistrées")[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        entry = self.rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return (entry.label, entry.code, str(entry.count))[index.column()]
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() == 2:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def replace_rows(self, rows):
        candidate = tuple(rows)
        if candidate == self.rows:
            return False
        self.beginResetModel()
        self.rows = candidate
        self.endResetModel()
        return True


class _ReportSignals(QObject):
    completed = Signal(int, object, str)


class _ReportWorker(QRunnable):
    def __init__(self, repository, token, filters):
        super().__init__()
        self.setAutoDelete(False)
        self.repository = repository
        self.token = token
        self.filters = filters
        self.signals = _ReportSignals()

    def run(self):
        try:
            result = self.repository.summary(**self.filters)
        except Exception as exc:
            self.signals.completed.emit(self.token, None, str(exc))
        else:
            self.signals.completed.emit(self.token, result, "")


class ConsumptionStateReportPage(QWidget):
    """États multi-sélectionnables, chiffres bruts, aucun accès à l'édition."""

    def __init__(self, consumption_repository, parent=None, *, background=True):
        super().__init__(parent)
        self.repository = ConsumptionStatusRepository(consumption_repository)
        self.background = background
        self._loaded = False
        self._token = 0
        self._worker = None
        self._queued = None
        self._batch = False
        self.last_result = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel("États des consommations — aperçu technique", self)
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Année : ", self))
        self.year_spin = QSpinBox(self)
        self.year_spin.setRange(1900, 2098)
        self.year_spin.setValue(min(2098, max(1900, dt.date.today().year)))
        self.year_spin.setAccessibleName("Année de l'aperçu des états")
        filters.addWidget(self.year_spin)
        filters.addWidget(QLabel("ID activité : ", self))
        self.activity_spin = QSpinBox(self)
        self.activity_spin.setRange(0, 9999999)
        self.activity_spin.setValue(0)
        self.activity_spin.setSpecialValueText("Toutes activités")
        self.activity_spin.setAccessibleName("Filtre ID activité exact")
        filters.addWidget(self.activity_spin)
        self.refresh_button = QPushButton("Actualiser", self)
        filters.addWidget(self.refresh_button)
        filters.addStretch(1)
        layout.addLayout(filters)

        group = QGroupBox("États à inclure dans le comptage (sélection par clic)", self)
        switches = QGridLayout(group)
        self.state_checks: dict[str, QCheckBox] = {}
        for index, (code, label) in enumerate(DISPLAY_STATES):
            check = QCheckBox(label, group)
            check.setObjectName("report_state_" + code)
            check.setChecked(True)
            switches.addWidget(check, index // 4, index % 4)
            self.state_checks[code] = check
        self.all_button = QPushButton("Tout sélectionner", group)
        self.none_button = QPushButton("Tout désélectionner", group)
        switches.addWidget(self.all_button, 2, 0, 1, 2)
        switches.addWidget(self.none_button, 2, 2, 1, 2)
        layout.addWidget(group)

        self.summary = QLabel("Choisissez les états, puis consultez le comptage.", self)
        layout.addWidget(self.summary)
        self.model = StateCountModel(self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        notice = QLabel(
            "Chaque résultat = nombre de lignes enregistrées de consommation. "
            "Les états inconnus et NULL sont regroupés dans Autres. "
            "Ce tableau ne constitue ni l'état officiel de consommation, "
            "ni la base de facturation, ni une déclaration CAF/AFAS. "
            "Aucune ligne ni montant n'est modifié.",
            self,
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)

        self.year_spin.valueChanged.connect(self.refresh)
        self.activity_spin.valueChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)
        for check in self.state_checks.values():
            check.toggled.connect(self.refresh)
        self.all_button.clicked.connect(lambda: self._set_all(True))
        self.none_button.clicked.connect(lambda: self._set_all(False))

    @property
    def selected_states(self):
        return frozenset(
            code for code, check in self.state_checks.items()
            if check.isChecked()
        )

    def activate(self):
        if not self._loaded:
            self.refresh()

    def _set_all(self, value):
        if (self.selected_states == ALL_STATES) == value and (
            value or not self.selected_states
        ):
            return
        self._batch = True
        controls = [QSignalBlocker(check) for check in self.state_checks.values()]
        try:
            for check in self.state_checks.values():
                check.setChecked(value)
        finally:
            for control in controls:
                control.unblock()
            self._batch = False
        self.refresh()

    def clear_context(self):
        """Clic de menu global : efface toute activité résiduelle."""
        if self.activity_spin.value() == 0:
            return
        with QSignalBlocker(self.activity_spin):
            self.activity_spin.setValue(0)
        if self._loaded:
            self.refresh()

    def refresh(self, *_args):
        if self._batch:
            return
        filters = {
            "year": self.year_spin.value(),
            "activity_id": self.activity_spin.value() or None,
            "states": self.selected_states,
        }
        try:
            validate_state_selection(**filters)
        except ValueError as exc:
            self._token += 1
            self._loaded = True
            self._error(str(exc))
            return
        self._loaded = True
        self._token += 1
        if not filters["states"]:
            self._queued = None
            result = StatusSummary(
                year=filters["year"], activity_id=filters["activity_id"],
                selected=frozenset(), rows=(), total=0,
            )
            self._apply_result(result)
            self.summary.setText("Aucun état sélectionné — aucune requête SQL.")
            return
        self.summary.setText("Lecture des états enregistrés…")
        if not self.background:
            try:
                result = self.repository.summary(**filters)
            except Exception as exc:
                self._error(str(exc))
            else:
                self._apply_result(result)
            return
        self._queued = (self._token, filters)
        self._launch()

    def _launch(self):
        if self._queued is None or self._worker is not None:
            return
        token, filters = self._queued
        self._queued = None
        worker = _ReportWorker(self.repository, token, filters)
        self._worker = worker
        worker.signals.completed.connect(self._completed)
        QThreadPool.globalInstance().start(worker)

    def _completed(self, token, result, error):
        self._worker = None
        self._launch()
        if token != self._token:
            return
        if error:
            self._error(error)
        elif isinstance(result, StatusSummary):
            self._apply_result(result)
        else:
            self._error("Réponse de l'état inattendue")

    def _error(self, message):
        self.last_result = None
        self.model.replace_rows(())
        self.summary.setText("Consultation indisponible : " + message)

    def _apply_result(self, result):
        self.last_result = result
        self.model.replace_rows(result.rows)
        self.summary.setText(
            f"{result.total} ligne(s) enregistrée(s) · "
            f"{len(result.selected)} état(s) sélectionné(s) · "
            f"{result.year} · aucune facturation calculée"
        )
