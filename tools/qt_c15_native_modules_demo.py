"""C15 : démonstration complète de la même coque Qt, sur SQLite inventé.

Deux profils Windows (clair 100 %, sombre 150 %), sans base ni profil réel.
Chaque capture et chaque rapport est produit uniquement sous artifacts/qt-c15.
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
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c15_modules_fixture import C15FictiveModulesDatabase


def _wait(app, callback, stage, seconds=9):
    stop = time.monotonic() + seconds
    while time.monotonic() < stop:
        app.processEvents()
        if callback():
            return
        QTest.qWait(20)
    raise AssertionError("C15 délai de navigation fictive : " + stage)


def smoke(app, window, fixture, profile):
    root = (ROOT / "artifacts" / "qt-c15").resolve()
    root.mkdir(parents=True, exist_ok=True)
    sequence = (
        "accueil", "echeances-global", "echeances-famille",
        "unites-cotisation", "attestations-famille", "attestations-global",
        "activites-unites", "activites-groupes", "activites-tarifs",
        "liens-inscriptions", "effectifs-inscriptions",
        "effectifs-consommations", "cotisations-c14", "factures-c13",
        "retour-accueil",
    )
    paths = [root / f"{profile}-{name}.png" for name in sequence]
    trace_path = root / f"{profile}-trace.json"
    for target in [*paths, trace_path]:
        if target.parent.resolve() != root or target.is_symlink():
            raise RuntimeError("Chemin d'export C15 non autorisé")
    before = fixture.dump()
    if not window.c15_enabled or not window.read_only_demo:
        raise AssertionError("Coque C15 fictive non isolée")
    if window.activities_action.isEnabled():
        raise AssertionError("Éditeur Activités non neutralisé")
    if window.navigation.count() != 18:
        raise AssertionError("Coque C15 incomplète")
    window.resize(1440, 900)
    window.show()
    app.processEvents()
    trace = []

    def capture(name, module=None, kind=None, ids=None):
        app.processEvents()
        panel = window.catalog_pages.get(module) if module else None
        page = panel.current_page if panel else None
        if panel:
            if window.stack.currentWidget() is not panel or page.kind != kind:
                raise AssertionError("Mauvais module Qt C15 : " + name)
            if page.table.editTriggers() != QAbstractItemView.EditTrigger.NoEditTriggers:
                raise AssertionError("Édition autorisée dans C15 : " + name)
            actual = {row.id for row in page.model.rows}
            if ids is not None and actual != set(ids):
                raise AssertionError(
                    f"Filtre C15 {name} : {actual} != {set(ids)}"
                )
        else:
            actual = []
        image = window.grab()
        dest = root / f"{profile}-{name}.png"
        if image.isNull() or not image.save(str(dest), "PNG") or dest.stat().st_size < 3000:
            raise AssertionError("Capture Qt C15 absente : " + name)
        trace.append({
            "stage": name, "module": module, "kind": kind,
            "visible_ids": sorted(actual), "return_depth": len(window._context_history),
            "pixels": [image.width(), image.height()],
        })

    capture("accueil")
    window.navigate("renewals")
    capture("echeances-global", "renewals", "membership_expiries", {1001, 1002, 1003})

    window._family_requested(100)
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "fiche famille fictive")
    window.details_page.catalog_buttons["renewals"].click()
    capture("echeances-famille", "renewals", "membership_expiries", {1001, 1003})
    hub = window.catalog_pages["renewals"]
    hub.tabs.setCurrentWidget(hub.pages["membership_units"])
    capture("unites-cotisation", "renewals", "membership_units", {1, 2})
    window.return_to_context()
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "retour famille")

    window.details_page.catalog_buttons["certificates"].click()
    capture("attestations-famille", "certificates", "certificates", {7001, 7003})
    window.navigate("home")
    window.navigate("certificates")
    capture("attestations-global", "certificates", "certificates", {7001, 7002, 7003})

    window.navigate("activity_settings")
    hub = window.catalog_pages["activity_settings"]
    hub.current_page.activity_spin.setValue(1)
    capture("activites-unites", "activity_settings", "activity_units", {11, 13})
    hub.tabs.setCurrentWidget(hub.pages["activity_groups"])
    hub.current_page.activity_spin.setValue(1)
    capture("activites-groupes", "activity_settings", "activity_groups", {21, 23})
    hub.tabs.setCurrentWidget(hub.pages["activity_tariff_categories"])
    hub.current_page.activity_spin.setValue(1)
    capture("activites-tarifs", "activity_settings", "activity_tariff_categories", {1, 3})
    page = hub.current_page
    page.table.selectRow(0)
    page.activity_button.click()
    _wait(app, lambda: window.stack.currentWidget() is window.inscriptions_page,
          "inscriptions reliées")
    if (
        window.inscriptions_page._filters["activity_id"] != 1
        or {row.id for row in window.inscriptions_page.model.rows} != {501, 503}
    ):
        raise AssertionError("Lien d'inscription C15 non exact")
    capture("liens-inscriptions")
    window.return_to_context()
    if window.stack.currentWidget() is not hub:
        raise AssertionError("Retour depuis inscriptions incorrect")

    window.navigate("headcounts")
    hub = window.catalog_pages["headcounts"]
    capture("effectifs-inscriptions", "headcounts", "enrollment_counts", {1, 2})
    rows = {row.id: row for row in hub.current_page.model.rows}
    if rows[2].value("enrollments") != 3 or rows[2].value("status_ok") != 2:
        raise AssertionError("Comptage inscriptions brut incorrect")
    hub.tabs.setCurrentWidget(hub.pages["consumption_counts"])
    capture("effectifs-consommations", "headcounts", "consumption_counts", {1, 2})
    if sum(row.value("consumptions") for row in hub.current_page.model.rows) != 112:
        raise AssertionError("Comptage brut de consommations incorrect")

    window.navigate("memberships")
    capture("cotisations-c14", "memberships", "fees", {1001, 1002, 1003})
    window.navigate("billing")
    if {row.id for row in window.finance_pages["billing"].current_page.model.rows} != {
        501, 502, 503, 990,
    }:
        raise AssertionError("Régression de Facturation C13")
    capture("factures-c13")
    window.navigate("home")
    capture("retour-accueil")
    if fixture.dump() != before:
        raise AssertionError("Source fictive altérée par consultation C15")

    trace_path.write_text(
        json.dumps({
            "lot": "C15",
            "source": "C15_SYNTHETIC_TEMPORARY_ONLY",
            "shell": "NoethysQtWindow",
            "profile": profile,
            "scale": os.environ.get("QT_SCALE_FACTOR", "system"),
            "frames": trace,
            "source_db_unchanged": True,
            "sql_business_writes_enabled": False,
            "activity_editor_enabled": False,
            "production_qualification": False,
            "manual_windows_qa_pending": True,
            "counting_scope": "stored rows; NOT official attendance or CAF report",
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if len(trace) != len(sequence):
        raise AssertionError("Étapes C15 manquantes")
    print(
        f"C15_MODULES_PASS profile={profile} frames={len(trace)} "
        "eight_domains=true four_modules=true source_fictive=true "
        "sqlite_unchanged=true"
    )


def main():
    parser = argparse.ArgumentParser(description="C15 : 4 grands modules Qt fictifs")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--theme", choices=("light", "dark", "system"), default="light")
    parser.add_argument("--profile", choices=("100", "125", "150"), default="100")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    app.setOrganizationName("Noethys-C15-Fictif")
    app.setApplicationName("Noethys Qt C15 démonstration")
    with C15FictiveModulesDatabase() as fixture, tempfile.TemporaryDirectory(
        prefix="noethys-c15-settings-"
    ) as directory:
        settings = QSettings(str(Path(directory) / "c15.ini"), QSettings.Format.IniFormat)
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            window = NoethysQtWindow(
                PeopleSearchRepository(fixture.repository.editor_repository),
                SqliteActivityRepository(fixture.path),
                editor_sqlite_path=fixture.path,
                source_label="C15 — BASE FICTIVE UNIQUEMENT — CONSULTATION",
                requested_theme=args.theme,
                read_only_demo=True,
                background_queries=not args.smoke,
                catalog_enabled=True, c15_enabled=True,
            )
        window.setWindowTitle("Noethys Qt C15 — modules inventés, sans écriture")
        try:
            if args.smoke:
                smoke(app, window, fixture, f"{args.theme}-{args.profile}")
                return 0
            window.show()
            print("C15 : données inventées ; aucune opération métier autorisée")
            return app.exec()
        finally:
            window.close()
            if not QThreadPool.globalInstance().waitForDone(10000):
                raise RuntimeError("Un worker de consultation C15 reste actif")
            app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
