"""C18 : parcours de la coque Qt sur données inventées uniquement."""
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
from tools.qt_c18_fixture import C18FictiveRegistryDatabase


def _wait(app, predicate, stage, seconds=9):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(20)
    raise AssertionError("C18 délai de fiche : " + stage)


def smoke(app, window, fixture, profile):
    root = (ROOT / "artifacts" / "qt-c18").resolve()
    root.mkdir(parents=True, exist_ok=True)
    stages = (
        "accueil", "ecoles", "classes", "niveaux",
        "parcours-fictifs", "fiche-individu-fictif",
        "parcours-individu-filtre", "retour-fiche-individu",
        "produits", "categories-produits", "types-pieces",
        "pieces-fictives", "pieces-famille", "fiche-famille-fictive",
        "retour-pieces", "suivi-activites-c17",
        "etats-consommations-c16", "retour-accueil",
    )
    paths = [root / f"{profile}-{name}.png" for name in stages]
    paths.append(root / f"{profile}-trace.json")
    if any(p.parent.resolve() != root or p.is_symlink() for p in paths):
        raise RuntimeError("Export C18 hors répertoire dédié")
    before = fixture.dump()
    if (
        not window.read_only_demo or not window.c18_enabled
        or not window.c18_sensitive_enabled or window.badge_logs_enabled
        or window.navigation.count() != 28
        or window.activities_action.isEnabled()
    ):
        raise RuntimeError("La démonstration C18 n'est pas isolée")
    window.resize(1536, 980)
    window.show()
    app.processEvents()
    history = []

    def snap(stage, *, module=None, domain=None, ids=None, kind=None, ident=None):
        app.processEvents()
        found = set()
        if module is not None:
            hub = window.catalog_pages[module]
            if window.stack.currentWidget() is not hub:
                raise AssertionError("Mauvais module C18 " + stage)
            page = hub.current_page
            if page.kind != domain:
                raise AssertionError("Mauvais onglet C18 " + stage)
            if page.table.editTriggers() != QAbstractItemView.EditTrigger.NoEditTriggers:
                raise AssertionError("Édition C18 non autorisée")
            found = {r.id for r in page.model.rows}
            if ids is not None and found != set(ids):
                raise AssertionError(f"Résultat C18 {stage} : {found} != {set(ids)}")
        if kind is not None and (
            window.details_page.loaded_kind != kind
            or window.details_page.current_id != ident
        ):
            raise AssertionError("Fiche C18 exacte absente " + stage)
        pixel = window.grab()
        dest = root / f"{profile}-{stage}.png"
        if pixel.isNull() or not pixel.save(str(dest), "PNG") or dest.stat().st_size < 3000:
            raise AssertionError("Capture C18 invalide " + stage)
        history.append({
            "stage": stage,
            "module": module,
            "domain": domain,
            "visible_ids": sorted(found),
            "detail_kind": kind,
            "detail_id": ident,
            "size": [pixel.width(), pixel.height()],
        })

    snap("accueil")
    window.navigate("school_registry")
    hub = window.catalog_pages["school_registry"]
    snap("ecoles", module="school_registry", domain="schools", ids={201, 202, 203})
    hub.tabs.setCurrentWidget(hub.pages["school_classes"])
    snap("classes", module="school_registry", domain="school_classes", ids={401, 402, 403})
    hub.tabs.setCurrentWidget(hub.pages["school_levels"])
    snap("niveaux", module="school_registry", domain="school_levels", ids={301, 302, 303})

    window.navigate("school_history")
    snap("parcours-fictifs", module="school_history", domain="school_history",
         ids={5011, 5012, 5013, 5014})
    page = window.catalog_pages["school_history"].current_page
    i = next(i for i, r in enumerate(page.model.rows) if r.id == 5011)
    page.table.selectRow(i)
    page.individual_button.click()
    _wait(app, lambda: (
        window.details_page.loaded_kind == "individual"
        and window.details_page.current_id == 10
    ), "individu 10")
    snap("fiche-individu-fictif", kind="individual", ident=10)
    window.details_page.individual_catalog_buttons["school_history"].click()
    snap("parcours-individu-filtre", module="school_history", domain="school_history",
         ids={5011})
    window.return_to_context()
    _wait(app, lambda: (
        window.details_page.loaded_kind == "individual"
        and window.details_page.current_id == 10
    ), "retour individu 10")
    snap("retour-fiche-individu", kind="individual", ident=10)

    window.navigate("product_registry")
    hub = window.catalog_pages["product_registry"]
    snap("produits", module="product_registry", domain="product_inventory",
         ids={1, 2, 3})
    hub.tabs.setCurrentWidget(hub.pages["product_categories"])
    snap("categories-produits", module="product_registry",
         domain="product_categories", ids={71, 72, 73})
    window.navigate("document_type_registry")
    snap("types-pieces", module="document_type_registry",
         domain="document_types", ids={801, 802, 803})

    window.navigate("document_records")
    page = window.catalog_pages["document_records"].current_page
    snap("pieces-fictives", module="document_records",
         domain="documents_metadata", ids={9011, 9012, 9013, 9014})
    window.catalog_pages["document_records"].set_family_context(100)
    snap("pieces-famille", module="document_records",
         domain="documents_metadata", ids={9012, 9014})
    i = next(i for i, row in enumerate(page.model.rows) if row.id == 9014)
    page.table.selectRow(i)
    page.family_button.click()
    _wait(app, lambda: (
        window.details_page.loaded_kind == "family"
        and window.details_page.current_id == 100
    ), "famille 100")
    snap("fiche-famille-fictive", kind="family", ident=100)
    window.return_to_context()
    snap("retour-pieces", module="document_records",
         domain="documents_metadata", ids={9012, 9014})

    window.navigate("activity_overview")
    snap("suivi-activites-c17", module="activity_overview",
         domain="activity_overview", ids={1, 2})
    window.navigate("consumption_reports")
    window.report_page.year_spin.setValue(2026)
    if window.report_page.last_result.total != 112:
        raise AssertionError("Régression du moteur commun C17")
    snap("etats-consommations-c16")
    window.navigate("home")
    snap("retour-accueil")

    if fixture.dump() != before:
        raise AssertionError("C18 : base temporaire modifiée pendant la consultation")
    if len(history) != len(stages):
        raise AssertionError("Parcours Qt C18 incomplet")
    (root / f"{profile}-trace.json").write_text(
        json.dumps({
            "lot": "C18",
            "source": "C8_TO_C18_TEMPORARY_FICTIVE_ONLY",
            "profile": profile,
            "images": history,
            "sqlite_unchanged": True,
            "personal_history_enabled_on_production": False,
            "pieces_enabled_on_production": False,
            "not_qualified_for_production": True,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"C18_REGISTRIES_PASS profile={profile} frames={len(stages)} "
        "five_modules=true eight_domains=true "
        "individual_exact=true family_exact=true "
        "sensitive_fixture_only=true sqlite_unchanged=true"
    )


def main():
    parser = argparse.ArgumentParser(description="C18 Qt : données fictives")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--theme", choices=("light", "dark", "system"), default="light")
    parser.add_argument("--profile", choices=("100", "125", "150"), default="100")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    app.setOrganizationName("Noethys-C18-Exclusivement-Fictif")
    app.setApplicationName("Noethys Qt C18")
    with C18FictiveRegistryDatabase() as fixture, tempfile.TemporaryDirectory(
        prefix="noethys-c18-settings-"
    ) as directory:
        settings = QSettings(str(Path(directory) / "c18.ini"), QSettings.Format.IniFormat)
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            window = NoethysQtWindow(
                PeopleSearchRepository(fixture.repository.editor_repository),
                SqliteActivityRepository(fixture.path),
                editor_sqlite_path=fixture.path,
                source_label="C18 : BASE FICTIVE — AUCUNE ÉCRITURE",
                requested_theme=args.theme,
                read_only_demo=True,
                background_queries=not args.smoke,
                catalog_enabled=True,
                c15_enabled=True, c16_enabled=True, c17_enabled=True,
                c18_enabled=True, c18_sensitive_enabled=True,
                badge_logs_enabled=False,
            )
        window.setWindowTitle("Noethys Qt C18 — démonstration entièrement fictive")
        try:
            if args.smoke:
                smoke(app, window, fixture, f"{args.theme}-{args.profile}")
                return 0
            window.show()
            return app.exec()
        finally:
            window.close()
            if not QThreadPool.globalInstance().waitForDone(10000):
                raise RuntimeError("Worker C18 actif après fermeture")
            app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
