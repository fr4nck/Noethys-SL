"""C10 : captures famille/individu/inscription sur une fixture fictive.

Production de trois PNG + un JSON par profil de test Windows. Aucun
profil utilisateur ni fichier SQLite configuré n'est jamais ouvert.
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

from PySide6.QtWidgets import QApplication
from noethys_qt.activity_visuals import apply_semantic_theme
from tools.qt_c8_fixture import C8FictiveDatabase
from tools.qt_c8_windows_demo import C8DemoWindow


def main():
    parser = argparse.ArgumentParser(description="Recette métier Qt C10 fictive")
    parser.add_argument("--theme", choices=("light", "dark"), required=True)
    parser.add_argument("--profile", choices=("100", "150"), required=True)
    args = parser.parse_args()
    root = (ROOT / "artifacts" / "qt-c10").resolve()
    root.mkdir(parents=True, exist_ok=True)
    prefix = f"{args.theme}-{args.profile}"
    outputs = [
        root / f"{prefix}-{step}.png"
        for step in ("famille", "individus", "inscriptions")
    ] + [root / f"{prefix}-verification.json"]
    for name in outputs:
        if name.parent.resolve() != root or name.is_symlink():
            raise RuntimeError("Capture en dehors du répertoire fictif interdite")

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    with C8FictiveDatabase() as db:
        initial = db.dump()
        window = C8DemoWindow(
            db.repository, theme=args.theme, background=False,
            fictive_db=db,
        )
        try:
            window.resize(1230, 800)
            window.show()
            window.activate_demo()
            window.tabs.setCurrentWidget(window.business_page)
            apply_semantic_theme(window)
            app.processEvents()
            page = window.business_page
            history = []

            def shot(step, expected_domain, expected_count):
                app.processEvents()
                if page.domain != expected_domain or page.table.rowCount() != expected_count:
                    raise AssertionError(
                        f"C10 {step}: mauvais contexte {page.domain} "
                        f"({page.table.rowCount()} entrées)"
                    )
                if not page.detail_title.text() or not page.detail_body.text():
                    raise AssertionError("Fiche vide")
                if not window.banner.isVisible():
                    raise AssertionError("Bannière fictive invisible")
                if (
                    page.table.viewport().width() < 170
                    or page.detail_body.width() < 150
                ):
                    raise AssertionError("Liste ou fiche trop étroite")
                image = window.grab()
                if image.isNull():
                    raise AssertionError("Capture Qt nulle")
                path = root / f"{prefix}-{step}.png"
                if not image.save(str(path), "PNG") or path.stat().st_size < 3000:
                    raise RuntimeError("Capture invalide")
                history.append({
                    "step": step, "domain": page.domain,
                    "visible_rows": page.table.rowCount(),
                    "selected_id": page._selected_id(),
                    "pixels": [image.width(), image.height()],
                })

            page.show_domain("familles")
            shot("famille", "familles", 2)
            if page._selected_id() != 100:
                raise AssertionError("La première famille fictive n'est pas #100")
            page._open_related(0, 0)
            shot("individus", "individus", 2)
            visible = {
                page.table.item(i, 0).text()
                for i in range(page.table.rowCount())
            }
            if visible != {"10", "12"}:
                raise AssertionError("Les membres affichés ne sont pas liés à la famille 100")
            page._open_related(0, 0)
            shot("inscriptions", "inscriptions", 1)
            if not page.back_button.isEnabled():
                raise AssertionError("Le retour contextuel est indisponible")
            page.go_back()
            page.go_back()
            if page.domain != "familles" or page._selected_id() != 100:
                raise AssertionError("Le retour n'a pas restauré la famille")
            if initial != db.dump():
                raise AssertionError("La recette a modifié la base fictive")
            document = {
                "lot": "C10", "source": "fictitious_local_temporary_sqlite",
                "theme": args.theme, "profile": args.profile,
                "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR", "system"),
                "images": history, "database_unchanged": True,
                "uses_real_family_categories": False,
                "manual_visual_review_required": True,
            }
            outputs[-1].write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"C10_BUSINESS_PASS theme={args.theme} scale={args.profile} "
                f"frames={len(history)} family_context=100 "
                "database_unchanged=true"
            )
        finally:
            window.close()
            app.processEvents()


if __name__ == "__main__":
    main()
