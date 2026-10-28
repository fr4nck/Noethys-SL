"""Première coque principale Qt de Noethys Upgrade.

Elle remplace le lancement isolé du module Activités par une navigation de
produit réelle. Les surfaces migrées restent indépendantes du runtime wx.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, QRunnable, QSettings, QThreadPool, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .activities_native import NativeActivitiesWindow, NativeConfiguredActivityRepository, _load_config
from .activities_prototype import ActivityRepository, SqliteActivityRepository, _parse_args
from .activity_editor import NativeActivityEditorRepository
from .activity_visuals import apply_activity_visuals, apply_semantic_theme
from .people_search import PeopleSearchPage, PeopleSearchRepository, PersonRow
from .people_details import FamilyDetails, PeopleDetailsPage, PeopleDetailsRepository
from .consumptions_core import ConsumptionRepository
from .consumptions_calendar_ui import ConsumptionCalendarPage
from .inscriptions_readonly import InscriptionPage, InscriptionRepository
from .finance_readonly_core import FinanceRepository, validate_finance_id
from .finance_readonly_ui import FinanceHubPage, MODULES
from .catalog_readonly_core import (
    CATALOG_MODULES, C14_MODULE_CODES, C15_MODULE_CODES,
    C16_CATALOG_MODULES, C16_RESTRICTED_MODULES,
    FAMILY_CATALOG_MODULES, C15_ACTIVITY_MODULES, CatalogRepository,
)
from .consumptions_status_ui import ConsumptionStateReportPage
from .catalog_readonly_ui import CatalogHubPage


class _DetailSignals(QObject):
    completed = Signal(int, str, object, str)


class _DetailWorker(QRunnable):
    """Une nouvelle connexion SQL dans un thread : aucun widget hors thread Qt."""

    def __init__(self, repository: PeopleDetailsRepository, request_id: int, kind: str, entity_id: int):
        super().__init__()
        self.setAutoDelete(False)
        self.repository = repository
        self.request_id = request_id
        self.kind = kind
        self.entity_id = entity_id
        self.signals = _DetailSignals()

    def run(self) -> None:
        try:
            detail = (
                self.repository.family(self.entity_id)
                if self.kind == "family"
                else self.repository.individual(self.entity_id)
            )
        except Exception as exc:
            self.signals.completed.emit(self.request_id, self.kind, None, str(exc))
        else:
            self.signals.completed.emit(self.request_id, self.kind, detail, "")


NAVIGATION = (
    ("home", "Accueil", True),
    ("people", "Individus / Familles", True),
    ("activities", "Activités", True),
    ("inscriptions", "Inscriptions", True),
    ("consumptions", "Consommations", True),
    ("billing", "Facturation", True),
    ("payments", "Règlements", True),
    ("accounting", "Comptabilité", True),
    ("memberships", "Cotisations", True),
    ("contracts", "Contrats", True),
    ("quotients", "Quotients familiaux", True),
    ("rentals", "Locations", True),
    ("orders", "Commandes", True),
    ("quotes", "Devis", True),
)
C15_NAVIGATION = (
    ("renewals", "Échéances d'adhésion", True),
    ("certificates", "Attestations", True),
    ("activity_settings", "Paramètres d'activités", True),
    ("headcounts", "Effectifs bruts", True),
)
C16_NAVIGATION = (
    ("planning", "Planning / événements", True),
    ("tariff_records", "Tarification enregistrée", True),
    ("consumption_reports", "États des consommations", True),
    ("badge_journal", "Journal de badgeage", True),
)


class NoethysQtWindow(QMainWindow):
    """Coque Qt native : navigation, recherche quotidienne et modules migrés."""

    def __init__(
        self,
        people_repository: PeopleSearchRepository,
        activities_repository: ActivityRepository,
        *,
        editor_sqlite_path: Path | None = None,
        requested_theme: str | None = None,
        source_label: str = "Base Noethys configurée",
        background_queries: bool = True,
        read_only_demo: bool = False,
        finance_enabled: bool = True,
        catalog_enabled: bool = True,
        c15_enabled: bool = False,
        c16_enabled: bool = False,
        badge_logs_enabled: bool = False,
    ):
        super().__init__()
        self.people_repository = people_repository
        self.details_repository = PeopleDetailsRepository(people_repository)
        self.consumptions_repository = ConsumptionRepository(people_repository.editor_repository)
        self.inscriptions_repository = InscriptionRepository(people_repository.editor_repository)
        self.finance_repository = FinanceRepository(people_repository.editor_repository)
        self.catalog_repository = CatalogRepository(people_repository.editor_repository)
        self.background_queries = background_queries
        # Seulement pour la démonstration C12 : ne jamais ouvrir le
        # panneau d'édition d'activité, même sur une fixture inventée.
        self.read_only_demo = read_only_demo
        # Ancienne fixture C12 sans tables comptables : masquer ses modules
        # plutôt que permettre une navigation vers une liste indisponible.
        self.finance_enabled = finance_enabled
        # C12/C13 : les anciennes bases fictives n'ont pas les tables C14.
        self.catalog_enabled = catalog_enabled
        # Les fixtures C12/C13/C14 n'ont pas les tables du lot C15.
        self.c15_enabled = c15_enabled
        self.c16_enabled = c16_enabled
        # Un journal nominatif ne peut être exposé par simple argument.
        # C16 ne l'ouvre que depuis la fixture éphémère C8->C16 dédiée,
        # jamais depuis un profil réseau/SQLite ou un dossier utilisateur.
        if badge_logs_enabled:
            source = Path(editor_sqlite_path) if editor_sqlite_path is not None else None
            if (
                not c16_enabled or not read_only_demo or source is None
                or source.is_symlink()
                or source.name != "C8_DEMONSTRATION_FICTIVE.sqlite"
                or not source.parent.name.startswith("noethys-qt-c8-fictif-")
                or not source.is_file()
            ):
                raise ValueError(
                    "Journal de badgeage C16 réservé à une fixture temporaire fictive"
                )
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(
                "file:" + source.resolve().as_posix() + "?mode=ro",
                uri=True,
            )) as sqlite:
                marker = sqlite.execute(
                    "SELECT token FROM c16_marker"
                ).fetchone()
            if marker != ("C16_ALL_FAKE_NOETHYS_ONLY",):
                raise ValueError(
                    "Marqueur C16 fictif absent : journal de badgeage interdit"
                )
        self.badge_logs_enabled = bool(c16_enabled and badge_logs_enabled)
        self._navigation_entries = (
            NAVIGATION
            + (C15_NAVIGATION if self.c15_enabled else ())
            + (C16_NAVIGATION if self.c16_enabled else ())
        )
        self._context_navigation = False
        self._context_history: list[tuple] = []
        self._return_context: tuple | None = None
        self._detail_request = 0
        self._detail_workers: dict[int, _DetailWorker] = {}
        self._current_detail: tuple[str, int] | None = None
        self.activities_repository = activities_repository
        self.editor_sqlite_path = editor_sqlite_path
        self.source_label = source_label
        self.settings = QSettings("Noethys", "NoethysQt")
        self._activities_window: NativeActivitiesWindow | None = None

        self.setWindowTitle("Noethys Qt — Upgrade")
        self.setMinimumSize(980, 660)
        self.resize(1320, 820)
        self._build_actions()
        self._build_toolbar(requested_theme)
        self._build_content()
        self._build_menus()
        self.statusBar().showMessage(source_label)
        self._restore_geometry()
        apply_semantic_theme(self)

    def _build_actions(self) -> None:
        style = self.style()
        self.home_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DesktopIcon), "Accueil", self)
        self.people_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon), "Individus / Familles", self)
        self.activities_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogListView), "Activités", self)
        self.inscriptions_action = QAction("Inscriptions", self)
        self.consumptions_action = QAction("Consommations", self)
        self.finance_actions = {
            "billing": QAction("Facturation", self),
            "payments": QAction("Règlements", self),
            "accounting": QAction("Comptabilité", self),
        }
        self.catalog_actions = {
            code: QAction(label, self) for code, (label, _domains) in CATALOG_MODULES.items()
        }
        self.report_action = QAction("États des consommations", self)
        self.back_context_action = QAction("Retour au dossier précédent", self)
        self.refresh_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Actualiser", self)
        self.quit_action = QAction("Quitter", self)

        self.home_action.setShortcut(QKeySequence("Alt+1"))
        self.people_action.setShortcut(QKeySequence("Alt+2"))
        self.activities_action.setShortcut(QKeySequence("Alt+3"))
        self.activities_action.setEnabled(not self.read_only_demo)
        self.inscriptions_action.setShortcut(QKeySequence("Alt+4"))
        self.consumptions_action.setShortcut(QKeySequence("Alt+5"))
        for code, digit in (("billing", 6), ("payments", 7), ("accounting", 8)):
            self.finance_actions[code].setEnabled(self.finance_enabled)
            self.finance_actions[code].setShortcut(QKeySequence(f"Alt+{digit}"))
            self.finance_actions[code].triggered.connect(
                lambda _checked=False, target=code: self.navigate(target)
            )
        for code, action in self.catalog_actions.items():
            action.setEnabled(
                self.catalog_enabled and (
                    code in C14_MODULE_CODES
                    or (code in C15_MODULE_CODES and self.c15_enabled)
                    or (code in C16_CATALOG_MODULES and self.c16_enabled
                        and (code not in C16_RESTRICTED_MODULES
                             or self.badge_logs_enabled))
                )
            )
            action.triggered.connect(
                lambda _checked=False, destination=code: self.navigate(destination)
            )
        self.report_action.setEnabled(self.c16_enabled)
        self.report_action.triggered.connect(
            lambda: self.navigate("consumption_reports")
        )
        self.back_context_action.setShortcut(QKeySequence("Alt+Left"))
        self.back_context_action.setEnabled(False)
        self.refresh_action.setShortcut(QKeySequence.Refresh)
        self.quit_action.setShortcut(QKeySequence.Quit)

        self.home_action.triggered.connect(lambda: self.navigate("home"))
        self.people_action.triggered.connect(lambda: self.navigate("people"))
        self.activities_action.triggered.connect(self.open_activities)
        self.inscriptions_action.triggered.connect(
            lambda: self.navigate("inscriptions")
        )
        self.consumptions_action.triggered.connect(
            lambda: self.navigate("consumptions")
        )
        self.back_context_action.triggered.connect(self.return_to_context)
        self.addAction(self.back_context_action)
        self.refresh_action.triggered.connect(self.refresh_current)
        self.quit_action.triggered.connect(self.close)

        self.search_action = QAction("Rechercher", self)
        self.search_action.setShortcut(QKeySequence.Find)
        self.search_action.triggered.connect(self.focus_current_search)
        self.addAction(self.search_action)

    def _build_toolbar(self, requested_theme: str | None) -> None:
        toolbar = QToolBar("Navigation", self)
        toolbar.setObjectName("mainNavigationToolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.addAction(self.home_action)
        toolbar.addAction(self.people_action)
        toolbar.addAction(self.activities_action)
        toolbar.addAction(self.inscriptions_action)
        toolbar.addAction(self.consumptions_action)
        toolbar.addSeparator()
        toolbar.addAction(self.refresh_action)
        spacer = QWidget(toolbar)
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy(), spacer.sizePolicy().verticalPolicy())
        toolbar.addWidget(spacer)
        toolbar.addWidget(QLabel("Thème :", toolbar))
        self.theme_combo = QComboBox(toolbar)
        self.theme_combo.addItem("Système", "system")
        self.theme_combo.addItem("Clair", "light")
        self.theme_combo.addItem("Sombre", "dark")
        requested = requested_theme or str(self.settings.value("appearance/theme", "system"))
        index = self.theme_combo.findData(requested)
        self.theme_combo.setCurrentIndex(index if index >= 0 else 0)
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        toolbar.addWidget(self.theme_combo)
        self.addToolBar(toolbar)

    def _build_content(self) -> None:
        root = QFrame(self)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.navigation = QListWidget(root)
        self.navigation.setObjectName("mainNavigation")
        self.navigation.setFixedWidth(205)
        self.navigation.setSpacing(1)
        self._nav_codes: list[str] = []
        for code, label, enabled in self._navigation_entries:
            item = QListWidgetItem(label if enabled else f"{label}  · à migrer")
            item.setData(Qt.ItemDataRole.UserRole, code)
            if (
                not enabled
                or (self.read_only_demo and code == "activities")
                or (not self.finance_enabled and code in MODULES)
                or (not self.catalog_enabled and code in CATALOG_MODULES)
                or (code in C15_ACTIVITY_MODULES and not self.c15_enabled)
                or (code in ("renewals", "certificates") and not self.c15_enabled)
                or (code in C16_CATALOG_MODULES and not self.c16_enabled)
                or (code in C16_RESTRICTED_MODULES and not self.badge_logs_enabled)
                or (code == "consumption_reports" and not self.c16_enabled)
            ):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.navigation.addItem(item)
            self._nav_codes.append(code)
        self.navigation.currentItemChanged.connect(self._navigation_changed)
        layout.addWidget(self.navigation)

        right = QWidget(root)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.context_bar = QFrame(right)
        route = QHBoxLayout(self.context_bar)
        route.setContentsMargins(10, 5, 10, 5)
        self.context_back_button = QPushButton("← Retour à la fiche", self.context_bar)
        self.context_back_button.clicked.connect(self.return_to_context)
        self.context_label = QLabel("", self.context_bar)
        self.context_label.setWordWrap(True)
        route.addWidget(self.context_back_button)
        route.addWidget(self.context_label, 1)
        right_layout.addWidget(self.context_bar)
        self.context_bar.hide()

        self.stack = QStackedWidget(right)
        self.home_page = self._build_home_page()
        self.people_page = PeopleSearchPage(
            self.people_repository, self.stack, background=self.background_queries
        )
        self.people_page.familyRequested.connect(self._family_requested)
        self.people_page.individualRequested.connect(self._individual_requested)
        self.details_page = PeopleDetailsPage(self.stack)
        self.details_page.family_invoices_button.setEnabled(self.finance_enabled)
        self.details_page.family_payments_button.setEnabled(self.finance_enabled)
        for code, button in self.details_page.catalog_buttons.items():
            button.setEnabled(
                self.catalog_enabled and (
                    code in C14_MODULE_CODES
                    or (code in C15_MODULE_CODES and self.c15_enabled)
                    or (code in C16_CATALOG_MODULES and self.c16_enabled
                        and (code not in C16_RESTRICTED_MODULES
                             or self.badge_logs_enabled))
                )
            )
        self.details_page.backRequested.connect(self._back_to_people)
        self.details_page.familyRequested.connect(self._family_requested)
        self.details_page.individualRequested.connect(self._individual_requested)
        self.details_page.familyInscriptionsRequested.connect(
            self._family_inscriptions_requested
        )
        self.details_page.individualInscriptionsRequested.connect(
            self._individual_inscriptions_requested
        )
        self.details_page.individualConsumptionsRequested.connect(
            self._individual_consumptions_requested
        )
        self.details_page.familyInvoicesRequested.connect(
            lambda ident: self._family_finance_requested("billing", ident)
        )
        self.details_page.familyPaymentsRequested.connect(
            lambda ident: self._family_finance_requested("payments", ident)
        )
        self.details_page.familyCatalogRequested.connect(self._family_catalog_requested)
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.people_page)
        self.stack.addWidget(self.details_page)
        self.inscriptions_page = InscriptionPage(
            self.inscriptions_repository, self.stack,
            background=self.background_queries,
        )
        self.inscriptions_page.familyRequested.connect(self._family_requested)
        self.inscriptions_page.individualRequested.connect(self._individual_requested)
        self.inscriptions_page.consumptionsRequested.connect(
            self._inscription_consumptions_requested
        )
        self.stack.addWidget(self.inscriptions_page)
        self.consumptions_page = ConsumptionCalendarPage(
            self.consumptions_repository, self.stack,
            background=self.background_queries,
        )
        self.stack.addWidget(self.consumptions_page)
        self.finance_pages = {}
        for code in MODULES:
            panel = FinanceHubPage(
                self.finance_repository, code, self.stack,
                background=self.background_queries,
            )
            panel.familyRequested.connect(
                lambda ident, origin=code: self._finance_family_requested(
                    origin, ident
                )
            )
            panel.relatedRequested.connect(
                lambda target, ident, origin=code: self._finance_related_requested(
                    origin, target, ident
                )
            )
            self.finance_pages[code] = panel
            self.stack.addWidget(panel)
        self.report_page = (
            ConsumptionStateReportPage(
                self.consumptions_repository, self.stack,
                background=self.background_queries,
            ) if self.c16_enabled else None
        )
        if self.report_page is not None:
            self.stack.addWidget(self.report_page)
        self.catalog_pages = {}
        for code in CATALOG_MODULES:
            if code in C16_CATALOG_MODULES:
                if not self.c16_enabled or (
                    code in C16_RESTRICTED_MODULES
                    and not self.badge_logs_enabled
                ):
                    continue
            elif code not in C14_MODULE_CODES and not self.c15_enabled:
                continue
            panel = CatalogHubPage(
                self.catalog_repository, code, self.stack,
                background=self.background_queries,
            )
            panel.familyRequested.connect(
                lambda ident, origin=code: self._catalog_family_requested(origin, ident)
            )
            panel.inscriptionRequested.connect(
                lambda ident, origin=code: self._catalog_inscription_requested(origin, ident)
            )
            panel.activityRequested.connect(
                lambda ident, origin=code: self._catalog_activity_requested(origin, ident)
            )
            self.catalog_pages[code] = panel
            self.stack.addWidget(panel)
        right_layout.addWidget(self.stack, 1)
        layout.addWidget(right, 1)
        self.setCentralWidget(root)
        self.navigation.setCurrentRow(0)

    def _build_home_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("Noethys Qt", page)
        title.setObjectName("mainTitle")
        subtitle = QLabel(
            "Coque Upgrade expérimentale — mêmes données Noethys, sans migration de schéma.", page
        )
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        source = QLabel(f"Données : {self.source_label}", page)
        layout.addWidget(source)

        section = QLabel("Accès quotidien", page)
        section.setObjectName("sectionTitle")
        layout.addWidget(section)
        quick = QHBoxLayout()
        people_button = QPushButton("Rechercher une famille ou un individu", page)
        activities_button = QPushButton("Paramétrer les activités", page)
        inscriptions_button = QPushButton("Consulter les inscriptions", page)
        consumptions_button = QPushButton("Consulter les consommations", page)
        people_button.clicked.connect(lambda: self.navigate("people"))
        activities_button.clicked.connect(self.open_activities)
        activities_button.setEnabled(not self.read_only_demo)
        inscriptions_button.clicked.connect(lambda: self.navigate("inscriptions"))
        consumptions_button.clicked.connect(lambda: self.navigate("consumptions"))
        quick.addWidget(people_button)
        quick.addWidget(activities_button)
        quick.addWidget(inscriptions_button)
        quick.addWidget(consumptions_button)
        quick.addStretch(1)
        layout.addLayout(quick)
        finance_quick = QHBoxLayout()
        for code, title in (
            ("billing", "Factures et prestations"),
            ("payments", "Règlements et ventilation"),
            ("accounting", "Trésorerie et dépôts"),
        ):
            button = QPushButton(title, page)
            button.clicked.connect(
                lambda _checked=False, destination=code:
                self.navigate(destination)
            )
            button.setEnabled(self.finance_enabled)
            finance_quick.addWidget(button)
        finance_quick.addStretch(1)
        layout.addLayout(finance_quick)

        for row_codes in (
            ("memberships", "contracts", "quotients"),
            ("rentals", "orders", "quotes"),
        ):
            catalog_quick = QHBoxLayout()
            for code in row_codes:
                button = QPushButton(CATALOG_MODULES[code][0], page)
                button.setEnabled(self.catalog_enabled)
                button.clicked.connect(
                    lambda _checked=False, target=code: self.navigate(target)
                )
                catalog_quick.addWidget(button)
            catalog_quick.addStretch(1)
            layout.addLayout(catalog_quick)
        if self.c15_enabled:
            extra = QHBoxLayout()
            for code in ("renewals", "certificates", "activity_settings", "headcounts"):
                button = QPushButton(CATALOG_MODULES[code][0], page)
                button.setEnabled(self.catalog_enabled)
                button.clicked.connect(
                    lambda _checked=False, target=code: self.navigate(target)
                )
                extra.addWidget(button)
            extra.addStretch(1)
            layout.addLayout(extra)

        if self.c16_enabled:
            extras = QHBoxLayout()
            for code, label in (
                ("planning", "Planning / événements"),
                ("tariff_records", "Tarification enregistrée"),
                ("consumption_reports", "États des consommations"),
                ("badge_journal", "Journal de badgeage"),
            ):
                button = QPushButton(label, page)
                button.setEnabled(
                    self.catalog_enabled and (
                        code not in C16_RESTRICTED_MODULES
                        or self.badge_logs_enabled
                    )
                )
                button.clicked.connect(
                    lambda _checked=False, target=code: self.navigate(target)
                )
                extras.addWidget(button)
            extras.addStretch(1)
            layout.addLayout(extras)

        migration = QLabel(
            "Disponible en Qt : Individus/Familles, Activités, Inscriptions, "
            "Consommations, Facturation, Règlements, Comptabilité, Cotisations, "
            "Contrats, Quotients, Locations, Commandes et Devis en consultation.\n"
            "À venir : saisie des consommations et opérations métier non qualifiées.",
            page,
        )
        migration.setWordWrap(True)
        layout.addWidget(migration)
        layout.addStretch(1)
        return page

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("Fichier")
        file_menu.addAction(self.quit_action)
        navigation_menu = self.menuBar().addMenu("Navigation")
        navigation_menu.addAction(self.home_action)
        navigation_menu.addAction(self.people_action)
        navigation_menu.addAction(self.activities_action)
        navigation_menu.addAction(self.inscriptions_action)
        navigation_menu.addAction(self.consumptions_action)
        for code in MODULES:
            navigation_menu.addAction(self.finance_actions[code])
        for code in CATALOG_MODULES:
            navigation_menu.addAction(self.catalog_actions[code])
        navigation_menu.addAction(self.report_action)
        navigation_menu.addAction(self.back_context_action)
        navigation_menu.addSeparator()
        navigation_menu.addAction(self.search_action)
        navigation_menu.addAction(self.refresh_action)

    def _theme_changed(self, *_args) -> None:
        theme = str(self.theme_combo.currentData() or "system")
        self.settings.setValue("appearance/theme", theme)
        apply_semantic_theme(self)

    def _restore_geometry(self) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _navigation_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        code = str(current.data(Qt.ItemDataRole.UserRole) or "")
        if code == "home":
            self._set_return_context(None)
            self._detail_request += 1
            self._current_detail = None
            self.stack.setCurrentWidget(self.home_page)
        elif code == "people":
            self._back_to_people()
        elif code == "activities":
            self.open_activities()
        elif code == "inscriptions":
            if not self._context_navigation:
                self._set_return_context(None)
                self.inscriptions_page.clear_context()
            self.stack.setCurrentWidget(self.inscriptions_page)
            self.inscriptions_page.activate()
        elif code == "consumptions":
            if not self._context_navigation:
                self._set_return_context(None)
                if (
                    self.consumptions_page._record_individual_id is not None
                    or self.consumptions_page._record_inscription_id is not None
                ):
                    self.consumptions_page.clear_record_context()
            self.stack.setCurrentWidget(self.consumptions_page)
            self.consumptions_page.activate()
        elif code == "consumption_reports" and self.report_page is not None:
            if not self._context_navigation:
                self._set_return_context(None)
                self.report_page.clear_context()
            self.stack.setCurrentWidget(self.report_page)
            self.report_page.activate()
        elif code in self.finance_pages:
            panel = self.finance_pages[code]
            if not self._context_navigation:
                self._set_return_context(None)
                if code != "accounting":
                    panel.set_family_context()
            self.stack.setCurrentWidget(panel)
            panel.activate()
        elif code in self.catalog_pages:
            panel = self.catalog_pages[code]
            if not self._context_navigation:
                self._set_return_context(None)
                panel.set_family_context()
            self.stack.setCurrentWidget(panel)
            panel.activate()

    def navigate(self, code: str) -> None:
        """Une entrée de menu = une navigation, sans double lecture SQL."""
        for row in range(self.navigation.count()):
            item = self.navigation.item(row)
            if item.data(Qt.ItemDataRole.UserRole) != code:
                continue
            if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
                return
            if self.navigation.currentRow() != row:
                # Le signal currentItemChanged effectue déjà la transition.
                self.navigation.setCurrentRow(row)
                return
            # Recliquer sur l'entrée courante doit seulement recharger son
            # contexte général, sans laisser un filtre de fiche résiduel.
            if code == "people" and self.stack.currentWidget() is self.details_page:
                self._back_to_people()
            elif code == "activities":
                self.open_activities()
            elif code == "inscriptions":
                if not self._context_navigation:
                    self.inscriptions_page.clear_context()
                    self._set_return_context(None)
                self.stack.setCurrentWidget(self.inscriptions_page)
                self.inscriptions_page.activate()
            elif code == "consumptions":
                if not self._context_navigation:
                    self._set_return_context(None)
                    if (
                        self.consumptions_page._record_individual_id is not None
                        or self.consumptions_page._record_inscription_id is not None
                    ):
                        self.consumptions_page.clear_record_context()
                self.stack.setCurrentWidget(self.consumptions_page)
                self.consumptions_page.activate()
            elif code == "consumption_reports" and self.report_page is not None:
                if not self._context_navigation:
                    self._set_return_context(None)
                    self.report_page.clear_context()
                self.stack.setCurrentWidget(self.report_page)
                self.report_page.activate()
            elif code in self.finance_pages:
                panel = self.finance_pages[code]
                if not self._context_navigation:
                    self._set_return_context(None)
                    if code != "accounting":
                        panel.set_family_context()
                self.stack.setCurrentWidget(panel)
                panel.activate()
            elif code in self.catalog_pages:
                panel = self.catalog_pages[code]
                if not self._context_navigation:
                    self._set_return_context(None)
                    panel.set_family_context()
                self.stack.setCurrentWidget(panel)
                panel.activate()
            return

    def focus_current_search(self) -> None:
        """Ctrl+F reste dans la rubrique active au lieu de changer de page."""
        current = self.stack.currentWidget()
        if current in self.catalog_pages.values():
            current.current_page.search_edit.setFocus(
                Qt.FocusReason.ShortcutFocusReason
            )
            current.current_page.search_edit.selectAll()
        elif current in self.finance_pages.values():
            current.current_page.search_edit.setFocus(
                Qt.FocusReason.ShortcutFocusReason
            )
            current.current_page.search_edit.selectAll()
        elif current is self.report_page and self.report_page is not None:
            self.report_page.activity_spin.setFocus(Qt.FocusReason.ShortcutFocusReason)
        elif current is self.inscriptions_page:
            self.inscriptions_page.search_edit.setFocus(
                Qt.FocusReason.ShortcutFocusReason
            )
            self.inscriptions_page.search_edit.selectAll()
        elif current is self.consumptions_page:
            self.consumptions_page.list_page.search_edit.setFocus(
                Qt.FocusReason.ShortcutFocusReason
            )
            self.consumptions_page.list_page.search_edit.selectAll()
        else:
            self.focus_people_search()

    def focus_people_search(self) -> None:
        self.navigate("people")
        self.people_page.focus_search()

    def refresh_current(self) -> None:
        if self.stack.currentWidget() is self.people_page:
            self.people_page.search_now()
            self.statusBar().showMessage("Recherche actualisée", 2500)
        elif self.stack.currentWidget() is self.consumptions_page:
            self.consumptions_page.refresh()
        elif self.stack.currentWidget() is self.inscriptions_page:
            self.inscriptions_page.refresh()
        elif self.report_page is not None and self.stack.currentWidget() is self.report_page:
            self.report_page.refresh()
        elif self.stack.currentWidget() in self.finance_pages.values():
            self.stack.currentWidget().current_page.refresh()
        elif self.stack.currentWidget() in self.catalog_pages.values():
            self.stack.currentWidget().current_page.refresh()
        elif self.stack.currentWidget() is self.details_page and self._current_detail:
            kind, entity_id = self._current_detail
            self._open_detail(kind, entity_id)
        else:
            self.statusBar().showMessage(self.source_label, 2500)

    def open_activities(self, *_args) -> None:
        if self.read_only_demo:
            self.statusBar().showMessage(
                "Démonstration fictive : éditeur d'activités désactivé.", 6500
            )
            return
        if self._activities_window is not None:
            self._activities_window.show()
            self._activities_window.raise_()
            self._activities_window.activateWindow()
            return
        try:
            window = NativeActivitiesWindow(
                self.activities_repository,
                editor_sqlite_path=self.editor_sqlite_path,
                requested_theme=str(self.theme_combo.currentData() or "system"),
            )
            apply_activity_visuals(window)
        except Exception as exc:
            QMessageBox.critical(self, "Activités", str(exc))
            return
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.destroyed.connect(self._activities_closed)
        self._activities_window = window
        window.show()

    def _activities_closed(self, *_args) -> None:
        self._activities_window = None

    def _back_to_people(self) -> None:
        self._set_return_context(None)
        self._detail_request += 1
        self._current_detail = None
        self.stack.setCurrentWidget(self.people_page)
        self.people_page.focus_search()

    def _open_detail(self, kind: str, entity_id: int) -> None:
        self._detail_request += 1
        token = self._detail_request
        self._current_detail = (kind, entity_id)
        self.details_page.show_loading(kind, entity_id)
        self.stack.setCurrentWidget(self.details_page)
        worker = _DetailWorker(self.details_repository, token, kind, entity_id)
        self._detail_workers[token] = worker
        worker.signals.completed.connect(self._detail_loaded)
        QThreadPool.globalInstance().start(worker)

    def _detail_loaded(self, token: int, kind: str, detail: object, error: str) -> None:
        self._detail_workers.pop(token, None)
        if token != self._detail_request or not self._current_detail:
            return
        current_kind, entity_id = self._current_detail
        if current_kind != kind:
            return
        if error:
            self.details_page.show_error(kind, entity_id, error)
            return
        if kind == "family" and isinstance(detail, FamilyDetails):
            self.details_page.show_family(detail)
        elif kind == "individual" and isinstance(detail, PersonRow):
            self.details_page.show_individual(detail)
        else:
            self.details_page.show_error(kind, entity_id, "Réponse inattendue.")

    def _set_return_context(self, value: tuple | None) -> None:
        """Empiler les étapes de navigation ; None annule le parcours."""
        if value is None:
            self._context_history.clear()
        else:
            self._context_history.append(value)
        self._render_context_back()

    def _render_context_back(self) -> None:
        self._return_context = (
            self._context_history[-1] if self._context_history else None
        )
        value = self._return_context
        self.context_bar.setVisible(value is not None)
        self.back_context_action.setEnabled(value is not None)
        if value is None:
            self.context_label.clear()
        elif value[0] == "details":
            self.context_label.setText(
                f"Retour à la fiche {value[1]} #{value[2]}"
            )
        elif value[0] == "inscriptions":
            self.context_label.setText("Retour à la liste des inscriptions")
        elif value[0] == "finance":
            self.context_label.setText(
                f"Retour à {MODULES[value[1]][0]}"
            )
        elif value[0] == "catalog":
            self.context_label.setText(
                f"Retour à {CATALOG_MODULES[value[1]][0]}"
            )

    def _navigate_with_context(self, code: str) -> None:
        self._context_navigation = True
        try:
            self.navigate(code)
        finally:
            self._context_navigation = False

    def _family_finance_requested(self, code: str, family_id: int) -> None:
        if code not in ("billing", "payments"):
            raise ValueError("Contexte famille indisponible pour ce domaine")
        self.finance_pages[code].set_family_context(family_id)
        self._navigate_with_context(code)
        self._set_return_context(("details", "family", family_id))

    def _finance_family_requested(self, origin: str, family_id: int) -> None:
        if origin not in ("billing", "payments"):
            raise ValueError("Lien vers une famille non autorisé")
        self._set_return_context(("finance", origin))
        self._open_detail("family", family_id)

    def _finance_related_requested(self, origin: str, target: str, record_id: int) -> None:
        if origin != "accounting" or target != "deposit_payments":
            raise ValueError("Lien financier inter-module inconnu")
        self.finance_pages["payments"].set_family_context()
        self.finance_pages["payments"].focus_related(
            "payments", record_id
        )
        self._navigate_with_context("payments")
        self._set_return_context(("finance", "accounting"))

    def _family_catalog_requested(self, code: str, family_id: int) -> None:
        if code not in FAMILY_CATALOG_MODULES:
            raise ValueError("Module non applicable à un dossier famille")
        validate_finance_id(family_id, "famille")
        self.catalog_pages[code].set_family_context(family_id)
        self._navigate_with_context(code)
        self._set_return_context(("details", "family", family_id))

    def _catalog_family_requested(self, origin: str, family_id: int) -> None:
        if origin not in FAMILY_CATALOG_MODULES:
            raise ValueError("Retour famille interdit pour ce domaine")
        validate_finance_id(family_id, "famille")
        self._set_return_context(("catalog", origin))
        self._open_detail("family", family_id)

    def _catalog_inscription_requested(self, origin: str, inscription_id: int) -> None:
        if origin != "contracts":
            raise ValueError("Lien inscription indisponible")
        try:
            link = self.inscriptions_repository.resolve_link(inscription_id)
        except (ValueError, LookupError, OSError, RuntimeError) as exc:
            self.statusBar().showMessage(f"Consultation indisponible : {exc}", 8000)
            return
        self.inscriptions_page.set_context(
            family_id=link.family_id, individual_id=link.individual_id
        )
        self._navigate_with_context("inscriptions")
        self._set_return_context(("catalog", origin))

    def _catalog_activity_requested(self, origin: str, activity_id: int) -> None:
        if origin not in C15_ACTIVITY_MODULES and origin not in (
            "planning", "tariff_records"
        ):
            raise ValueError("Ce lien vers les inscriptions est indisponible")
        validate_finance_id(activity_id, "activité")
        self.inscriptions_page.set_context(activity_id=activity_id)
        self._navigate_with_context("inscriptions")
        self._set_return_context(("catalog", origin))

    def _family_inscriptions_requested(self, family_id: int) -> None:
        self._show_inscriptions_from_detail("family", family_id)

    def _individual_inscriptions_requested(self, individual_id: int) -> None:
        self._show_inscriptions_from_detail("individual", individual_id)

    def _show_inscriptions_from_detail(self, kind: str, entity_id: int) -> None:
        if not isinstance(entity_id, int) or isinstance(entity_id, bool) or entity_id <= 0:
            raise ValueError("Fiche invalide")
        if kind not in ("family", "individual"):
            raise ValueError("Type de fiche invalide")
        filters = (
            {"family_id": entity_id} if kind == "family"
            else {"individual_id": entity_id}
        )
        self.inscriptions_page.set_context(**filters)
        self._navigate_with_context("inscriptions")
        self._set_return_context(("details", kind, entity_id))

    def _individual_consumptions_requested(self, individual_id: int) -> None:
        self._show_consumptions(
            individual_id=individual_id,
            origin=("details", "individual", individual_id),
        )

    def _inscription_consumptions_requested(self, inscription_id: int) -> None:
        try:
            link = self.inscriptions_repository.resolve_link(inscription_id)
        except (ValueError, LookupError, OSError, RuntimeError) as exc:
            self.statusBar().showMessage(
                f"Consultation indisponible : {exc}", 8000
            )
            return
        self._show_consumptions(
            individual_id=link.individual_id,
            inscription_id=link.inscription_id,
            origin=("inscriptions",),
        )

    def _show_consumptions(
        self, *, individual_id: int, inscription_id: int | None = None,
        origin: tuple | None = None,
    ) -> None:
        # Aucun recalcul financier ; les filtres exacts sont appliqués en
        # lecture seule sur la même page que la navigation principale.
        if not isinstance(individual_id, int) or isinstance(individual_id, bool) or individual_id <= 0:
            raise ValueError("Identifiant individu invalide")
        self.consumptions_page.focus_record(
            individual_id=individual_id, inscription_id=inscription_id
        )
        self._navigate_with_context("consumptions")
        self._set_return_context(origin)

    def return_to_context(self) -> None:
        origin = self._return_context
        if origin is None:
            return
        self._context_history.pop()
        self._render_context_back()
        if origin[0] == "inscriptions":
            self._navigate_with_context("inscriptions")
        elif origin[0] == "details":
            self.navigate("people")
            self._open_detail(origin[1], origin[2])
        elif origin[0] == "finance":
            self._navigate_with_context(origin[1])
        elif origin[0] == "catalog":
            self._navigate_with_context(origin[1])

    def _family_requested(self, family_id: int) -> None:
        self._open_detail("family", family_id)

    def _individual_requested(self, individual_id: int) -> None:
        self._open_detail("individual", individual_id)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.settings.setValue("window/geometry", self.saveGeometry())
        if self._activities_window is not None:
            self._activities_window.close()
        super().closeEvent(event)


def _configured_source_label(sqlite_path: Path | None) -> str:
    if sqlite_path is not None:
        return f"copie SQLite {sqlite_path.name}"
    try:
        descriptor = str(_load_config().get("nomFichier") or "").strip()
    except Exception:
        return "configuration Noethys"
    if "[RESEAU]" in descriptor:
        _before, database = descriptor.split("[RESEAU]", 1)
        return f"base réseau {database}"
    return f"base locale {descriptor}" if descriptor else "configuration Noethys"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Noethys Qt")
    app.setOrganizationName("Noethys")

    editor_repository = NativeActivityEditorRepository(args.sqlite)
    people_repository = PeopleSearchRepository(editor_repository)
    activities_repository: ActivityRepository
    if args.sqlite:
        activities_repository = SqliteActivityRepository(args.sqlite)
    else:
        activities_repository = NativeConfiguredActivityRepository()

    window = NoethysQtWindow(
        people_repository,
        activities_repository,
        editor_sqlite_path=args.sqlite,
        requested_theme=args.theme,
        source_label=_configured_source_label(args.sqlite),
        c15_enabled=True,
        c16_enabled=True,
        badge_logs_enabled=False,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
