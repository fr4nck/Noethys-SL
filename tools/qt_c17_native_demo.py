"""C17 smoke — suivi transversal Qt et moteur commun sur fictif exclusivement.

Aucun profil ou fichier Noethys réel. L'artefact ne contient que les
tables inventées C8-C16 et aucun journal nominatif rendu.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtWidgets import QApplication, QAbstractItemView

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.consumptions_core import ALL_STATES
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c16_fixture import C16FictivePlanningDatabase


def _smoke(app, window, fixture, profile):
    root = (ROOT / "artifacts" / "qt-c17").resolve()
    root.mkdir(parents=True, exist_ok=True)
    stages = (
        "accueil", "activites-stockees", "activite-1-selectionnee",
        "planning-activite-1", "retour-activite-1",
        "tarifs-activite-2", "retour-activite-2",
        "etats-activite-2", "etats-selection-vide",
        "retour-etats", "inscriptions-activite-1",
        "retour-inscriptions", "menu-planning-sans-filtre",
        "etats-globaux", "retour-accueil",
    )
    paths = [
        root / f"{profile}-{name}.png" for name in stages
    ] + [root / f"{profile}-trace.json"]
    if any(
        p.parent.resolve() != root or p.is_symlink()
        for p in paths
    ):
        raise RuntimeError("Export C17 hors périmètre fictif")
    before = fixture.dump()
    if not window.read_only_demo or not window.c17_enabled or window.badge_logs_enabled:
        raise RuntimeError("La demonstration C17 ne peut pas accéder au badgeage")
    if window.navigation.count() != 23:
        raise AssertionError("La coque Qt C17 doit comporter 23 rubriques")
    if "badge_journal" in window.catalog_pages:
        raise AssertionError("Journal sensible accessible dans la démonstration")
    if window.activities_action.isEnabled():
        raise AssertionError("Éditeur d'activités actif dans la démonstration")

    trace = []
    window.resize(1500, 960)
    window.show()
    app.processEvents()

    def capture(stage, *, module=None, selected=None, ids=None, states=None):
        app.processEvents()
        if module is not None:
            hub = window.catalog_pages[module]
            if window.stack.currentWidget() is not hub:
                raise AssertionError("Mauvais module C17 : " + stage)
            page = hub.current_page
            if page.table.editTriggers() != QAbstractItemView.EditTrigger.NoEditTriggers:
                raise AssertionError("Édition disponible en C17")
            found = {r.id for r in page.model.rows}
            if ids is not None and found != set(ids):
                raise AssertionError(f"{stage}: {found} != {set(ids)}")
            if selected is not None and (
                page.selected_row() is None
                or page.selected_row().id != selected
            ):
                raise AssertionError("L'activité sélectionnée a été perdue")
        else:
            found = set()
        if states is not None:
            report = window.report_page
            if window.stack.currentWidget() is not report:
                raise AssertionError("Le rapport d'états n'est pas actif")
            if report.last_result is None or report.last_result.total != states:
                raise AssertionError("Comptage d'états inattendu : " + stage)
        pix = window.grab()
        target = root / f"{profile}-{stage}.png"
        if pix.isNull() or not pix.save(str(target), "PNG") or target.stat().st_size < 3000:
            raise AssertionError("Capture C17 absente : " + stage)
        trace.append({
            "stage": stage,
            "module": module,
            "shown_ids": sorted(found),
            "selected_activity": selected,
            "status_total": states,
            "pixels": [pix.width(), pix.height()],
        })

    def select(ident):
        window.navigate("activity_overview")
        page = window.catalog_pages["activity_overview"].current_page
        i = next(i for i, r in enumerate(page.model.rows) if r.id == ident)
        page.table.selectRow(i)
        if page.selected_row().id != ident:
            raise AssertionError("Sélection exacte impossible")
        return page

    capture("accueil")
    window.navigate("activity_overview")
    capture("activites-stockees", module="activity_overview", ids={1, 2})
    page = select(1)
    capture(
        "activite-1-selectionnee", module="activity_overview",
        selected=1, ids={1, 2},
    )
    page.related_buttons["planning"].click()
    if window.catalog_pages["planning"].current_page.activity_spin.value() != 1:
        raise AssertionError("Le planning ne respecte pas l'ID d'activité")
    capture("planning-activite-1", module="planning", ids={601, 603})
    window.return_to_context()
    capture("retour-activite-1", module="activity_overview", selected=1, ids={1, 2})

    page = select(2)
    page.related_buttons["tariff_records"].click()
    if window.catalog_pages["tariff_records"].current_page.activity_spin.value() != 2:
        raise AssertionError("Les tarifs ne respectent pas l'ID d'activité")
    capture("tarifs-activite-2", module="tariff_records", ids={802})
    window.return_to_context()
    capture("retour-activite-2", module="activity_overview", selected=2, ids={1, 2})

    report = window.report_page
    report.year_spin.setValue(2027)
    select(2).related_buttons["consumption_reports"].click()
    if report.activity_spin.value() != 2:
        raise AssertionError("Les états ne respectent pas l'ID d'activité")
    capture("etats-activite-2", states=2)
    report.none_button.click()
    if report.selected_states:
        raise AssertionError("Aucun état doit être sélectionné")
    capture("etats-selection-vide", states=0)
    report.all_button.click()
    if report.selected_states != ALL_STATES:
        raise AssertionError("Les sept états ne sont pas rétablis")
    window.return_to_context()
    capture("retour-etats", module="activity_overview", selected=2, ids={1, 2})

    select(1).activity_button.click()
    if (
        window.inscriptions_page._filters["activity_id"] != 1
        or {r.id for r in window.inscriptions_page.model.rows} != {501, 503}
    ):
        raise AssertionError("Lien d'inscription erroné")
    capture("inscriptions-activite-1")
    window.return_to_context()
    capture("retour-inscriptions", module="activity_overview", selected=1, ids={1, 2})

    window.navigate("home")
    window.navigate("planning")
    if window.catalog_pages["planning"].current_page.activity_spin.value() != 0:
        raise AssertionError("Le filtre d'activité a fui vers le menu global")
    capture("menu-planning-sans-filtre", module="planning", ids={601, 602, 603})
    window.navigate("consumption_reports")
    if report.activity_spin.value() != 0:
        raise AssertionError("Le filtre d'état a fui vers le menu global")
    report.year_spin.setValue(2026)
    capture("etats-globaux", states=112)
    window.navigate("home")
    capture("retour-accueil")
    if fixture.dump() != before:
        raise AssertionError("La source inventée a été modifiée")
    if len(trace) != len(stages):
        raise AssertionError("La recette C17 est incomplète")
    (root / f"{profile}-trace.json").write_text(
        json.dumps({
            "milestone": "C17",
            "profile": profile,
            "source": "C16_TEMPORARY_100_PERCENT_FAKE",
            "contract": "stored-consumption-state-counts/1",
            "frames": trace,
            "sqlite_unchanged": True,
            "audit_badge_data_excluded": True,
            "business_writes": False,
            "production_qualified": False,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"C17_OVERVIEW_PASS profile={profile} frames={len(stages)} "
        "shared_motor=true cross_module_links=true "
        "badge_disabled=true sqlite_unchanged=true fake_only=true"
    )


def main():
    parser = argparse.ArgumentParser(description="C17 : données fictives exclusivement")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--theme", choices=("light", "dark", "system"), default="light")
    parser.add_argument("--profile", choices=("100", "125", "150"), default="100")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    with (
        C16FictivePlanningDatabase() as fixture,
        tempfile.TemporaryDirectory(prefix="noethys-c17-settings-") as settings_dir,
    ):
        settings = QSettings(
            str(Path(settings_dir) / "config.ini"), QSettings.Format.IniFormat
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            window = NoethysQtWindow(
                PeopleSearchRepository(fixture.repository.editor_repository),
                SqliteActivityRepository(fixture.path),
                editor_sqlite_path=fixture.path,
                requested_theme=args.theme,
                source_label="C17 : BASE FICTIVE UNIQUEMENT",
                read_only_demo=True,
                background_queries=not args.smoke,
                c15_enabled=True, c16_enabled=True, c17_enabled=True,
                badge_logs_enabled=False,
            )
        window.setWindowTitle("Noethys Qt C17 — Suivi d'activités fictives")
        try:
            if args.smoke:
                _smoke(app, window, fixture, f"{args.theme}-{args.profile}")
                return 0
            window.show()
            print("C17: données 100 % fictives, sans écriture métier")
            return app.exec()
        finally:
            window.close()
            if not QThreadPool.globalInstance().waitForDone(10000):
                raise RuntimeError("Worker C17 non terminé")
            app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
