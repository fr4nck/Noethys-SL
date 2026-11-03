"""C19 — démonstration native Qt, uniquement sur une base fictive jetable.

Aucune configuration, sauvegarde, donnée familiale ou compte bancaire réel.
Le mode sensible C19 n'est activé qu'après vérification du marqueur SQLite.
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
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c19_fixture import C19FictiveRegistryDatabase


def smoke(app, window, fixture, profile):
    root = (ROOT / "artifacts" / "qt-c19").resolve()
    root.mkdir(parents=True, exist_ok=True)
    if root.parent != (ROOT / "artifacts").resolve():
        raise RuntimeError("C19 : export hors artifacts")
    stages = (
        "accueil", "exercices", "exercices-2026",
        "analytiques", "categories-compta", "plan-comptable",
        "budgets", "budget-id-101", "budget-id-102",
        "budget-exercice-2027", "modes-reglements",
        "comptes-intitules", "banques-etablissements",
        "regimes", "caisses", "secteurs",
        "ecoles-c18", "suivi-c17", "etats-c16",
        "factures-c13", "retour-accueil",
    )
    paths = [
        root / f"{profile}-{name}.png" for name in stages
    ] + [root / f"{profile}-trace.json"]
    for target in paths:
        if target.parent.resolve() != root or target.is_symlink():
            raise RuntimeError("C19 : export symlink ou hors dossier")
    before = fixture.dump()
    if (
        not window.read_only_demo
        or not window.c19_enabled
        or not window.c19_sensitive_enabled
        or not window.c18_sensitive_enabled
        or window.badge_logs_enabled
        or window.navigation.count() != 32
        or window.activities_action.isEnabled()
    ):
        raise AssertionError("C19 exige la coque entièrement fictive")
    window.resize(1550, 960)
    window.show()
    app.processEvents()
    trace = []

    def snap(name, module=None, kind=None, expected=None, total=None):
        app.processEvents()
        ids = ()
        if module is not None:
            hub = (
                window.finance_pages[module] if module in window.finance_pages
                else window.catalog_pages[module]
            )
            page = hub.current_page
            if window.stack.currentWidget() is not hub or page.kind != kind:
                raise AssertionError("C19 mauvaise page : " + name)
            if page.table.editTriggers() != QAbstractItemView.EditTrigger.NoEditTriggers:
                raise AssertionError("C19 écriture Qt permise : " + name)
            ids = tuple(sorted(row.id for row in page.model.rows))
            if expected is not None and set(ids) != set(expected):
                raise AssertionError(
                    f"C19 mauvaises lignes {name}: {ids} != {sorted(expected)}"
                )
            if kind == "bank_accounts_metadata":
                for row in page.model.rows:
                    if any("DEMO_SECRET_" in str(v) for v in row.values):
                        raise AssertionError("C19 fuite de compte bancaire test")
        if total is not None:
            report = window.report_page
            if (
                window.stack.currentWidget() is not report
                or report.last_result is None
                or report.last_result.total != total
            ):
                raise AssertionError("C19 régression des états du C17")
        img = window.grab()
        dest = root / f"{profile}-{name}.png"
        if img.isNull() or not img.save(str(dest), "PNG") or dest.stat().st_size < 3000:
            raise AssertionError("C19 capture absente : " + name)
        trace.append({
            "stage": name, "module": module, "kind": kind,
            "ids": list(ids), "state_total": total,
            "pixels": [img.width(), img.height()],
        })

    snap("accueil")

    window.navigate("accounting_settings")
    hub = window.catalog_pages["accounting_settings"]
    snap("exercices", "accounting_settings", "accounting_periods", {11, 12, 13})
    hub.current_page.year_spin.setValue(2026)
    snap("exercices-2026", "accounting_settings", "accounting_periods", {11})
    hub.tabs.setCurrentWidget(hub.pages["analytic_sections"])
    snap("analytiques", "accounting_settings", "analytic_sections", {21, 22, 23})
    hub.tabs.setCurrentWidget(hub.pages["accounting_categories"])
    snap("categories-compta", "accounting_settings", "accounting_categories", {41, 42, 43})
    hub.tabs.setCurrentWidget(hub.pages["ledger_accounts"])
    snap("plan-comptable", "accounting_settings", "ledger_accounts", {31, 32, 33})

    window.navigate("budget_settings")
    hub = window.catalog_pages["budget_settings"]
    snap("budgets", "budget_settings", "budget_definitions", {101, 102, 103})
    source = hub.pages["budget_definitions"]
    index = next(i for i, row in enumerate(source.model.rows) if row.id == 101)
    source.table.selectRow(index)
    source.budget_button.click()
    if hub.current_page.kind != "budget_categories":
        raise AssertionError("C19 lien vers catégories budgétaires indisponible")
    snap("budget-id-101", "budget_settings", "budget_categories", {201, 202})
    line = hub.current_page
    line.budget_spin.setValue(102)
    snap("budget-id-102", "budget_settings", "budget_categories", {203})
    hub.tabs.setCurrentWidget(source)
    source.year_spin.setValue(2027)
    snap("budget-exercice-2027", "budget_settings", "budget_definitions", {102})

    window.navigate("payment_settings")
    hub = window.catalog_pages["payment_settings"]
    snap("modes-reglements", "payment_settings", "payment_modes_settings", {1, 2})
    hub.tabs.setCurrentWidget(hub.pages["bank_accounts_metadata"])
    snap("comptes-intitules", "payment_settings", "bank_accounts_metadata", {1, 2})
    hub.tabs.setCurrentWidget(hub.pages["banks_directory"])
    snap("banques-etablissements", "payment_settings", "banks_directory", {301, 302, 303})

    window.navigate("organisation_settings")
    hub = window.catalog_pages["organisation_settings"]
    snap("regimes", "organisation_settings", "social_regimes", {401, 402})
    hub.tabs.setCurrentWidget(hub.pages["allowance_funds"])
    snap("caisses", "organisation_settings", "allowance_funds", {501, 502, 503})
    hub.tabs.setCurrentWidget(hub.pages["geographic_sectors"])
    snap("secteurs", "organisation_settings", "geographic_sectors", {601, 602, 603})

    window.navigate("school_registry")
    snap("ecoles-c18", "school_registry", "schools", {201, 202, 203})
    window.navigate("activity_overview")
    snap("suivi-c17", "activity_overview", "activity_overview", {1, 2})
    window.navigate("consumption_reports")
    window.report_page.year_spin.setValue(2026)
    snap("etats-c16", total=112)
    window.navigate("billing")
    snap("factures-c13", "billing", "invoices", {501, 502, 503, 990})
    window.navigate("home")
    snap("retour-accueil")

    if fixture.dump() != before:
        raise AssertionError("C19 : la base fictive a été modifiée en lecture")
    if len(trace) != len(stages):
        raise AssertionError("C19 : parcours incomplet")
    (root / f"{profile}-trace.json").write_text(
        json.dumps({
            "lot": "C19",
            "source": "C8_TO_C19_100_PERCENT_SYNTHETIC_TEMPORARY",
            "profile": profile,
            "screenshots": trace,
            "sqlite_unchanged": True,
            "private_bank_details_exposed": False,
            "account_balance_calculated": False,
            "budget_formula_executed": False,
            "production_enabled_financial_references": False,
            "qualified_for_production": False,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"C19_REGISTRIES_PASS profile={profile} frames={len(stages)} "
        "four_modules=true twelve_domains=true private_bank_fields_hidden=true "
        "budget_link_exact=true sqlite_unchanged=true synthetic_only=true"
    )


def main():
    parser = argparse.ArgumentParser(description="Noethys Qt C19 sur base 100% fictive")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--theme", choices=("light", "dark", "system"), default="light")
    parser.add_argument("--profile", choices=("100", "125", "150"), default="100")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    app.setOrganizationName("Noethys-C19-Demo-Fixture")
    app.setApplicationName("Noethys Qt C19 fictif")
    with C19FictiveRegistryDatabase() as fixture, tempfile.TemporaryDirectory(
        prefix="noethys-c19-settings-"
    ) as directory:
        settings = QSettings(
            str(Path(directory) / "c19.ini"), QSettings.Format.IniFormat,
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            window = NoethysQtWindow(
                PeopleSearchRepository(fixture.repository.editor_repository),
                SqliteActivityRepository(fixture.path),
                editor_sqlite_path=fixture.path,
                source_label="C19 — base entièrement fictive",
                requested_theme=args.theme,
                background_queries=not args.smoke,
                read_only_demo=True,
                finance_enabled=True, catalog_enabled=True,
                c15_enabled=True, c16_enabled=True, c17_enabled=True,
                c18_enabled=True, c18_sensitive_enabled=True,
                c19_enabled=True, c19_sensitive_enabled=True,
                badge_logs_enabled=False,
            )
        window.setWindowTitle("Noethys Qt C19 — données inventées, aucune écriture")
        try:
            if args.smoke:
                smoke(app, window, fixture, f"{args.theme}-{args.profile}")
                return 0
            window.show()
            print("C19 : uniquement données inventées ; aucune écriture.")
            return app.exec()
        finally:
            window.close()
            if not QThreadPool.globalInstance().waitForDone(10000):
                raise RuntimeError("C19 : worker SQL fictif actif")
            app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
