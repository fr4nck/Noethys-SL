"""C14 — listes administratives natives Qt, strictement consultatives.

Ne charge aucune vue wx et ne propose aucune écriture ou calcul métier.
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

from .catalog_readonly_core import (
    CATALOG_DOMAINS, CATALOG_MODULES, ACTIVITY_LINK_DOMAINS,
    CatalogRepository, CatalogResult, validate_catalog_query,
    C17_ACTIVITY_DESTINATIONS,
)
from .finance_readonly_core import display_finance_value, validate_finance_id


class CatalogTableModel(QAbstractTableModel):
    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.rows = ()

    def replace_rows(self, rows):
        new_rows = tuple(rows)
        if new_rows == self.rows:
            return False
        self.beginResetModel()
        self.rows = new_rows
        self.endResetModel()
        return True

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(CATALOG_DOMAINS[self.kind].headers)

    def headerData(self, section, orientation, role=int(Qt.ItemDataRole.DisplayRole)):
        if role == int(Qt.ItemDataRole.DisplayRole) and orientation == Qt.Orientation.Horizontal:
            return CATALOG_DOMAINS[self.kind].headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        spec = CATALOG_DOMAINS[self.kind]
        row = self.rows[index.row()]
        if role == int(Qt.ItemDataRole.UserRole):
            return row
        if role == int(Qt.ItemDataRole.DisplayRole):
            return display_finance_value(
                row.values[index.column()],
                amount=spec.keys[index.column()] in spec.numeric_keys,
            )
        if role == int(Qt.ItemDataRole.TextAlignmentRole):
            if spec.keys[index.column()] in spec.numeric_keys:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


class _CatalogSignals(QObject):
    completed = Signal(int, object, str)


class _CatalogWorker(QRunnable):
    def __init__(self, repository, token, kind, filters):
        super().__init__()
        self.setAutoDelete(False)
        self.repository = repository
        self.token = token
        self.kind = kind
        self.filters = filters
        self.signals = _CatalogSignals()

    def run(self):
        try:
            result = self.repository.search(self.kind, **self.filters)
        except Exception as exc:
            self.signals.completed.emit(self.token, None, str(exc))
        else:
            self.signals.completed.emit(self.token, result, "")


class CatalogTablePage(QWidget):
    """Tableau borné, filtré par identifiants SQL et sans édition."""

    familyRequested = Signal(int)
    inscriptionRequested = Signal(int)
    activityRequested = Signal(int)
    individualRequested = Signal(int)
    relatedActivityRequested = Signal(str, int)

    def __init__(self, repository: CatalogRepository, kind: str, parent=None,
                 *, background=True):
        super().__init__(parent)
        if kind not in CATALOG_DOMAINS:
            raise ValueError("Domaine administratif inconnu")
        self.kind = kind
        self.spec = CATALOG_DOMAINS[kind]
        self.repository = repository
        self.background = background
        self.model = CatalogTableModel(kind)
        self._family_id = None
        self._activity_id = None
        self._individual_id = None
        self._token = 0
        self._queued = None
        self._worker = None
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        header = QHBoxLayout()
        self.context_label = QLabel("Tous les dossiers · lecture seule", self)
        header.addWidget(self.context_label)
        self.search_edit = QLineEdit(self)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Rechercher une donnée enregistrée…")
        self.search_edit.setAccessibleName("Recherche " + self.spec.label)
        header.addWidget(self.search_edit, 1)
        self.year_spin = QSpinBox(self)
        self.year_spin.setRange(0, 2098)
        self.year_spin.setSpecialValueText("Toutes années")
        self.year_spin.setValue(0)
        self.year_spin.setVisible(self.spec.date_column is not None)
        header.addWidget(self.year_spin)
        self.activity_spin = QSpinBox(self)
        self.activity_spin.setRange(0, 9999999)
        self.activity_spin.setSpecialValueText("Toutes activités")
        self.activity_spin.setAccessibleName("Filtre ID activité de " + self.spec.label)
        self.activity_spin.setValue(0)
        self.activity_spin.setVisible(self.spec.activity_column is not None)
        header.addWidget(self.activity_spin)
        self.clear_button = QPushButton("Tous les dossiers", self)
        header.addWidget(self.clear_button)
        self.reload_button = QPushButton("Actualiser", self)
        header.addWidget(self.reload_button)
        layout.addLayout(header)

        self.summary = QLabel("Consultation uniquement — valeurs enregistrées.", self)
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
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header_view.setStretchLastSection(True)
        header_view.resizeSection(0, 76)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.family_button = QPushButton("Ouvrir la famille", self)
        self.inscription_button = QPushButton("Voir les inscriptions de la famille", self)
        buttons.addWidget(self.family_button)
        buttons.addWidget(self.inscription_button)
        self.activity_button = QPushButton("Inscriptions de l'activité", self)
        buttons.addWidget(self.activity_button)
        self.individual_button = QPushButton("Ouvrir la fiche individu", self)
        buttons.addWidget(self.individual_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.related_buttons: dict[str, QPushButton] = {}
        if self.kind == "activity_overview":
            related = QHBoxLayout()
            for destination, label in (
                ("planning", "Ouvrir le planning de l'activité"),
                ("tariff_records", "Ouvrir les tarifs de l'activité"),
                ("consumption_reports", "Ouvrir les états de l'activité"),
            ):
                button = QPushButton(label, self)
                button.setAccessibleName(label + " sélectionnée")
                button.clicked.connect(
                    lambda _checked=False, target=destination:
                    self._open_related_activity(target)
                )
                self.related_buttons[destination] = button
                related.addWidget(button)
            related.addStretch(1)
            layout.addLayout(related)

        self.notice = QLabel(
            "Aucune écriture ni recalcul métier. Liste limitée à 250 enregistrements ; "
            "les informations historiques sont affichées sans attestation de validité.",
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
        self.activity_spin.valueChanged.connect(lambda _value: self.refresh())
        self.clear_button.clicked.connect(self.clear_context)
        self.reload_button.clicked.connect(self.refresh)
        self.family_button.clicked.connect(self._open_family)
        self.inscription_button.clicked.connect(self._open_inscriptions)
        self.activity_button.clicked.connect(self._open_activity)
        self.individual_button.clicked.connect(self._open_individual)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(lambda _index: self._open_family())
        self._selection_changed()

    def activate(self):
        if not self._loaded:
            self.refresh()

    def _filters(self):
        return {
            "family_id": self._family_id,
            "activity_id": self.activity_spin.value() or None,
            "individual_id": self._individual_id,
            "year": self.year_spin.value() or None,
            "text": self.search_edit.text().strip(),
        }

    def set_context(self, *, family_id=None, activity_id=None, individual_id=None):
        validate_finance_id(family_id, "famille")
        validate_finance_id(activity_id, "activité")
        validate_finance_id(individual_id, "individu")
        if family_id is not None and self.spec.family_column is None:
            raise ValueError("Filtre famille non applicable à ce tableau")
        if activity_id is not None and self.spec.activity_column is None:
            raise ValueError("Filtre activité non applicable à ce tableau")
        if individual_id is not None and self.spec.individual_column is None:
            raise ValueError("Filtre individu non applicable à ce tableau")
        changed = (
            self._family_id != family_id
            or self._activity_id != activity_id
            or self._individual_id != individual_id
            or bool(self.search_edit.text())
            or self.year_spin.value() != 0
        )
        blockers = [
            QSignalBlocker(self.search_edit),
            QSignalBlocker(self.year_spin),
            QSignalBlocker(self.activity_spin),
        ]
        try:
            self.search_edit.clear()
            self.year_spin.setValue(0)
            self.activity_spin.setValue(activity_id or 0)
        finally:
            for blocker in blockers:
                blocker.unblock()
        self.timer.stop()
        self._family_id = family_id
        self._activity_id = activity_id
        self._individual_id = individual_id
        scopes = []
        if family_id is not None:
            scopes.append(f"Famille #{family_id}")
        if activity_id is not None:
            scopes.append(f"Activité #{activity_id}")
        if individual_id is not None:
            scopes.append(f"Individu #{individual_id}")
        self.context_label.setText(
            (" · ".join(scopes) if scopes else "Tous les dossiers") + " · lecture seule"
        )
        if self._loaded and changed:
            self.refresh()

    def clear_context(self):
        self.set_context()

    def refresh(self, *_args):
        self.timer.stop()
        filters = self._filters()
        # Validation AVANT de lancer tout worker ou d'ouvrir une connexion.
        try:
            validate_catalog_query(self.kind, **filters)
        except ValueError as exc:
            self._token += 1
            self._loaded = True
            self._error(str(exc))
            return
        self._loaded = True
        self._token += 1
        self.summary.setText("Chargement des données enregistrées…")
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
        worker = _CatalogWorker(self.repository, token, self.kind, filters)
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
        elif isinstance(result, CatalogResult):
            self._apply_result(result)
        else:
            self._error("Réponse administrative inattendue")

    def _error(self, message):
        self.model.replace_rows(())
        self.table.clearSelection()
        self._selection_changed()
        self.summary.setText("Consultation indisponible : " + message)

    def _apply_result(self, result: CatalogResult):
        old = self.selected_row()
        old_id = old.id if old else None
        self.model.replace_rows(result.rows)
        if old_id is not None:
            for index, row in enumerate(result.rows):
                if row.id == old_id:
                    self.table.selectRow(index)
                    break
        self._selection_changed()
        self.summary.setText(
            f"{len(result.rows)}{'+' if result.truncated else ''} ligne(s)"
            + (" · affiner les filtres" if result.truncated else "")
            + " · aucun calcul ni rapprochement"
        )

    def selected_row(self):
        chosen = self.table.selectionModel().selectedRows()
        if not chosen:
            return None
        index = chosen[0].row()
        return self.model.rows[index] if 0 <= index < len(self.model.rows) else None

    def _selection_changed(self, *_args):
        row = self.selected_row()
        family = row.value("family") if row and "family" in self.spec.keys else None
        self.family_button.setVisible("family" in self.spec.keys)
        self.family_button.setEnabled(
            isinstance(family, int) and not isinstance(family, bool) and family > 0
        )
        self.inscription_button.setVisible(self.kind == "contracts")
        self.inscription_button.setEnabled(
            self.kind == "contracts" and row is not None
            and isinstance(row.value("inscription"), int)
            and row.value("inscription") > 0
        )
        self.activity_button.setVisible(self.kind in ACTIVITY_LINK_DOMAINS)
        activity = self._selected_activity_id(row)
        activity_is_valid = (
            isinstance(activity, int) and not isinstance(activity, bool)
            and activity > 0
        )
        self.activity_button.setEnabled(activity_is_valid)
        self.individual_button.setVisible(self.spec.individual_column is not None)
        individual = row.value("individual") if row and "individual" in self.spec.keys else None
        self.individual_button.setEnabled(
            isinstance(individual, int) and not isinstance(individual, bool)
            and individual > 0
        )
        for button in self.related_buttons.values():
            button.setEnabled(activity_is_valid)

    def _selected_activity_id(self, row):
        if row is None or self.kind not in ACTIVITY_LINK_DOMAINS:
            return None
        return (
            row.value("activity_id")
            if "activity_id" in self.spec.keys else row.id
        )

    def _open_activity(self):
        activity = self._selected_activity_id(self.selected_row())
        if isinstance(activity, int) and not isinstance(activity, bool) and activity > 0:
            self.activityRequested.emit(activity)

    def _open_related_activity(self, target: str):
        if (
            self.kind != "activity_overview"
            or target not in C17_ACTIVITY_DESTINATIONS
        ):
            raise ValueError("Lien d'activité non autorisé")
        identity = self._selected_activity_id(self.selected_row())
        if (
            isinstance(identity, int) and not isinstance(identity, bool)
            and identity > 0
        ):
            self.relatedActivityRequested.emit(target, identity)

    def _open_individual(self):
        row = self.selected_row()
        if row is None or self.spec.individual_column is None:
            return
        individual = row.value("individual")
        if isinstance(individual, int) and not isinstance(individual, bool) and individual > 0:
            self.individualRequested.emit(individual)

    def _open_family(self):
        row = self.selected_row()
        if row is None or "family" not in self.spec.keys:
            return
        family = row.value("family")
        if isinstance(family, int) and not isinstance(family, bool) and family > 0:
            self.familyRequested.emit(family)

    def _open_inscriptions(self):
        if self.kind != "contracts":
            return
        row = self.selected_row()
        if row is None:
            return
        identity = row.value("inscription")
        if isinstance(identity, int) and not isinstance(identity, bool) and identity > 0:
            self.inscriptionRequested.emit(identity)


class CatalogHubPage(QWidget):
    """Un grand module métier, une ou deux listes administratives natives."""

    familyRequested = Signal(int)
    inscriptionRequested = Signal(int)
    activityRequested = Signal(int)
    individualRequested = Signal(int)
    relatedActivityRequested = Signal(str, int)

    def __init__(self, repository: CatalogRepository, module: str, parent=None,
                 *, background=True):
        super().__init__(parent)
        if module not in CATALOG_MODULES:
            raise ValueError("Module métier Qt inconnu")
        self.module = module
        self._family_id = None
        self._activity_id = None
        self._individual_id = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        title = QLabel(CATALOG_MODULES[module][0] + " — consultation", self)
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)
        self.pages = {}
        for kind in CATALOG_MODULES[module][1]:
            page = CatalogTablePage(repository, kind, self.tabs, background=background)
            page.familyRequested.connect(self.familyRequested.emit)
            page.inscriptionRequested.connect(self.inscriptionRequested.emit)
            page.activityRequested.connect(self.activityRequested.emit)
            page.individualRequested.connect(self.individualRequested.emit)
            page.relatedActivityRequested.connect(self.relatedActivityRequested.emit)
            self.pages[kind] = page
            self.tabs.addTab(page, CATALOG_DOMAINS[kind].label)
        self.tabs.currentChanged.connect(self._tab_changed)

    @property
    def current_page(self):
        return self.tabs.currentWidget()

    def activate(self):
        self.current_page.activate()

    def _tab_changed(self, _index):
        self.activate()

    def set_family_context(self, family_id=None):
        validate_finance_id(family_id, "famille")
        if family_id is not None and not any(
            CATALOG_DOMAINS[kind].family_column is not None
            for kind in CATALOG_MODULES[self.module][1]
        ):
            raise ValueError("Ce module ne possède pas de dossier famille")
        self._family_id = family_id
        for page in self.pages.values():
            page.set_context(
                family_id=family_id if page.spec.family_column is not None else None
            )
        self.tabs.setCurrentIndex(0)

    def set_individual_context(self, individual_id=None):
        """Filtre un parcours de scolarité ou des pièces par ID individu exact."""
        validate_finance_id(individual_id, "individu")
        if individual_id is not None and not any(
            CATALOG_DOMAINS[kind].individual_column is not None
            for kind in CATALOG_MODULES[self.module][1]
        ):
            raise ValueError("Ce module ne possède pas de filtre individu")
        self._individual_id = individual_id
        for page in self.pages.values():
            page.set_context(
                individual_id=individual_id
                if page.spec.individual_column is not None else None
            )
        self.tabs.setCurrentIndex(0)

    def set_activity_context(self, activity_id=None):
        """Applique un identifiant d'activité aux onglets qui le supportent."""
        validate_finance_id(activity_id, "activité")
        if activity_id is not None and not any(
            CATALOG_DOMAINS[kind].activity_column is not None
            for kind in CATALOG_MODULES[self.module][1]
        ):
            raise ValueError("Ce module ne possède pas de filtre activité")
        self._activity_id = activity_id
        for page in self.pages.values():
            page.set_context(
                activity_id=activity_id
                if page.spec.activity_column is not None else None
            )
        self.tabs.setCurrentIndex(0)
