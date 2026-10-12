"""Fenêtre Qt de modification d'une activité Noethys.

La migration reste progressive : l'onglet Généralités reproduit les champs
simples du dialogue historique et les enregistre directement dans la base
Noethys existante. Les autres pages historiques sont matérialisées dans le
même ordre pour préparer leur migration sans changer les habitudes.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
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
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


UNLIMITED_START = dt.date(1977, 1, 1)
UNLIMITED_END = dt.date(2999, 1, 1)


@dataclass(slots=True)
class ActivityDetails:
    activity_id: int
    name: str
    short_name: str
    coords_from_organizer: bool
    street: str
    postal_code: str
    city: str
    phone: str
    fax: str
    email: str
    website: str
    start_date: dt.date | None
    end_date: dt.date | None
    max_members: int | None
    accounting_code: str
    regie_id: int | None
    local_product_code: str
    multiple_registrations: bool
    service_code: str
    analytic_code: str


class NativeActivityEditorRepository:
    """Accès direct à la base configurée, sans import de wx/GestionDB."""

    def __init__(self, sqlite_path: Path | None = None):
        self.sqlite_path = sqlite_path

    def _connect(self):
        if self.sqlite_path is not None:
            return sqlite3.connect(self.sqlite_path), "?"

        from .activities_native import (
            _data_database_name,
            _decode_network_password,
            _load_config,
            _local_database_path,
            _user_config_dir,
        )

        config = _load_config()
        descriptor = str(config.get("nomFichier") or "").strip()
        if not descriptor:
            raise RuntimeError("Config.json ne contient aucun 'nomFichier' actif.")

        if "[RESEAU]" not in descriptor:
            return sqlite3.connect(_local_database_path(descriptor)), "?"

        try:
            import mysql.connector
        except ImportError as exc:
            raise RuntimeError(
                "mysql-connector-python manque dans l'environnement Qt."
            ) from exc

        before, database = descriptor.split("[RESEAU]", 1)
        try:
            port, host, user, encoded_password = before.split(";", 3)
        except ValueError as exc:
            raise RuntimeError("Descripteur réseau Noethys invalide dans Config.json.") from exc

        params = {
            "host": host,
            "port": int(port),
            "user": user,
            "password": _decode_network_password(encoded_password),
            "database": _data_database_name(database).lower(),
            "use_unicode": True,
        }
        ca_path = _user_config_dir() / "ca-cert.pem"
        if ca_path.is_file():
            params["ssl_ca"] = str(ca_path)
        return mysql.connector.connect(**params), "%s"

    def load(self, activity_id: int) -> ActivityDetails:
        connection, placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"""
                    SELECT nom, abrege, coords_org, rue, cp, ville, tel, fax,
                           mail, site, date_debut, date_fin, nbre_inscrits_max,
                           code_comptable, regie, code_produit_local,
                           inscriptions_multiples, code_service, code_analytique
                    FROM activites
                    WHERE IDactivite={placeholder}
                    """,
                    (activity_id,),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
        finally:
            connection.close()

        if row is None:
            raise RuntimeError(f"Activité {activity_id} introuvable.")

        return ActivityDetails(
            activity_id=activity_id,
            name=str(row[0] or ""),
            short_name=str(row[1] or ""),
            coords_from_organizer=bool(row[2]),
            street=str(row[3] or ""),
            postal_code=str(row[4] or ""),
            city=str(row[5] or ""),
            phone=str(row[6] or ""),
            fax=str(row[7] or ""),
            email=str(row[8] or ""),
            website=str(row[9] or ""),
            start_date=_to_date(row[10]),
            end_date=_to_date(row[11]),
            max_members=int(row[12]) if row[12] not in (None, "") else None,
            accounting_code=str(row[13] or ""),
            regie_id=int(row[14]) if row[14] not in (None, "") else None,
            local_product_code=str(row[15] or ""),
            multiple_registrations=bool(row[16]),
            service_code=str(row[17] or ""),
            analytic_code=str(row[18] or ""),
        )

    def list_regies(self) -> list[tuple[int, str]]:
        connection, _placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT IDregie, nom FROM factures_regies ORDER BY nom")
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return [(int(row[0]), str(row[1] or "")) for row in rows]

    def list_group_types(self, activity_id: int) -> list[tuple[int, str, bool]]:
        connection, placeholder = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    f"""
                    SELECT t.IDtype_groupe_activite, t.nom,
                           CASE WHEN g.IDactivite IS NULL THEN 0 ELSE 1 END
                    FROM types_groupes_activites t
                    LEFT JOIN groupes_activites g
                      ON g.IDtype_groupe_activite=t.IDtype_groupe_activite
                     AND g.IDactivite={placeholder}
                    ORDER BY t.nom
                    """,
                    (activity_id,),
                )
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        return [(int(row[0]), str(row[1] or ""), bool(row[2])) for row in rows]

    def save(self, details: ActivityDetails, group_ids: Iterable[int]) -> None:
        connection, placeholder = self._connect()
        cursor = connection.cursor()
        try:
            coords_org = 1 if details.coords_from_organizer else 0
            if coords_org:
                street = postal_code = city = phone = fax = email = website = None
            else:
                street = details.street or None
                postal_code = details.postal_code or None
                city = details.city or None
                phone = details.phone or None
                fax = details.fax or None
                email = details.email or None
                website = details.website or None

            fields = (
                "nom", "abrege", "coords_org", "rue", "cp", "ville", "tel",
                "fax", "mail", "site", "date_debut", "date_fin",
                "nbre_inscrits_max", "code_comptable", "regie",
                "code_produit_local", "inscriptions_multiples", "code_service",
                "code_analytique",
            )
            values = (
                details.name,
                details.short_name,
                coords_org,
                street,
                postal_code,
                city,
                phone,
                fax,
                email,
                website,
                details.start_date.isoformat() if details.start_date else None,
                details.end_date.isoformat() if details.end_date else None,
                details.max_members,
                details.accounting_code or None,
                details.regie_id,
                details.local_product_code or None,
                1 if details.multiple_registrations else 0,
                details.service_code or None,
                details.analytic_code or None,
            )
            assignments = ", ".join(f"{field}={placeholder}" for field in fields)
            cursor.execute(
                f"UPDATE activites SET {assignments} WHERE IDactivite={placeholder}",
                values + (details.activity_id,),
            )

            cursor.execute(
                f"DELETE FROM groupes_activites WHERE IDactivite={placeholder}",
                (details.activity_id,),
            )
            for group_id in sorted(set(int(value) for value in group_ids)):
                cursor.execute(
                    "INSERT INTO groupes_activites "
                    f"(IDtype_groupe_activite, IDactivite) VALUES ({placeholder}, {placeholder})",
                    (group_id, details.activity_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()


def _to_date(value: object) -> dt.date | None:
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


def _qdate(value: dt.date | None, fallback: dt.date) -> QDate:
    value = value or fallback
    return QDate(value.year, value.month, value.day)


class ActivityEditorDialog(QDialog):
    """Éditeur Qt progressif d'une activité existante."""

    PAGE_NAMES = (
        "Généralités",
        "Agréments",
        "Groupes",
        "Renseignements",
        "Étiquettes",
        "Unités",
        "Calendrier",
        "Portail",
        "Tarification",
    )

    def __init__(
        self,
        repository: NativeActivityEditorRepository,
        activity_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.activity_id = activity_id
        self.details = repository.load(activity_id)
        self.setWindowTitle(f"Modifier une activité — {self.details.name}")
        self.setModal(True)
        self.setMinimumSize(760, 560)
        if parent is not None:
            self.resize(max(820, int(parent.width() * 0.72)), max(620, int(parent.height() * 0.82)))
        else:
            self.resize(900, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 10)
        root.setSpacing(10)

        title = QLabel(self.details.name, self)
        title.setObjectName("activityEditorTitle")
        root.addWidget(title)

        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_general_page(), self.PAGE_NAMES[0])
        for name in self.PAGE_NAMES[1:]:
            self.tabs.addTab(self._placeholder_page(name), name)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Enregistrer")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._load_into_controls()
        self._sync_coordinate_state()
        self._sync_validity_state()
        self._sync_max_state()
        self._apply_local_style()

    def _build_general_page(self) -> QWidget:
        content = QWidget(self)
        layout = QGridLayout(content)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        identity = QGroupBox("Nom de l'activité", content)
        identity_form = QFormLayout(identity)
        self.name_edit = QLineEdit(identity)
        self.short_name_edit = QLineEdit(identity)
        identity_form.addRow("Nom complet :", self.name_edit)
        identity_form.addRow("Nom abrégé :", self.short_name_edit)
        layout.addWidget(identity, 0, 0)

        validity = QGroupBox("Dates de validité", content)
        validity_layout = QGridLayout(validity)
        self.unlimited_radio = QRadioButton("Illimitée", validity)
        self.limited_radio = QRadioButton("Période limitée", validity)
        validity_group = QButtonGroup(validity)
        validity_group.addButton(self.unlimited_radio)
        validity_group.addButton(self.limited_radio)
        self.start_date_edit = QDateEdit(validity)
        self.end_date_edit = QDateEdit(validity)
        for editor in (self.start_date_edit, self.end_date_edit):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd/MM/yyyy")
        validity_layout.addWidget(self.unlimited_radio, 0, 0, 1, 3)
        validity_layout.addWidget(self.limited_radio, 1, 0, 1, 3)
        validity_layout.addWidget(QLabel("Du", validity), 2, 0)
        validity_layout.addWidget(self.start_date_edit, 2, 1)
        validity_layout.addWidget(QLabel("au", validity), 2, 2)
        validity_layout.addWidget(self.end_date_edit, 2, 3)
        self.unlimited_radio.toggled.connect(self._sync_validity_state)
        layout.addWidget(validity, 0, 1)

        coordinates = QGroupBox("Coordonnées", content)
        coordinates_layout = QGridLayout(coordinates)
        self.coords_org_radio = QRadioButton("Identiques à l'organisateur", coordinates)
        self.coords_other_radio = QRadioButton("Autres coordonnées", coordinates)
        coords_group = QButtonGroup(coordinates)
        coords_group.addButton(self.coords_org_radio)
        coords_group.addButton(self.coords_other_radio)
        self.street_edit = QPlainTextEdit(coordinates)
        self.street_edit.setMaximumBlockCount(4)
        self.street_edit.setFixedHeight(self.street_edit.fontMetrics().lineSpacing() * 3 + 14)
        self.postal_code_edit = QLineEdit(coordinates)
        self.city_edit = QLineEdit(coordinates)
        self.phone_edit = QLineEdit(coordinates)
        self.email_edit = QLineEdit(coordinates)
        self.fax_edit = QLineEdit(coordinates)
        self.website_edit = QLineEdit(coordinates)
        coordinates_layout.addWidget(self.coords_org_radio, 0, 0, 1, 4)
        coordinates_layout.addWidget(self.coords_other_radio, 1, 0, 1, 4)
        coordinates_layout.addWidget(QLabel("Rue :", coordinates), 2, 0)
        coordinates_layout.addWidget(self.street_edit, 2, 1, 1, 3)
        coordinates_layout.addWidget(QLabel("C.P. :", coordinates), 3, 0)
        coordinates_layout.addWidget(self.postal_code_edit, 3, 1)
        coordinates_layout.addWidget(QLabel("Ville :", coordinates), 3, 2)
        coordinates_layout.addWidget(self.city_edit, 3, 3)
        coordinates_layout.addWidget(QLabel("Tél. :", coordinates), 4, 0)
        coordinates_layout.addWidget(self.phone_edit, 4, 1)
        coordinates_layout.addWidget(QLabel("Email :", coordinates), 4, 2)
        coordinates_layout.addWidget(self.email_edit, 4, 3)
        coordinates_layout.addWidget(QLabel("Fax :", coordinates), 5, 0)
        coordinates_layout.addWidget(self.fax_edit, 5, 1)
        coordinates_layout.addWidget(QLabel("Site :", coordinates), 5, 2)
        coordinates_layout.addWidget(self.website_edit, 5, 3)
        coordinates_layout.setColumnStretch(1, 1)
        coordinates_layout.setColumnStretch(3, 1)
        self.coords_org_radio.toggled.connect(self._sync_coordinate_state)
        layout.addWidget(coordinates, 1, 0, 1, 2)

        accounting = QGroupBox("Comptabilité", content)
        accounting_form = QFormLayout(accounting)
        self.accounting_code_edit = QLineEdit(accounting)
        self.local_product_code_edit = QLineEdit(accounting)
        self.service_code_edit = QLineEdit(accounting)
        self.analytic_code_edit = QLineEdit(accounting)
        self.regie_combo = QComboBox(accounting)
        accounting_form.addRow("Code comptable :", self.accounting_code_edit)
        accounting_form.addRow("Code produit local :", self.local_product_code_edit)
        accounting_form.addRow("Code service :", self.service_code_edit)
        accounting_form.addRow("Code analytique :", self.analytic_code_edit)
        accounting_form.addRow("Régie de facturation :", self.regie_combo)
        layout.addWidget(accounting, 2, 0)

        registrations = QGroupBox("Inscriptions", content)
        registrations_layout = QVBoxLayout(registrations)
        limit_row = QHBoxLayout()
        self.max_members_check = QCheckBox("Nombre d'inscrits maximal :", registrations)
        self.max_members_spin = QSpinBox(registrations)
        self.max_members_spin.setRange(1, 99999)
        limit_row.addWidget(self.max_members_check)
        limit_row.addWidget(self.max_members_spin)
        limit_row.addStretch(1)
        self.multiple_check = QCheckBox(
            "Autoriser les inscriptions multiples pour un individu",
            registrations,
        )
        registrations_layout.addLayout(limit_row)
        registrations_layout.addWidget(self.multiple_check)
        self.max_members_check.toggled.connect(self._sync_max_state)
        layout.addWidget(registrations, 2, 1)

        grouping = QGroupBox("Regroupement d'activités", content)
        grouping_layout = QVBoxLayout(grouping)
        self.groups_list = QListWidget(grouping)
        self.groups_list.setAlternatingRowColors(True)
        self.groups_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        grouping_layout.addWidget(self.groups_list)
        layout.addWidget(grouping, 3, 0)

        pending = QGroupBox("Responsables et logo", content)
        pending_layout = QVBoxLayout(pending)
        pending_label = QLabel(
            "Les responsables et le logo restent inchangés dans cette première fenêtre Qt. "
            "Ils seront raccordés sans conversion de données dans la passe suivante.",
            pending,
        )
        pending_label.setWordWrap(True)
        pending_layout.addWidget(pending_label)
        pending_layout.addStretch(1)
        layout.addWidget(pending, 3, 1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _placeholder_page(self, page_name: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        label = QLabel(
            f"{page_name} — la page historique est conservée comme contrat fonctionnel. "
            "Sa migration Qt arrive après validation de Généralités.",
            page,
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _load_into_controls(self) -> None:
        details = self.details
        self.name_edit.setText(details.name)
        self.short_name_edit.setText(details.short_name)
        self.coords_org_radio.setChecked(details.coords_from_organizer)
        self.coords_other_radio.setChecked(not details.coords_from_organizer)
        self.street_edit.setPlainText(details.street)
        self.postal_code_edit.setText(details.postal_code)
        self.city_edit.setText(details.city)
        self.phone_edit.setText(details.phone)
        self.fax_edit.setText(details.fax)
        self.email_edit.setText(details.email)
        self.website_edit.setText(details.website)

        unlimited = details.start_date == UNLIMITED_START and details.end_date == UNLIMITED_END
        self.unlimited_radio.setChecked(unlimited)
        self.limited_radio.setChecked(not unlimited)
        today = dt.date.today()
        self.start_date_edit.setDate(_qdate(details.start_date if not unlimited else today, today))
        self.end_date_edit.setDate(_qdate(details.end_date if not unlimited else today, today))

        self.max_members_check.setChecked(details.max_members is not None)
        self.max_members_spin.setValue(details.max_members or 1)
        self.multiple_check.setChecked(details.multiple_registrations)
        self.accounting_code_edit.setText(details.accounting_code)
        self.local_product_code_edit.setText(details.local_product_code)
        self.service_code_edit.setText(details.service_code)
        self.analytic_code_edit.setText(details.analytic_code)

        self.regie_combo.addItem("Aucune régie", None)
        for regie_id, name in self.repository.list_regies():
            self.regie_combo.addItem(name, regie_id)
        index = self.regie_combo.findData(details.regie_id)
        self.regie_combo.setCurrentIndex(index if index >= 0 else 0)

        for group_id, name, checked in self.repository.list_group_types(self.activity_id):
            item = QListWidgetItem(name, self.groups_list)
            item.setData(Qt.ItemDataRole.UserRole, group_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _sync_coordinate_state(self, *_args) -> None:
        enabled = self.coords_other_radio.isChecked()
        for control in (
            self.street_edit,
            self.postal_code_edit,
            self.city_edit,
            self.phone_edit,
            self.fax_edit,
            self.email_edit,
            self.website_edit,
        ):
            control.setEnabled(enabled)

    def _sync_validity_state(self, *_args) -> None:
        enabled = self.limited_radio.isChecked()
        self.start_date_edit.setEnabled(enabled)
        self.end_date_edit.setEnabled(enabled)

    def _sync_max_state(self, *_args) -> None:
        self.max_members_spin.setEnabled(self.max_members_check.isChecked())

    def _collect(self) -> ActivityDetails:
        name = self.name_edit.text().strip()
        short_name = self.short_name_edit.text().strip()
        if not name:
            raise ValueError("Le nom de l'activité doit être obligatoirement saisi.")
        if not short_name:
            raise ValueError("Le nom abrégé de l'activité doit être obligatoirement saisi.")

        if self.unlimited_radio.isChecked():
            start_date = UNLIMITED_START
            end_date = UNLIMITED_END
        else:
            start_date = self.start_date_edit.date().toPython()
            end_date = self.end_date_edit.date().toPython()
            if start_date > end_date:
                raise ValueError("La date de début de validité doit précéder la date de fin.")

        return ActivityDetails(
            activity_id=self.activity_id,
            name=name,
            short_name=short_name,
            coords_from_organizer=self.coords_org_radio.isChecked(),
            street=self.street_edit.toPlainText().strip(),
            postal_code=self.postal_code_edit.text().strip(),
            city=self.city_edit.text().strip(),
            phone=self.phone_edit.text().strip(),
            fax=self.fax_edit.text().strip(),
            email=self.email_edit.text().strip(),
            website=self.website_edit.text().strip(),
            start_date=start_date,
            end_date=end_date,
            max_members=self.max_members_spin.value() if self.max_members_check.isChecked() else None,
            accounting_code=self.accounting_code_edit.text().strip(),
            regie_id=self.regie_combo.currentData(),
            local_product_code=self.local_product_code_edit.text().strip(),
            multiple_registrations=self.multiple_check.isChecked(),
            service_code=self.service_code_edit.text().strip(),
            analytic_code=self.analytic_code_edit.text().strip(),
        )

    def _checked_group_ids(self) -> list[int]:
        result: list[int] = []
        for index in range(self.groups_list.count()):
            item = self.groups_list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return result

    def _save(self) -> None:
        try:
            details = self._collect()
            self.repository.save(details, self._checked_group_ids())
        except ValueError as exc:
            QMessageBox.warning(self, "Erreur de saisie", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement impossible", str(exc))
            return
        self.details = details
        self.accept()

    def _apply_local_style(self) -> None:
        self.setStyleSheet(
            """
            QLabel#activityEditorTitle { font-size: 18px; font-weight: 600; padding: 2px 2px 6px 2px; }
            QGroupBox { font-weight: 600; margin-top: 9px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            QLineEdit, QPlainTextEdit, QDateEdit, QSpinBox, QComboBox, QListWidget {
                padding: 4px 6px;
            }
            QTabWidget::pane { border: 0; }
            QTabBar::tab { padding: 7px 11px; }
            """
        )
