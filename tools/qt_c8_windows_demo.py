"""C8 : interface Windows de recette des consommations Qt, DONNÉES FICTIVES.

Par défaut ouvre une fenêtre interactive sur la base temporaire générée
par qt_c8_fixture. Aucun accès au profil Noethys ni à une base configurée.
--smoke automatise un parcours et des captures pour GitHub Actions.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# DPI doit être configuré AVANT la création de QApplication.
if __name__ == "__main__":
    _pre = argparse.ArgumentParser(add_help=False)
    _pre.add_argument("--scale", choices=("1", "1.25", "1.5"), default=None)
    _known, _unknown = _pre.parse_known_args()
    if _known.scale is not None:
        os.environ["QT_SCALE_FACTOR"] = _known.scale

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QDate, Qt, QThreadPool
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)
from noethys_qt.activity_visuals import apply_semantic_theme
from noethys_qt.consumptions_calendar_ui import ConsumptionCalendarPage
from tools.qt_c8_fixture import C8FictiveDatabase, EXPECTED_ROWS, FIRST_DAY, MARKER
from tools.qt_c9_navigation import C9BusinessPage


class C8DemoWindow(QMainWindow):
    def __init__(self, repository, *, theme="system", background=True, fictive_db=None):
        super().__init__()
        self.setObjectName("qtC8DemoWindow")
        self.setWindowTitle("Noethys Qt C8 — démonstration FICTIVE / lecture seule")
        self.setMinimumSize(960, 650)
        self.resize(1180, 790)
        outer = QWidget(self)
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(5)

        self.banner = QLabel(
            "DÉMONSTRATION 100 % FICTIVE — lecture seule — aucune donnée Noéthys réelle",
            outer,
        )
        self.banner.setObjectName("c8FictiveBanner")
        self.banner.setWordWrap(True)
        self.banner.setAccessibleName("Avertissement : données fictives, lecture seule")
        layout.addWidget(self.banner)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Thème :", outer))
        self.theme_combo = QComboBox(outer)
        for label, code in (("Système", "system"), ("Clair", "light"), ("Sombre", "dark")):
            self.theme_combo.addItem(label, code)
        index = self.theme_combo.findData(theme)
        self.theme_combo.setCurrentIndex(index if index >= 0 else 0)
        self.theme_combo.setAccessibleName("Thème du démonstrateur Qt")
        toolbar.addWidget(self.theme_combo)
        self.refresh_button = QPushButton("Actualiser (F5)", outer)
        toolbar.addWidget(self.refresh_button)
        self.reset_button = QPushButton("2 octobre 2026", outer)
        toolbar.addWidget(self.reset_button)
        toolbar.addStretch(1)
        toolbar.addWidget(QLabel("Fermer la fenêtre pour effacer la base temporaire", outer))
        layout.addLayout(toolbar)

        self.page = ConsumptionCalendarPage(repository, outer, background=background)
        if fictive_db is not None:
            self.tabs = QTabWidget(outer)
            self.business_page = C9BusinessPage(fictive_db, self.tabs)
            self.tabs.addTab(self.business_page, "Familles · Individus · Activités · Inscriptions")
            self.tabs.addTab(self.page, "Consommations")
            self.business_page.on_domain_requested = self._open_business_consumptions
            self.tabs.setCurrentWidget(self.page)
            layout.addWidget(self.tabs, 1)
        else:
            # Compatibilité des tests C8/C7 qui fournissent un repository seul.
            self.tabs = None
            self.business_page = None
            layout.addWidget(self.page, 1)
        self.setCentralWidget(outer)
        self.statusBar().showMessage("Base fictive créée uniquement en mémoire de recette")

        self.theme_combo.currentIndexChanged.connect(lambda _i: apply_semantic_theme(self))
        self.refresh_button.clicked.connect(self.page.refresh)
        self.reset_button.clicked.connect(self.focus_sample_day)
        self.refresh_action = QAction(self)
        self.refresh_action.setShortcut(QKeySequence.Refresh)
        self.refresh_action.triggered.connect(self.page.refresh)
        self.addAction(self.refresh_action)

        self.find_action = QAction(self)
        self.find_action.setShortcut(QKeySequence.Find)
        self.find_action.triggered.connect(self.page.list_page.search_edit.setFocus)
        self.addAction(self.find_action)
        apply_semantic_theme(self)

    def _open_business_consumptions(self, domain, *, individual_id=None,
                                    inscription_id=None):
        if domain != "consommations" or self.tabs is None:
            raise ValueError("Destination métier indisponible.")
        self.page.focus_record(
            individual_id=individual_id, inscription_id=inscription_id,
            year=FIRST_DAY.year,
        )
        self.tabs.setCurrentWidget(self.page)

    def focus_sample_day(self):
        self.page.list_page.year_spin.setValue(2026)
        self.page.calendar.setSelectedDate(QDate(2026, 10, 2))
        if not self.page.only_day.isChecked():
            self.page.only_day.setChecked(True)

    def activate_demo(self):
        # Les filtres sont prêts avant toute lecture SQL.
        self.focus_sample_day()
        self.page.activate()


def _wait_for(app, condition, description, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        QTest.qWait(20)
    raise AssertionError("Délai C8 dépassé : " + description)


def smoke(app, window, db, *, label):
    """Séquence automatisée dans la VRAIE surface Qt, source fictive."""
    initial_dump = db.dump()
    window.show()
    window.activate_demo()
    page = window.page
    _wait_for(
        app,
        lambda: page.list_page.model.rowCount() == 4
        and len(page._date_counts) == 28
        and page._activity_loaded,
        "jour, calendrier et activités",
    )
    if not page.preparation_panel.warning.isVisible() or not window.banner.isVisible():
        raise AssertionError("L'avertissement lecture seule n'est pas visible")

    page.list_page.table.selectRow(1)
    _wait_for(
        app, lambda: "Consommation #" in page.details_label.text(),
        "détail de la consommation sélectionnée",
    )
    selected_id = page.list_page.model.rows[1].consumption_id

    # Plusieurs actualisations sans altérer la sélection.
    for _ in range(7):
        window.refresh_button.click()
    _wait_for(
        app, lambda: page.list_page.model.rowCount() == 4
        and page.list_page.table.selectionModel().hasSelection(),
        "conservation de sélection",
    )
    indices = page.list_page.table.selectionModel().selectedRows()
    if not indices or page.list_page.model.rows[indices[0].row()].consumption_id != selected_id:
        raise AssertionError("Sélection perdue pendant actualisation")

    # Aller-retour sur activité et états ; les sept choix restent accessibles.
    page.activity_combo.setCurrentIndex(page.activity_combo.findData(1))
    _wait_for(app, lambda: page.list_page.model.rowCount() == 2, "activité 1")
    page.activity_combo.setCurrentIndex(0)
    _wait_for(app, lambda: page.list_page.model.rowCount() == 4, "toutes les activités")
    page.list_page.none_button.click()
    _wait_for(app, lambda: page.list_page.model.rowCount() == 0, "aucun état")
    page.list_page.all_button.click()
    _wait_for(app, lambda: page.list_page.model.rowCount() == 4, "tous les états")

    # Précontrôle strictement non exécutable, avec base de démo complète.
    page.list_page.table.selectRow(0)
    page.preparation_panel.target_combo.setCurrentIndex(
        page.preparation_panel.target_combo.findData("present")
    )
    page.preparation_panel.preview_button.click()
    _wait_for(
        app, lambda: page.preparation_panel.last_preview is not None,
        "précontrôle bloqué",
    )
    if page.preparation_panel.last_preview.executable:
        raise AssertionError("Une écriture a été activée dans la démonstration")

    # Thème et redimensionnement réellement appliqués au widget Qt.
    current_theme = window.theme_combo.currentData()
    alternate = "dark" if current_theme != "dark" else "light"
    window.theme_combo.setCurrentIndex(window.theme_combo.findData(alternate))
    app.processEvents()
    window.theme_combo.setCurrentIndex(window.theme_combo.findData(current_theme))
    app.processEvents()
    for width, height in ((1010, 700), (1250, 820), (1100, 740)):
        window.resize(width, height)
        app.processEvents()
        if not window.banner.isVisible() or not page.preparation_panel.warning.isVisible():
            raise AssertionError("Avertissement masqué par le redimensionnement")
        if page.calendar.width() < 160 or page.list_page.table.viewport().width() < 180:
            raise AssertionError("Calendrier ou tableau insuffisamment large")

    # Capture seulement APRÈS les interactions pour inspecter le résultat.
    outdir = (ROOT / "artifacts" / "qt-c8").resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    if not re.fullmatch(r"[a-z0-9_-]{1,48}", label):
        raise ValueError("Étiquette de capture non autorisée")
    capture = outdir / (label + ".png")
    report = outdir / (label + ".json")
    for output in (capture, report):
        if output.is_symlink() or output.parent.resolve() != outdir:
            raise RuntimeError("Destination de capture interdite")
    window.resize(1180, 790)
    app.processEvents()
    image = window.grab()
    if image.isNull() or not image.save(str(capture), "PNG"):
        raise RuntimeError("Capture Qt C8 impossible")
    if capture.stat().st_size < 3000:
        raise RuntimeError("Image de recette trop petite")

    if db.dump() != initial_dump:
        raise AssertionError("La démonstration a écrit dans sa propre base fictive")

    info = {
        "lot": "C8",
        "source": "C8_SYNTHETIC_ONLY",
        "marker": MARKER,
        "platform": sys.platform,
        "qt_platform": os.environ.get("QT_QPA_PLATFORM", "default"),
        "scale_factor": os.environ.get("QT_SCALE_FACTOR", "system"),
        "theme": current_theme,
        "image_pixels": [image.width(), image.height()],
        "fixture_rows": EXPECTED_ROWS,
        "day_rows": page.list_page.model.rowCount(),
        "states_available": len(page.list_page.state_checks),
        "selected_date": page.calendar.selectedDate().toString(Qt.DateFormat.ISODate),
        "preflight_executable": page.preparation_panel.last_preview.executable
        if page.preparation_panel.last_preview is not None else None,
        "database_unchanged": True,
        "manual_flicker_review_required": True,
    }
    report.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"C8_SMOKE_PASS label={label} size={image.width()}x{image.height()} "
        f"rows={EXPECTED_ROWS} day_rows={page.list_page.model.rowCount()} "
        f"theme={current_theme} scale={info['scale_factor']} database_unchanged=true"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Noethys Qt - démonstration fictive C8")
    parser.add_argument("--theme", choices=("system", "light", "dark"), default="system")
    parser.add_argument("--scale", choices=("1", "1.25", "1.5"))
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--label", default="c8-smoke")
    args = parser.parse_args(argv)

    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setOrganizationName("Noethys-C8-Fictif")
    app.setApplicationName("Noethys Qt C8 Démonstration")
    app.setStyle("Fusion")

    with C8FictiveDatabase() as db:
        window = C8DemoWindow(db.repository, theme=args.theme, background=True, fictive_db=db)
        try:
            if args.smoke:
                smoke(app, window, db, label=args.label)
                return 0
            window.show()
            window.activate_demo()
            print(
                "DEMONSTRATION FICTIVE — aucune base configurée utilisée. "
                "Fermez la fenêtre Qt pour terminer."
            )
            return app.exec()
        finally:
            window.close()
            # Connexions worker terminées avant suppression de la fixture
            # sur Windows; aucun autre accès à une base réelle possible.
            if not QThreadPool.globalInstance().waitForDone(10000):
                raise RuntimeError("Travail Qt encore actif, fichier temporaire conservé")
            app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
