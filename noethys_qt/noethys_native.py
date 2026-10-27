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
    ("billing", "Facturation", False),
    ("payments", "Règlements", False),
    ("accounting", "Comptabilité", False),
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
    ):
        super().__init__()
        self.people_repository = people_repository
        self.details_repository = PeopleDetailsRepository(people_repository)
        self.consumptions_repository = ConsumptionRepository(people_repository.editor_repository)
        self.inscriptions_repository = InscriptionRepository(people_repository.editor_repository)
        self.background_queries = background_queries
        self._context_navigation = False
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
        self.back_context_action = QAction("Retour au dossier précédent", self)
        self.refresh_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Actualiser", self)
        self.quit_action = QAction("Quitter", self)

        self.home_action.setShortcut(QKeySequence("Alt+1"))
        self.people_action.setShortcut(QKeySequence("Alt+2"))
        self.activities_action.setShortcut(QKeySequence("Alt+3"))
        self.inscriptions_action.setShortcut(QKeySequence("Alt+4"))
        self.consumptions_action.setShortcut(QKeySequence("Alt+5"))
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
        self.search_action.triggered.connect(self.focus_people_search)
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
        for code, label, enabled in NAVIGATION:
            item = QListWidgetItem(label if enabled else f"{label}  · à migrer")
            item.setData(Qt.ItemDataRole.UserRole, code)
            if not enabled:
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
        inscriptions_button.clicked.connect(lambda: self.navigate("inscriptions"))
        consumptions_button.clicked.connect(lambda: self.navigate("consumptions"))
        quick.addWidget(people_button)
        quick.addWidget(activities_button)
        quick.addWidget(inscriptions_button)
        quick.addWidget(consumptions_button)
        quick.addStretch(1)
        layout.addLayout(quick)

        migration = QLabel(
            "Disponible en Qt : Individus/Familles, Activités, Inscriptions et consultation des consommations.\n"
            "À venir : saisie des consommations, facturation et règlements.",
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
            return

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
        elif self.stack.currentWidget() is self.details_page and self._current_detail:
            kind, entity_id = self._current_detail
            self._open_detail(kind, entity_id)
        else:
            self.statusBar().showMessage(self.source_label, 2500)

    def open_activities(self, *_args) -> None:
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
        self._return_context = value
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

    def _navigate_with_context(self, code: str) -> None:
        self._context_navigation = True
        try:
            self.navigate(code)
        finally:
            self._context_navigation = False

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
        self._set_return_context(None)
        if origin[0] == "inscriptions":
            self._navigate_with_context("inscriptions")
        elif origin[0] == "details":
            self.navigate("people")
            self._open_detail(origin[1], origin[2])

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
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
