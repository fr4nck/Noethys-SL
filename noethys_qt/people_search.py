"""Recherche Qt native des individus et familles Noethys.

La surface reprend les invariants du panneau historique : recherche rapide,
limite de 30 résultats, fallback approximatif, adresses héritées via
``adresse_auto`` et rattachements familiaux. Aucun import wx/GestionDB.
"""

from __future__ import annotations

import datetime as dt
import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .activity_editor import NativeActivityEditorRepository


RESULT_LIMIT = 30
_ROLE_LABELS = {1: "représentant", 2: "enfant", 3: "contact"}
_PHONE_RE = re.compile(r"\D+")


def _date(value: object) -> dt.date | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _age(value: dt.date | None, today: dt.date | None = None) -> int | None:
    if value is None:
        return None
    today = today or dt.date.today()
    return today.year - value.year - int((today.month, today.day) < (value.month, value.day))


def _normalize(value: object) -> str:
    text = str(value or "").casefold().strip()
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    return " ".join(text.split())


def _phone(value: object) -> str:
    return _PHONE_RE.sub("", str(value or ""))


@dataclass(frozen=True, slots=True)
class FamilyLink:
    family_id: int
    family_label: str
    category: int
    holder: bool

    @property
    def role_label(self) -> str:
        label = _ROLE_LABELS.get(self.category, "rattachement")
        if self.category == 1 and self.holder:
            return f"{label} titulaire"
        return label


@dataclass(frozen=True, slots=True)
class PersonRow:
    individual_id: int
    last_name: str
    first_name: str
    birth_date: dt.date | None
    street: str
    postal_code: str
    city: str
    home_phone: str
    mobile_phone: str
    work_phone: str
    email: str
    work_email: str
    profession: str
    employer: str
    state: str | None
    families: tuple[FamilyLink, ...]

    @property
    def age(self) -> int | None:
        return _age(self.birth_date)

    @property
    def family_text(self) -> str:
        return " | ".join(link.family_label for link in self.families)

    @property
    def phone_text(self) -> str:
        return self.mobile_phone or self.home_phone or self.work_phone

    @property
    def state_label(self) -> str:
        return {"archive": "Archivé", "efface": "Effacé"}.get(self.state or "", "")

    @property
    def search_text(self) -> str:
        values: Iterable[object] = (
            self.last_name,
            self.first_name,
            self.street,
            self.postal_code,
            self.city,
            self.home_phone,
            self.mobile_phone,
            self.work_phone,
            self.email,
            self.work_email,
            self.profession,
            self.employer,
            self.family_text,
        )
        return _normalize(" ".join(str(value or "") for value in values))

    @property
    def phone_digits(self) -> str:
        return " ".join(
            value for value in (_phone(self.home_phone), _phone(self.mobile_phone), _phone(self.work_phone)) if value
        )


@dataclass(frozen=True, slots=True)
class SearchResult:
    rows: tuple[PersonRow, ...]
    total: int
    approximate: bool = False


class PeopleSearchRepository:
    """Lecture de recherche sur la base Noethys configurée ou une copie SQLite."""

    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont natif transitoire

    def fetch_people(
        self,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> list[PersonRow]:
        connection, _placeholder = self._connect()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """SELECT IDindividu, nom, prenom, date_naiss, adresse_auto,
                          rue_resid, cp_resid, ville_resid, tel_domicile, tel_mobile,
                          travail_tel, mail, travail_mail, profession, employeur, etat
                   FROM individus"""
            )
            raw_rows = cursor.fetchall()
            by_id: dict[int, tuple[object, ...]] = {int(row[0]): tuple(row) for row in raw_rows}

            cursor.execute(
                """SELECT IDindividu, IDfamille, IDcategorie, titulaire
                   FROM rattachements
                   ORDER BY IDfamille, IDcategorie, titulaire DESC, IDindividu"""
            )
            raw_links = [tuple(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
            connection.close()

        family_members: dict[int, list[tuple[int, int, bool]]] = {}
        individual_links: dict[int, list[tuple[int, int, bool]]] = {}
        for individual_id, family_id, category, holder in raw_links:
            individual_id = int(individual_id)
            family_id = int(family_id)
            category = int(category or 0)
            value = (individual_id, category, bool(holder))
            family_members.setdefault(family_id, []).append(value)
            individual_links.setdefault(individual_id, []).append((family_id, category, bool(holder)))

        family_labels: dict[int, str] = {}
        for family_id, members in family_members.items():
            representatives = [item for item in members if item[1] == 1]
            candidates = representatives or members
            candidates = sorted(candidates, key=lambda item: (not item[2], item[0]))
            labels: list[str] = []
            for individual_id, _category, _holder in candidates:
                raw = by_id.get(individual_id)
                if raw is None:
                    continue
                name = " ".join(part for part in (str(raw[1] or "").strip(), str(raw[2] or "").strip()) if part)
                if name and name not in labels:
                    labels.append(name)
            family_labels[family_id] = " / ".join(labels) if labels else f"Famille #{family_id}"

        rows: list[PersonRow] = []
        for raw in raw_rows:
            individual_id = int(raw[0])
            state = str(raw[15]) if raw[15] not in (None, "") else None
            if state == "archive" and not include_archived:
                continue
            if state == "efface" and not include_deleted:
                continue
            if state not in (None, "archive", "efface"):
                continue

            address_source = by_id.get(int(raw[4])) if raw[4] not in (None, "") and str(raw[4]).isdigit() else None
            source = address_source or raw
            links = tuple(
                FamilyLink(
                    family_id=family_id,
                    family_label=family_labels.get(family_id, f"Famille #{family_id}"),
                    category=category,
                    holder=holder,
                )
                for family_id, category, holder in individual_links.get(individual_id, ())
            )
            rows.append(
                PersonRow(
                    individual_id=individual_id,
                    last_name=str(raw[1] or ""),
                    first_name=str(raw[2] or ""),
                    birth_date=_date(raw[3]),
                    street=str(source[5] or ""),
                    postal_code=str(source[6] or ""),
                    city=str(source[7] or ""),
                    home_phone=str(raw[8] or ""),
                    mobile_phone=str(raw[9] or ""),
                    work_phone=str(raw[10] or ""),
                    email=str(raw[11] or ""),
                    work_email=str(raw[12] or ""),
                    profession=str(raw[13] or ""),
                    employer=str(raw[14] or ""),
                    state=state,
                    families=links,
                )
            )
        rows.sort(key=lambda row: (_normalize(row.last_name), _normalize(row.first_name), row.individual_id))
        return rows

    @staticmethod
    def _exact_match(row: PersonRow, query: str) -> bool:
        normalized = _normalize(query)
        if not normalized:
            return True
        tokens = normalized.split()
        if all(token in row.search_text for token in tokens):
            return True
        digits = _phone(query)
        return len(digits) >= 4 and digits in row.phone_digits.replace(" ", "")

    @staticmethod
    def _approximate_match(row: PersonRow, query: str) -> bool:
        normalized = _normalize(query)
        if not normalized:
            return True
        candidates = [
            _normalize(f"{row.last_name} {row.first_name}"),
            _normalize(f"{row.first_name} {row.last_name}"),
            *(_normalize(link.family_label) for link in row.families),
            _normalize(row.city),
            _normalize(row.email),
        ]
        return any(
            candidate and difflib.SequenceMatcher(None, normalized, candidate).ratio() >= 0.72
            for candidate in candidates
        )

    def search(
        self,
        query: str,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
        limit: int | None = RESULT_LIMIT,
    ) -> SearchResult:
        people = self.fetch_people(
            include_archived=include_archived,
            include_deleted=include_deleted,
        )
        query = query.strip()
        if not query:
            matches = people
            approximate = False
        else:
            matches = [row for row in people if self._exact_match(row, query)]
            approximate = False
            if not matches:
                matches = [row for row in people if self._approximate_match(row, query)]
                approximate = bool(matches)
        total = len(matches)
        if limit is not None:
            matches = matches[:limit]
        return SearchResult(tuple(matches), total, approximate)


class PeopleTableModel(QAbstractTableModel):
    HEADERS = ("Nom", "Prénom", "Date naiss.", "Âge", "Famille(s)", "Ville", "Téléphone", "Email", "État")

    def __init__(self, rows: Iterable[PersonRow] = ()):  # noqa: D107
        super().__init__()
        self.rows = list(rows)

    def replace_rows(self, rows: Iterable[PersonRow]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = int(Qt.ItemDataRole.DisplayRole)):  # noqa: N802,E501
        if role == int(Qt.ItemDataRole.DisplayRole) and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == int(Qt.ItemDataRole.DisplayRole):
            values = (
                row.last_name,
                row.first_name,
                row.birth_date.strftime("%d/%m/%Y") if row.birth_date else "",
                "" if row.age is None else str(row.age),
                row.family_text,
                row.city,
                row.phone_text,
                row.email or row.work_email,
                row.state_label,
            )
            return values[index.column()]
        if role == int(Qt.ItemDataRole.UserRole):
            return row
        return None

    def row_at(self, index: int) -> PersonRow:
        return self.rows[index]


class PeopleSearchPage(QWidget):
    """Surface quotidienne de recherche personnes/familles."""

    familyRequested = Signal(int)
    individualRequested = Signal(int)

    def __init__(self, repository: PeopleSearchRepository, parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository
        self.model = PeopleTableModel()
        self._last_query = ""
        self._show_all = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        controls = QHBoxLayout()
        self.summary = QLabel("Recherche rapide", self)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Rechercher une famille ou un individu…")
        self.search_edit.setClearButtonEnabled(True)
        self.archives_check = QCheckBox("Archives", self)
        self.deleted_check = QCheckBox("Effacés", self)
        self.show_all_button = QPushButton("Voir tout", self)
        controls.addWidget(self.summary)
        controls.addWidget(self.search_edit, 1)
        controls.addWidget(self.archives_check)
        controls.addWidget(self.deleted_check)
        controls.addWidget(self.show_all_button)
        root.addLayout(controls)

        self.hint = QLabel("Nom, prénom, téléphone, email, adresse, code postal, ville ou famille.", self)
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.table = QTableView(splitter)
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.table)

        details = QGroupBox("Sélection", splitter)
        detail_layout = QVBoxLayout(details)
        self.person_label = QLabel("Aucun individu sélectionné", details)
        self.person_label.setWordWrap(True)
        self.family_label = QLabel("", details)
        self.family_label.setWordWrap(True)
        self.contact_label = QLabel("", details)
        self.contact_label.setWordWrap(True)
        self.open_family_button = QPushButton("Ouvrir la famille", details)
        self.open_individual_button = QPushButton("Fiche individuelle", details)
        detail_layout.addWidget(self.person_label)
        detail_layout.addWidget(self.family_label)
        detail_layout.addWidget(self.contact_label)
        detail_layout.addStretch(1)
        detail_layout.addWidget(self.open_family_button)
        detail_layout.addWidget(self.open_individual_button)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(160)
        self.timer.timeout.connect(self.search_now)
        self.search_edit.textChanged.connect(self._queue_search)
        self.archives_check.toggled.connect(lambda _value: self.search_now())
        self.deleted_check.toggled.connect(lambda _value: self.search_now())
        self.show_all_button.clicked.connect(self.show_all)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(self._activate_row)
        self.open_family_button.clicked.connect(self._request_family)
        self.open_individual_button.clicked.connect(self._request_individual)
        self._sync_buttons()

    def _queue_search(self, *_args) -> None:
        self._show_all = False
        self.timer.start()

    def search_now(self) -> None:
        self.timer.stop()
        query = self.search_edit.text().strip()
        self._last_query = query
        limit = None if self._show_all and not query else RESULT_LIMIT
        try:
            result = self.repository.search(
                query,
                include_archived=self.archives_check.isChecked(),
                include_deleted=self.deleted_check.isChecked(),
                limit=limit,
            )
        except Exception as exc:
            self.model.replace_rows(())
            self.summary.setText("Recherche indisponible")
            self.hint.setText(str(exc))
            self._sync_buttons()
            return

        self.model.replace_rows(result.rows)
        if query:
            suffix = " · proches" if result.approximate else ""
            plus = "+" if result.total > len(result.rows) else ""
            self.summary.setText(f"{plus}{len(result.rows)} résultat(s){suffix}")
            self.hint.setText(
                f"{result.total} correspondance(s) pour « {query} »." if result.total else f"Aucune fiche ne correspond à « {query} »."
            )
        else:
            self.summary.setText(
                f"{len(result.rows)} individu(s) · liste complète" if self._show_all else "Recherche rapide"
            )
            self.hint.setText(
                "Liste complète des individus actifs." if self._show_all else "Saisissez un nom, prénom, téléphone, email, adresse, code postal, ville ou famille."
            )
        self._selection_changed()

    def show_all(self) -> None:
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self._show_all = True
        self.search_now()

    def focus_search(self) -> None:
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search_edit.selectAll()

    def selected_person(self) -> PersonRow | None:
        index = self.table.currentIndex()
        if not index.isValid() or index.row() >= len(self.model.rows):
            return None
        return self.model.row_at(index.row())

    def _selection_changed(self, *_args) -> None:
        row = self.selected_person()
        if row is None:
            self.person_label.setText("Aucun individu sélectionné")
            self.family_label.clear()
            self.contact_label.clear()
            self._sync_buttons()
            return
        name = " ".join(part for part in (row.last_name, row.first_name) if part)
        birth = f" · né(e) le {row.birth_date:%d/%m/%Y}" if row.birth_date else ""
        self.person_label.setText(f"<b>{name}</b>{birth}")
        if row.families:
            self.family_label.setText("<br>".join(
                f"Famille {link.family_label} — {link.role_label}" for link in row.families
            ))
        else:
            self.family_label.setText("Rattaché à aucune famille")
        address = " ".join(part for part in (row.street, row.postal_code, row.city) if part)
        contact = " · ".join(part for part in (row.phone_text, row.email or row.work_email) if part)
        self.contact_label.setText("<br>".join(part for part in (address, contact) if part))
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        row = self.selected_person()
        self.open_individual_button.setEnabled(row is not None)
        self.open_family_button.setEnabled(row is not None and bool(row.families))

    def _request_family(self) -> None:
        row = self.selected_person()
        if row is None or not row.families:
            return
        self.familyRequested.emit(row.families[0].family_id)

    def _request_individual(self) -> None:
        row = self.selected_person()
        if row is not None:
            self.individualRequested.emit(row.individual_id)

    def _activate_row(self, *_args) -> None:
        row = self.selected_person()
        if row is None:
            return
        if len(row.families) == 1:
            self.familyRequested.emit(row.families[0].family_id)
        else:
            self.individualRequested.emit(row.individual_id)
