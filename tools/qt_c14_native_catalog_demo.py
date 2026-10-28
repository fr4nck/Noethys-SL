"""C14 — démonstration de la coque native et de 9 listes sur SQLite inventé.

Aucune configuration Noethys, aucun réseau et aucune sauvegarde .nod.
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
from PySide6.QtWidgets import QApplication

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c14_catalog_fixture import C14FictiveCatalogDatabase


def _wait(app, predicate, what, seconds=9):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(20)
    raise AssertionError("C14 : étape non atteinte : " + what)


def _smoke(app, window, db, label):
    root = (ROOT / "artifacts" / "qt-c14").resolve()
    root.mkdir(parents=True, exist_ok=True)
    stage_names = (
        "accueil", "cotisations-globales", "cotisations-famille",
        "types-cotisations", "contrats-famille", "inscriptions-contrat",
        "quotients-famille", "types-quotients", "locations-famille",
        "demandes-locations", "commandes", "devis-famille",
        "factures-c13", "retour-global",
    )
    destinations = [root / f"{label}-{name}.png" for name in stage_names]
    trace_path = root / f"{label}-trace.json"
    for target in [*destinations, trace_path]:
        if target.parent.resolve() != root or target.is_symlink():
            raise RuntimeError("Chemin de capture interdit")

    before = db.dump()
    window.resize(1400, 850)
    window.show()
    app.processEvents()
    if not window.read_only_demo or window.activities_action.isEnabled():
        raise AssertionError("Éditeur non verrouillé en démonstration")
    if not window.catalog_enabled:
        raise AssertionError("Rubriques administratives absentes")

    timeline = []

    def frame(name, module=None, kind=None, expected=None):
        app.processEvents()
        active = window.stack.currentWidget()
        panel = window.catalog_pages.get(module) if module else None
        page = panel.current_page if panel else None
        if panel is not None:
            if active is not panel or page.kind != kind:
                raise AssertionError("Navigation C14 incohérente : " + name)
            if page.table.editTriggers() != page.table.EditTrigger.NoEditTriggers:
                raise AssertionError("Tableau éditable : " + name)
            found = {row.id for row in page.model.rows}
            if expected is not None and found != set(expected):
                raise AssertionError(f"{name} : {found} != {expected}")
        image = window.grab()
        if image.isNull():
            raise AssertionError("Image Qt vide : " + name)
        target = root / f"{label}-{name}.png"
        if not image.save(str(target), "PNG") or target.stat().st_size < 3000:
            raise AssertionError("Capture C14 invalide : " + name)
        timeline.append({
            "stage": name,
            "module": module,
            "kind": kind,
            "visible_ids": [row.id for row in page.model.rows] if page else [],
            "pixels": [image.width(), image.height()],
            "return_depth": len(window._context_history),
        })

    frame("accueil")
    window.navigate("memberships")
    frame("cotisations-globales", "memberships", "fees", {1001, 1002, 1003})

    window._family_requested(100)
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "famille fictive")
    window.details_page.catalog_buttons["memberships"].click()
    frame("cotisations-famille", "memberships", "fees", {1001, 1003})
    hub = window.catalog_pages["memberships"]
    hub.tabs.setCurrentWidget(hub.pages["fee_types"])
    frame("types-cotisations", "memberships", "fee_types", {1, 2})
    window.return_to_context()
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "retour famille")

    window.details_page.catalog_buttons["contracts"].click()
    frame("contrats-famille", "contracts", "contracts", {2001, 2003})
    page = window.catalog_pages["contracts"].current_page
    idx = next(i for i, row in enumerate(page.model.rows) if row.id == 2001)
    page.table.selectRow(idx)
    page.inscription_button.click()
    _wait(app, lambda: window.stack.currentWidget() is window.inscriptions_page,
          "inscriptions par clés")
    if (
        window.inscriptions_page._filters["family_id"] != 100
        or window.inscriptions_page._filters["individual_id"] != 10
        or {row.id for row in window.inscriptions_page.model.rows} != {501}
    ):
        raise AssertionError("Lien Contrat → Inscriptions non exact")
    frame("inscriptions-contrat")
    window.return_to_context()
    if window.stack.currentWidget() is not window.catalog_pages["contracts"]:
        raise AssertionError("Retour depuis inscriptions incorrect")
    window.return_to_context()
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "famille après contrats")

    window.details_page.catalog_buttons["quotients"].click()
    frame("quotients-famille", "quotients", "quotients", {3001, 3003})
    hub = window.catalog_pages["quotients"]
    hub.tabs.setCurrentWidget(hub.pages["quotient_types"])
    frame("types-quotients", "quotients", "quotient_types", {1, 2})
    window.return_to_context()
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "famille après quotients")

    window.details_page.catalog_buttons["rentals"].click()
    frame("locations-famille", "rentals", "rentals", {4001, 4003})
    hub = window.catalog_pages["rentals"]
    hub.tabs.setCurrentWidget(hub.pages["rental_requests"])
    frame("demandes-locations", "rentals", "rental_requests", {4101})
    window.return_to_context()
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "famille après locations")

    window.navigate("orders")
    frame("commandes", "orders", "orders", {5001, 5002})

    window._family_requested(100)
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "famille devis")
    window.details_page.catalog_buttons["quotes"].click()
    frame("devis-famille", "quotes", "quotes", {6001, 6003})
    window.navigate("billing")
    if {r.id for r in window.finance_pages["billing"].current_page.model.rows} != {
        501, 502, 503, 990
    }:
        raise AssertionError("C13 régressé dans la fixture C14")
    frame("factures-c13")
    window.navigate("memberships")
    frame("retour-global", "memberships", "fees", {1001, 1002, 1003})
    if db.dump() != before:
        raise AssertionError("Une consultation a modifié la base fictive")

    trace_path.write_text(
        json.dumps({
            "lot": "C14",
            "source": "C14_SYNTHETIC_TEMPORARY_ONLY",
            "shell": "NoethysQtWindow",
            "profile": label,
            "scale": os.environ.get("QT_SCALE_FACTOR", "system"),
            "frames": timeline,
            "source_db_unchanged": True,
            "sql_business_writes_enabled": False,
            "activity_editor_enabled": False,
            "production_qualification": False,
            "manual_windows_qa_pending": True,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"C14_CATALOG_PASS profile={label} frames={len(timeline)} "
        "nine_domains=true source_fictive=true sqlite_unchanged=true"
    )


def main():
    parser = argparse.ArgumentParser(description="C14 grands modules Qt fictifs")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--theme", choices=("light", "dark", "system"), default="light")
    parser.add_argument("--profile", choices=("100", "125", "150"), default="100")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    app.setOrganizationName("Noethys-C14-Synthetique")
    app.setApplicationName("Noethys Qt C14 démonstration")
    with C14FictiveCatalogDatabase() as db, tempfile.TemporaryDirectory(
        prefix="noethys-c14-settings-"
    ) as directory:
        settings = QSettings(str(Path(directory) / "c14.ini"), QSettings.Format.IniFormat)
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            window = NoethysQtWindow(
                PeopleSearchRepository(db.repository.editor_repository),
                SqliteActivityRepository(db.path),
                editor_sqlite_path=db.path,
                source_label="C14 : BASE TOTALEMENT FICTIVE — LECTURE SEULE",
                requested_theme=args.theme, read_only_demo=True,
                background_queries=not args.smoke,
                catalog_enabled=True,
            )
        window.setWindowTitle("Noethys Qt C14 — modules fictifs en consultation")
        try:
            if args.smoke:
                _smoke(app, window, db, f"{args.theme}-{args.profile}")
                return 0
            window.show()
            print("C14 : démonstration fictive, aucun enregistrement métier autorisé.")
            return app.exec()
        finally:
            window.close()
            if not QThreadPool.globalInstance().waitForDone(10000):
                raise RuntimeError("Un worker Qt de consultation reste actif")
            app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
