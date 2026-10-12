"""Page Qt « Renseignements » de la fiche Activité.

La page reprend les quatre obligations historiques : pièces à fournir,
cotisations à jour, vaccins obligatoires et informations du dossier à
renseigner. Elle écrit exclusivement dans les tables Noethys existantes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .activity_calendar import ActivityEditorDialog as CalendarActivityEditorDialog
from .activity_editor import NativeActivityEditorRepository


INFORMATION_TYPES = (
    (1, "Date de naissance"),
    (2, "Lieu de naissance"),
    (3, "Numéro de sécurité sociale"),
    (6, "Médecin traitant"),
    (12, "Quotient familial"),
    (7, "Caisse d'allocations"),
    (8, "Numéro d'allocataire"),
    (9, "Titulaire allocataire"),
    (10, "Titulaire Hélios"),
    (11, "Code comptable"),
)


@dataclass(frozen=True, slots=True)
class RequirementsState:
    piece_ids: frozenset[int]
    cotisation_required: bool
    cotisation_ids: frozenset[int]
    vaccines_required: bool
    information_ids: frozenset[int]


class ActivityRequirementsRepository:
    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001 - pont transitoire volontaire

    def _pairs(self, sql: str) -> list[tuple[int, str]]:
        connection, _placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(sql)
            return [(int(row[0]), str(row[1] or "")) for row in cursor.fetchall()]
        finally:
            cursor.close(); connection.close()

    def list_pieces(self) -> list[tuple[int, str]]:
        return self._pairs("SELECT IDtype_piece, nom FROM types_pieces ORDER BY nom")

    def list_cotisations(self) -> list[tuple[int, str]]:
        return self._pairs("SELECT IDtype_cotisation, nom FROM types_cotisations ORDER BY nom")

    def load(self, activity_id: int) -> RequirementsState:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT IDtype_piece FROM pieces_activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            pieces = frozenset(int(row[0]) for row in cursor.fetchall())
            cursor.execute(
                f"SELECT IDtype_cotisation FROM cotisations_activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            cotisations = frozenset(int(row[0]) for row in cursor.fetchall())
            cursor.execute(
                f"SELECT IDtype_renseignement FROM renseignements_activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            informations = frozenset(int(row[0]) for row in cursor.fetchall())
            cursor.execute(
                f"SELECT vaccins_obligatoires FROM activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Activité introuvable.")
            vaccines = bool(row[0])
            return RequirementsState(
                piece_ids=pieces,
                cotisation_required=bool(cotisations),
                cotisation_ids=cotisations,
                vaccines_required=vaccines,
                information_ids=informations,
            )
        finally:
            cursor.close(); connection.close()

    @staticmethod
    def validate(state: RequirementsState) -> None:
        if state.cotisation_required and not state.cotisation_ids:
            raise ValueError(
                "Vous avez activé l'obligation de cotisation sans sélectionner de cotisation."
            )

    def save(self, activity_id: int, state: RequirementsState) -> None:
        self.validate(state)
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"UPDATE activites SET vaccins_obligatoires={placeholder} WHERE IDactivite={placeholder}",
                (1 if state.vaccines_required else 0, activity_id),
            )

            cursor.execute(
                f"DELETE FROM pieces_activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            for piece_id in sorted(state.piece_ids):
                cursor.execute(
                    f"INSERT INTO pieces_activites (IDactivite, IDtype_piece) VALUES ({placeholder}, {placeholder})",
                    (activity_id, piece_id),
                )

            cursor.execute(
                f"DELETE FROM cotisations_activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            if state.cotisation_required:
                for cotisation_id in sorted(state.cotisation_ids):
                    cursor.execute(
                        f"INSERT INTO cotisations_activites (IDactivite, IDtype_cotisation) VALUES ({placeholder}, {placeholder})",
                        (activity_id, cotisation_id),
                    )

            cursor.execute(
                f"DELETE FROM renseignements_activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            for information_id in sorted(state.information_ids):
                cursor.execute(
                    f"INSERT INTO renseignements_activites (IDactivite, IDtype_renseignement) VALUES ({placeholder}, {placeholder})",
                    (activity_id, information_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close(); connection.close()


class CheckList(QListWidget):
    def set_values(self, choices: Iterable[tuple[int, str]], checked: Iterable[int]) -> None:
        checked_ids = set(int(value) for value in checked)
        self.clear()
        for item_id, label in choices:
            item = QListWidgetItem(label, self)
            item.setData(Qt.ItemDataRole.UserRole, int(item_id))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if int(item_id) in checked_ids else Qt.CheckState.Unchecked
            )

    def checked_ids(self) -> frozenset[int]:
        return frozenset(
            int(self.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.count())
            if self.item(index).checkState() == Qt.CheckState.Checked
        )


class ActivityRequirementsPage(QWidget):
    def __init__(
        self,
        editor_repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.activity_id = activity_id
        self.repository = ActivityRequirementsRepository(editor_repository)
        self.state = self.repository.load(activity_id)

        root = QVBoxLayout(self); root.setContentsMargins(10, 10, 10, 10); root.setSpacing(10)

        pieces_box = QGroupBox("Pièces à fournir", self); pieces_layout = QVBoxLayout(pieces_box)
        self.pieces = CheckList(pieces_box); pieces_layout.addWidget(self.pieces)
        pieces_layout.addWidget(QLabel("Cochez les pièces que l'individu doit fournir pour cette activité.", pieces_box))
        root.addWidget(pieces_box, 1)

        cotisations_box = QGroupBox("Cotisations", self); cotisations_layout = QVBoxLayout(cotisations_box)
        self.cotisation_required = QCheckBox(
            "L'individu inscrit doit avoir à jour au moins l'une des cotisations suivantes :",
            cotisations_box,
        )
        self.cotisations = CheckList(cotisations_box)
        cotisations_layout.addWidget(self.cotisation_required); cotisations_layout.addWidget(self.cotisations)
        self.cotisation_required.toggled.connect(self.cotisations.setEnabled)
        root.addWidget(cotisations_box, 1)

        vaccines_box = QGroupBox("Vaccins obligatoires", self); vaccines_layout = QVBoxLayout(vaccines_box)
        self.vaccines_required = QCheckBox(
            "L'individu inscrit doit avoir ses vaccins à jour",
            vaccines_box,
        )
        vaccines_layout.addWidget(self.vaccines_required)
        vaccines_layout.addWidget(QLabel(
            "Les types de vaccins et maladies restent ceux du paramétrage général Noethys.",
            vaccines_box,
        ))
        root.addWidget(vaccines_box)

        infos_box = QGroupBox("Informations à renseigner", self); infos_layout = QVBoxLayout(infos_box)
        self.informations = CheckList(infos_box); infos_layout.addWidget(self.informations)
        root.addWidget(infos_box, 1)

        self._load_controls()

    def _load_controls(self) -> None:
        self.pieces.set_values(self.repository.list_pieces(), self.state.piece_ids)
        self.cotisations.set_values(self.repository.list_cotisations(), self.state.cotisation_ids)
        self.cotisation_required.setChecked(self.state.cotisation_required)
        self.cotisations.setEnabled(self.state.cotisation_required)
        self.vaccines_required.setChecked(self.state.vaccines_required)
        self.informations.set_values(INFORMATION_TYPES, self.state.information_ids)

    def collect(self) -> RequirementsState:
        state = RequirementsState(
            piece_ids=self.pieces.checked_ids(),
            cotisation_required=self.cotisation_required.isChecked(),
            cotisation_ids=self.cotisations.checked_ids(),
            vaccines_required=self.vaccines_required.isChecked(),
            information_ids=self.informations.checked_ids(),
        )
        self.repository.validate(state)
        return state

    def save(self, state: RequirementsState | None = None) -> None:
        state = state or self.collect()
        self.repository.save(self.activity_id, state)
        self.state = state


class ActivityEditorDialog(CalendarActivityEditorDialog):
    """Fiche Activité avec Renseignements enregistrés par le bouton principal."""

    def __init__(
        self,
        repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(repository, activity_id, parent)
        old_page = self.tabs.widget(3); self.tabs.removeTab(3)
        if old_page is not None:
            old_page.deleteLater()
        self.requirements_page = ActivityRequirementsPage(repository, activity_id, self)
        self.tabs.insertTab(3, self.requirements_page, "Renseignements")

    def _save(self) -> None:
        try:
            # Valider l'ensemble avant la première écriture évite tout commit partiel
            # dû à une erreur de saisie utilisateur.
            details = self._collect()
            requirements = self.requirements_page.collect()
            self.repository.save(details, self._checked_group_ids())
            self.requirements_page.save(requirements)
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))
            return
        self.details = details
        self.accept()
