"""Consultation Qt des individus et familles, sans écriture ni dépendance wx.

Ce premier lot ne remplace pas les fiches historiques : il expose les identifiants
stables, les coordonnées minimales et les rattachements pour valider la navigation.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .people_search import FamilyLink, PeopleSearchRepository, PersonRow


@dataclass(frozen=True, slots=True)
class FamilyMember:
    person: PersonRow
    link: FamilyLink


@dataclass(frozen=True, slots=True)
class FamilyDetails:
    family_id: int
    state: str | None
    members: tuple[FamilyMember, ...]

    @property
    def label(self) -> str:
        holders = [
            " ".join(part for part in (m.person.last_name, m.person.first_name) if part)
            for m in self.members if m.link.holder
        ]
        return " / ".join(holders) or f"Famille #{self.family_id}"


class PeopleDetailsRepository:
    """Requêtes SELECT uniquement ; la connexion est fermée même en cas d'erreur."""

    def __init__(self, people: PeopleSearchRepository):
        self.people = people

    def individual(self, individual_id: int) -> PersonRow:
        for row in self.people.fetch_people(include_archived=True, include_deleted=True):
            if row.individual_id == individual_id:
                return row
        raise LookupError(f"Individu #{individual_id} introuvable.")

    def family(self, family_id: int) -> FamilyDetails:
        connection, placeholder = self.people._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"SELECT etat FROM familles WHERE IDfamille={placeholder}", (family_id,)
                )
                value = cursor.fetchone()
            finally:
                cursor.close()
        finally:
            connection.close()
        if value is None:
            raise LookupError(f"Famille #{family_id} introuvable.")

        members = [
            FamilyMember(person, link)
            for person in self.people.fetch_people(
                include_archived=True, include_deleted=True
            )
            for link in person.families
            if link.family_id == family_id
        ]
        members.sort(
            key=lambda member: (
                member.link.category,
                not member.link.holder,
                member.person.last_name.casefold(),
                member.person.first_name.casefold(),
                member.person.individual_id,
            )
        )
        return FamilyDetails(
            family_id=family_id,
            state=str(value[0]) if value[0] not in (None, "") else None,
            members=tuple(members),
        )


def _plain_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _readonly_table(headers: tuple[str, ...]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(False)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    return table


class PeopleDetailsPage(QWidget):
    """Vue compacte : aucun formulaire éditable, mutation ou onglet wx."""

    backRequested = Signal()
    familyRequested = Signal(int)
    individualRequested = Signal(int)
    familyInscriptionsRequested = Signal(int)
    individualInscriptionsRequested = Signal(int)
    individualConsumptionsRequested = Signal(int)
    familyInvoicesRequested = Signal(int)
    familyPaymentsRequested = Signal(int)
    familyCatalogRequested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.loaded_kind: str | None = None
        self.current_id: int | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)

        header = QHBoxLayout()
        self.back_button = QPushButton("Retour à la recherche", self)
        self.back_button.clicked.connect(self.backRequested.emit)
        header.addWidget(self.back_button)
        header.addStretch(1)
        self.readonly_label = _plain_label("Consultation uniquement — aucune modification")
        header.addWidget(self.readonly_label)
        root.addLayout(header)

        self.title = _plain_label()
        self.title.setObjectName("sectionTitle")
        root.addWidget(self.title)
        self.message = _plain_label()
        root.addWidget(self.message)

        # C12 : actions contextuelles compactes, pas de nouvelle fenêtre.
        actions = QHBoxLayout()
        self.family_inscriptions_button = QPushButton(
            "Inscriptions de cette famille", self
        )
        self.individual_inscriptions_button = QPushButton(
            "Inscriptions de cet individu", self
        )
        self.individual_consumptions_button = QPushButton(
            "Consommations de cet individu", self
        )
        self.family_invoices_button = QPushButton(
            "Factures de cette famille", self
        )
        self.family_payments_button = QPushButton(
            "Règlements de cette famille", self
        )
        for button in (
            self.family_inscriptions_button,
            self.individual_inscriptions_button,
            self.individual_consumptions_button,
            self.family_invoices_button,
            self.family_payments_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)
        self.family_inscriptions_button.clicked.connect(
            self._request_family_inscriptions
        )
        self.individual_inscriptions_button.clicked.connect(
            self._request_individual_inscriptions
        )
        self.individual_consumptions_button.clicked.connect(
            self._request_individual_consumptions
        )
        self.family_invoices_button.clicked.connect(
            self._request_family_invoices
        )
        self.family_payments_button.clicked.connect(
            self._request_family_payments
        )

        # C14 : deuxième rangée compacte, sans ajouter cinq boutons
        # dans l'ancienne rangée des accès Familles/Consommations.
        catalog_actions = QHBoxLayout()
        self.catalog_buttons = {}
        for code, title in (
            ("memberships", "Cotisations"), ("contracts", "Contrats"),
            ("quotients", "Quotients"), ("rentals", "Locations"),
            ("quotes", "Devis"),
        ):
            button = QPushButton(title + " de cette famille", self)
            button.clicked.connect(
                lambda _checked=False, target=code: self._request_family_catalog(target)
            )
            self.catalog_buttons[code] = button
            catalog_actions.addWidget(button)
        catalog_actions.addStretch(1)
        root.addLayout(catalog_actions)

        self.person_group = QGroupBox("Identité et coordonnées", self)
        person_form = QFormLayout(self.person_group)
        self.person_name = _plain_label()
        self.person_birth = _plain_label()
        self.person_state = _plain_label()
        self.person_address = _plain_label()
        self.person_phone = _plain_label()
        self.person_email = _plain_label()
        for caption, label in (
            ("Nom", self.person_name),
            ("Naissance", self.person_birth),
            ("État", self.person_state),
            ("Adresse", self.person_address),
            ("Téléphone", self.person_phone),
            ("Email", self.person_email),
        ):
            person_form.addRow(caption, label)
        root.addWidget(self.person_group)

        self.links_group = QGroupBox("Familles de l'individu", self)
        link_layout = QVBoxLayout(self.links_group)
        self.links_table = _readonly_table(("ID famille", "Famille", "Rôle", "Titulaire"))
        link_layout.addWidget(self.links_table)
        link_layout.addWidget(
            _plain_label("Double-clic sur une famille pour la consulter.")
        )
        root.addWidget(self.links_group, 1)

        self.family_group = QGroupBox("Composition familiale", self)
        family_layout = QVBoxLayout(self.family_group)
        self.family_state = _plain_label()
        family_layout.addWidget(self.family_state)
        self.members_table = _readonly_table(("ID individu", "Identité", "Rôle", "Titulaire", "État"))
        family_layout.addWidget(self.members_table)
        family_layout.addWidget(
            _plain_label("Double-clic sur un individu pour consulter sa fiche.")
        )
        root.addWidget(self.family_group, 1)

        self.links_table.cellDoubleClicked.connect(self._open_family_row)
        self.members_table.cellDoubleClicked.connect(self._open_individual_row)
        self.show_loading("individual", 0)

    def _toggle_sections(self, *, individual: bool = False, family: bool = False) -> None:
        self.person_group.setVisible(individual)
        self.links_group.setVisible(individual)
        self.family_group.setVisible(family)
        self.family_inscriptions_button.setVisible(family)
        self.individual_inscriptions_button.setVisible(individual)
        self.individual_consumptions_button.setVisible(individual)
        self.family_invoices_button.setVisible(family)
        self.family_payments_button.setVisible(family)
        for button in self.catalog_buttons.values():
            button.setVisible(family)

    def _request_family_invoices(self) -> None:
        if self.loaded_kind == "family" and self.current_id is not None:
            self.familyInvoicesRequested.emit(self.current_id)

    def _request_family_payments(self) -> None:
        if self.loaded_kind == "family" and self.current_id is not None:
            self.familyPaymentsRequested.emit(self.current_id)

    def _request_family_catalog(self, code: str) -> None:
        if self.loaded_kind == "family" and self.current_id is not None:
            if code in self.catalog_buttons:
                self.familyCatalogRequested.emit(code, self.current_id)

    def _request_family_inscriptions(self) -> None:
        if self.loaded_kind == "family" and self.current_id is not None:
            self.familyInscriptionsRequested.emit(self.current_id)

    def _request_individual_inscriptions(self) -> None:
        if self.loaded_kind == "individual" and self.current_id is not None:
            self.individualInscriptionsRequested.emit(self.current_id)

    def _request_individual_consumptions(self) -> None:
        if self.loaded_kind == "individual" and self.current_id is not None:
            self.individualConsumptionsRequested.emit(self.current_id)

    def show_loading(self, kind: str, record_id: int) -> None:
        self.loaded_kind = None
        self.current_id = None
        self.title.setText("Chargement…")
        self.message.setText(
            f"Lecture de la {'famille' if kind == 'family' else 'fiche individuelle'} #{record_id}."
        )
        self._toggle_sections()

    def show_error(self, kind: str, record_id: int, error: str) -> None:
        self.loaded_kind = "error"
        self.current_id = record_id
        self.title.setText("Fiche indisponible")
        self.message.setText(error)
        self._toggle_sections()

    def show_individual(self, person: PersonRow) -> None:
        self.loaded_kind = "individual"
        self.current_id = person.individual_id
        self.title.setText(f"Individu #{person.individual_id}")
        self.message.setText("Fiche individuelle — lecture seule")
        self.person_name.setText(" ".join(part for part in (person.last_name, person.first_name) if part))
        self.person_birth.setText(person.birth_date.strftime("%d/%m/%Y") if person.birth_date else "Non renseignée")
        self.person_state.setText(person.state_label or "Actif")
        self.person_address.setText(
            " ".join(part for part in (person.street, person.postal_code, person.city) if part) or "Non renseignée"
        )
        self.person_phone.setText(person.phone_text or "Non renseigné")
        self.person_email.setText(person.email or person.work_email or "Non renseigné")
        self.links_table.setRowCount(len(person.families))
        for index, link in enumerate(person.families):
            self.links_table.setItem(index, 0, QTableWidgetItem(str(link.family_id)))
            self.links_table.setItem(index, 1, QTableWidgetItem(link.family_label))
            self.links_table.setItem(index, 2, QTableWidgetItem(link.role_label))
            self.links_table.setItem(index, 3, QTableWidgetItem("Oui" if link.holder else "Non"))
        self._toggle_sections(individual=True)

    def show_family(self, family: FamilyDetails) -> None:
        self.loaded_kind = "family"
        self.current_id = family.family_id
        self.title.setText(f"Famille #{family.family_id} — {family.label}")
        self.message.setText("Fiche familiale — lecture seule")
        self.family_state.setText(
            "État de la famille : " + (family.state or "Actif") +
            f" · {len(family.members)} rattachement(s)"
        )
        self.members_table.setRowCount(len(family.members))
        for index, member in enumerate(family.members):
            self.members_table.setItem(index, 0, QTableWidgetItem(str(member.person.individual_id)))
            name = " ".join(part for part in (member.person.last_name, member.person.first_name) if part)
            self.members_table.setItem(index, 1, QTableWidgetItem(name))
            self.members_table.setItem(index, 2, QTableWidgetItem(member.link.role_label))
            self.members_table.setItem(index, 3, QTableWidgetItem("Oui" if member.link.holder else "Non"))
            self.members_table.setItem(index, 4, QTableWidgetItem(member.person.state_label or "Actif"))
        self._toggle_sections(family=True)

    def _open_family_row(self, row: int, _column: int) -> None:
        item = self.links_table.item(row, 0)
        if item is not None:
            self.familyRequested.emit(int(item.text()))

    def _open_individual_row(self, row: int, _column: int) -> None:
        item = self.members_table.item(row, 0)
        if item is not None:
            self.individualRequested.emit(int(item.text()))
