"""C19 — référentiels métier en lecture seule et confidentialité sur fixtures.

Toutes les bases sont créées sous TemporaryDirectory et détruites ensuite.
Aucun fichier familial, compte bancaire réel, configuration réseau ou .nod.
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
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QAbstractItemView, QApplication

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.c19_sensitive_guard import (
    C19_MARKER, require_c19_synthetic_source,
)
from noethys_qt.catalog_readonly_core import (
    CATALOG_DOMAINS, CATALOG_MODULES, C18_DOMAIN_CODES,
    C18_MODULE_CODES, C19_CATALOG_MODULES, C19_RESTRICTED_MODULES,
    C19_RESTRICTED_DOMAINS, CatalogRepository, build_catalog_query,
)
from noethys_qt.catalog_readonly_ui import CatalogTableModel
from noethys_qt.noethys_native import C19_NAVIGATION, NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c19_fixture import C19FictiveRegistryDatabase


EXPECTED = {
    "accounting_periods": {11, 12, 13},
    "analytic_sections": {21, 22, 23},
    "accounting_categories": {41, 42, 43},
    "ledger_accounts": {31, 32, 33},
    "budget_definitions": {101, 102, 103},
    "budget_categories": {201, 202, 203, 204},
    "payment_modes_settings": {1, 2},
    "bank_accounts_metadata": {1, 2},
    "banks_directory": {301, 302, 303},
    "social_regimes": {401, 402},
    "allowance_funds": {501, 502, 503},
    "geographic_sectors": {601, 602, 603},
}
PRIVATE = "DEMO_SECRET_"


class C19SqlContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = C19FictiveRegistryDatabase()
        self.addCleanup(self.fixture.close)
        self.reader = CatalogRepository(
            self.fixture.repository.editor_repository,
            sensitive_allowed=True, c19_sensitive_allowed=True,
        )

    def test_exactly_twelve_domains_and_four_modules(self):
        self.assertEqual(set(CATALOG_DOMAINS) - C18_DOMAIN_CODES, set(EXPECTED))
        self.assertEqual(
            set(CATALOG_MODULES) - C18_MODULE_CODES, set(C19_CATALOG_MODULES)
        )
        self.assertEqual(len(C19_CATALOG_MODULES), 4)
        self.assertEqual(sum(map(len, (
            domains for _label, domains in C19_CATALOG_MODULES.values()
        ))), 12)

    def test_all_twelve_catalogs_use_existing_reader(self):
        for kind, expected_ids in EXPECTED.items():
            with self.subTest(kind=kind):
                result = self.reader.search(kind)
                self.assertEqual({row.id for row in result.rows}, expected_ids)
                self.assertFalse(result.truncated)
                self.assertTrue(all(row.kind == kind for row in result.rows))

    def test_financial_domains_restricted_but_organisations_public(self):
        self.assertEqual(C19_RESTRICTED_MODULES, {
            "accounting_settings", "budget_settings", "payment_settings",
        })
        self.assertEqual(
            C19_RESTRICTED_DOMAINS,
            set(EXPECTED) - {"social_regimes", "allowance_funds", "geographic_sectors"},
        )

    def test_budget_filter_uses_exact_foreign_key_not_name(self):
        for budget_id, wanted in (
            (101, {201, 202}), (102, {203}), (103, {204}),
        ):
            with self.subTest(budget_id=budget_id):
                rows = self.reader.search("budget_categories", budget_id=budget_id).rows
                self.assertEqual({row.id for row in rows}, wanted)
                self.assertTrue(all(row.value("budget_id") == budget_id for row in rows))
        self.assertEqual(
            self.reader.search("budget_categories", budget_id=999).rows, ()
        )

    def test_budget_formula_is_never_executed_or_calculated(self):
        rows = self.reader.search("budget_categories", budget_id=101).rows
        raw = next(row for row in rows if row.id == 202)
        self.assertEqual(raw.value("stored_value"), "800 + {NBRE_UNITE_11}")
        value = next(
            row for row in self.reader.search("budget_categories").rows if row.id == 203
        ).value("stored_value")
        self.assertEqual(value, "1000.0003")
        self.assertNotIsInstance(value, float)

    def test_year_is_creation_start_year_not_financial_period_overlap(self):
        self.assertEqual(
            {row.id for row in self.reader.search("accounting_periods", year=2026).rows},
            {11},
        )
        self.assertEqual(
            {row.id for row in self.reader.search("budget_definitions", year=2026).rows},
            {101, 103},
        )
        self.assertEqual(
            {row.id for row in self.reader.search("budget_definitions", year=2027).rows},
            {102},
        )

    def test_ledger_account_numbers_are_strings_not_money(self):
        row = next(
            row for row in self.reader.search("ledger_accounts").rows if row.id == 31
        )
        self.assertEqual(row.value("number"), "706100")
        self.assertEqual(row.value("name"), "Prestation imaginaire")
        self.assertEqual(
            next(row for row in self.reader.search("accounting_categories").rows
                 if row.id == 41).value("ledger_id"), 31,
        )

    def test_funds_join_keeps_unmatched_regime_as_null(self):
        rows = self.reader.search("allowance_funds").rows
        orphan = next(row for row in rows if row.id == 503)
        self.assertEqual(orphan.value("regime_id"), 999)
        self.assertIsNone(orphan.value("regime"))
        self.assertEqual(
            next(row for row in rows if row.id == 501).value("regime"),
            "Régime inventé général",
        )

    def test_payment_fees_preserve_decimal_strings(self):
        rows = {row.id: row for row in self.reader.search("payment_modes_settings").rows}
        self.assertEqual(rows[1].value("fee_amount"), "12.005")
        self.assertEqual(rows[2].value("fee_percent"), "1.0003")
        model = CatalogTableModel("payment_modes_settings")
        model.replace_rows((rows[1], rows[2]))
        self.assertEqual(model.data(model.index(0, 5)), "12,005")
        self.assertEqual(model.data(model.index(1, 6)), "1,0003")

    def test_bank_sensitive_identifiers_are_never_fetched_or_displayed(self):
        spec = CATALOG_DOMAINS["bank_accounts_metadata"]
        sql = spec.sql.lower()
        for secret_column in (".iban", ".bic", ".numero", "cle_rib", "dft_iban"):
            self.assertNotIn(secret_column, sql)
        rows = self.reader.search("bank_accounts_metadata").rows
        serialized = repr(tuple(row.values for row in rows))
        self.assertNotIn(PRIVATE, serialized)
        self.assertEqual({row.value("name") for row in rows},
                         {"Banque A fictive", "Banque B fictive"})
        # Valeurs tests présentes seulement dans la fixture : lecture métier
        # ne doit ni les SELECT ni les copier dans les artefacts.
        with sqlite3.connect(self.fixture.path) as db:
            sentinel = db.execute(
                "SELECT iban FROM comptes_bancaires WHERE IDcompte=1"
            ).fetchone()[0]
        self.assertTrue(sentinel.startswith(PRIVATE))
        self.assertNotIn(sentinel, serialized)

    def test_search_parameters_and_like_specials_are_escaped(self):
        sql, params = build_catalog_query(
            "budget_categories", budget_id=101, text="800 + {NBRE_UNITE_11}",
        )
        self.assertNotIn("800 +", sql)
        self.assertEqual(sql.count("?"), len(params))
        self.assertEqual(params[0], 101)
        self.assertIn("ESCAPE '!'", sql)
        self.assertEqual(
            {row.id for row in self.reader.search(
                "budget_categories", budget_id=101, text="800 + {NBRE_UNITE_11}"
            ).rows}, {202}
        )
        self.assertEqual(
            self.reader.search("budget_categories", text="' OR 1=1 --").rows,
            (),
        )
        self.assertEqual(
            self.reader.search("payment_modes_settings", text="%_").rows,
            (),
        )

    def test_mysql_placeholders_for_budget_and_year(self):
        sql, params = build_catalog_query(
            "budget_categories", budget_id=102,
            placeholder="%s", text="1000",
        )
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params[0], 102)
        self.assertIn("LIMIT %s", sql)
        dates, vals = build_catalog_query(
            "accounting_periods", year=2026, placeholder="%s",
        )
        self.assertEqual(vals[:2], ("2026-01-01", "2027-01-01"))
        self.assertEqual(dates.count("%s"), len(vals))

    def test_invalid_budget_filters_rejected_before_connection(self):
        with patch.object(
            self.reader.editor_repository, "_connect",
            side_effect=AssertionError("NO CONNECTION SHOULD OPEN"),
        ):
            for code, filters in (
                ("budget_categories", {"budget_id": -1}),
                ("budget_categories", {"budget_id": 0}),
                ("budget_categories", {"budget_id": True}),
                ("budget_categories", {"budget_id": "101"}),
                ("budget_definitions", {"budget_id": 101}),
                ("accounting_periods", {"budget_id": 101}),
                ("budget_categories", {"year": 2026}),
                ("ledger_accounts", {"activity_id": 1}),
                ("geographic_sectors", {"family_id": 100}),
                ("bank_accounts_metadata", {"individual_id": 10}),
                ("payment_modes_settings", {"limit": 251}),
                ("budget_categories", {"text": "x" * 121}),
            ):
                with self.subTest(code=code, filters=filters):
                    with self.assertRaises(ValueError):
                        self.reader.search(code, **filters)

    def test_financial_module_rejected_before_sql_connection(self):
        reader = CatalogRepository(self.fixture.repository.editor_repository)
        with patch.object(
            reader.editor_repository, "_connect",
            side_effect=AssertionError("NO CONNECTION SHOULD OPEN"),
        ):
            for code in C19_RESTRICTED_DOMAINS:
                with self.subTest(code=code), self.assertRaises(PermissionError):
                    reader.search(code)

    def test_nonfinancial_registries_still_accessible_without_override(self):
        reader = CatalogRepository(self.fixture.repository.editor_repository)
        for code in ("social_regimes", "allowance_funds", "geographic_sectors"):
            with self.subTest(code=code):
                self.assertEqual(
                    {row.id for row in reader.search(code).rows}, EXPECTED[code],
                )

    def test_fixture_guard_rejects_real_mode_and_bad_path(self):
        self.assertTrue(require_c19_synthetic_source(
            self.fixture.path, read_only_demo=True,
            c18_enabled=True, c19_enabled=True,
        ))
        for args in (
            {"read_only_demo": False, "c18_enabled": True, "c19_enabled": True},
            {"read_only_demo": True, "c18_enabled": False, "c19_enabled": True},
            {"read_only_demo": True, "c18_enabled": True, "c19_enabled": False},
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                require_c19_synthetic_source(self.fixture.path, **args)

    def test_fixture_guard_fails_for_unmarked_copy(self):
        with tempfile.TemporaryDirectory(prefix="noethys-c19-unmarked-") as temp:
            file = Path(temp) / "C8_DEMONSTRATION_FICTIVE.sqlite"
            file.touch()
            with self.assertRaises(ValueError):
                require_c19_synthetic_source(
                    file, read_only_demo=True,
                    c18_enabled=True, c19_enabled=True,
                )

    def test_schema_does_not_use_user_provided_table_names(self):
        for kind in EXPECTED:
            sql = CATALOG_DOMAINS[kind].sql
            self.assertTrue(sql.startswith("SELECT "))
            self.assertNotIn(" FROM (SELECT ", sql.upper())
            self.assertNotIn("INSERT INTO", sql.upper())
            self.assertNotIn("UPDATE ", sql.upper())
            self.assertNotIn("DELETE ", sql.upper())
            self.assertEqual(
                len(CATALOG_DOMAINS[kind].headers), len(CATALOG_DOMAINS[kind].keys),
            )

    def test_selected_rows_never_infer_a_live_account_balance(self):
        values = {r.id: r for r in self.reader.search("bank_accounts_metadata").rows}
        self.assertEqual(values[1].value("default"), 1)
        self.assertEqual(values[2].value("default"), 0)
        self.assertEqual(len(values[1].values), 4)

    def test_truncation_uses_server_limit_plus_one(self):
        result = self.reader.search("budget_categories", limit=1)
        self.assertEqual(len(result.rows), 1)
        self.assertTrue(result.truncated)

    def test_c18_scolarite_and_c13_finance_unchanged(self):
        school = self.reader.search("schools").rows
        self.assertEqual({r.id for r in school}, {201, 202, 203})
        finance = self.fixture.repository.editor_repository
        self.assertIsNotNone(finance)

    def test_every_c19_select_keeps_full_temporary_source_unchanged(self):
        before = self.fixture.dump()
        for code in EXPECTED:
            self.reader.search(code)
        self.reader.search("budget_categories", budget_id=101)
        self.assertEqual(before, self.fixture.dump())


class C19QtModulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.fixture = C19FictiveRegistryDatabase()
        self.addCleanup(self.fixture.close)
        self.settings_directory = tempfile.TemporaryDirectory(prefix="c19-qt-settings-")
        self.addCleanup(self.settings_directory.cleanup)
        settings = QSettings(
            str(Path(self.settings_directory.name) / "c19.ini"),
            QSettings.Format.IniFormat,
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            self.window = NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path,
                requested_theme="light",
                read_only_demo=True, background_queries=False,
                finance_enabled=True, catalog_enabled=True,
                c15_enabled=True, c16_enabled=True, c17_enabled=True,
                c18_enabled=True, c18_sensitive_enabled=True,
                c19_enabled=True, c19_sensitive_enabled=True,
                badge_logs_enabled=False,
                source_label="C19 — 100 POUR CENT DONNÉES INVENTÉES",
            )
        self.addCleanup(self.window.close)
        self.window.show()
        self.app.processEvents()

    def test_c19_four_new_entries_in_same_native_shell(self):
        self.assertEqual(len(C19_NAVIGATION), 4)
        self.assertEqual(self.window.navigation.count(), 32)
        for code in C19_CATALOG_MODULES:
            with self.subTest(code=code):
                index = next(
                    index for index in range(self.window.navigation.count())
                    if self.window.navigation.item(index).data(
                        Qt.ItemDataRole.UserRole
                    ) == code
                )
                self.assertTrue(
                    self.window.navigation.item(index).flags()
                    & Qt.ItemFlag.ItemIsEnabled
                )
                self.window.navigate(code)
                self.assertIs(
                    self.window.stack.currentWidget(), self.window.catalog_pages[code],
                )

    def test_each_twelve_tabs_is_read_only_and_complete(self):
        for module in C19_CATALOG_MODULES:
            self.window.navigate(module)
            hub = self.window.catalog_pages[module]
            for code, page in hub.pages.items():
                with self.subTest(code=code):
                    hub.tabs.setCurrentWidget(page)
                    page.activate()
                    self.assertEqual({r.id for r in page.model.rows}, EXPECTED[code])
                    self.assertEqual(
                        page.table.editTriggers(),
                        QAbstractItemView.EditTrigger.NoEditTriggers,
                    )

    def test_budget_row_opens_only_its_own_categories(self):
        self.window.navigate("budget_settings")
        hub = self.window.catalog_pages["budget_settings"]
        source = hub.pages["budget_definitions"]
        target = hub.pages["budget_categories"]
        self.assertEqual(hub.current_page.kind, "budget_definitions")
        index = next(i for i, row in enumerate(source.model.rows) if row.id == 101)
        source.table.selectRow(index)
        self.assertTrue(source.budget_button.isEnabled())
        source.budget_button.click()
        self.assertIs(hub.current_page, target)
        self.assertEqual(target.budget_spin.value(), 101)
        self.assertEqual(target._budget_id, 101)
        self.assertEqual({r.id for r in target.model.rows}, {201, 202})
        hub.tabs.setCurrentWidget(source)
        self.assertEqual(source.selected_row().id, 101)

    def test_manual_budget_filter_uses_numeric_exact_key(self):
        self.window.navigate("budget_settings")
        hub = self.window.catalog_pages["budget_settings"]
        hub.tabs.setCurrentWidget(hub.pages["budget_categories"])
        page = hub.current_page
        self.assertTrue(page.budget_spin.isVisible())
        page.budget_spin.setValue(102)
        self.assertEqual({r.id for r in page.model.rows}, {203})
        page.budget_spin.setValue(103)
        self.assertEqual({r.id for r in page.model.rows}, {204})
        page.budget_spin.setValue(0)
        self.assertEqual({r.id for r in page.model.rows}, {201, 202, 203, 204})

    def test_budget_context_does_not_leak_when_menu_reopened(self):
        self.window.navigate("budget_settings")
        hub = self.window.catalog_pages["budget_settings"]
        page = hub.pages["budget_categories"]
        hub.tabs.setCurrentWidget(page)
        page.budget_spin.setValue(101)
        self.assertEqual({r.id for r in page.model.rows}, {201, 202})
        self.window.navigate("home")
        self.window.navigate("budget_settings")
        self.assertEqual(page.budget_spin.value(), 0)
        hub.tabs.setCurrentWidget(page)
        self.assertEqual({r.id for r in page.model.rows}, EXPECTED["budget_categories"])

    def test_selection_unchanged_does_not_reset_qt_model(self):
        self.window.navigate("organisation_settings")
        page = self.window.catalog_pages["organisation_settings"].current_page
        spy = QSignalSpy(page.model.modelReset)
        page.table.selectRow(0)
        original = page.selected_row().id
        page.refresh()
        self.assertEqual(spy.count(), 0)
        self.assertEqual(page.selected_row().id, original)

    def test_restricted_modules_hidden_without_synthetic_authorization(self):
        settings = QSettings(
            str(Path(self.settings_directory.name) / "c19-safe.ini"),
            QSettings.Format.IniFormat,
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            safe = NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path,
                read_only_demo=True, background_queries=False,
                c15_enabled=True, c16_enabled=True, c17_enabled=True,
                c18_enabled=True, c18_sensitive_enabled=False,
                c19_enabled=True, c19_sensitive_enabled=False,
                badge_logs_enabled=False,
            )
        self.addCleanup(safe.close)
        self.assertEqual(safe.navigation.count(), 32)
        for module in C19_RESTRICTED_MODULES:
            with self.subTest(module=module):
                self.assertNotIn(module, safe.catalog_pages)
                self.assertFalse(safe.catalog_actions[module].isEnabled())
                index = next(
                    i for i in range(safe.navigation.count())
                    if safe.navigation.item(i).data(Qt.ItemDataRole.UserRole) == module
                )
                self.assertFalse(
                    safe.navigation.item(index).flags() & Qt.ItemFlag.ItemIsEnabled
                )
        self.assertIn("organisation_settings", safe.catalog_pages)
        with self.assertRaises(PermissionError):
            safe.catalog_repository.search("bank_accounts_metadata")

    def test_restricted_mode_rejected_on_non_demo_configuration(self):
        with self.assertRaises(ValueError):
            NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path, read_only_demo=False,
                background_queries=False,
                c18_enabled=True, c19_enabled=True,
                c19_sensitive_enabled=True,
            )

    def test_safe_module_remains_enabled_with_restricted_modules_closed(self):
        settings = QSettings(
            str(Path(self.settings_directory.name) / "c19-safe-2.ini"),
            QSettings.Format.IniFormat,
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            safe = NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path, read_only_demo=True,
                background_queries=False,
                c15_enabled=True, c16_enabled=True, c17_enabled=True,
                c18_enabled=True, c19_enabled=True,
                c18_sensitive_enabled=False, c19_sensitive_enabled=False,
            )
        self.addCleanup(safe.close)
        safe.navigate("organisation_settings")
        hub = safe.catalog_pages["organisation_settings"]
        self.assertIs(safe.stack.currentWidget(), hub)
        self.assertEqual(
            {r.id for r in hub.current_page.model.rows}, {401, 402}
        )

    def test_bank_metadata_view_does_not_expose_secret_fields(self):
        self.window.navigate("payment_settings")
        hub = self.window.catalog_pages["payment_settings"]
        hub.tabs.setCurrentWidget(hub.pages["bank_accounts_metadata"])
        page = hub.current_page
        self.assertEqual(page.model.columnCount(), 4)
        text = " ".join(
            str(page.model.data(page.model.index(i, j)) or "")
            for i in range(page.model.rowCount())
            for j in range(page.model.columnCount())
        )
        self.assertNotIn(PRIVATE, text)
        self.assertNotIn("IBAN", text.upper())
        self.assertEqual({r.id for r in page.model.rows}, {1, 2})

    def test_c18_sensitive_and_c17_overview_are_not_regressed(self):
        self.window.navigate("school_history")
        self.assertEqual(
            {r.id for r in self.window.catalog_pages[
                "school_history"
            ].current_page.model.rows}, {5011, 5012, 5013, 5014},
        )
        self.window.navigate("activity_overview")
        self.assertEqual(
            {r.id for r in self.window.catalog_pages[
                "activity_overview"
            ].current_page.model.rows}, {1, 2},
        )

    def test_c16_state_counts_and_c13_finance_not_regressed(self):
        self.window.navigate("consumption_reports")
        self.window.report_page.year_spin.setValue(2026)
        self.assertEqual(self.window.report_page.last_result.total, 112)
        self.window.navigate("billing")
        self.assertEqual(
            {r.id for r in self.window.finance_pages[
                "billing"
            ].current_page.model.rows}, {501, 502, 503, 990},
        )

    def test_organisation_not_a_family_lookup(self):
        self.window.navigate("organisation_settings")
        hub = self.window.catalog_pages["organisation_settings"]
        for page in hub.pages.values():
            hub.tabs.setCurrentWidget(page)
            page.table.selectRow(0)
            self.assertFalse(page.family_button.isVisible())
            self.assertFalse(page.individual_button.isVisible())
            self.assertFalse(page.activity_button.isVisible())

    def test_no_business_mutation_on_all_c19_tabs(self):
        before = self.fixture.dump()
        self.assertFalse(self.window.activities_action.isEnabled())
        for module in C19_CATALOG_MODULES:
            self.window.navigate(module)
            hub = self.window.catalog_pages[module]
            for page in hub.pages.values():
                hub.tabs.setCurrentWidget(page)
                page.activate()
        self.window.navigate("budget_settings")
        hub = self.window.catalog_pages["budget_settings"]
        hub.pages["budget_definitions"].table.selectRow(0)
        hub.pages["budget_definitions"].budget_button.click()
        self.window.navigate("home")
        self.assertEqual(before, self.fixture.dump())

    def test_c19_menus_and_actions_have_exact_labels(self):
        self.assertEqual(
            self.window.catalog_actions["budget_settings"].text(),
            "Budgets enregistrés",
        )
        self.assertTrue(self.window.catalog_actions["payment_settings"].isEnabled())
        self.assertFalse(self.window.catalog_actions["badge_journal"].isEnabled())


if __name__ == "__main__":
    unittest.main()
