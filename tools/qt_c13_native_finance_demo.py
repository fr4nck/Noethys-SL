"""C13 : coque native Qt + six listes financières sur base totalement fictive.

N'utilise ni Config.json ni .nod ni réseau. En démonstration, l'éditeur
Activités est désactivé et les modules financiers n'écrivent jamais.
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

_prefetch = argparse.ArgumentParser(add_help=False)
_prefetch.add_argument("--scale", choices=("1", "1.25", "1.5"))
_options, _ = _prefetch.parse_known_args()
if _options.scale:
    os.environ["QT_SCALE_FACTOR"] = _options.scale

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c13_finance_fixture import C13FictiveFinanceDatabase


def _wait(app, predicate, label, seconds=9):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(20)
    raise AssertionError("C13 étape manquante : " + label)


def _smoke(app, window, db, label):
    root = (ROOT / "artifacts" / "qt-c13").resolve()
    root.mkdir(parents=True, exist_ok=True)
    stages = (
        "accueil", "factures-famille", "prestations-facture",
        "reglements-famille", "ventilation-reglement", "tresorerie",
        "depots", "reglements-depot", "factures-globales",
    )
    output = [root / f"{label}-{name}.png" for name in stages]
    trace = root / f"{label}-trace.json"
    for path in [*output, trace]:
        if path.parent.resolve() != root or path.is_symlink():
            raise RuntimeError("Destination de capture Qt interdite")

    original = db.dump()
    timeline = []
    window.resize(1390, 840)
    window.show()
    app.processEvents()
    if not window.read_only_demo or window.activities_action.isEnabled():
        raise AssertionError("Démonstration non protégée : éditeur actif")

    def frame(name, module=None, kind=None, expected=None):
        app.processEvents()
        active = window.stack.currentWidget()
        if module is not None:
            hub = window.finance_pages[module]
            if active is not hub or hub.current_page.kind != kind:
                raise AssertionError("Navigation financière incohérente à " + name)
            page = hub.current_page
            if page.table.editTriggers() != page.table.EditTrigger.NoEditTriggers:
                raise AssertionError("Écriture graphique rendue possible")
            if expected is not None:
                ids = {entry.id for entry in page.model.rows}
                if ids != set(expected):
                    raise AssertionError(f"{name}: mauvais IDs {ids} au lieu de {expected}")
        else:
            page = None
        image = window.grab()
        if image.isNull():
            raise RuntimeError("Pixmap Qt nulle")
        target = root / f"{label}-{name}.png"
        if not image.save(str(target), "PNG") or target.stat().st_size < 3200:
            raise RuntimeError("Capture Qt C13 invalide : " + name)
        timeline.append({
            "stage": name, "pixels": [image.width(), image.height()],
            "module": module, "kind": kind,
            "visible_ids": [r.id for r in page.model.rows] if page else [],
            "history_depth": len(window._context_history),
        })

    frame("accueil")
    window._family_requested(100)
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "famille fictive")
    window.details_page.family_invoices_button.click()
    frame("factures-famille", "billing", "invoices", {501, 503})
    invoices = window.finance_pages["billing"].pages["invoices"]
    idx = next(i for i, record in enumerate(invoices.model.rows)
               if record.id == 501)
    invoices.table.selectRow(idx)
    invoices.related_button.click()
    frame("prestations-facture", "billing", "services", {301, 305})
    window.return_to_context()
    _wait(app, lambda: window.details_page.loaded_kind == "family"
          and window.details_page.current_id == 100, "retour famille")
    window.details_page.family_payments_button.click()
    frame("reglements-famille", "payments", "payments", {401, 403})
    payments = window.finance_pages["payments"].pages["payments"]
    idx = next(i for i, record in enumerate(payments.model.rows)
               if record.id == 401)
    payments.table.selectRow(idx)
    payments.related_button.click()
    frame("ventilation-reglement", "payments", "allocations", {701, 702})

    window.navigate("home")
    window.navigate("accounting")
    frame("tresorerie", "accounting", "treasury", {801, 802, 803})
    accounting = window.finance_pages["accounting"]
    accounting.tabs.setCurrentWidget(accounting.pages["deposits"])
    frame("depots", "accounting", "deposits", {1, 2})
    deposits = accounting.pages["deposits"]
    index = next(i for i, record in enumerate(deposits.model.rows)
                 if record.id == 2)
    deposits.table.selectRow(index)
    deposits.related_button.click()
    frame("reglements-depot", "payments", "payments", {402, 404})
    if window.finance_pages["payments"].current_page._related_id != 2:
        raise AssertionError("Le filtre dépôt n'est pas exact")
    window.return_to_context()
    if window.stack.currentWidget() is not accounting:
        raise AssertionError("Le retour au module comptable a échoué")

    window.navigate("home")
    window.navigate("billing")
    frame("factures-globales", "billing", "invoices", {501, 502, 503, 990})
    if db.dump() != original:
        raise AssertionError("La démonstration a modifié sa base fictive")

    trace.write_text(json.dumps({
        "lot": "C13", "source": "C13_SYNTHETIC_TEMPORARY_ONLY",
        "shell": "NoethysQtWindow", "profile": label,
        "scale": os.environ.get("QT_SCALE_FACTOR", "system"),
        "frames": timeline,
        "source_db_unchanged": True,
        "finance_writes_enabled": False,
        "activity_editor_enabled": False,
        "manual_windows_qa_pending": True,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"C13_FINANCE_PASS profile={label} frames={len(timeline)} "
        "six_domains=true sources_fictives=true sqlite_unchanged=true"
    )


def main():
    parser = argparse.ArgumentParser(description="C13 gros modules Qt fictifs")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--theme", choices=("light", "dark", "system"), default="light")
    parser.add_argument("--profile", choices=("100", "125", "150"), default="100")
    parser.add_argument("--scale", choices=("1", "1.25", "1.5"))
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    app.setOrganizationName("Noethys-C13-Synthetique")
    app.setApplicationName("Noethys Qt C13 démonstration")
    with C13FictiveFinanceDatabase() as db, tempfile.TemporaryDirectory(
        prefix="noethys-c13-settings-"
    ) as settings_dir:
        settings = QSettings(
            str(Path(settings_dir) / "c13.ini"), QSettings.Format.IniFormat
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            window = NoethysQtWindow(
                PeopleSearchRepository(db.repository.editor_repository),
                SqliteActivityRepository(db.path),
                editor_sqlite_path=db.path,
                source_label="DONNÉES FICTIVES C13 — AUCUNE COMPTABILISATION",
                requested_theme=args.theme, read_only_demo=True,
                background_queries=False if args.smoke else True,
            )
        window.setWindowTitle("Noethys Qt C13 — modules FICTIFS / lecture seule")
        try:
            if args.smoke:
                _smoke(app, window, db, f"{args.theme}-{args.profile}")
                return 0
            window.show()
            print("C13 : données fictives seulement, aucun calcul financier ni saisie.")
            return app.exec()
        finally:
            window.close()
            if not QThreadPool.globalInstance().waitForDone(10000):
                raise RuntimeError("Un worker Qt de lecture est encore actif")
            app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
