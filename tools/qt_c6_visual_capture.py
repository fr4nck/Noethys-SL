"""Captures de consommation Qt 100% fictives pour recette visuelle Windows C6.

N'utilise jamais la base ou la configuration Noethys; screenshots statiques,
sans preuve d'absence de scintillement ou validation DPI humaine.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_qt"))

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication
from noethys_qt.consumptions_calendar_ui import ConsumptionCalendarPage
from test_consumptions_calendar import ConsumptionCalendarSqlTests


def main():
    parser = argparse.ArgumentParser(description="Capture Qt sur base fictive")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    permitted_dir = (ROOT / "artifacts" / "qt-c6").resolve()
    if (
        output.parent != permitted_dir
        or output.suffix.lower() != ".png"
        or output.is_symlink()
    ):
        parser.error("Destination imposee : artifacts/qt-c6/*.png")
    permitted_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Noethys Qt — capture synthétique C6")
    fixture = ConsumptionCalendarSqlTests(
        "test_month_counts_are_exact_and_bound_to_month"
    )
    fixture.setUp()
    page = None
    try:
        page = ConsumptionCalendarPage(fixture.core, background=False)
        page.setWindowTitle("Noethys Qt — DONNÉES FICTIVES")
        page.resize(1280, 830)
        page.show()
        app.processEvents()
        page.activate()
        page.list_page.year_spin.setValue(2026)
        page.calendar.setSelectedDate(QDate(2026, 10, 2))
        app.processEvents()
        if {r.consumption_id for r in page.list_page.model.rows} != {3, 4}:
            raise AssertionError("Le filtre du jour ne montre pas les données fictives")
        if not page.only_day.isChecked():
            raise AssertionError("Filtre calendrier non activé")
        if not page.preparation_panel.warning.isVisible():
            raise AssertionError("L'avertissement d'écriture désactivée est invisible")
        if page.list_page.table.viewport().width() <= 120:
            raise AssertionError("Tableau Qt trop étroit")
        if page.calendar.width() <= 100:
            raise AssertionError("Calendrier Qt trop étroit")
        page.list_page.table.selectRow(1)
        page.preparation_panel.target_combo.setCurrentIndex(
            page.preparation_panel.target_combo.findData("present")
        )
        app.processEvents()
        picture = page.grab()
        if picture.isNull() or picture.width() <= 600 or picture.height() <= 350:
            raise AssertionError("Capture Qt nulle ou trop petite")
        if not picture.save(str(output), "PNG"):
            raise RuntimeError("Impossible de sauvegarder la capture")
        if output.stat().st_size < 2000:
            raise RuntimeError("PNG anormalement petit")
        print(
            f"C6_VISUAL_PASS file={output} "
            f"pixels={picture.width()}x{picture.height()} "
            f"rows={page.list_page.model.rowCount()} "
            f"days={len(page._date_counts)} source=synthetic"
        )
    finally:
        if page is not None:
            page.close()
        app.processEvents()
        fixture.doCleanups()


if __name__ == "__main__":
    main()
