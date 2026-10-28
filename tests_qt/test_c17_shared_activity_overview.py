"""C17 — vrai service partagé et navigation transversale Qt sur SQLite inventé."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QAbstractItemView, QApplication

from noethys.Utils import UTILS_Consumption_StateCounts as SHARED
from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.catalog_readonly_core import (
    CATALOG_DOMAINS, CATALOG_MODULES, C16_DOMAIN_CODES,
    C16_CATALOG_MODULE_CODES, C17_CATALOG_MODULES,
    C17_ACTIVITY_DESTINATIONS, CatalogRepository, build_catalog_query,
)
from noethys_qt.consumptions_core import (
    STATES as QT_STATES, ALL_STATES as QT_ALL_STATES, OTHER as QT_OTHER,
)
from noethys_qt.consumptions_status_core import (
    CONTRACT, ConsumptionStatusRepository,
    StateCount, StatusSummary, validate_state_selection,
    build_state_summary_statement, make_status_summary,
)
from noethys_qt.noethys_native import (
    C17_NAVIGATION, NoethysQtWindow,
)
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c16_fixture import C16FictivePlanningDatabase


class SharedContractTests(unittest.TestCase):
    def test_state_codes_are_shared_by_identity_not_copied(self):
        self.assertIs(QT_STATES, SHARED.STATES)
        self.assertIs(QT_ALL_STATES, SHARED.ALL_STATES)
        self.assertIs(CONTRACT, SHARED.CONTRACT)
        self.assertEqual(QT_OTHER, SHARED.OTHER)

    def test_qt_sql_builder_and_validator_are_shared(self):
        self.assertIs(validate_state_selection, SHARED.validate_state_selection)
        self.assertIs(build_state_summary_statement, SHARED.build_state_summary_statement)
        self.assertIs(make_status_summary, SHARED.make_status_summary)
        self.assertIs(StateCount, SHARED.StateCount)
        self.assertIs(StatusSummary, SHARED.StatusSummary)

    def test_shared_sql_state_filters_match_previous_c16_contract(self):
        sql, params = build_state_summary_statement(
            year=2026, activity_id=1, states={"present", SHARED.OTHER},
        )
        self.assertIn("GROUP BY", sql)
        self.assertEqual(
            params, ("2026-01-01", "2027-01-01", 1, "present"),
        )
        self.assertEqual(sql.count("?"), len(params))

    def test_shared_rejects_unexpected_counts_instead_of_silent_report(self):
        for records in (
            (("present", -1),),
            (("present", 1), ("present", 1)),
            (("attente", 1),),
        ):
            with self.assertRaises(ValueError):
                make_status_summary(
                    year=2026, states={"present"}, grouped_rows=records
                )

    def test_widget_facing_summary_uses_shared_dataclass(self):
        with C16FictivePlanningDatabase() as fake:
            reader = ConsumptionStatusRepository(fake.repository)
            result = reader.summary(year=2026, states={"present", SHARED.OTHER})
            self.assertIsInstance(result, SHARED.StatusSummary)
            self.assertEqual(result.total, 41)
            self.assertEqual(
                {row.code: row.count for row in result.rows},
                {"present": 16, SHARED.OTHER: 25},
            )

    def test_no_sql_connection_with_empty_state_selection(self):
        with C16FictivePlanningDatabase() as fake:
            reader = ConsumptionStatusRepository(fake.repository)
            with patch.object(
                fake.repository.editor_repository, "_connect",
                side_effect=AssertionError("SQL must not be opened"),
            ):
                result = reader.summary(year=2026, states=frozenset())
            self.assertEqual(result.total, 0)


class ActivityOverviewSqlTests(unittest.TestCase):
    def setUp(self):
        self.fixture = C16FictivePlanningDatabase()
        self.addCleanup(self.fixture.close)
        self.reader = CatalogRepository(self.fixture.repository.editor_repository)

    def test_one_new_closed_catalog_domain_and_module(self):
        self.assertEqual(set(CATALOG_DOMAINS) - C16_DOMAIN_CODES, {"activity_overview"})
        self.assertEqual(
            set(CATALOG_MODULES) - C16_CATALOG_MODULE_CODES, {"activity_overview"},
        )
        self.assertEqual(C17_CATALOG_MODULES["activity_overview"][1],
                         ("activity_overview",))
        self.assertEqual(
            C17_ACTIVITY_DESTINATIONS,
            {"planning", "tariff_records", "consumption_reports"},
        )

    def test_two_activities_counts_avoid_join_multiplication(self):
        results = self.reader.search("activity_overview")
        self.assertFalse(results.truncated)
        self.assertEqual({row.id for row in results.rows}, {1, 2})
        by_id = {row.id: row for row in results.rows}
        self.assertEqual(
            tuple(by_id[1].value(key) for key in (
                "enrollments", "status_ok", "consumptions",
                "present", "openings", "events", "tariffs",
            )),
            (2, 2, 57, 9, 2, 2, 2),
        )
        self.assertEqual(
            tuple(by_id[2].value(key) for key in (
                "enrollments", "status_ok", "consumptions",
                "present", "openings", "events", "tariffs",
            )),
            (3, 2, 58, 8, 1, 1, 1),
        )

    def test_scope_filters_by_numeric_activity_id(self):
        self.assertEqual(
            {r.id for r in self.reader.search(
                "activity_overview", activity_id=2,
            ).rows},
            {2},
        )
        self.assertEqual(
            self.reader.search("activity_overview", activity_id=777).rows, (),
        )

    def test_text_search_is_literal_and_escaped(self):
        sql, args = build_catalog_query(
            "activity_overview", text="Café%", activity_id=1,
        )
        self.assertEqual(sql.count("?"), len(args))
        self.assertNotIn("Café%", sql)
        self.assertIn("ESCAPE '!'", sql)
        self.assertEqual(args[0], 1)
        self.assertIn("%Café!%%", args)
        self.assertEqual(
            self.reader.search("activity_overview", text="' OR 1=1 --").rows,
            (),
        )

    def test_year_family_and_bad_ids_rejected_before_connection(self):
        with patch.object(
            self.reader.editor_repository, "_connect",
            side_effect=AssertionError("SQL should not open"),
        ):
            for filters in (
                {"year": 2026}, {"family_id": 100},
                {"activity_id": True}, {"activity_id": -2},
                {"limit": 251}, {"text": "X" * 121},
            ):
                with self.subTest(filters=filters):
                    with self.assertRaises(ValueError):
                        self.reader.search("activity_overview", **filters)

    def test_one_row_limit_is_signaled_not_called_global_total(self):
        result = self.reader.search("activity_overview", limit=1)
        self.assertEqual(len(result.rows), 1)
        self.assertTrue(result.truncated)

    def test_empty_activity_has_zero_counts_not_null(self):
        con = sqlite3.connect(":memory:")
        self.addCleanup(con.close)
        con.executescript("""
            CREATE TABLE activites (IDactivite INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE inscriptions (IDactivite INTEGER, statut TEXT);
            CREATE TABLE consommations (IDactivite INTEGER, etat TEXT);
            CREATE TABLE ouvertures (IDactivite INTEGER);
            CREATE TABLE evenements (IDactivite INTEGER);
            CREATE TABLE tarifs (IDactivite INTEGER);
            INSERT INTO activites VALUES (7, 'Sans aucune ligne fictive');
        """)
        statement, binds = build_catalog_query("activity_overview")
        record = con.execute(statement, binds).fetchone()
        self.assertEqual(record[0:2], (7, "Sans aucune ligne fictive"))
        self.assertEqual(record[2:], (0, 0, 0, 0, 0, 0, 0))

    def test_source_dump_unchanged_after_all_overview_filters(self):
        before = self.fixture.dump()
        for opts in ({}, {"activity_id": 1}, {"activity_id": 2},
                     {"text": "Fictif"}, {"limit": 1}):
            self.reader.search("activity_overview", **opts)
        self.assertEqual(before, self.fixture.dump())


class ActivityOverviewQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.fixture = C16FictivePlanningDatabase()
        self.addCleanup(self.fixture.close)
        self.temp = tempfile.TemporaryDirectory(prefix="noethys-c17-settings-")
        self.addCleanup(self.temp.cleanup)
        settings = QSettings(
            str(Path(self.temp.name) / "config.ini"),
            QSettings.Format.IniFormat,
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            self.window = NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path,
                requested_theme="light", background_queries=False,
                read_only_demo=True, catalog_enabled=True,
                c15_enabled=True, c16_enabled=True, c17_enabled=True,
                badge_logs_enabled=False,
                source_label="C17 FICTIVE ONLY",
            )
        self.addCleanup(self.window.close)
        self.window.show()
        self.app.processEvents()

    def _select_activity(self, ident):
        self.window.navigate("activity_overview")
        page = self.window.catalog_pages["activity_overview"].current_page
        index = next(i for i, row in enumerate(page.model.rows) if row.id == ident)
        page.table.selectRow(index)
        self.assertEqual(page.selected_row().id, ident)
        return page

    def test_23_entries_and_restricted_badgeage(self):
        self.assertEqual(len(C17_NAVIGATION), 1)
        self.assertEqual(self.window.navigation.count(), 23)
        self.assertIn("activity_overview", self.window.catalog_pages)
        self.assertNotIn("badge_journal", self.window.catalog_pages)
        self.assertFalse(self.window.catalog_actions["badge_journal"].isEnabled())
        self.window.navigate("activity_overview")
        self.assertIs(
            self.window.stack.currentWidget(),
            self.window.catalog_pages["activity_overview"],
        )

    def test_overview_is_strictly_read_only(self):
        page = self._select_activity(1)
        self.assertEqual(
            page.table.editTriggers(),
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.assertEqual(len(page.related_buttons), 3)
        self.assertTrue(page.activity_button.isEnabled())
        self.assertTrue(all(b.isEnabled() for b in page.related_buttons.values()))

    def test_planning_link_preserves_selected_activity_and_back(self):
        page = self._select_activity(1)
        page.related_buttons["planning"].click()
        self.assertIs(
            self.window.stack.currentWidget(), self.window.catalog_pages["planning"]
        )
        target = self.window.catalog_pages["planning"].current_page
        self.assertEqual(target.activity_spin.value(), 1)
        self.assertEqual({r.id for r in target.model.rows}, {601, 603})
        self.window.return_to_context()
        self.assertIs(
            self.window.stack.currentWidget(),
            self.window.catalog_pages["activity_overview"],
        )
        self.assertEqual(page.selected_row().id, 1)

    def test_tariffs_link_scopes_and_restores_context(self):
        page = self._select_activity(2)
        page.related_buttons["tariff_records"].click()
        target = self.window.catalog_pages["tariff_records"].current_page
        self.assertEqual(target.activity_spin.value(), 2)
        self.assertEqual({r.id for r in target.model.rows}, {802})
        self.window.return_to_context()
        self.assertEqual(page.selected_row().id, 2)

    def test_state_report_link_uses_same_numeric_id(self):
        page = self._select_activity(2)
        self.window.report_page.year_spin.setValue(2027)
        page.related_buttons["consumption_reports"].click()
        report = self.window.report_page
        self.assertIs(self.window.stack.currentWidget(), report)
        self.assertEqual(report.activity_spin.value(), 2)
        self.assertEqual(report.last_result.total, 2)
        self.window.return_to_context()
        self.assertEqual(page.selected_row().id, 2)

    def test_inscriptions_link_uses_existing_native_page(self):
        page = self._select_activity(1)
        page.activity_button.click()
        self.assertIs(
            self.window.stack.currentWidget(), self.window.inscriptions_page
        )
        self.assertEqual(self.window.inscriptions_page._filters["activity_id"], 1)
        self.assertEqual(
            {r.id for r in self.window.inscriptions_page.model.rows}, {501, 503}
        )
        self.window.return_to_context()
        self.assertEqual(page.selected_row().id, 1)

    def test_global_navigation_clears_transversal_activity_context(self):
        self._select_activity(2).related_buttons["tariff_records"].click()
        target = self.window.catalog_pages["tariff_records"].current_page
        self.assertEqual(target.activity_spin.value(), 2)
        self.window.navigate("home")
        self.window.navigate("tariff_records")
        self.assertEqual(target.activity_spin.value(), 0)
        self.assertEqual({r.id for r in target.model.rows}, {801, 802, 803})

    def test_global_navigation_clears_state_report_context(self):
        self._select_activity(1).related_buttons["consumption_reports"].click()
        report = self.window.report_page
        self.assertEqual(report.activity_spin.value(), 1)
        report.year_spin.setValue(2026)
        self.window.navigate("home")
        self.window.navigate("consumption_reports")
        self.assertEqual(report.activity_spin.value(), 0)
        self.assertEqual(report.last_result.total, 112)

    def test_missing_selection_disables_all_related_buttons(self):
        page = self._select_activity(1)
        page.table.clearSelection()
        self.assertFalse(page.activity_button.isEnabled())
        self.assertFalse(any(b.isEnabled() for b in page.related_buttons.values()))

    def test_illegal_related_module_rejected_before_navigation(self):
        page = self._select_activity(1)
        with self.assertRaises(ValueError):
            page._open_related_activity("billing")
        with self.assertRaises(ValueError):
            self.window._catalog_related_activity_requested(
                "activity_overview", "badge_journal", 1,
            )
        with self.assertRaises(ValueError):
            self.window._catalog_related_activity_requested(
                "activity_overview", "planning", True,
            )
        self.assertIs(
            self.window.stack.currentWidget(),
            self.window.catalog_pages["activity_overview"],
        )

    def test_same_query_preserves_selection_without_model_reset(self):
        page = self._select_activity(1)
        spy = QSignalSpy(page.model.modelReset)
        page.refresh()
        self.assertEqual(spy.count(), 0)
        self.assertEqual(page.selected_row().id, 1)

    def test_c16_and_c15_modules_still_work_in_c17_shell(self):
        self.window.navigate("planning")
        self.assertEqual(
            {r.id for r in self.window.catalog_pages["planning"].current_page.model.rows},
            {601, 602, 603},
        )
        self.window.navigate("certificates")
        self.assertEqual(
            {r.id for r in self.window.catalog_pages["certificates"].current_page.model.rows},
            {7001, 7002, 7003},
        )
        self.window.navigate("billing")
        self.assertEqual(
            {r.id for r in self.window.finance_pages["billing"].current_page.model.rows},
            {501, 502, 503, 990},
        )

    def test_full_navigation_never_alters_fixture(self):
        before = self.fixture.dump()
        for target in ("planning", "tariff_records",
                       "consumption_reports", "inscriptions"):
            page = self._select_activity(1)
            if target == "inscriptions":
                page.activity_button.click()
            else:
                page.related_buttons[target].click()
            self.window.return_to_context()
        self.assertEqual(before, self.fixture.dump())
        self.assertFalse(self.window.activities_action.isEnabled())


if __name__ == "__main__":
    unittest.main()
