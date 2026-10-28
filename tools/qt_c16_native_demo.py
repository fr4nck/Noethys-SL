"""C16 — Windows smoke sur SQLite temporaire entièrement inventé.

Planning, tarifs, journaux fictifs et compteurs par états cochés à la main.
Ni export de données ni base familiale réelle ni écriture métier.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.consumptions_core import ALL_STATES, OTHER
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c16_fixture import C16FictivePlanningDatabase


def _wait(app, callback, stage, seconds=10):
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        app.processEvents()
        if callback():
            return
        QTest.qWait(20)
    raise AssertionError("C16 timeout on synthetic GUI : " + stage)


def _smoke(app, window, fixture, profile):
    root = (ROOT / "artifacts" / "qt-c16").resolve()
    root.mkdir(parents=True, exist_ok=True)
    steps = (
        "accueil", "ouvertures", "ouvertures-activite",
        "evenements", "evenements-2027",
        "tarifs", "lignes-tarifs", "lignes-activite",
        "journal-fictif", "etats-tous-2026",
        "etats-present", "etats-autres", "etats-aucun",
        "etats-restaures", "etats-2027",
        "attestations-c15", "facturation-c13", "retour-accueil",
    )
    targets = [
        root / f"{profile}-{item}.png" for item in steps
    ] + [root / f"{profile}-trace.json"]
    for path in targets:
        if path.parent.resolve() != root or path.is_symlink():
            raise RuntimeError("Export C16 hors répertoire autorisé")
    original = fixture.dump()
    if not window.read_only_demo or not window.c16_enabled or not window.badge_logs_enabled:
        raise AssertionError("Les données du C16 doivent rester exclusivement fictives")
    if window.navigation.count() != 22:
        raise AssertionError("La coque C16 attend 22 rubriques")
    if window.activities_action.isEnabled():
        raise AssertionError("Le moteur d'édition d'activité est resté actif")
    window.resize(1500, 950)
    window.show()
    app.processEvents()
    trace = []

    def picture(stage, module=None, kind=None, expected=None, report_total=None):
        app.processEvents()
        if module is not None:
            hub = window.catalog_pages[module]
            if window.stack.currentWidget() is not hub or hub.current_page.kind != kind:
                raise AssertionError("Module C16 inattendu : " + stage)
            page = hub.current_page
            if page.table.editTriggers() != QAbstractItemView.EditTrigger.NoEditTriggers:
                raise AssertionError("Édition autorisée en C16 : " + stage)
            ids = {row.id for row in page.model.rows}
            if expected is not None and ids != set(expected):
                raise AssertionError(f"C16 {stage} : {ids} != {set(expected)}")
        else:
            ids = set()
        if report_total is not None:
            page = window.report_page
            if window.stack.currentWidget() is not page:
                raise AssertionError("La page d'états C16 n'est pas active")
            if page.last_result is None or page.last_result.total != report_total:
                raise AssertionError(f"Total C16 incorrect au stade {stage}")
            if page.table.editTriggers() != QAbstractItemView.EditTrigger.NoEditTriggers:
                raise AssertionError("Édition d'état autorisée")
        img = window.grab()
        target = root / f"{profile}-{stage}.png"
        if img.isNull() or not img.save(str(target), "PNG") or target.stat().st_size < 3000:
            raise AssertionError("Capture C16 absente : " + stage)
        trace.append({
            "stage": stage, "module": module, "kind": kind,
            "ids": sorted(ids), "state_count": report_total,
            "size": [img.width(), img.height()],
        })

    picture("accueil")
    window.navigate("planning")
    hub = window.catalog_pages["planning"]
    picture("ouvertures", "planning", "openings", {601, 602, 603})
    hub.current_page.activity_spin.setValue(1)
    picture("ouvertures-activite", "planning", "openings", {601, 603})
    hub.tabs.setCurrentWidget(hub.pages["events"])
    picture("evenements", "planning", "events", {41, 42, 43})
    hub.current_page.year_spin.setValue(2027)
    picture("evenements-2027", "planning", "events", {43})

    window.navigate("tariff_records")
    hub = window.catalog_pages["tariff_records"]
    picture("tarifs", "tariff_records", "tariffs", {801, 802, 803})
    hub.tabs.setCurrentWidget(hub.pages["tariff_lines"])
    picture("lignes-tarifs", "tariff_records", "tariff_lines", {901, 902, 903})
    hub.current_page.activity_spin.setValue(1)
    picture("lignes-activite", "tariff_records", "tariff_lines", {901, 903})

    window.navigate("badge_journal")
    picture("journal-fictif", "badge_journal", "badge_actions", {1001, 1002, 1003})

    window.navigate("consumption_reports")
    state = window.report_page
    state.year_spin.setValue(2026)
    picture("etats-tous-2026", report_total=112)
    state.none_button.click()
    state.state_checks["present"].click()
    if state.selected_states != {"present"}:
        raise AssertionError("La sélection par clic est incohérente")
    picture("etats-present", report_total=16)
    state.none_button.click()
    state.state_checks[OTHER].click()
    picture("etats-autres", report_total=25)
    state.none_button.click()
    picture("etats-aucun", report_total=0)
    state.all_button.click()
    if state.selected_states != ALL_STATES:
        raise AssertionError("Sept états non restaurés")
    picture("etats-restaures", report_total=112)
    state.year_spin.setValue(2027)
    picture("etats-2027", report_total=3)

    window.navigate("certificates")
    picture("attestations-c15", "certificates", "certificates", {7001, 7002, 7003})
    window.navigate("billing")
    if {r.id for r in window.finance_pages["billing"].current_page.model.rows} != {
        501, 502, 503, 990,
    }:
        raise AssertionError("Non-régression C13 : facturation")
    picture("facturation-c13")
    window.navigate("home")
    picture("retour-accueil")
    if fixture.dump() != original:
        raise AssertionError("La fixture C16 a été modifiée par la consultation")
    if len(trace) != len(steps):
        raise AssertionError("Captures C16 manquantes")
    (root / f"{profile}-trace.json").write_text(
        json.dumps({
            "milestone": "C16",
            "source": "TEMPORARY_100_PERCENT_SYNTHETIC",
            "shell": "NoethysQtWindow",
            "theme_scale": profile,
            "frames": trace,
            "source_unchanged": True,
            "billing_calculation": False,
            "official_CAF_AFAS": False,
            "badge_log_production_enabled": False,
            "production_qualified": False,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"C16_MODULES_PASS profile={profile} frames={len(steps)} "
        "three_catalog_modules=true one_status_report=true "
        "state_filter_clicks=true seven_state_codes=true "
        "sqlite_unchanged=true synthetic_only=true"
    )


def main():
    parser = argparse.ArgumentParser(description="C16 Noethys Qt — fixture uniquement")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--theme", choices=("light", "dark", "system"), default="light")
    parser.add_argument("--profile", choices=("100", "125", "150"), default="100")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    app.setOrganizationName("Noethys-C16-Fixture")
    app.setApplicationName("Noethys Qt C16 (fictif)")
    with C16FictivePlanningDatabase() as fixture, tempfile.TemporaryDirectory(
        prefix="noethys-c16-qt-settings-"
    ) as directory:
        settings = QSettings(str(Path(directory) / "c16.ini"), QSettings.Format.IniFormat)
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            window = NoethysQtWindow(
                PeopleSearchRepository(fixture.repository.editor_repository),
                SqliteActivityRepository(fixture.path),
                editor_sqlite_path=fixture.path,
                source_label="C16 : BASE FICTIVE UNIQUEMENT — AUCUNE ÉCRITURE",
                requested_theme=args.theme,
                read_only_demo=True,
                background_queries=not args.smoke,
                catalog_enabled=True,
                c15_enabled=True,
                c16_enabled=True,
                badge_logs_enabled=True,
            )
        window.setWindowTitle("Noethys Qt C16 — démonstration fictive")
        try:
            if args.smoke:
                _smoke(app, window, fixture, f"{args.theme}-{args.profile}")
                return 0
            window.show()
            print("C16 : toutes les données sont inventées. Pas d'écriture.")
            return app.exec()
        finally:
            window.close()
            if not QThreadPool.globalInstance().waitForDone(10000):
                raise RuntimeError("Un worker Qt C16 reste actif")
            app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
