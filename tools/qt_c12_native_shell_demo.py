"""C12 : lancer la VRAIE coque principale Qt sur des données fictives.

Interactive : fenêtre native, recherche, fiches, inscriptions et
consommations; éditeur d'activités désactivé. Base C8 créée en
TemporaryDirectory puis détruite. Aucun profil Noethys utilisé.

--smoke : capture le parcours complet dans artifacts/qt-c12.
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

# Un éventuel facteur de mise à l'échelle doit être lu AVANT PySide6.
_preview = argparse.ArgumentParser(add_help=False)
_preview.add_argument("--scale", choices=("1", "1.25", "1.5"))
_preview_args, _ = _preview.parse_known_args()
if _preview_args.scale:
    os.environ["QT_SCALE_FACTOR"] = _preview_args.scale

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, QThreadPool, Qt
from PySide6.QtWidgets import QApplication

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c8_fixture import C8FictiveDatabase, EXPECTED_ROWS


def await_qt(app, check, name, timeout=8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if check():
            return
        from PySide6.QtTest import QTest
        QTest.qWait(20)
    raise RuntimeError("C12 : étape Qt sans résultat : " + name)


def capture_scenario(app, window, fictive, label):
    """Navigation par clic sur des clés réelles de la fixture inventée."""
    root = (ROOT / "artifacts" / "qt-c12").resolve()
    root.mkdir(parents=True, exist_ok=True)
    labels = (
        "accueil", "recherche", "fiche-famille", "inscriptions-famille",
        "consommations-inscription", "retour-inscriptions", "fiche-individu",
        "consommations-individu", "vue-globale",
    )
    output_files = [root / (label + "-" + stage + ".png") for stage in labels]
    report = root / (label + "-trace.json")
    for path in [*output_files, report]:
        if path.parent.resolve() != root or path.is_symlink():
            raise RuntimeError("Chemin de sortie non autorisé")
    if not window.read_only_demo:
        raise AssertionError("La coque de démonstration doit être verrouillée")
    initial = fictive.dump()
    result = []
    window.resize(1330, 830)
    window.show()
    app.processEvents()

    def shot(stage, *, expected_widget, expected_rows=None):
        app.processEvents()
        if window.stack.currentWidget() is not expected_widget:
            raise AssertionError("La page active ne correspond pas à " + stage)
        if window._activities_window is not None:
            raise AssertionError("Éditeur d'activité interdit pendant la recette")
        if window.activities_action.isEnabled():
            raise AssertionError("Action d'édition activité non neutralisée")
        if expected_rows is not None:
            if expected_widget is window.inscriptions_page:
                count = expected_widget.model.rowCount()
            elif expected_widget is window.consumptions_page:
                count = expected_widget.list_page.model.rowCount()
            else:
                count = expected_widget.model.rowCount()
            if count != expected_rows:
                raise AssertionError(
                    f"{stage}: {count} lignes au lieu de {expected_rows}"
                )
        image = window.grab()
        if image.isNull():
            raise RuntimeError("Image Qt nulle")
        path = root / (label + "-" + stage + ".png")
        if not image.save(str(path), "PNG") or path.stat().st_size < 3000:
            raise RuntimeError("Capture Qt C12 invalide")
        result.append({
            "stage": stage,
            "pixels": [image.width(), image.height()],
            "view": window.stack.currentWidget().__class__.__name__,
            "return_depth": len(window._context_history),
            "individual_id": window.consumptions_page._record_individual_id,
            "inscription_id": window.consumptions_page._record_inscription_id,
        })

    shot("accueil", expected_widget=window.home_page)
    window.navigate("people")
    window.people_page.search_edit.setText("Exemple")
    window.people_page.search_now()
    await_qt(
        app, lambda: window.people_page.model.rowCount() == 2,
        "recherche des individus fictifs",
    )
    shot("recherche", expected_widget=window.people_page, expected_rows=2)

    row = next(i for i, person in enumerate(window.people_page.model.rows)
               if person.individual_id == 10)
    window.people_page.table.selectRow(row)
    window.people_page.open_family_button.click()
    await_qt(
        app, lambda: window.details_page.loaded_kind == "family"
        and window.details_page.current_id == 100,
        "fiche famille #100",
    )
    shot("fiche-famille", expected_widget=window.details_page)
    window.details_page.family_inscriptions_button.click()
    await_qt(
        app, lambda: window.inscriptions_page.model.rowCount() == 2
        and window.inscriptions_page._filters["family_id"] == 100,
        "inscriptions de la famille",
    )
    shot("inscriptions-famille", expected_widget=window.inscriptions_page,
         expected_rows=2)
    number = next(i for i, item in enumerate(window.inscriptions_page.model.rows)
                  if item.id == 503)
    window.inscriptions_page.table.selectRow(number)
    window.inscriptions_page.consumptions_button.click()
    await_qt(
        app, lambda: window.consumptions_page.list_page.model.rowCount() == 28
        and window.consumptions_page._record_inscription_id == 503,
        "consommations inscription #503",
    )
    if window.consumptions_page._record_individual_id != 12:
        raise AssertionError("L'ID individu résolu n'est pas #12")
    shot("consommations-inscription",
         expected_widget=window.consumptions_page, expected_rows=28)

    window.return_to_context()
    if window.inscriptions_page.selected_row().id != 503:
        raise AssertionError("Sélection inscription perdue au retour")
    shot("retour-inscriptions", expected_widget=window.inscriptions_page,
         expected_rows=2)
    window.return_to_context()
    await_qt(
        app, lambda: window.details_page.loaded_kind == "family"
        and window.details_page.current_id == 100,
        "retour fiche famille",
    )

    members = window.details_page.members_table
    index = next(i for i in range(members.rowCount())
                 if members.item(i, 0).text() == "12")
    window.details_page._open_individual_row(index, 0)
    await_qt(
        app, lambda: window.details_page.loaded_kind == "individual"
        and window.details_page.current_id == 12,
        "fiche de l'individu #12",
    )
    shot("fiche-individu", expected_widget=window.details_page)
    window.details_page.individual_consumptions_button.click()
    await_qt(
        app, lambda: window.consumptions_page._record_individual_id == 12
        and window.consumptions_page._record_inscription_id is None
        and window.consumptions_page.list_page.model.rowCount() == 28,
        "consommations de l'individu",
    )
    shot("consommations-individu",
         expected_widget=window.consumptions_page, expected_rows=28)

    window.navigate("home")
    window.navigate("inscriptions")
    if window.inscriptions_page.model.rowCount() != 4:
        raise AssertionError("Liste générale des inscriptions incomplète")
    window.navigate("consumptions")
    await_qt(
        app, lambda: window.consumptions_page.list_page.model.rowCount()
        == EXPECTED_ROWS and
        window.consumptions_page._record_individual_id is None,
        "consommations globales",
    )
    shot("vue-globale", expected_widget=window.consumptions_page,
         expected_rows=EXPECTED_ROWS)

    if fictive.dump() != initial:
        raise AssertionError("Une écriture a modifié la base de recette C12")
    if len(result) != len(labels):
        raise AssertionError("Une capture attendue manque")
    report.write_text(json.dumps({
        "lot": "C12", "source": "synthetic_temporary_sqlite_only",
        "gui": "real_NoethysQtWindow",
        "theme": label.split("-")[0],
        "scale": os.environ.get("QT_SCALE_FACTOR", "system"),
        "stages": result, "database_unchanged": True,
        "write_mode": "disabled_for_demo",
        "configured_database_loaded": False,
        "manual_windows_visual_qa_pending": True,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"C12_NATIVE_PASS profile={label} captures={len(result)} "
        "exact_link=12/503 back_stack=PASS sqlite_unchanged=true"
    )


def main():
    parser = argparse.ArgumentParser(description="Noethys Qt — coque native C12 FICTIVE")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--theme", choices=("system", "light", "dark"), default="light")
    parser.add_argument("--profile", choices=("100", "125", "150"), default="100")
    parser.add_argument("--scale", choices=("1", "1.25", "1.5"))
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    app.setApplicationName("Noethys Qt C12 - FICTIF")
    with C8FictiveDatabase() as fictive, tempfile.TemporaryDirectory(
        prefix="noethys-c12-settings-isole-"
    ) as settings_dir:
        settings = QSettings(
            str(Path(settings_dir) / "window.ini"), QSettings.Format.IniFormat
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            window = NoethysQtWindow(
                PeopleSearchRepository(fictive.repository.editor_repository),
                SqliteActivityRepository(fictive.path),
                editor_sqlite_path=fictive.path,
                source_label="DÉMONSTRATION — données 100 % fictives / consultation",
                requested_theme=args.theme,
                background_queries=False if args.smoke else True,
                read_only_demo=True,
            )
        window.setWindowTitle(
            "Noethys Qt — démonstration C12 — AUCUNE donnée réelle"
        )
        try:
            if args.smoke:
                capture_scenario(app, window, fictive,
                                 f"{args.theme}-{args.profile}")
                return 0
            window.show()
            print(
                "C12 DEMONSTRATION FICTIVE : aucune configuration Noethys, "
                "aucun traitement financier. Fermer la fenêtre pour arrêter."
            )
            return app.exec()
        finally:
            window.close()
            if not QThreadPool.globalInstance().waitForDone(10000):
                raise RuntimeError("Requête Qt encore en cours lors de la fermeture")
            app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
