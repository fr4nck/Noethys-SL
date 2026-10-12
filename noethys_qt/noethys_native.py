"""Première coque principale Qt de Noethys Upgrade.

Elle remplace le lancement isolé du module Activités par une navigation de
produit réelle. Les surfaces migrées restent indépendantes du runtime wx.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QSettings, Qt
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
from .people_search import PeopleSearchPage, PeopleSearchRepository


NAVIGATION = (
    ("home", "Accueil", True),
    ("people", "Individus / Familles", True),
    ("activities", "Activités", True),
    ("consumptions", "Consommations", False),
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
    ):
        super().__init__()
        self.people_repository = people_repository
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
        self.refresh_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload), "Actualiser", self)
        self.quit_action = QAction("Quitter", self)

        self.home_action.setShortcut(QKeySequence("Alt+1"))
        self.people_action.setShortcut(QKeySequence("Alt+2"))
        self.activities_action.setShortcut(QKeySequence("Alt+3"))
        self.refresh_action.setShortcut(QKeySequence.Refresh)
        self.quit_action.setShortcut(QKeySequence.Quit)

        self.home_action.triggered.connect(lambda: self.navigate("home"))
        self.people_action.triggered.connect(lambda: self.navigate("people"))
        self.activities_action.triggered.connect(self.open_activities)
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

        self.stack = QStackedWidget(root)
        self.home_page = self._build_home_page()
        self.people_page = PeopleSearchPage(self.people_repository, self.stack)
        self.people_page.familyRequested.connect(self._family_requested)
        self.people_page.individualRequested.connect(self._individual_requested)
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.people_page)
        layout.addWidget(self.stack, 1)
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
        people_button.clicked.connect(lambda: self.navigate("people"))
        activities_button.clicked.connect(self.open_activities)
        quick.addWidget(people_button)
        quick.addWidget(activities_button)
        quick.addStretch(1)
        layout.addLayout(quick)

        migration = QLabel(
            "Disponible en Qt : recherche Individus/Familles et module Activités.\n"
            "Prochains P0 : fiches Famille/Individu puis gestionnaire des consommations.",
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
            self.stack.setCurrentWidget(self.home_page)
        elif code == "people":
            self.stack.setCurrentWidget(self.people_page)
            self.people_page.focus_search()
        elif code == "activities":
            self.open_activities()

    def navigate(self, code: str) -> None:
        for row in range(self.navigation.count()):
            item = self.navigation.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == code:
                self.navigation.setCurrentRow(row)
                if code == "activities":
                    self.open_activities()
                return

    def focus_people_search(self) -> None:
        self.navigate("people")
        self.people_page.focus_search()

    def refresh_current(self) -> None:
        if self.stack.currentWidget() is self.people_page:
            self.people_page.search_now()
            self.statusBar().showMessage("Recherche actualisée", 2500)
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

    def _family_requested(self, family_id: int) -> None:
        self.statusBar().showMessage(
            f"Famille #{family_id} sélectionnée — fiche Qt complète = prochain P0", 5000
        )

    def _individual_requested(self, individual_id: int) -> None:
        self.statusBar().showMessage(
            f"Individu #{individual_id} sélectionné — fiche Qt complète = prochain P0", 5000
        )

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
