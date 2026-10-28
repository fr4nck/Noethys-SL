"""C16 : SQL, sélection des états et navigation Qt sur données inventées."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QAbstractItemView, QApplication

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.catalog_readonly_core import (
    CATALOG_DOMAINS, CATALOG_MODULES, C15_DOMAIN_CODES,
    C15_MODULE_CODES, C16_CATALOG_MODULES, C16_ACTIVITY_LINK_DOMAINS,
    C16_RESTRICTED_MODULES, CatalogRepository, build_catalog_query,
)
from noethys_qt.catalog_readonly_ui import CatalogTableModel
from noethys_qt.consumptions_core import ALL_STATES, OTHER
from noethys_qt.consumptions_status_core import (
    CONTRACT, ConsumptionStatusRepository, DISPLAY_STATES,
    build_state_summary_statement,
)
from noethys_qt.noethys_native import C16_NAVIGATION, NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c16_fixture import C16FictivePlanningDatabase


EXPECTED = {
    "openings": {601, 602, 603},
    "events": {41, 42, 43},
    "tariffs": {801, 802, 803},
    "tariff_lines": {901, 902, 903},
    "badge_actions": {1001, 1002, 1003},
}


class C16SqlTests(unittest.TestCase):
    def setUp(self):
        self.fixture = C16FictivePlanningDatabase()
        self.addCleanup(self.fixture.close)
        self.catalog = CatalogRepository(self.fixture.repository.editor_repository)
        self.summary = ConsumptionStatusRepository(self.fixture.repository)

    def test_closed_domain_contract_and_source_scopes(self):
        self.assertEqual(
            set(CATALOG_DOMAINS) - C15_DOMAIN_CODES, set(EXPECTED)
        )
        self.assertEqual(
            set(CATALOG_MODULES) - C15_MODULE_CODES,
            set(C16_CATALOG_MODULES),
        )
        self.assertEqual(set(C16_CATALOG_MODULES), {
            "planning", "tariff_records", "badge_journal",
        })
        self.assertEqual(C16_RESTRICTED_MODULES, {"badge_journal"})
        self.assertEqual(CONTRACT, "stored-consumption-state-counts/1")

    def test_exact_five_new_sql_tables(self):
        for kind, wanted in EXPECTED.items():
            with self.subTest(kind=kind):
                result = self.catalog.search(kind)
                self.assertEqual({row.id for row in result.rows}, wanted)
                self.assertFalse(result.truncated)
                self.assertTrue(all(row.kind == kind for row in result.rows))

    def test_planning_by_activity_and_exact_year(self):
        self.assertEqual(
            {r.id for r in self.catalog.search("openings", activity_id=1).rows},
            {601, 603},
        )
        self.assertEqual(
            {r.id for r in self.catalog.search(
                "events", activity_id=1, year=2027,
            ).rows}, {43},
        )
        self.assertEqual(
            {r.id for r in self.catalog.search("openings", year=2027).rows},
            {603},
        )

    def test_tariff_conditions_are_not_simulated(self):
        row = self.catalog.search("tariffs", year=2027, activity_id=1).rows
        self.assertEqual({item.id for item in row}, {803})
        entry = row[0]
        self.assertEqual(entry.value("categories"), "[1]")
        self.assertEqual(entry.value("method"), "qf")
        lines = self.catalog.search("tariff_lines", activity_id=1).rows
        self.assertEqual({item.id for item in lines}, {901, 903})
        amount = next(item for item in lines if item.id == 903)
        self.assertEqual(amount.value("amount"), "1000.0003")
        self.assertEqual(amount.value("adjustment"), "-0.0003")

    def test_precision_is_visible_without_financial_rounding(self):
        model = CatalogTableModel("events")
        model.replace_rows(self.catalog.search("events").rows)
        position = next(i for i, row in enumerate(model.rows) if row.id == 43)
        self.assertEqual(model.data(model.index(position, 9)), "1000,0003")
        lines = CatalogTableModel("tariff_lines")
        lines.replace_rows(self.catalog.search("tariff_lines").rows)
        pos = next(i for i, row in enumerate(lines.rows) if row.id == 903)
        self.assertEqual(lines.data(lines.index(pos, 7)), "1000,0003")

    def test_badge_log_is_raw_history_without_verdict(self):
        self.assertEqual(
            {r.id for r in self.catalog.search("badge_actions", year=2026).rows},
            {1001, 1002},
        )
        action = next(
            row for row in self.catalog.search("badge_actions").rows
            if row.id == 1002
        )
        self.assertEqual(action.value("outcome"), "0")
        self.assertEqual(action.value("individual_id"), 11)
        self.assertEqual(action.value("individual"), "Fictif Morgan exemple")

    def test_catalog_filters_are_parameterized_and_reject_bad_ids(self):
        sql, params = build_catalog_query(
            "events", activity_id=1, year=2027, text="Événement"
        )
        self.assertNotIn("Événement", sql)
        self.assertEqual(sql.count("?"), len(params))
        self.assertEqual(params[:3], (1, "2027-01-01", "2028-01-01"))
        mysql, binding = build_catalog_query(
            "tariffs", activity_id=1, placeholder="%s",
        )
        self.assertEqual(mysql.count("%s"), len(binding))
        self.assertEqual(self.catalog.search(
            "events", text="' OR 1=1 --"
        ).rows, ())
        with patch.object(
            self.catalog.editor_repository, "_connect",
            side_effect=AssertionError("No SQL connection allowed"),
        ):
            for kind, args in [
                ("events", {"activity_id": True}),
                ("events", {"activity_id": -1}),
                ("openings", {"family_id": 100}),
                ("badge_actions", {"activity_id": 1}),
                ("tariff_lines", {"year": 2026}),
                ("tariffs", {"text": "A" * 121}),
                ("events", {"limit": 251}),
            ]:
                with self.subTest(kind=kind, args=args):
                    with self.assertRaises(ValueError):
                        self.catalog.search(kind, **args)

    def test_limited_result_is_explicitly_truncated(self):
        result = self.catalog.search("events", limit=1)
        self.assertEqual(len(result.rows), 1)
        self.assertTrue(result.truncated)

    def test_single_state_summary_counts_source_rows_no_money(self):
        summary = self.summary.summary(year=2026)
        self.assertEqual(summary.total, 112)
        self.assertEqual(len(summary.rows), 7)
        self.assertEqual({row.code for row in summary.rows}, ALL_STATES)
        self.assertEqual(
            sum(row.count for row in summary.rows), summary.total
        )
        by_code = {row.code: row.count for row in summary.rows}
        self.assertEqual(by_code["present"], 16)
        self.assertEqual(by_code[OTHER], 25)

    def test_status_by_click_selection_matches_source(self):
        selected = self.summary.summary(year=2026, states={"present", "reservation"})
        self.assertEqual(selected.total, 29)
        self.assertEqual({row.code for row in selected.rows}, {"present", "reservation"})
        self.assertEqual({r.code: r.count for r in selected.rows}, {"present": 16, "reservation": 13})
        other = self.summary.summary(year=2026, states={OTHER})
        self.assertEqual(other.total, 25)
        self.assertEqual(other.rows[0].code, OTHER)
        self.assertEqual(self.summary.summary(year=2026, states={"present"}).total, 16)

    def test_unknown_and_null_states_are_grouped_once(self):
        state = self.summary.summary(year=2027)
        self.assertEqual(state.total, 3)
        counts = {r.code: r.count for r in state.rows}
        self.assertEqual(counts["present"], 1)
        self.assertEqual(counts[OTHER], 2)
        self.assertEqual(
            self.summary.summary(year=2027, states={"reservation"}).total, 0
        )
        self.assertEqual(
            self.summary.summary(year=2027, states={OTHER}, activity_id=2).total, 2
        )

    def test_activity_filter_counts_every_consumption_not_every_child(self):
        for code in (1, 2):
            self.assertEqual(
                self.summary.summary(year=2026, activity_id=code).total, 56
            )
        self.assertEqual(
            self.summary.summary(year=2027, activity_id=1).total, 1
        )
        self.assertEqual(
            self.summary.summary(year=2027, activity_id=2).total, 2
        )

    def test_empty_state_selection_does_not_connect(self):
        with patch.object(
            self.summary.consumption_repository.editor_repository,
            "_connect", side_effect=AssertionError("No SQL allowed"),
        ):
            empty = self.summary.summary(year=2026, states=())
        self.assertEqual(empty.total, 0)
        self.assertEqual(empty.rows, ())
        self.assertEqual(empty.selected, frozenset())

    def test_bad_status_or_year_is_rejected_before_connect(self):
        with patch.object(
            self.summary.consumption_repository.editor_repository,
            "_connect", side_effect=AssertionError("No SQL allowed"),
        ):
            for args in [
                {"year": 2026, "states": {"'; DROP TABLE consommations;"}},
                {"year": 2026, "states": {"Present"}},
                {"year": 2026, "activity_id": True},
                {"year": 2026, "activity_id": -3},
                {"year": 2099},
                {"year": True},
                {"year": 2026, "states": None},
            ]:
                with self.subTest(args=args):
                    with self.assertRaises(ValueError):
                        self.summary.summary(**args)

    def test_build_state_query_sqlite_mysql_and_empty(self):
        sql, args = build_state_summary_statement(
            year=2026, states={"present", OTHER}, activity_id=1,
        )
        self.assertTrue(sql.startswith("SELECT "))
        self.assertIn("COUNT(*)", sql)
        self.assertNotIn("INSERT", sql.upper())
        self.assertIn("GROUP BY", sql)
        self.assertEqual(sql.count("?"), len(args))
        mysql, values = build_state_summary_statement(
            year=2026, states={"present", OTHER}, activity_id=1,
            placeholder="%s",
        )
        self.assertEqual(mysql.count("%s"), len(values))
        self.assertEqual(values, args)
        self.assertEqual(
            build_state_summary_statement(year=2026, states=()),
            (None, ()),
        )

    def test_preserves_temporary_database_after_all_readers(self):
        before = self.fixture.dump()
        for code in CATALOG_DOMAINS:
            self.catalog.search(code)
        for year in (2026, 2027):
            self.summary.summary(year=year)
            self.summary.summary(year=year, states={OTHER})
        self.assertEqual(before, self.fixture.dump())


class C16NativeQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.fixture = C16FictivePlanningDatabase()
        self.addCleanup(self.fixture.close)
        self.holder = tempfile.TemporaryDirectory(prefix="noethys-c16-settings-")
        self.addCleanup(self.holder.cleanup)
        settings = QSettings(
            str(Path(self.holder.name) / "c16.ini"), QSettings.Format.IniFormat
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            self.window = NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path,
                source_label="C16 DATA COMPLETEMENT FICTIVES",
                requested_theme="light",
                read_only_demo=True, background_queries=False,
                finance_enabled=True, catalog_enabled=True,
                c15_enabled=True, c16_enabled=True, badge_logs_enabled=True,
            )
        self.addCleanup(self.window.close)
        self.window.show()
        self.app.processEvents()

    def _wait(self, predicate, message, seconds=5):
        stop = time.monotonic() + seconds
        while time.monotonic() < stop:
            self.app.processEvents()
            if predicate():
                return
            QTest.qWait(20)
        self.fail("C16 Qt timeout : " + message)

    def test_c16_four_new_entries_and_old_navigation_preserved(self):
        self.assertEqual(len(C16_NAVIGATION), 4)
        self.assertEqual(self.window.navigation.count(), 22)
        for code in ("planning", "tariff_records", "consumption_reports", "badge_journal"):
            index = next(
                i for i in range(self.window.navigation.count())
                if self.window.navigation.item(i).data(Qt.ItemDataRole.UserRole) == code
            )
            self.assertTrue(
                self.window.navigation.item(index).flags() & Qt.ItemFlag.ItemIsEnabled
            )
            self.window.navigate(code)
        self.assertIs(self.window.stack.currentWidget(),
                      self.window.catalog_pages["badge_journal"])

    def test_all_five_lists_readable_without_edits(self):
        for code in C16_CATALOG_MODULES:
            self.window.navigate(code)
            hub = self.window.catalog_pages[code]
            for kind, page in hub.pages.items():
                with self.subTest(kind=kind):
                    hub.tabs.setCurrentWidget(page)
                    page.activate()
                    self.assertEqual({r.id for r in page.model.rows}, EXPECTED[kind])
                    self.assertEqual(
                        page.table.editTriggers(),
                        QAbstractItemView.EditTrigger.NoEditTriggers,
                    )

    def test_navigation_links_activity_sql_key_not_name(self):
        self.window.navigate("planning")
        page = self.window.catalog_pages["planning"].current_page
        index = next(i for i, r in enumerate(page.model.rows) if r.id == 601)
        page.table.selectRow(index)
        self.assertTrue(page.activity_button.isEnabled())
        page.activity_button.click()
        self.assertEqual(self.window.inscriptions_page._filters["activity_id"], 1)
        self.assertEqual(
            {r.id for r in self.window.inscriptions_page.model.rows}, {501, 503}
        )
        self.window.return_to_context()
        self.assertIs(
            self.window.stack.currentWidget(), self.window.catalog_pages["planning"],
        )

    def test_tariffs_browse_exact_activity_and_preserve_selected_row(self):
        self.window.navigate("tariff_records")
        hub = self.window.catalog_pages["tariff_records"]
        hub.current_page.activity_spin.setValue(1)
        self.assertEqual(
            {r.id for r in hub.current_page.model.rows}, {801, 803}
        )
        hub.tabs.setCurrentWidget(hub.pages["tariff_lines"])
        self.assertEqual(
            {r.id for r in hub.current_page.model.rows}, {901, 902, 903}
        )
        hub.current_page.activity_spin.setValue(1)
        self.assertEqual(
            {r.id for r in hub.current_page.model.rows}, {901, 903}
        )
        hub.current_page.table.selectRow(0)
        row = hub.current_page.selected_row().id
        hub.current_page.refresh()
        self.assertEqual(hub.current_page.selected_row().id, row)

    def test_report_has_all_clickable_states_and_exact_first_total(self):
        self.window.navigate("consumption_reports")
        page = self.window.report_page
        page.year_spin.setValue(2026)
        self.assertEqual(len(page.state_checks), 7)
        self.assertEqual(page.selected_states, ALL_STATES)
        self.assertEqual(page.last_result.total, 112)
        self.assertTrue(page.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers)

    def test_state_checkboxes_control_count_without_implicit_code(self):
        self.window.navigate("consumption_reports")
        page = self.window.report_page
        page.year_spin.setValue(2026)
        page.none_button.click()
        self.assertFalse(page.selected_states)
        self.assertEqual(page.last_result.total, 0)
        self.assertIn("aucune requête SQL", page.summary.text())
        page.state_checks["present"].click()
        self.assertEqual(page.selected_states, {"present"})
        self.assertEqual(page.last_result.total, 16)
        page.state_checks[OTHER].click()
        self.assertEqual(page.selected_states, {"present", OTHER})
        self.assertEqual(page.last_result.total, 41)
        page.all_button.click()
        self.assertEqual(page.selected_states, ALL_STATES)
        self.assertEqual(page.last_result.total, 112)

    def test_activity_and_year_filters_do_not_leak_across_menu(self):
        self.window.navigate("consumption_reports")
        page = self.window.report_page
        page.year_spin.setValue(2027)
        page.activity_spin.setValue(2)
        self.assertEqual(page.last_result.total, 2)
        self.window.navigate("planning")
        self.window.navigate("consumption_reports")
        self.assertEqual(page.activity_spin.value(), 0)
        self.assertEqual(page.last_result.total, 3)
        self.assertEqual(page.year_spin.value(), 2027)

    def test_badgeage_disabled_unless_explicitly_enabled(self):
        with patch(
            "noethys_qt.noethys_native.QSettings",
            return_value=QSettings(
                str(Path(self.holder.name) / "no-badges.ini"),
                QSettings.Format.IniFormat,
            ),
        ):
            separate = NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path,
                source_label="C16 BASE FICTIVE", requested_theme="light",
                background_queries=False, read_only_demo=True,
                c15_enabled=True, c16_enabled=True,
                badge_logs_enabled=False,
            )
        self.addCleanup(separate.close)
        self.assertNotIn("badge_journal", separate.catalog_pages)
        self.assertFalse(separate.catalog_actions["badge_journal"].isEnabled())
        badge = next(
            separate.navigation.item(i)
            for i in range(separate.navigation.count())
            if separate.navigation.item(i).data(Qt.ItemDataRole.UserRole) == "badge_journal"
        )
        self.assertFalse(badge.flags() & Qt.ItemFlag.ItemIsEnabled)
        separate.navigate("badge_journal")
        self.assertIs(separate.stack.currentWidget(), separate.home_page)
        with self.assertRaisesRegex(ValueError, "fixture temporaire fictive"):
            NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path,
                source_label="Aucun droit réel",
                background_queries=False,
                read_only_demo=False, c15_enabled=True,
                c16_enabled=True, badge_logs_enabled=True,
            )

    def test_report_does_not_use_a_limited_list_of_consumptions(self):
        self.window.navigate("consumption_reports")
        page = self.window.report_page
        page.year_spin.setValue(2026)
        self.assertEqual(page.last_result.total, 112)
        self.assertEqual(sum(row.count for row in page.model.rows), 112)
        self.assertEqual(len(page.model.rows), 7)

    def test_whole_shell_is_read_only_and_fixture_unchanged(self):
        before = self.fixture.dump()
        self.assertFalse(self.window.activities_action.isEnabled())
        for code in C16_CATALOG_MODULES:
            self.window.navigate(code)
            hub = self.window.catalog_pages[code]
            for page in hub.pages.values():
                hub.tabs.setCurrentWidget(page)
                page.activate()
        self.window.navigate("consumption_reports")
        self.window.report_page.none_button.click()
        self.window.report_page.all_button.click()
        self.window.navigate("home")
        self.assertEqual(before, self.fixture.dump())

    def test_old_c13_c14_c15_still_open_on_c16_fixture(self):
        for code, kind, expected in (
            ("billing", "invoices", {501, 502, 503, 990}),
            ("memberships", "fees", {1001, 1002, 1003}),
            ("certificates", "certificates", {7001, 7002, 7003}),
        ):
            self.window.navigate(code)
            hub = (
                self.window.finance_pages[code]
                if code == "billing"
                else self.window.catalog_pages[code]
            )
            self.assertEqual(
                hub.current_page.kind, kind
            )
            self.assertEqual(
                {r.id for r in hub.current_page.model.rows}, expected
            )


if __name__ == "__main__":
    unittest.main()
