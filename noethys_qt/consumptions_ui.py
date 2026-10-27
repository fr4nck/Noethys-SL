"""Consultation Qt des consommations : filtres par clic, requetes bornees."""
from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QRunnable, QThreadPool, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QSpinBox, QTableView, QVBoxLayout, QWidget,
)

from .consumptions_core import (
    ALL_STATES, MAX_RESULTS, OTHER, STATES,
    Consumption, ConsumptionRepository, ConsumptionResult, format_date, state_label,
)


class ConsumptionTableModel(QAbstractTableModel):
    HEADERS = (
        "ID", "Date", "État", "Activité", "Unité", "Groupe",
        "Nom", "Prénom", "Horaires", "ID prestation", "Montant prestation",
    )

    def __init__(self):
        super().__init__()
        self.rows: tuple[Consumption, ...] = ()

    def replace_rows(self, rows):
        self.beginResetModel()
        self.rows = tuple(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):  # noqa: N802
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=int(Qt.ItemDataRole.DisplayRole)):  # noqa: N802
        if role == int(Qt.ItemDataRole.DisplayRole) and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == int(Qt.ItemDataRole.UserRole):
            return row
        if role == int(Qt.ItemDataRole.DisplayRole):
            fields = (
                row.consumption_id, format_date(row.date), state_label(row.state),
                row.activity, row.unit, row.group,
                row.last_name, row.first_name, row.hours_label,
                row.prestation_id if row.prestation_id is not None else "",
                row.amount_label,
            )
            return str(fields[index.column()])
        if role == int(Qt.ItemDataRole.ToolTipRole):
            return f"Consommation #{row.consumption_id} — consultation uniquement"
        return None


class _ResultSignals(QObject):
    completed = Signal(int, object, str)


class _ResultWorker(QRunnable):
    def __init__(self, repository, token, filters):
        super().__init__()
        self.setAutoDelete(False)
        self.repository = repository
        self.token = token
        self.filters = filters
        self.signals = _ResultSignals()

    def run(self):
        try:
            result = self.repository.search(**self.filters)
        except Exception as exc:
            self.signals.completed.emit(self.token, None, str(exc))
        else:
            self.signals.completed.emit(self.token, result, "")


class ConsumptionPage(QWidget):
    """Aucune lecture à la construction ; activation explicite à l'ouverture."""

    def __init__(self, repository: ConsumptionRepository, parent=None, *, background=True):
        super().__init__(parent)
        self.repository = repository
        self.background = background
        self.model = ConsumptionTableModel()
        # C2 : filtre additionnel facultatif fourni par le calendrier parent.
        self.filter_context = None
        self._loaded = False
        self._batch = False
        self._token = 0
        self._queued = None
        self._worker = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(220)
        self._debounce.timeout.connect(self.refresh)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        title = QLabel("Consommations — consultation", self)
        title.setObjectName("sectionTitle")
        root.addWidget(title)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Année :", self))
        self.year_spin = QSpinBox(self)
        self.year_spin.setRange(1900, 2098)
        self.year_spin.setValue(dt.date.today().year)
        self.year_spin.setAccessibleName("Année des consommations")
        bar.addWidget(self.year_spin)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Nom, prénom, activité, unité, groupe ou ID…")
        self.search_edit.setClearButtonEnabled(True)
        bar.addWidget(self.search_edit, 1)
        self.refresh_button = QPushButton("Actualiser", self)
        bar.addWidget(self.refresh_button)
        root.addLayout(bar)

        group = QGroupBox("États à afficher (cocher pour inclure)", self)
        checks = QGridLayout(group)
        self.state_checks: dict[str, QCheckBox] = {}
        labels = (*STATES, (OTHER, "Autres / non renseignés"))
        for index, (code, label) in enumerate(labels):
            check = QCheckBox(label, group)
            check.setObjectName("state_" + code)
            check.setChecked(True)
            self.state_checks[code] = check
            checks.addWidget(check, index // 4, index % 4)
        self.all_button = QPushButton("Tout sélectionner", group)
        self.none_button = QPushButton("Tout désélectionner", group)
        checks.addWidget(self.all_button, 2, 0, 1, 2)
        checks.addWidget(self.none_button, 2, 2, 1, 2)
        root.addWidget(group)

        self.summary = QLabel("Sélectionnez une année et les états à afficher.", self)
        root.addWidget(self.summary)
        self.hint = QLabel(
            "Lecture seule · affichage plafonné à 300 lignes. "
            "Le montant est celui de la prestation liée, sans totalisation ni recalcul.",
            self,
        )
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)  # Le serveur fournit l'ordre et la limite.
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.year_spin.valueChanged.connect(self.refresh)
        self.search_edit.textChanged.connect(lambda _value: self._debounce.start())
        self.refresh_button.clicked.connect(self.refresh)
        for check in self.state_checks.values():
            check.toggled.connect(self.refresh)
        self.all_button.clicked.connect(lambda: self._select_all(True))
        self.none_button.clicked.connect(lambda: self._select_all(False))

    @property
    def selected_states(self) -> frozenset[str]:
        return frozenset(code for code, check in self.state_checks.items() if check.isChecked())

    def _select_all(self, selected: bool) -> None:
        self._batch = True
        try:
            for check in self.state_checks.values():
                check.setChecked(selected)
        finally:
            self._batch = False
        self.refresh()

    def activate(self) -> None:
        if not self._loaded:
            self.refresh()

    def refresh(self, *_args) -> None:
        if self._batch:
            return
        self._debounce.stop()
        self._loaded = True
        self._token += 1
        states = self.selected_states
        if not states:
            self._queued = None
            self.model.replace_rows(())
            self.table.setEnabled(True)
            self.summary.setText("Aucun état sélectionné : cochez les états à consulter.")
            return
        filters = dict(
            year=self.year_spin.value(),
            states=states,
            text=self.search_edit.text().strip(),
            limit=MAX_RESULTS,
        )
        if self.filter_context is not None:
            filters.update(self.filter_context())
        self.summary.setText("Chargement des consommations…")
        self.table.setEnabled(False)
        if not self.background:
            try:
                result = self.repository.search(**filters)
            except Exception as exc:
                self._apply_error(str(exc))
            else:
                self._apply_result(result)
            return
        self._queued = (self._token, filters)
        self._launch()

    def _launch(self) -> None:
        if self._worker is not None or self._queued is None:
            return
        token, filters = self._queued
        self._queued = None
        worker = _ResultWorker(self.repository, token, filters)
        self._worker = worker
        worker.signals.completed.connect(self._completed)
        QThreadPool.globalInstance().start(worker)

    def _completed(self, token, result, error) -> None:
        self._worker = None
        self._launch()  # Coalescer les changements successifs ; dernier état gagnant.
        if token != self._token:
            return
        if error:
            self._apply_error(error)
        elif isinstance(result, ConsumptionResult):
            self._apply_result(result)
        else:
            self._apply_error("Réponse SQL inattendue.")

    def _apply_error(self, error: str) -> None:
        self.model.replace_rows(())
        self.table.setEnabled(True)
        self.summary.setText("Consultation indisponible")
        self.hint.setText(error)

    def _apply_result(self, result: ConsumptionResult) -> None:
        self.model.replace_rows(result.rows)
        self.table.setEnabled(True)
        count = len(result.rows)
        suffix = " (limite atteinte, affiner les filtres)" if result.has_more else ""
        self.summary.setText(f"{count}{'+' if result.has_more else ''} consommation(s) affichée(s){suffix}")
        self.hint.setText(
            "Lecture seule. Montants des prestations liées affichés individuellement ; "
            "aucun total financier ni changement d'état."
        )
