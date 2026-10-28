"""C14 : SQL administratif et coque native Qt sur bases 100 % inventées.

Aucun test n'accède à un fichier .nod, Config.json, réseau ou données réelles.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.catalog_readonly_core import (
    CATALOG_DOMAINS, CATALOG_MODULES, C14_DOMAIN_CODES,
    C14_MODULE_CODES, CatalogRepository, build_catalog_query,
    validate_catalog_query,
)
from noethys_qt.noethys_native import NAVIGATION, NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c14_catalog_fixture import C14FictiveCatalogDatabase


EXPECTED = {
    "fees": {1001, 1002, 1003},
    "fee_types": {1, 2},
    "contracts": {2001, 2002, 2003, 2004},
    "quotients": {3001, 3002, 3003},
    "quotient_types": {1, 2},
    "rentals": {4001, 4002, 4003},
    "rental_requests": {4101, 4102},
    "orders": {5001, 5002},
    "quotes": {6001, 6002, 6003},
}


class C14CatalogSqlTests(unittest.TestCase):
    def setUp(self):
        self.db = C14FictiveCatalogDatabase()
        self.addCleanup(self.db.close)
        self.repository = CatalogRepository(self.db.repository.editor_repository)

    def test_all_nine_catalog_tables_are_readable(self):
        self.assertEqual(set(C14_DOMAIN_CODES), set(EXPECTED))
        for kind, wanted in EXPECTED.items():
            with self.subTest(kind=kind):
                result = self.repository.search(kind)
                self.assertEqual({row.id for row in result.rows}, wanted)
                self.assertFalse(result.truncated)
                self.assertTrue(all(row.kind == kind for row in result.rows))

    def test_separate_family_scopes_and_orphan_not_attributed(self):
        expected = {
            "fees": {1001, 1003},
            "contracts": {2001, 2003},
            "quotients": {3001, 3003},
            "rentals": {4001, 4003},
            "rental_requests": {4101},
            "quotes": {6001, 6003},
        }
        for kind, wanted in expected.items():
            with self.subTest(kind=kind):
                results = self.repository.search(kind, family_id=100).rows
                self.assertEqual({row.id for row in results}, wanted)
                self.assertTrue(all(row.value("family") == 100 for row in results))
        self.assertIsNone(next(
            row for row in self.repository.search("contracts").rows if row.id == 2004
        ).value("family"))

    def test_types_and_orders_never_accept_a_family_scope(self):
        for kind in ("fee_types", "quotient_types", "orders"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.repository.search(kind, family_id=100)

    def test_year_filters_use_exact_source_date_and_clear_bounds(self):
        expected = {
            "fees": {1003},
            "contracts": {2003},
            "quotients": {3003},
            "rentals": {4003},
            "orders": {5002},
            "quotes": {6003},
        }
        for kind, wanted in expected.items():
            with self.subTest(kind=kind):
                got = {row.id for row in self.repository.search(kind, year=2027).rows}
                self.assertEqual(got, wanted)
        for kind in ("fee_types", "quotient_types"):
            with self.assertRaises(ValueError):
                self.repository.search(kind, year=2027)

    def test_cotisations_keep_individual_and_family_ids_separate(self):
        rows = {r.id: r for r in self.repository.search("fees").rows}
        self.assertEqual(rows[1001].value("family"), 100)
        self.assertIsNone(rows[1001].value("individual"))
        self.assertEqual(rows[1002].value("individual"), 11)
        self.assertEqual(rows[1003].value("individual"), 12)

    def test_contract_reuses_exact_inscription_id(self):
        rows = {r.id: r for r in self.repository.search("contracts").rows}
        self.assertEqual(rows[2001].value("inscription"), 501)
        self.assertEqual(rows[2003].value("inscription"), 503)
        self.assertEqual(rows[2004].value("inscription"), 999)

    def test_precision_is_preserved_without_sums_or_rounding(self):
        from noethys_qt.catalog_readonly_ui import CatalogTableModel
        from PySide6.QtCore import Qt
        records = self.repository.search("quotients", family_id=100).rows
        model = CatalogTableModel("quotients")
        model.replace_rows(records)
        q = next(i for i, row in enumerate(records) if row.id == 3001)
        self.assertEqual(model.data(model.index(q, 4), int(Qt.ItemDataRole.DisplayRole)), "12,005")
        self.assertEqual(model.data(model.index(q, 5), int(Qt.ItemDataRole.DisplayRole)), "1000,0003")
        quotes = self.repository.search("quotes", year=2027).rows
        self.assertEqual(str(quotes[0].value("total")), "1000.0003")

    def test_sql_uses_parameters_for_text_year_family_and_limit(self):
        sql, args = build_catalog_query(
            "fees", family_id=100, year=2026, text="CARTE-100", limit=5,
        )
        self.assertEqual(args, (100, "2026-01-01", "2027-01-01", "%CARTE-100%",
                                "%CARTE-100%", "%CARTE-100%", "%CARTE-100%", 6))
        self.assertEqual(sql.count("?"), len(args))
        self.assertIn("LIMIT ?", sql)
        self.assertNotIn("CARTE-100", sql)
        self.assertNotIn("100", sql)

    def test_percent_underscore_and_exclamation_are_literal(self):
        self.assertEqual(
            {r.id for r in self.repository.search("rentals", text="%_ !").rows},
            {4001},
        )
        self.assertEqual(
            {r.id for r in self.repository.search("rentals", text="' OR 1=1 --").rows},
            set(),
        )

    def test_mysql_placeholder_is_supported_without_opening_mysql(self):
        sql, params = build_catalog_query(
            "quotes", family_id=101, year=2026, text="DEV", placeholder="%s"
        )
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params[0], 101)
        self.assertIn("ESCAPE '!'", sql)

    def test_invalid_ids_and_fields_are_rejected_before_connection(self):
        with patch.object(
            self.repository.editor_repository, "_connect",
            side_effect=AssertionError("Doit rester déconnecté"),
        ):
            bad = (
                ("fees", {"family_id": True}),
                ("contracts", {"family_id": -2}),
                ("contracts", {"family_id": "100"}),
                ("quotients", {"year": 2099}),
                ("quotients", {"year": False}),
                ("orders", {"text": "X" * 121}),
                ("orders", {"limit": 0}),
                ("orders", {"limit": 251}),
                ("not_a_table", {}),
                ("fee_types", {"family_id": 100}),
            )
            for kind, options in bad:
                with self.subTest(kind=kind, options=options):
                    with self.assertRaises(ValueError):
                        self.repository.search(kind, **options)

    def test_bounded_rows_never_claim_full_population(self):
        result = self.repository.search("fees", limit=1)
        self.assertEqual(len(result.rows), 1)
        self.assertTrue(result.truncated)

    def test_sqlite_connection_is_query_only_and_closed(self):
        editor = self.repository.editor_repository
        connect = editor._connect
        observed = []
        def connect_spy():
            connection, placeholder = connect()
            observed.append(connection)
            return connection, placeholder
        with patch.object(editor, "_connect", side_effect=connect_spy):
            self.repository.search("quotes")
        self.assertEqual(len(observed), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            observed[0].execute("SELECT 1")

    def test_fixture_unchanged_after_all_sql_reads(self):
        before = self.db.dump()
        for kind in C14_DOMAIN_CODES:
            self.repository.search(kind)
        self.assertEqual(before, self.db.dump())

    def test_no_sql_table_or_column_is_generated_from_user_input(self):
        for kind, spec in CATALOG_DOMAINS.items():
            with self.subTest(kind=kind):
                self.assertEqual(len(spec.headers), len(spec.keys))
                self.assertTrue(spec.sql.upper().startswith("SELECT "))
                self.assertNotIn(";", spec.sql)
                self.assertNotIn("INTO ", spec.sql.upper())
                self.assertEqual(spec.keys[0], "id")
        for module, (_label, kinds) in CATALOG_MODULES.items():
            self.assertTrue(kinds, module)
            self.assertTrue(set(kinds).issubset(CATALOG_DOMAINS))


class C14NativeCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.db = C14FictiveCatalogDatabase()
        self.addCleanup(self.db.close)
        settings_dir = tempfile.TemporaryDirectory(prefix="noethys-c14-test-settings-")
        self.addCleanup(settings_dir.cleanup)
        settings = QSettings(
            str(Path(settings_dir.name) / "c14.ini"), QSettings.Format.IniFormat
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            self.window = NoethysQtWindow(
                PeopleSearchRepository(self.db.repository.editor_repository),
                SqliteActivityRepository(self.db.path),
                editor_sqlite_path=self.db.path, source_label="C14 FAKE DATA ONLY",
                requested_theme="light", read_only_demo=True,
                background_queries=False, catalog_enabled=True,
            )
        self.addCleanup(self.window.close)
        self.window.show()
        self.app.processEvents()

    def _wait(self, test, label="signal Qt", seconds=4):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            self.app.processEvents()
            if test():
                return
            QTest.qWait(20)
        self.fail("C14 timeout : " + label)

    def _family(self, ident=100):
        self.window._family_requested(ident)
        self._wait(
            lambda: self.window.details_page.loaded_kind == "family"
            and self.window.details_page.current_id == ident,
            "fiche famille",
        )
        return self.window.details_page

    def test_six_new_modules_are_in_native_shell(self):
        self.assertEqual(len(NAVIGATION), 14)
        self.assertEqual(self.window.navigation.count(), 14)
        for module in C14_MODULE_CODES:
            with self.subTest(module=module):
                row = next(
                    i for i in range(self.window.navigation.count())
                    if self.window.navigation.item(i).data(Qt.ItemDataRole.UserRole) == module
                )
                self.assertTrue(
                    self.window.navigation.item(row).flags() & Qt.ItemFlag.ItemIsEnabled
                )
                self.window.navigate(module)
                self.assertIs(
                    self.window.stack.currentWidget(), self.window.catalog_pages[module]
                )

    def test_nine_catalog_lists_render_without_editing(self):
        for module, hub in self.window.catalog_pages.items():
            self.window.navigate(module)
            for kind, page in hub.pages.items():
                with self.subTest(module=module, kind=kind):
                    hub.tabs.setCurrentWidget(page)
                    page.activate()
                    self.assertEqual(
                        {r.id for r in page.model.rows}, EXPECTED[kind]
                    )
                    self.assertEqual(
                        page.table.editTriggers(),
                        QAbstractItemView.EditTrigger.NoEditTriggers,
                    )

    def test_family_shortcuts_open_exact_family_scope(self):
        family = self._family(100)
        for module in ("memberships", "contracts", "quotients", "rentals", "quotes"):
            with self.subTest(module=module):
                family.catalog_buttons[module].click()
                hub = self.window.catalog_pages[module]
                self.assertIs(self.window.stack.currentWidget(), hub)
                self.assertEqual(hub.current_page._family_id, 100)
                self.assertTrue(all(
                    row.value("family") == 100 for row in hub.current_page.model.rows
                ))
                self.window.return_to_context()
                self._wait(
                    lambda: self.window.details_page.loaded_kind == "family"
                    and self.window.details_page.current_id == 100,
                    "retour famille",
                )

    def test_global_module_click_clears_stale_family_scope(self):
        self._family().catalog_buttons["memberships"].click()
        hub = self.window.catalog_pages["memberships"]
        self.assertEqual(hub.current_page._family_id, 100)
        self.window.navigate("home")
        self.window.navigate("memberships")
        self.assertIsNone(hub.current_page._family_id)
        self.assertEqual(
            {r.id for r in hub.current_page.model.rows}, EXPECTED["fees"]
        )
        self.assertEqual(self.window._context_history, [])

    def test_selected_contract_links_to_existing_inscriptions(self):
        self.window.navigate("contracts")
        page = self.window.catalog_pages["contracts"].current_page
        idx = next(i for i, row in enumerate(page.model.rows) if row.id == 2001)
        page.table.selectRow(idx)
        self.assertTrue(page.inscription_button.isEnabled())
        page.inscription_button.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.inscriptions_page)
        self.assertEqual(self.window.inscriptions_page._filters["family_id"], 100)
        self.assertEqual(self.window.inscriptions_page._filters["individual_id"], 10)
        self.window.return_to_context()
        self.assertIs(self.window.stack.currentWidget(), self.window.catalog_pages["contracts"])

    def test_orphan_contract_does_not_fake_a_family_or_navigate(self):
        self.window.navigate("contracts")
        page = self.window.catalog_pages["contracts"].current_page
        idx = next(i for i, row in enumerate(page.model.rows) if row.id == 2004)
        page.table.selectRow(idx)
        self.assertFalse(page.family_button.isEnabled())
        previous = self.window.stack.currentWidget()
        page.inscription_button.click()
        self.assertIs(self.window.stack.currentWidget(), previous)
        self.assertEqual(self.window._context_history, [])

    def test_catalog_row_opens_family_and_returns_with_selection(self):
        self.window.navigate("quotes")
        hub = self.window.catalog_pages["quotes"]
        idx = next(i for i, row in enumerate(hub.current_page.model.rows) if row.id == 6001)
        hub.current_page.table.selectRow(idx)
        hub.current_page.family_button.click()
        self._wait(lambda: self.window.details_page.loaded_kind == "family"
                   and self.window.details_page.current_id == 100)
        self.window.return_to_context()
        self.assertIs(self.window.stack.currentWidget(), hub)
        self.assertEqual(hub.current_page.selected_row().id, 6001)

    def test_ctrl_f_targets_current_catalog_search(self):
        self.window.navigate("rentals")
        self.window.focus_current_search()
        self.assertIs(
            self.app.focusWidget(),
            self.window.catalog_pages["rentals"].current_page.search_edit,
        )

    def test_year_and_text_filters_preserve_one_query_semantics(self):
        self.window.navigate("quotes")
        page = self.window.catalog_pages["quotes"].current_page
        with patch.object(page.repository, "search", wraps=page.repository.search) as query:
            page.year_spin.setValue(2027)
            self.assertEqual({r.id for r in page.model.rows}, {6003})
            self.assertEqual(query.call_count, 1)
            page.search_edit.setText("DEV-FAKE-03")
            page.timer.stop()
            page.refresh()
            self.assertEqual({r.id for r in page.model.rows}, {6003})
            self.assertEqual(query.call_count, 2)

    def test_unchanged_rows_do_not_reset_table_model(self):
        from PySide6.QtTest import QSignalSpy
        self.window.navigate("memberships")
        page = self.window.catalog_pages["memberships"].current_page
        model_reset = QSignalSpy(page.model.modelReset)
        page.refresh()
        self.assertEqual(model_reset.count(), 0)

    def test_readonly_isolation_preserves_sqlite_bytes(self):
        original = self.db.dump()
        self.assertTrue(self.window.read_only_demo)
        self.assertFalse(self.window.activities_action.isEnabled())
        for module, hub in self.window.catalog_pages.items():
            self.window.navigate(module)
            for page in hub.pages.values():
                hub.tabs.setCurrentWidget(page)
                page.activate()
                self.assertEqual(
                    page.table.editTriggers(),
                    QAbstractItemView.EditTrigger.NoEditTriggers,
                )
        self.window.navigate("home")
        self.assertEqual(original, self.db.dump())

    def test_c13_financial_tabs_still_work_with_c14_fixture(self):
        self.window.navigate("billing")
        self.assertEqual(
            {x.id for x in self.window.finance_pages["billing"].current_page.model.rows},
            {501, 502, 503, 990},
        )


if __name__ == "__main__":
    unittest.main()
