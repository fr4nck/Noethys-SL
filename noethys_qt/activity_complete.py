"""Complète la fiche Activité Qt avec responsables et logo.

Les responsables gardent le comportement historique d'édition immédiate.
Le choix du logo, lui, est validé avec le bouton Enregistrer de la fiche et
participe à la transaction composée avec Généralités/Renseignements/Agréments/
Portail.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .activity_agreements import ActivityAgreementsRepository
from .activity_editor import NativeActivityEditorRepository
from .activity_portal import (
    ActivityEditorDialog as PortalActivityEditorDialog,
    ActivityPortalRepository,
)
from .activity_requirements import ActivityRequirementsRepository
from .activity_transaction import activity_transaction


@dataclass(frozen=True, slots=True)
class ActivityResponsible:
    responsible_id: int
    activity_id: int
    name: str
    function: str
    is_default: bool
    gender: str


@dataclass(frozen=True, slots=True)
class ActivityLogoState:
    from_organizer: bool
    image: bytes | None


class ActivityGeneralExtrasRepository:
    def __init__(self, editor_repository: NativeActivityEditorRepository):
        self.editor_repository = editor_repository

    def _connect(self):
        return self.editor_repository._connect()  # noqa: SLF001

    def list_responsibles(self, activity_id: int) -> list[ActivityResponsible]:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"""SELECT IDresponsable, IDactivite, nom, fonction, defaut, sexe
                    FROM responsables_activite WHERE IDactivite={placeholder}
                    ORDER BY nom, IDresponsable""",
                (activity_id,),
            )
            return [
                ActivityResponsible(
                    responsible_id=int(row[0]), activity_id=int(row[1]),
                    name=str(row[2] or ""), function=str(row[3] or ""),
                    is_default=bool(row[4]), gender=str(row[5] or "H"),
                )
                for row in cursor.fetchall()
            ]
        finally:
            cursor.close(); connection.close()

    def save_responsible(
        self,
        activity_id: int,
        name: str,
        function: str,
        gender: str,
        responsible_id: int | None = None,
    ) -> int:
        name = name.strip(); function = function.strip(); gender = gender.strip().upper()
        if not name:
            raise ValueError("Vous devez obligatoirement saisir le nom du responsable.")
        if gender not in {"H", "F"}:
            raise ValueError("Le genre du responsable doit être H ou F.")
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            if responsible_id is None:
                cursor.execute(
                    f"SELECT COUNT(*) FROM responsables_activite WHERE IDactivite={placeholder}",
                    (activity_id,),
                )
                is_default = 1 if int(cursor.fetchone()[0] or 0) == 0 else 0
                cursor.execute(
                    "INSERT INTO responsables_activite (IDactivite, sexe, nom, fonction, defaut) "
                    f"VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})",
                    (activity_id, gender, name, function or None, is_default),
                )
                responsible_id = int(cursor.lastrowid)
            else:
                cursor.execute(
                    f"UPDATE responsables_activite SET sexe={placeholder}, nom={placeholder}, fonction={placeholder} "
                    f"WHERE IDresponsable={placeholder} AND IDactivite={placeholder}",
                    (gender, name, function or None, responsible_id, activity_id),
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        f"SELECT 1 FROM responsables_activite WHERE IDresponsable={placeholder} AND IDactivite={placeholder}",
                        (responsible_id, activity_id),
                    )
                    if cursor.fetchone() is None:
                        raise ValueError("Responsable introuvable.")
            connection.commit(); return int(responsible_id)
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def delete_responsible(self, activity_id: int, responsible_id: int) -> None:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT defaut FROM responsables_activite WHERE IDresponsable={placeholder} AND IDactivite={placeholder}",
                (responsible_id, activity_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Responsable introuvable.")
            was_default = bool(row[0])
            cursor.execute(
                f"DELETE FROM responsables_activite WHERE IDresponsable={placeholder} AND IDactivite={placeholder}",
                (responsible_id, activity_id),
            )
            if was_default:
                cursor.execute(
                    f"SELECT IDresponsable FROM responsables_activite WHERE IDactivite={placeholder} ORDER BY nom, IDresponsable",
                    (activity_id,),
                )
                replacement = cursor.fetchone()
                if replacement is not None:
                    cursor.execute(
                        f"UPDATE responsables_activite SET defaut=1 WHERE IDresponsable={placeholder} AND IDactivite={placeholder}",
                        (int(replacement[0]), activity_id),
                    )
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def set_default(self, activity_id: int, responsible_id: int) -> None:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT 1 FROM responsables_activite WHERE IDresponsable={placeholder} AND IDactivite={placeholder}",
                (responsible_id, activity_id),
            )
            if cursor.fetchone() is None:
                raise ValueError("Responsable introuvable.")
            cursor.execute(
                f"UPDATE responsables_activite SET defaut=0 WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            cursor.execute(
                f"UPDATE responsables_activite SET defaut=1 WHERE IDresponsable={placeholder} AND IDactivite={placeholder}",
                (responsible_id, activity_id),
            )
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()

    def load_logo(self, activity_id: int) -> ActivityLogoState:
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT logo_org, logo FROM activites WHERE IDactivite={placeholder}",
                (activity_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Activité introuvable.")
            image = bytes(row[1]) if row[1] is not None else None
            return ActivityLogoState(from_organizer=bool(row[0]), image=image)
        finally:
            cursor.close(); connection.close()

    def save_logo(self, activity_id: int, state: ActivityLogoState) -> None:
        if not state.from_organizer and state.image is None:
            raise ValueError("Vous avez sélectionné un logo personnalisé sans choisir d'image.")
        connection, placeholder = self._connect(); cursor = connection.cursor()
        try:
            cursor.execute(
                f"UPDATE activites SET logo_org={placeholder}, logo={placeholder} WHERE IDactivite={placeholder}",
                (1 if state.from_organizer else 0, None if state.from_organizer else state.image, activity_id),
            )
            if cursor.rowcount == 0:
                cursor.execute(f"SELECT 1 FROM activites WHERE IDactivite={placeholder}", (activity_id,))
                if cursor.fetchone() is None:
                    raise ValueError("Activité introuvable.")
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close(); connection.close()


class ResponsibleDialog(QDialog):
    def __init__(self, responsible: ActivityResponsible | None = None, parent: QWidget | None = None):
        super().__init__(parent); self.responsible = responsible
        self.setWindowTitle("Responsable de l'activité")
        root = QVBoxLayout(self); form = QFormLayout(); root.addLayout(form)
        self.gender_combo = QComboBox(self); self.gender_combo.addItem("Homme", "H"); self.gender_combo.addItem("Femme", "F")
        self.name_edit = QLineEdit(self); self.function_edit = QLineEdit(self)
        form.addRow("Genre :", self.gender_combo); form.addRow("Nom :", self.name_edit); form.addRow("Fonction :", self.function_edit)
        if responsible is not None:
            index = self.gender_combo.findData(responsible.gender); self.gender_combo.setCurrentIndex(max(0, index))
            self.name_edit.setText(responsible.name); self.function_edit.setText(responsible.function)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer"); buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def values(self) -> tuple[str, str, str]:
        name = self.name_edit.text().strip()
        if not name: raise ValueError("Vous devez obligatoirement saisir le nom du responsable.")
        return name, self.function_edit.text().strip(), str(self.gender_combo.currentData())

    def _accept(self) -> None:
        try: self.values()
        except ValueError as exc: QMessageBox.warning(self, "Erreur de saisie", str(exc)); return
        self.accept()


class GeneralExtrasBox(QGroupBox):
    def __init__(self, editor_repository: NativeActivityEditorRepository, activity_id: int,
                 parent: QWidget | None = None):
        super().__init__("Responsables et logo", parent)
        self.repository = ActivityGeneralExtrasRepository(editor_repository); self.activity_id = activity_id
        self.logo_state = self.repository.load_logo(activity_id); self.logo_bytes = self.logo_state.image
        layout = QGridLayout(self)

        responsibles = QGroupBox("Responsables de l'activité", self); resp_layout = QHBoxLayout(responsibles)
        self.table = QTableWidget(0, 4, responsibles); self.table.setHorizontalHeaderLabels(("Défaut", "Nom", "Fonction", "Genre")); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.doubleClicked.connect(self.edit_responsible)
        resp_layout.addWidget(self.table, 1); buttons = QVBoxLayout()
        for label, slot in (("Ajouter", self.add_responsible), ("Modifier", self.edit_responsible), ("Supprimer", self.delete_responsible), ("Par défaut", self.set_default)):
            button = QPushButton(label, responsibles); button.clicked.connect(slot); buttons.addWidget(button)
        buttons.addStretch(1); resp_layout.addLayout(buttons); layout.addWidget(responsibles, 0, 0, 1, 2)

        logo = QGroupBox("Logo", self); logo_layout = QVBoxLayout(logo)
        radios = QHBoxLayout(); self.logo_org = QRadioButton("Identique à l'organisateur", logo); self.logo_custom = QRadioButton("Logo personnalisé", logo); group = QButtonGroup(logo); group.addButton(self.logo_org); group.addButton(self.logo_custom); radios.addWidget(self.logo_org); radios.addWidget(self.logo_custom); radios.addStretch(1); logo_layout.addLayout(radios)
        image_row = QHBoxLayout(); self.preview = QLabel("Aucun logo", logo); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview.setMinimumSize(110, 75); image_row.addWidget(self.preview, 1)
        image_buttons = QVBoxLayout(); self.choose_button = QPushButton("Choisir…", logo); self.remove_button = QPushButton("Supprimer", logo); self.view_button = QPushButton("Visualiser", logo)
        self.choose_button.clicked.connect(self.choose_logo); self.remove_button.clicked.connect(self.remove_logo); self.view_button.clicked.connect(self.view_logo)
        for button in (self.choose_button, self.remove_button, self.view_button): image_buttons.addWidget(button)
        image_buttons.addStretch(1); image_row.addLayout(image_buttons); logo_layout.addLayout(image_row); layout.addWidget(logo, 1, 0, 1, 2)
        self.logo_custom.toggled.connect(self._sync_logo); self.logo_org.setChecked(self.logo_state.from_organizer); self.logo_custom.setChecked(not self.logo_state.from_organizer)
        self.refresh_responsibles(); self._refresh_preview(); self._sync_logo()

    def refresh_responsibles(self) -> None:
        self.rows = self.repository.list_responsibles(self.activity_id); self.table.setRowCount(len(self.rows))
        for row_index, responsible in enumerate(self.rows):
            values = ("✓" if responsible.is_default else "", responsible.name, responsible.function, "Homme" if responsible.gender == "H" else "Femme")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value); item.setData(Qt.ItemDataRole.UserRole, responsible.responsible_id); self.table.setItem(row_index, column, item)
        self.table.resizeColumnsToContents()

    def _selected(self) -> ActivityResponsible | None:
        row = self.table.currentRow(); return self.rows[row] if 0 <= row < len(self.rows) else None

    def add_responsible(self, *_args) -> None:
        dialog = ResponsibleDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        try:
            name, function, gender = dialog.values(); self.repository.save_responsible(self.activity_id, name, function, gender)
        except Exception as exc: QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self.refresh_responsibles()

    def edit_responsible(self, *_args) -> None:
        responsible = self._selected()
        if responsible is None: return
        dialog = ResponsibleDialog(responsible, self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        try:
            name, function, gender = dialog.values(); self.repository.save_responsible(self.activity_id, name, function, gender, responsible.responsible_id)
        except Exception as exc: QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self.refresh_responsibles()

    def delete_responsible(self, *_args) -> None:
        responsible = self._selected()
        if responsible is None: return
        if QMessageBox.question(self, "Suppression", f"Supprimer le responsable « {responsible.name} » ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        try: self.repository.delete_responsible(self.activity_id, responsible.responsible_id)
        except Exception as exc: QMessageBox.critical(self, "Suppression impossible", str(exc)); return
        self.refresh_responsibles()

    def set_default(self, *_args) -> None:
        responsible = self._selected()
        if responsible is None: return
        try: self.repository.set_default(self.activity_id, responsible.responsible_id)
        except Exception as exc: QMessageBox.critical(self, "Modification impossible", str(exc)); return
        self.refresh_responsibles()

    def _sync_logo(self, *_args) -> None:
        enabled = self.logo_custom.isChecked()
        for control in (self.choose_button, self.remove_button, self.view_button): control.setEnabled(enabled)

    def choose_logo(self, *_args) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Sélectionnez une image", "", "Images (*.bmp *.gif *.jpg *.jpeg *.png);;Tous les fichiers (*.*)")
        if not path: return
        image = QImage(path)
        if image.isNull(): QMessageBox.warning(self, "Image invalide", "Le fichier sélectionné n'est pas une image lisible."); return
        if max(image.width(), image.height()) > 1000:
            image = image.scaled(1000, 1000, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        array = QByteArray(); buffer = QBuffer(array); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        try:
            if not image.save(buffer, "PNG"): raise ValueError("Conversion PNG impossible.")
        finally: buffer.close()
        self.logo_bytes = bytes(array); self._refresh_preview()

    def remove_logo(self, *_args) -> None:
        self.logo_bytes = None; self._refresh_preview()

    def _refresh_preview(self) -> None:
        pixmap = QPixmap()
        if self.logo_bytes and pixmap.loadFromData(self.logo_bytes):
            self.preview.setText(""); self.preview.setPixmap(pixmap.scaled(180, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview.setPixmap(QPixmap()); self.preview.setText("Aucun logo")

    def view_logo(self, *_args) -> None:
        if not self.logo_bytes: return
        pixmap = QPixmap();
        if not pixmap.loadFromData(self.logo_bytes): return
        dialog = QDialog(self); dialog.setWindowTitle("Logo de l'activité"); layout = QVBoxLayout(dialog); label = QLabel(dialog); label.setPixmap(pixmap); layout.addWidget(label); buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog); buttons.rejected.connect(dialog.reject); buttons.clicked.connect(dialog.accept); layout.addWidget(buttons); dialog.exec()

    def collect_logo(self) -> ActivityLogoState:
        state = ActivityLogoState(from_organizer=self.logo_org.isChecked(), image=self.logo_bytes)
        if not state.from_organizer and state.image is None:
            raise ValueError("Vous avez sélectionné un logo personnalisé sans choisir d'image.")
        return state


class ActivityEditorDialog(PortalActivityEditorDialog):
    """Fiche Activité Qt avec les neuf pages et Généralités finalisée."""

    def __init__(self, repository: NativeActivityEditorRepository, activity_id: int,
                 parent: QWidget | None = None):
        super().__init__(repository, activity_id, parent)
        pending = next((box for box in self.findChildren(QGroupBox) if box.title() == "Responsables et logo"), None)
        if pending is not None and pending.parentWidget() is not None:
            parent_widget = pending.parentWidget(); parent_layout = parent_widget.layout(); index = parent_layout.indexOf(pending)
            position = parent_layout.getItemPosition(index) if isinstance(parent_layout, QGridLayout) else None
            parent_layout.removeWidget(pending); pending.deleteLater(); self.general_extras = GeneralExtrasBox(repository, activity_id, parent_widget)
            if position is not None:
                row, column, row_span, column_span = position; parent_layout.addWidget(self.general_extras, row, column, row_span, column_span)
            else: parent_layout.addWidget(self.general_extras)
        else:
            self.general_extras = GeneralExtrasBox(repository, activity_id, self)

    def _save(self) -> None:
        if not self._validate_composed_editor(): return
        try:
            details = self._collect(); requirements = self.requirements_page.collect(); agreements = self.agreements_page.collect(confirm_delete=True); portal = self.portal_page.collect(); logo = self.general_extras.collect_logo()
            with activity_transaction(self.repository) as shared_repository:
                NativeActivityEditorRepository.save(shared_repository, details, self._checked_group_ids())
                ActivityRequirementsRepository(shared_repository).save(self.activity_id, requirements)
                ActivityAgreementsRepository(shared_repository).save(self.activity_id, agreements)
                ActivityPortalRepository(shared_repository).save_settings(self.activity_id, portal)
                ActivityGeneralExtrasRepository(shared_repository).save_logo(self.activity_id, logo)
        except ValueError as exc: QMessageBox.warning(self, "Erreur de saisie", str(exc)); return
        except Exception as exc: QMessageBox.critical(self, "Enregistrement impossible", str(exc)); return
        self.details = details; self.requirements_page.state = requirements; self.agreements_page.state = agreements; self.portal_page.state = portal; self.general_extras.logo_state = logo; self.accept()
