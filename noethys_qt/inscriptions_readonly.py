"""Inscriptions Qt, consultation native sur le schéma Noethys existant.

Ne modifie aucune inscription, aucun statut, tarif ou règlement. Les états
sont présentés tels qu'enregistrés, sans en inférer une facturation.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, QObject, QRunnable, QThreadPool,
    Qt, QTimer, Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableView, QVBoxLayout, QWidget,
)

from .consumptions_core import _escape_like, format_date

MAX_INSCRIPTIONS = 250


@dataclass(frozen=True, slots=True)
class InscriptionRow:
    id: int
    individual_id: int
    family_id: int | None
    activity_id: int | None
    group_id: int | None
    tariff_category_id: int | None
    registered: object
    withdrawn: object
    status: str | None
    last_name: str
    first_name: str
    activity: str
    group: str

    @property
    def individual_label(self) -> str:
        return " ".join(part for part in (self.last_name, self.first_name) if part)


@dataclass(frozen=True, slots=True)
class InscriptionResult:
    rows: tuple[InscriptionRow, ...]
    truncated: bool


def _valid_id(value: int | None, label: str) -> None:
    if value is not None and (
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
    ):
        raise ValueError(f"Identifiant {label} invalide.")


def build_inscription_query(
    *, family_id: int | None = None, individual_id: int | None = None,
    activity_id: int | None = None, text: str = "",
    limit: int = MAX_INSCRIPTIONS, placeholder: str = "?",
) -> tuple[str, tuple[object, ...]]:
    if placeholder not in ("?", "%s"):
        raise ValueError("Marqueur SQL non autorisé.")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_INSCRIPTIONS:
        raise ValueError("Limite d'inscriptions invalide.")
    for name, val in (
        ("famille", family_id), ("individu", individual_id), ("activité", activity_id)
    ):
        _valid_id(val, name)
    where: list[str] = []
    values: list[object] = []
    for field, val in (
        ("s.IDfamille", family_id), ("s.IDindividu", individual_id),
        ("s.IDactivite", activity_id)
    ):
        if val is not None:
            where.append(f"{field} = {placeholder}")
            values.append(val)
    query = text.strip()
    if query:
        parts = [
            f"{col} LIKE {placeholder} ESCAPE '!'"
            for col in ("i.nom", "i.prenom", "a.nom", "g.nom")
        ]
        values.extend([_escape_like(query)] * len(parts))
        if query.isdecimal() and len(query) <= 18:
            parts.extend((f"s.IDinscription = {placeholder}", f"s.IDindividu = {placeholder}"))
            values.extend((int(query), int(query)))
        where.append("(" + " OR ".join(parts) + ")")
    sql = (
        "SELECT s.IDinscription, s.IDindividu, s.IDfamille, s.IDactivite, "
        "s.IDgroupe, s.IDcategorie_tarif, s.date_inscription, "
        "s.date_desinscription, s.statut, i.nom, i.prenom, a.nom, g.nom "
        "FROM inscriptions s "
        "LEFT JOIN individus i ON i.IDindividu = s.IDindividu "
        "LEFT JOIN activites a ON a.IDactivite = s.IDactivite "
        "LEFT JOIN groupes g ON g.IDgroupe = s.IDgroupe "
        + ("WHERE " + " AND ".join(where) + " " if where else "")
        + "ORDER BY s.IDinscription DESC "
        + f"LIMIT {placeholder}"
    )
    values.append(limit + 1)
    return sql, tuple(values)


class InscriptionRepository:
    def __init__(self, editor_repository):
        self.editor_repository = editor_repository

    def search(
        self, *, family_id=None, individual_id=None,
        activity_id=None, text="", limit=MAX_INSCRIPTIONS,
    ) -> InscriptionResult:
        sql_params = dict(
            family_id=family_id, individual_id=individual_id,
            activity_id=activity_id, text=text, limit=limit,
        )
        # Validate before connecting to the configured database.
        build_inscription_query(**sql_params)
        connection, placeholder = self.editor_repository._connect()
        try:
            if isinstance(connection, sqlite3.Connection):
                connection.execute("PRAGMA query_only = ON")
            sql, params = build_inscription_query(**sql_params, placeholder=placeholder)
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                found = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        rows = tuple(
            InscriptionRow(
                id=int(r[0]), individual_id=int(r[1]),
                family_id=int(r[2]) if r[2] is not None else None,
                activity_id=int(r[3]) if r[3] is not None else None,
                group_id=int(r[4]) if r[4] is not None else None,
                tariff_category_id=int(r[5]) if r[5] is not None else None,
                registered=r[6], withdrawn=r[7],
                status=str(r[8]) if r[8] not in (None, "") else None,
                last_name=str(r[9] or ""), first_name=str(r[10] or ""),
                activity=str(r[11] or ""), group=str(r[12] or ""),
            )
            for r in found[:limit]
        )
        return InscriptionResult(rows, len(found) > limit)


class InscriptionTableModel(QAbstractTableModel):
    HEADERS = (
        "Inscription", "Individu", "Famille", "Nom", "Activité",
        "Groupe", "Inscrit le", "Désinscrit le", "Statut",
    )

    def __init__(self):
        super().__init__()
        self.rows: tuple[InscriptionRow, ...] = ()

    def replace_rows(self, rows) -> None:
        next_rows = tuple(rows)
        if next_rows == self.rows:
            return
        self.beginResetModel()
        self.rows = next_rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=int(Qt.ItemDataRole.DisplayRole)):
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
            return str((
                row.id, row.individual_id, row.family_id or "",
                row.individual_label, row.activity, row.group,
                format_date(row.registered), format_date(row.withdrawn),
                row.status or "Non renseigné",
            )[index.column()])
        return None


class _Signals(QObject):
    completed = Signal(int, object, str)


class _Worker(QRunnable):
    def __init__(self, repo, token, filters):
        super().__init__()
        self.setAutoDelete(False)
        self.repo, self.token, self.filters = repo, token, filters
        self.signals = _Signals()

    def run(self):
        try:
            result = self.repo.search(**self.filters)
        except Exception as exc:
            self.signals.completed.emit(self.token, None, str(exc))
        else:
            self.signals.completed.emit(self.token, result, "")


class InscriptionPage(QWidget):
    """Liste et liens de consultation ; aucune action de saisie possible."""

    familyRequested = Signal(int)
    individualRequested = Signal(int)
    consumptionsRequested = Signal(int)

    def __init__(self, repository: InscriptionRepository, parent=None, *, background=True):
        super().__init__(parent)
        self.repository = repository
        self.background = background
        self.model = InscriptionTableModel()
        self._filters = dict(family_id=None, individual_id=None, activity_id=None)
        self._token = 0
        self._queued = None
        self._worker = None
        self._loaded = False

        root = QVBoxLayout(self)
        title = QLabel("Inscriptions — consultation", self)
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        controls = QHBoxLayout()
        self.context_label = QLabel("Toutes les inscriptions", self)
        controls.addWidget(self.context_label)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Nom, activité, groupe ou identifiant…")
        self.search_edit.setClearButtonEnabled(True)
        controls.addWidget(self.search_edit, 1)
        self.clear_filter_button = QPushButton("Tous les dossiers", self)
        controls.addWidget(self.clear_filter_button)
        self.reload_button = QPushButton("Actualiser", self)
        controls.addWidget(self.reload_button)
        root.addLayout(controls)
        self.summary = QLabel("Liste limitée à 250 inscriptions. Aucun calcul financier.", self)
        root.addWidget(self.summary)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.family_button = QPushButton("Ouvrir la famille", self)
        self.individual_button = QPushButton("Ouvrir l'individu", self)
        self.consumptions_button = QPushButton("Consommations de l'inscription", self)
        buttons.addWidget(self.family_button)
        buttons.addWidget(self.individual_button)
        buttons.addWidget(self.consumptions_button)
        buttons.addStretch(1)
        root.addLayout(buttons)
        self.notice = QLabel(
            "Lecture seule — aucune inscription, facturation ou consommation n'est modifiée.",
            self,
        )
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(lambda _index: self._open_individual())
        self.family_button.clicked.connect(self._open_family)
        self.individual_button.clicked.connect(self._open_individual)
        self.consumptions_button.clicked.connect(self._open_consumptions)
        self.clear_filter_button.clicked.connect(self.clear_context)
        self.reload_button.clicked.connect(self.refresh)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.refresh)
        self.search_edit.textChanged.connect(lambda _value: self.timer.start())
        self._selection_changed()

    def activate(self):
        if not self._loaded:
            self.refresh()

    def set_context(self, *, family_id=None, individual_id=None, activity_id=None):
        for name, value in (
            ("famille", family_id), ("individu", individual_id), ("activité", activity_id)
        ):
            _valid_id(value, name)
        self._filters = dict(
            family_id=family_id, individual_id=individual_id, activity_id=activity_id
        )
        words = [f"{label} #{val}" for label, val in (
            ("Famille", family_id), ("Individu", individual_id), ("Activité", activity_id)
        ) if val is not None]
        self.context_label.setText(" · ".join(words) if words else "Toutes les inscriptions")
        self.search_edit.clear()
        if self._loaded:
            self.refresh()

    def clear_context(self):
        self.set_context()

    def refresh(self, *_args):
        self.timer.stop()
        self._loaded = True
        self._token += 1
        filters = {**self._filters, "text": self.search_edit.text().strip()}
        self.summary.setText("Chargement des inscriptions…")
        if not self.background:
            try:
                self._apply_result(self.repository.search(**filters))
            except Exception as exc:
                self._error(str(exc))
            return
        self._queued = (self._token, filters)
        self._launch()

    def _launch(self):
        if self._worker is not None or self._queued is None:
            return
        token, filters = self._queued
        self._queued = None
        worker = _Worker(self.repository, token, filters)
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
        elif isinstance(result, InscriptionResult):
            self._apply_result(result)
        else:
            self._error("Résultat inattendu.")

    def _error(self, message):
        self.model.replace_rows(())
        self._selection_changed()
        self.summary.setText("Inscriptions indisponibles : " + message)

    def _apply_result(self, result: InscriptionResult):
        old = self.selected_row()
        previous_id = old.id if old else None
        self.model.replace_rows(result.rows)
        if previous_id is not None:
            for index, row in enumerate(result.rows):
                if row.id == previous_id:
                    self.table.selectRow(index)
                    break
        self._selection_changed()
        self.summary.setText(
            f"{len(result.rows)}{'+' if result.truncated else ''} inscription(s)"
            + (" · affiner les filtres" if result.truncated else "")
        )

    def selected_row(self) -> InscriptionRow | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        return self.model.rows[index] if 0 <= index < len(self.model.rows) else None

    def _selection_changed(self, *_args):
        item = self.selected_row()
        self.family_button.setEnabled(item is not None and item.family_id is not None)
        self.individual_button.setEnabled(item is not None)
        self.consumptions_button.setEnabled(item is not None)

    def _open_family(self):
        row = self.selected_row()
        if row and row.family_id is not None:
            self.familyRequested.emit(row.family_id)

    def _open_individual(self):
        row = self.selected_row()
        if row:
            self.individualRequested.emit(row.individual_id)

    def _open_consumptions(self):
        row = self.selected_row()
        if row:
            self.consumptionsRequested.emit(row.id)
