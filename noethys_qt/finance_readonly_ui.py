"""Qt C13 — grandes rubriques financières en consultation uniquement.

Facturation (factures/prestations), règlements (règlements/ventilation),
comptabilité (opérations de trésorerie/dépôts). Les écrans ne comportent
aucun bouton Enregistrer, Valider, Compenser ou Éditer.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, QObject, QRunnable, QSignalBlocker,
    QThreadPool, Qt, QTimer, Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTabWidget, QTableView, QVBoxLayout, QWidget,
)

from .finance_readonly_core import (
    FAMILY_DOMAINS, FINANCE_DOMAINS, FinanceRepository, FinanceResult,
    display_finance_value, validate_finance_id,
)

MODULES = {
    "billing": ("Facturation", ("invoices", "services")),
    "payments": ("Règlements", ("payments", "allocations")),
    "accounting": ("Comptabilité / trésorerie", ("treasury", "deposits")),
}
RELATED_ACTIONS = {
    "invoices": ("services", "Voir les prestations de cette facture"),
    "payments": ("allocations", "Voir la ventilation de ce règlement"),
    "deposits": ("deposit_payments", "Voir les règlements du dépôt"),
}


class FinanceTableModel(QAbstractTableModel):
    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.rows = ()

    def replace_rows(self, rows):
        incoming = tuple(rows)
        if self.rows == incoming:
            return False
        self.beginResetModel()
        self.rows = incoming
        self.endResetModel()
        return True

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(FINANCE_DOMAINS[self.kind][1])

    def headerData(self, section, orientation, role=int(Qt.ItemDataRole.DisplayRole)):
        if (
            role == int(Qt.ItemDataRole.DisplayRole)
            and orientation == Qt.Orientation.Horizontal
        ):
            return FINANCE_DOMAINS[self.kind][1][section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        record = self.rows[index.row()]
        if role == int(Qt.ItemDataRole.UserRole):
            return record
        if role == int(Qt.ItemDataRole.DisplayRole):
            key = FINANCE_DOMAINS[self.kind][2][index.column()]
            return display_finance_value(
                record.values[index.column()],
                amount=key in FINANCE_DOMAINS[self.kind][3],
            )
        if role == int(Qt.ItemDataRole.TextAlignmentRole):
            key = FINANCE_DOMAINS[self.kind][2][index.column()]
            if key in FINANCE_DOMAINS[self.kind][3]:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


class _FinanceSignals(QObject):
    completed = Signal(int, object, str)


class _FinanceWorker(QRunnable):
    def __init__(self, repository, token, kind, filters):
        super().__init__()
        self.setAutoDelete(False)
        self.repository, self.token, self.kind, self.filters = (
            repository, token, kind, filters
        )
        self.signals = _FinanceSignals()

    def run(self):
        try:
            result = self.repository.search(self.kind, **self.filters)
        except Exception as exc:
            self.signals.completed.emit(self.token, None, str(exc))
        else:
            self.signals.completed.emit(self.token, result, "")


class FinanceTablePage(QWidget):
    """Liste d'un domaine, recherche et filtres, aucun parcours de saisie."""

    relatedRequested = Signal(str, int)
    familyRequested = Signal(int)

    def __init__(self, repository: FinanceRepository, kind: str, parent=None,
                 *, background=True):
        super().__init__(parent)
        if kind not in FINANCE_DOMAINS:
            raise ValueError("Domaine financier inconnu")
        self.repository = repository
        self.kind = kind
        self.background = background
        self.model = FinanceTableModel(kind)
        self._family_id = None
        self._related_id = None
        self._loaded = False
        self._token = 0
        self._queued = None
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        header = QHBoxLayout()
        self.context_label = QLabel("Tous les dossiers · lecture seule", self)
        header.addWidget(self.context_label)
        self.search_edit = QLineEdit(self)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Recherche dans les données enregistrées…")
        self.search_edit.setAccessibleName(
            "Recherche " + FINANCE_DOMAINS[kind][0]
        )
        header.addWidget(self.search_edit, 1)
        self.year_spin = QSpinBox(self)
        self.year_spin.setRange(0, 2098)
        self.year_spin.setSpecialValueText("Toutes années")
        self.year_spin.setValue(0)
        self.year_spin.setAccessibleName("Année des opérations enregistrées")
        header.addWidget(self.year_spin)
        self.clear_button = QPushButton("Tous les dossiers", self)
        header.addWidget(self.clear_button)
        self.reload_button = QPushButton("Actualiser", self)
        header.addWidget(self.reload_button)
        layout.addLayout(header)

        self.summary = QLabel(
            "Consultation uniquement : aucun solde n'est recalculé.", self
        )
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)
        h.resizeSection(0, 76)
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.related_button = QPushButton("Voir les opérations liées", self)
        self.family_button = QPushButton("Ouvrir la famille", self)
        actions.addWidget(self.related_button)
        actions.addWidget(self.family_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.notice = QLabel(
            "Montants : valeurs enregistrées sans recalcul ni arrondi imposé. "
            "Liste limitée à 250 lignes ; les données financières ne sont "
            "pas certifiées par ce seul écran.",
            self,
        )
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.refresh)
        self.search_edit.textChanged.connect(lambda _text: self.timer.start())
        self.year_spin.valueChanged.connect(lambda _value: self.refresh())
        self.clear_button.clicked.connect(self.clear_context)
        self.reload_button.clicked.connect(self.refresh)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(lambda _idx: self._open_related())
        self.related_button.clicked.connect(self._open_related)
        self.family_button.clicked.connect(self._open_family)
        self._selection_changed()

    def activate(self):
        if not self._loaded:
            self.refresh()

    def _filters(self):
        return {
            "family_id": self._family_id,
            "year": self.year_spin.value() or None,
            "text": self.search_edit.text().strip(),
            "related_id": self._related_id,
        }

    def set_context(self, *, family_id=None, related_id=None):
        validate_finance_id(family_id, "famille")
        validate_finance_id(related_id, "liaison")
        if family_id is not None and self.kind not in FAMILY_DOMAINS:
            raise ValueError("Ce domaine n'accepte pas de filtre famille")
        if related_id is not None and self.kind not in (
            "services", "allocations", "payments"
        ):
            raise ValueError("Ce domaine n'accepte pas ce lien")
        blockers = [
            QSignalBlocker(self.search_edit), QSignalBlocker(self.year_spin)
        ]
        try:
            self.search_edit.clear()
            self.year_spin.setValue(0)
        finally:
            for blocker in blockers:
                blocker.unblock()
        self.timer.stop()
        self._family_id, self._related_id = family_id, related_id
        context = []
        if family_id is not None:
            context.append(f"Famille #{family_id}")
        if related_id is not None:
            qualifier = {
                "services": "facture", "allocations": "règlement",
                "payments": "dépôt",
            }[self.kind]
            context.append(f"{qualifier} #{related_id}")
        self.context_label.setText(
            " · ".join(context) + " · lecture seule" if context
            else "Tous les dossiers · lecture seule"
        )
        if self._loaded:
            self.refresh()

    def clear_context(self):
        self.set_context()

    def refresh(self, *_args):
        self.timer.stop()
        self._loaded = True
        self._token += 1
        filters = self._filters()
        self.summary.setText("Lecture des données financières…")
        if not self.background:
            try:
                result = self.repository.search(self.kind, **filters)
            except Exception as exc:
                self._error(str(exc))
            else:
                self._apply_result(result)
            return
        self._queued = (self._token, filters)
        self._launch()

    def _launch(self):
        if self._worker is not None or self._queued is None:
            return
        token, filters = self._queued
        self._queued = None
        worker = _FinanceWorker(self.repository, token, self.kind, filters)
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
        elif isinstance(result, FinanceResult):
            self._apply_result(result)
        else:
            self._error("Réponse financière inattendue.")

    def _error(self, message):
        self.model.replace_rows(())
        self.table.clearSelection()
        self._selection_changed()
        self.summary.setText("Lecture indisponible : " + message)

    def _apply_result(self, result: FinanceResult):
        previous = self.selected_row()
        old_id = previous.id if previous else None
        self.model.replace_rows(result.rows)
        if old_id is not None:
            for index, record in enumerate(result.rows):
                if record.id == old_id:
                    self.table.selectRow(index)
                    break
        self._selection_changed()
        self.summary.setText(
            f"{len(result.rows)}{'+' if result.truncated else ''} ligne(s) "
            + ("· affiner les filtres" if result.truncated else "")
            + " · montants bruts enregistrés, non rapprochés"
        )

    def selected_row(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        return self.model.rows[index] if 0 <= index < len(self.model.rows) else None

    def _selection_changed(self, *_args):
        row = self.selected_row()
        related = RELATED_ACTIONS.get(self.kind)
        self.related_button.setVisible(related is not None)
        self.related_button.setEnabled(row is not None and related is not None)
        if related is not None:
            self.related_button.setText(related[1])
        family = row.value("family") if row and self.kind in FAMILY_DOMAINS else None
        self.family_button.setVisible(self.kind in FAMILY_DOMAINS)
        self.family_button.setEnabled(family is not None)

    def _open_related(self):
        row = self.selected_row()
        if row is None or self.kind not in RELATED_ACTIONS:
            return
        self.relatedRequested.emit(RELATED_ACTIONS[self.kind][0], row.id)

    def _open_family(self):
        row = self.selected_row()
        if row is None or self.kind not in FAMILY_DOMAINS:
            return
        family = row.value("family")
        if family is not None:
            self.familyRequested.emit(int(family))


class FinanceHubPage(QWidget):
    """Une rubrique principale Qt avec deux listes historiques proches."""

    familyRequested = Signal(int)
    relatedRequested = Signal(str, int)

    def __init__(self, repository: FinanceRepository, module: str, parent=None,
                 *, background=True):
        super().__init__(parent)
        if module not in MODULES:
            raise ValueError("Rubrique financière inconnue")
        self.repository = repository
        self.module = module
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        title = QLabel(MODULES[module][0] + " — consultation", self)
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)
        self.pages = {}
        for kind in MODULES[module][1]:
            panel = FinanceTablePage(
                repository, kind, self.tabs, background=background
            )
            panel.relatedRequested.connect(self._related)
            panel.familyRequested.connect(self.familyRequested.emit)
            self.pages[kind] = panel
            self.tabs.addTab(panel, FINANCE_DOMAINS[kind][0])
        self.tabs.currentChanged.connect(self._tab_changed)

    @property
    def current_page(self):
        return self.tabs.currentWidget()

    def activate(self):
        self.current_page.activate()

    def _tab_changed(self, _index):
        self.activate()

    def set_family_context(self, family_id=None):
        if family_id is not None and self.module == "accounting":
            raise ValueError("Comptabilité non filtrable par famille")
        validate_finance_id(family_id, "famille")
        for page in self.pages.values():
            page.set_context(family_id=family_id)

    def focus_related(self, kind, related_id, *, family_id=None):
        if kind not in self.pages:
            raise ValueError("Domaine de détail étranger à cette rubrique")
        page = self.pages[kind]
        page.set_context(family_id=family_id, related_id=related_id)
        self.tabs.setCurrentWidget(page)
        page.activate()

    def _related(self, kind, record_id):
        if kind in self.pages:
            self.focus_related(kind, record_id)
        else:
            self.relatedRequested.emit(kind, record_id)
