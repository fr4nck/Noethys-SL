"""Scénario dynamique C7 : captures et métriques Qt sur base FICTIVE.

Ce script n'utilise jamais Config.json, la base de l'association ni wx.
Il compte les resets du modèle, Paint/Resize et vérifie les états
après interactions; des PNG statiques ne prouvent pas à eux seuls
l'absence de scintillement réel pendant une vidéo de l'application.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_qt"))

from PySide6.QtCore import QDate, QEvent, QObject
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from noethys_qt.consumptions_calendar_ui import ConsumptionCalendarPage
from test_consumptions_calendar import ConsumptionCalendarSqlTests


class Events(QObject):
    def __init__(self):
        super().__init__()
        self.paint = 0
        self.resize = 0

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Paint:
            self.paint += 1
        if event.type() == QEvent.Type.Resize:
            self.resize += 1
        return False  # Ne bloque JAMAIS le rendu Qt.


def _dump(path):
    with closing(sqlite3.connect(path)) as con:
        return tuple(con.iterdump())


def main():
    parser = argparse.ArgumentParser(description="Recette Qt dynamique fictive C7")
    parser.add_argument("--profile", required=True, choices=("100", "150"))
    args = parser.parse_args()

    root = (ROOT / "artifacts" / "qt-c7").resolve()
    root.mkdir(parents=True, exist_ok=True)
    outputs = (
        [root / f"scale{args.profile}-{label}.png" for label in
         ("initial", "filtered", "restored")]
        + [root / f"scale{args.profile}-metrics.json"]
    )
    for output in outputs:
        if output.is_symlink() or output.parent.resolve() != root:
            raise RuntimeError("Chemin de sortie externe interdit")

    app = QApplication.instance() or QApplication([])
    fixture = ConsumptionCalendarSqlTests(
        "test_month_counts_are_exact_and_bound_to_month"
    )
    fixture.setUp()
    page = None
    try:
        initial_dump = _dump(fixture.path)
        page = ConsumptionCalendarPage(fixture.core, background=False)
        page.setWindowTitle("Noethys Qt C7 — DONNÉES FICTIVES — NON MODIFIABLES")
        page.resize(1240, 800)
        page.show()
        app.processEvents()
        page.activate()
        page.list_page.year_spin.setValue(2026)
        page.calendar.setSelectedDate(QDate(2026, 10, 2))
        page.list_page.table.selectRow(1)
        app.processEvents()

        counter_table = Events()
        counter_calendar = Events()
        page.list_page.table.viewport().installEventFilter(counter_table)
        page.calendar.installEventFilter(counter_calendar)
        resets = QSignalSpy(page.list_page.model.modelReset)
        records = []

        def screenshot(label, expected):
            app.processEvents()
            actual = [row.consumption_id for row in page.list_page.model.rows]
            if set(actual) != set(expected):
                raise AssertionError(f"Étape {label}: attendu {expected}; obtenu {actual}")
            if not page.preparation_panel.warning.isVisible():
                raise AssertionError("L'interdiction d'écrire a disparu")
            if page.list_page.table.viewport().width() <= 120:
                raise AssertionError("Tableau Qt illisible")
            if page.calendar.width() <= 100:
                raise AssertionError("Calendrier Qt trop petit")
            picture = page.grab()
            if picture.isNull():
                raise AssertionError("Pixmap Qt invalide")
            destination = root / f"scale{args.profile}-{label}.png"
            if not picture.save(str(destination), "PNG"):
                raise RuntimeError("Échec de capture Qt")
            if destination.stat().st_size < 2000:
                raise RuntimeError("PNG dynamique vide")
            selected = page.list_page.table.selectionModel().selectedRows()
            selected_id = (
                page.list_page.model.rows[selected[0].row()].consumption_id
                if selected else None
            )
            records.append({
                "step": label,
                "size_px": [picture.width(), picture.height()],
                "ids": actual,
                "selected_id": selected_id,
                "marked_days": len(page._date_counts),
                "month_summary": page.month_summary.text(),
                "table_enabled": page.list_page.table.isEnabled(),
            })

        screenshot("initial", [4, 3])
        for _ in range(20):
            page.refresh()
            app.processEvents()
        unchanged_model_resets = resets.count()
        if unchanged_model_resets != 0:
            raise AssertionError(
                f"{unchanged_model_resets} modelReset parasites en rafraîchissement identique"
            )
        selected = page.list_page.table.selectionModel().selectedRows()
        if not selected or page.list_page.model.rows[selected[0].row()].consumption_id != 3:
            raise AssertionError("La sélection ID 3 n'a pas été conservée")

        page.activity_combo.setCurrentIndex(page.activity_combo.findData(1))
        page.list_page.none_button.click()
        page.list_page.state_checks["absentj"].click()
        page.list_page.table.selectRow(0)
        screenshot("filtered", [3])

        page.list_page.all_button.click()
        page.activity_combo.setCurrentIndex(0)
        page.year_button.click()
        page.resize(1040, 720)
        screenshot("restored", [7, 6, 5, 4, 3, 2, 1])

        for cycle in range(24):
            page.calendar.setSelectedDate(QDate(2026, 10, 1 + cycle % 2))
            page.activity_combo.setCurrentIndex(
                page.activity_combo.findData(1 if cycle % 2 else 2)
            )
            page.list_page.table.viewport().update()
            app.processEvents()

        page.activity_combo.setCurrentIndex(0)
        page.calendar.setSelectedDate(QDate(2026, 10, 2))
        app.processEvents()
        if {r.consumption_id for r in page.list_page.model.rows} != {3, 4}:
            raise AssertionError("L'état final après 24 changements est incohérent")
        if _dump(fixture.path) != initial_dump:
            raise AssertionError("La recette C7 a modifié les données fictives")

        metrics = {
            "suite": "C7 Qt dynamic synthetic",
            "source": "synthetic_fixture_only",
            "profile": args.profile,
            "qt_scale_factor": os.environ.get("QT_SCALE_FACTOR", "1"),
            "rows_unchanged_refresh_resets": unchanged_model_resets,
            "repeated_refresh_count": 20,
            "rapid_filter_switch_count": 24,
            "paint_events_observed": {
                "table_viewport": counter_table.paint,
                "calendar": counter_calendar.paint,
            },
            "resize_events_observed": {
                "table_viewport": counter_table.resize,
                "calendar": counter_calendar.resize,
            },
            "frames": records,
            "database_unchanged": True,
            "writes_enabled": False,
            "warning": "Pas de preuve d'absence de scintillement sur poste utilisateur",
        }
        filename = root / f"scale{args.profile}-metrics.json"
        filename.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"C7_DYNAMIC_PASS profile={args.profile} "
            f"frames={len(records)} no_op_resets={unchanged_model_resets} "
            f"table_paints={counter_table.paint} "
            f"calendar_paints={counter_calendar.paint} synthetic_only=true"
        )
    finally:
        if page is not None:
            page.close()
        app.processEvents()
        fixture.doCleanups()


if __name__ == "__main__":
    main()
