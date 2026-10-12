"""Interface Qt des assistants de création d'activités.

Le sélecteur reprend les six choix historiques : création manuelle puis les cinq
assistants annuelle, séjour, stage, cantine et sorties. Les assistants Qt
collectent les paramètres structurants et délèguent toute écriture au moteur
atomique de :mod:`activity_assistants_core`.
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QWidget,
)

from .activity_assistants_core import (
    ASSISTANT_CHOICES,
    INFORMATION_TYPES,
    ActivityAssistantRepository,
    AssistantConfiguration,
)


class CheckList(QListWidget):
    def set_choices(self, choices: tuple[tuple[int, str], ...] | list[tuple[int, str]]) -> None:
        self.clear()
        for value, label in choices:
            item = QListWidgetItem(label, self)
            item.setData(Qt.ItemDataRole.UserRole, int(value))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)

    def checked_ids(self) -> tuple[int, ...]:
        return tuple(
            int(self.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.count())
            if self.item(index).checkState() == Qt.CheckState.Checked
        )


class ActivityAssistantChoiceDialog(QDialog):
    """Equivalent Qt de ``DLG_Nouvelle_activite``."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Créer une nouvelle activité")
        self.setModal(True)
        self.resize(680, 460)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Sélectionnez la création manuelle ou l'un des assistants proposés :", self))
        self.list = QListWidget(self)
        self.list.setAlternatingRowColors(True)
        for code, name, description in ASSISTANT_CHOICES:
            item = QListWidgetItem(f"{name}\n{description}", self.list)
            item.setData(Qt.ItemDataRole.UserRole, code)
            item.setToolTip(description)
            item.setSizeHint(item.sizeHint().expandedTo(self.list.fontMetrics().boundingRect(0, 0, 600, 80, 0, item.text()).size()))
        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        root.addWidget(self.list, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Continuer")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept(self) -> None:
        if self.list.currentItem() is None:
            QMessageBox.warning(self, "Erreur de saisie", "Vous devez sélectionner un assistant dans la liste.")
            return
        self.accept()

    def selected_code(self) -> str:
        item = self.list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else "nouveau"


class ActivityAssistantDialog(QWizard):
    """Assistant Qt compact pour l'une des cinq familles historiques."""

    def __init__(self, repository: ActivityAssistantRepository, code: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.repository = repository
        self.code = code
        choice = next((item for item in ASSISTANT_CHOICES if item[0] == code), None)
        if choice is None or code == "nouveau":
            raise ValueError("Assistant de création inconnu.")
        self.setWindowTitle(choice[1])
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.resize(760, 620)
        self._build_general_page()
        self._build_structure_page()
        self._build_requirements_page()
        self._build_pricing_page()
        self._prefill_responsible()
        self._sync_code_specific_controls()
        self._sync_pricing()

    def _new_page(self, title: str, subtitle: str = "") -> tuple[QWizardPage, QVBoxLayout]:
        page = QWizardPage(self)
        page.setTitle(title)
        if subtitle:
            page.setSubTitle(subtitle)
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        self.addPage(page)
        return page, layout

    def _build_general_page(self) -> None:
        page, root = self._new_page("Généralités", "Les informations de base restent compatibles avec la fiche Activité historique.")
        form = QFormLayout(); root.addLayout(form)
        self.name_edit = QLineEdit(page)
        self.name_edit.setPlaceholderText("Nom de l'activité")
        if self.code == "cantine":
            self.name_edit.setText("Cantine")
        form.addRow("Nom :", self.name_edit)

        today = dt.date.today()
        self.start_date = QDateEdit(page); self.end_date = QDateEdit(page)
        for control in (self.start_date, self.end_date):
            control.setCalendarPopup(True); control.setDisplayFormat("dd/MM/yyyy")
        default_end = today + (dt.timedelta(days=365) if self.code == "annuelle" else dt.timedelta(days=6))
        self.start_date.setDate(QDate(today.year, today.month, today.day))
        self.end_date.setDate(QDate(default_end.year, default_end.month, default_end.day))
        self.start_label = QLabel("Date de début :", page); self.end_label = QLabel("Date de fin :", page)
        form.addRow(self.start_label, self.start_date); form.addRow(self.end_label, self.end_date)

        self.max_members = QSpinBox(page); self.max_members.setRange(0, 99999); self.max_members.setSpecialValueText("Illimité")
        form.addRow("Nombre maximal d'inscrits :", self.max_members)
        self.agreement_edit = QLineEdit(page); self.agreement_label = QLabel("N° d'agrément :", page)
        form.addRow(self.agreement_label, self.agreement_edit)

        responsible = QGroupBox("Responsable facultatif", page); responsible_form = QFormLayout(responsible)
        self.responsible_name = QLineEdit(responsible); self.responsible_function = QLineEdit(responsible)
        self.responsible_female = QCheckBox("Responsable de genre féminin", responsible)
        responsible_form.addRow("Nom :", self.responsible_name)
        responsible_form.addRow("Fonction :", self.responsible_function)
        responsible_form.addRow("", self.responsible_female)
        root.addWidget(responsible)
        root.addStretch(1)

    def _build_structure_page(self) -> None:
        page, root = self._new_page("Groupes et structure", "Une ligne par groupe ou service. Laissez vide pour créer « Groupe unique ».")
        self.groups_label = QLabel("Groupes (un nom par ligne) :", page)
        root.addWidget(self.groups_label)
        self.groups_edit = QPlainTextEdit(page); self.groups_edit.setPlaceholderText("Ex. Petits\nGrands")
        if self.code == "cantine":
            self.groups_edit.setPlaceholderText("Ex. Service 1\nService 2")
        root.addWidget(self.groups_edit, 1)

        session_box = QGroupBox("Pointage des séances", page)
        session_layout = QVBoxLayout(session_box)
        self.track_sessions = QCheckBox("Créer une unité « Séance » et les ouvertures correspondantes", session_box)
        session_layout.addWidget(self.track_sessions)
        days = QHBoxLayout(); self.weekday_checks: list[QCheckBox] = []
        for label in ("Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"):
            check = QCheckBox(label, session_box); self.weekday_checks.append(check); days.addWidget(check)
        days.addStretch(1); session_layout.addLayout(days)
        root.addWidget(session_box)
        self.session_box = session_box
        self.track_sessions.toggled.connect(self._sync_session_days)

        group_types_box = QGroupBox("Groupes d'activités associés", page); group_types_layout = QVBoxLayout(group_types_box)
        self.group_types = CheckList(group_types_box)
        try:
            self.group_types.set_choices(self.repository.list_activity_group_types())
        except Exception as exc:
            self.group_types.setEnabled(False)
            self.group_types.setToolTip(str(exc))
        group_types_layout.addWidget(self.group_types)
        root.addWidget(group_types_box, 1)

    def _build_requirements_page(self) -> None:
        page, root = self._new_page("Renseignements", "Retrouvez les pièces, cotisations et renseignements proposés par les assistants historiques.")
        grid = QGridLayout(); root.addLayout(grid, 1)
        pieces_box = QGroupBox("Pièces à fournir", page); pieces_layout = QVBoxLayout(pieces_box); self.pieces = CheckList(pieces_box); pieces_layout.addWidget(self.pieces)
        cotisations_box = QGroupBox("Cotisations à jour", page); cotisations_layout = QVBoxLayout(cotisations_box); self.cotisations = CheckList(cotisations_box); cotisations_layout.addWidget(self.cotisations)
        infos_box = QGroupBox("Renseignements", page); infos_layout = QVBoxLayout(infos_box); self.informations = CheckList(infos_box); infos_layout.addWidget(self.informations)
        try:
            self.pieces.set_choices(self.repository.list_pieces())
        except Exception as exc:
            self.pieces.setEnabled(False); self.pieces.setToolTip(str(exc))
        try:
            self.cotisations.set_choices(self.repository.list_cotisations())
        except Exception as exc:
            self.cotisations.setEnabled(False); self.cotisations.setToolTip(str(exc))
        self.informations.set_choices(list(INFORMATION_TYPES))
        grid.addWidget(pieces_box, 0, 0); grid.addWidget(cotisations_box, 0, 1); grid.addWidget(infos_box, 1, 0, 1, 2)

    def _build_pricing_page(self) -> None:
        page, root = self._new_page("Tarification", "L'assistant crée au minimum une catégorie ; les méthodes avancées restent disponibles dans la fiche complète.")
        pricing_box = QGroupBox("Mode", page); pricing_form = QFormLayout(pricing_box)
        from PySide6.QtWidgets import QComboBox  # import local pour garder la liste d'imports compacte
        self.pricing_mode = QComboBox(pricing_box)
        self.pricing_mode.addItem("Configurer la tarification ensuite", "later")
        if self.code == "annuelle":
            self.pricing_mode.addItem("Activité gratuite", "free")
        self.pricing_mode.addItem("Montant fixe", "fixed")
        self.amount = QDoubleSpinBox(pricing_box); self.amount.setRange(0.0, 999999.0); self.amount.setDecimals(2); self.amount.setSuffix(" €")
        pricing_form.addRow("Tarification :", self.pricing_mode); pricing_form.addRow("Montant :", self.amount)
        root.addWidget(pricing_box)
        categories_box = QGroupBox("Catégories tarifaires", page); categories_layout = QVBoxLayout(categories_box)
        categories_layout.addWidget(QLabel("Un nom par ligne. Laissez vide pour « Catégorie unique ».", categories_box))
        self.categories_edit = QPlainTextEdit(categories_box); self.categories_edit.setPlaceholderText("Ex. Commune\nHors commune")
        categories_layout.addWidget(self.categories_edit, 1); root.addWidget(categories_box, 1)
        self.pricing_note = QLabel("", page); self.pricing_note.setWordWrap(True); root.addWidget(self.pricing_note)
        self.pricing_mode.currentIndexChanged.connect(self._sync_pricing)

    def _prefill_responsible(self) -> None:
        try:
            previous = self.repository.last_responsible()
        except Exception:
            previous = None
        if previous is None:
            return
        gender, name, function = previous
        self.responsible_name.setText(name); self.responsible_function.setText(function)
        self.responsible_female.setChecked(gender == "F")

    def _sync_code_specific_controls(self) -> None:
        dated = self.code in {"annuelle", "sejour", "stage"}
        for control in (self.start_label, self.start_date, self.end_label, self.end_date):
            control.setVisible(dated)
        agreement = self.code == "sejour"
        self.agreement_label.setVisible(agreement); self.agreement_edit.setVisible(agreement)
        self.session_box.setVisible(self.code == "annuelle")
        self.groups_label.setText("Services (un nom par ligne) :" if self.code == "cantine" else "Groupes (un nom par ligne) :")
        self._sync_session_days()
        if self.code == "sorties":
            self.pricing_mode.setEnabled(False)
            self.amount.setEnabled(False)
            self.pricing_note.setText("Les sorties utilisent le montant porté par chaque évènement, comme dans l'assistant historique.")

    def _sync_session_days(self, *_args) -> None:
        enabled = self.code == "annuelle" and self.track_sessions.isChecked()
        for check in self.weekday_checks:
            check.setEnabled(enabled)

    def _sync_pricing(self, *_args) -> None:
        if self.code == "sorties":
            return
        fixed = self.pricing_mode.currentData() == "fixed"
        self.amount.setEnabled(fixed)
        if fixed:
            self.pricing_note.setText("Le montant fixe sera créé pour chaque catégorie. Il restera modifiable dans Tarification.")
        elif self.pricing_mode.currentData() == "free":
            self.pricing_note.setText("Une catégorie sera créée, sans tarif facturable.")
        else:
            self.pricing_note.setText("La structure sera créée sans tarif ; finalisez-la ensuite dans l'onglet Tarification.")

    @staticmethod
    def _date(control: QDateEdit) -> dt.date:
        value = control.date()
        return dt.date(value.year(), value.month(), value.day())

    @staticmethod
    def _lines(control: QPlainTextEdit) -> tuple[str, ...]:
        return tuple(line.strip() for line in control.toPlainText().splitlines() if line.strip())

    def configuration(self) -> AssistantConfiguration:
        dated = self.code in {"annuelle", "sejour", "stage"}
        return AssistantConfiguration(
            code=self.code,
            name=self.name_edit.text().strip(),
            start_date=self._date(self.start_date) if dated else None,
            end_date=self._date(self.end_date) if dated else None,
            max_members=self.max_members.value() or None,
            activity_group_type_ids=self.group_types.checked_ids() if self.group_types.isEnabled() else (),
            group_names=self._lines(self.groups_edit),
            session_weekdays=tuple(index for index, check in enumerate(self.weekday_checks) if check.isChecked()),
            track_sessions=self.track_sessions.isChecked() if self.code == "annuelle" else False,
            agreement_number=self.agreement_edit.text().strip() if self.code == "sejour" else "",
            responsible_name=self.responsible_name.text().strip(),
            responsible_function=self.responsible_function.text().strip(),
            responsible_gender="F" if self.responsible_female.isChecked() else "H",
            piece_ids=self.pieces.checked_ids() if self.pieces.isEnabled() else (),
            cotisation_ids=self.cotisations.checked_ids() if self.cotisations.isEnabled() else (),
            information_ids=self.informations.checked_ids(),
            pricing_mode=str(self.pricing_mode.currentData() or "later"),
            pricing_categories=self._lines(self.categories_edit),
            amount=float(self.amount.value()) if self.pricing_mode.currentData() == "fixed" else None,
        )

    def accept(self) -> None:
        try:
            configuration = self.configuration()
            self.repository.validate(configuration)
        except Exception as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc))
            return
        super().accept()
