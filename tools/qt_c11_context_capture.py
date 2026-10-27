"""C11 : recette graphique de navigation par identifiants sur SQLite FICTIVE.

Ne lit pas Config.json ; n'ouvre aucune base Noethys réelle. Cette
recette dynamique Windows prend des captures hors écran et vérifie
que les données sont inchangées, sans conclure à la parité métier.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from tools.qt_c8_fixture import C8FictiveDatabase, EXPECTED_ROWS
from tools.qt_c8_windows_demo import C8DemoWindow


def main():
    parser = argparse.ArgumentParser(description="Parcours C11 fictif")
    parser.add_argument("--theme", choices=("light", "dark"), required=True)
    parser.add_argument("--profile", choices=("100", "150"), required=True)
    args = parser.parse_args()

    root = (ROOT / "artifacts" / "qt-c11").resolve()
    root.mkdir(parents=True, exist_ok=True)
    prefix = args.theme + "-" + args.profile
    phases = ("fiche-individu", "consommations-individu",
              "consommations-inscription", "consommations-globales")
    files = [root / f"{prefix}-{name}.png" for name in phases]
    report = root / f"{prefix}-controle.json"
    for output in [*files, report]:
        if output.parent.resolve() != root or output.is_symlink():
            raise RuntimeError("Dossier de sortie non autorisé")

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    with C8FictiveDatabase() as fictive:
        original = fictive.dump()
        window = C8DemoWindow(
            fictive.repository, fictive_db=fictive,
            background=False, theme=args.theme,
        )
        timeline = []
        try:
            window.show()
            window.activate_demo()
            window.resize(1250, 820)
            window.tabs.setCurrentWidget(window.business_page)
            app.processEvents()
            business = window.business_page
            consumptions = window.page

            def frame(phase, expected_rows, expected_individual=None,
                      expected_inscription=None):
                app.processEvents()
                if not window.banner.isVisible():
                    raise AssertionError("La bannière fictive n'est pas visible")
                if consumptions.preparation_panel.last_preview is not None:
                    if consumptions.preparation_panel.last_preview.executable:
                        raise AssertionError("La saisie Qt est devenue possible")
                if phase != "fiche-individu":
                    if consumptions.list_page.model.rowCount() != expected_rows:
                        raise AssertionError("Mauvais nombre de lignes de consommations")
                    if consumptions._record_individual_id != expected_individual:
                        raise AssertionError("Filtre individu perdu")
                    if consumptions._record_inscription_id != expected_inscription:
                        raise AssertionError("Filtre inscription perdu")
                    if not consumptions.preparation_panel.warning.isVisible():
                        raise AssertionError("L'avertissement lecture seule a disparu")
                    if sum(x.count for x in consumptions._date_counts) != expected_rows:
                        raise AssertionError("Les agrégats mensuels ne correspondent pas")
                pixmap = window.grab()
                if pixmap.isNull():
                    raise RuntimeError("Capture Qt nulle")
                path = root / f"{prefix}-{phase}.png"
                if not pixmap.save(str(path), "PNG"):
                    raise RuntimeError("Échec de capture C11")
                if path.stat().st_size < 3000:
                    raise RuntimeError("PNG C11 trop petit")
                timeline.append({
                    "phase": phase, "px": [pixmap.width(), pixmap.height()],
                    "visible_rows": (
                        business.table.rowCount() if phase == "fiche-individu"
                        else consumptions.list_page.model.rowCount()
                    ),
                    "individual_id": expected_individual,
                    "inscription_id": expected_inscription,
                    "selected_date": consumptions.calendar.selectedDate().toString(
                        Qt.DateFormat.ISODate
                    ),
                })

            business.show_domain("individus")
            person_row = next(
                idx for idx in range(business.table.rowCount())
                if business.table.item(idx, 0).data(
                    Qt.ItemDataRole.UserRole) == 12
            )
            business.table.selectRow(person_row)
            if not business.individual_consumptions_button.isVisible():
                raise AssertionError("Accès direct individu manquant")
            frame("fiche-individu", 4)

            business.individual_consumptions_button.click()
            if window.tabs.currentWidget() is not consumptions:
                raise AssertionError("L'écran des consommations n'est pas ouvert")
            frame("consommations-individu", 28, 12, None)

            window.tabs.setCurrentWidget(business)
            business.show_domain("inscriptions", individual_id=12)
            if business.table.rowCount() != 1:
                raise AssertionError("Inscription choisie non unique")
            if business.table.item(0, 0).text() != "503":
                raise AssertionError("Identifiant inscription inattendu")
            business._open_related(0, 0)
            frame("consommations-inscription", 28, 12, 503)

            consumptions.clear_record_button.click()
            frame("consommations-globales", EXPECTED_ROWS, None, None)
            if fictive.dump() != original:
                raise AssertionError("La base fictive a été modifiée")
            output = {
                "lot": "C11", "source": "temporary_fictive_sqlite_only",
                "theme": args.theme, "profile": args.profile,
                "scale": os.environ.get("QT_SCALE_FACTOR", "system"),
                "frames": timeline, "database_unchanged": True,
                "any_write_enabled": False,
                "manual_visual_review_needed": True,
            }
            report.write_text(
                json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"C11_EXACT_PASS theme={args.theme} profile={args.profile} "
                f"frames={len(timeline)} exact_IDs=12,503 "
                "no_foreign_rows=true db_unchanged=true"
            )
        finally:
            window.close()
            app.processEvents()


if __name__ == "__main__":
    main()
