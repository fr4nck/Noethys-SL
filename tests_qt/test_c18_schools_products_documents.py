"""C18 : scolarité, produits et pièces — SQL + Qt, 100 % inventés."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.c18_sensitive_guard import C18_MARKER, require_c18_synthetic_source
from noethys_qt.catalog_readonly_core import (
    CATALOG_DOMAINS, CATALOG_MODULES, C17_DOMAIN_CODES, C17_MODULE_CODES,
    C18_CATALOG_MODULES, C18_RESTRICTED_DOMAINS,
    C18_RESTRICTED_MODULES, C18_INDIVIDUAL_LINK_DOMAINS,
    CatalogRepository, build_catalog_query,
)
from noethys_qt.catalog_readonly_ui import CatalogTableModel
from noethys_qt.noethys_native import C18_NAVIGATION, NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c18_fixture import C18FictiveRegistryDatabase


EXPECTED = {
    "schools": {201, 202, 203},
    "school_classes": {401, 402, 403},
    "school_levels": {301, 302, 303},
    "school_history": {5011, 5012, 5013, 5014},
    "product_inventory": {1, 2, 3},
    "product_categories": {71, 72, 73},
    "document_types": {801, 802, 803},
    "documents_metadata": {9011, 9012, 9013, 9014},
}


class C18SqlTests(unittest.TestCase):
    def setUp(self):
        self.fixture = C18FictiveRegistryDatabase()
        self.addCleanup(self.fixture.close)
        self.reader = CatalogRepository(
            self.fixture.repository.editor_repository, sensitive_allowed=True
        )

    def test_eight_domains_and_five_new_module_contracts(self):
        self.assertEqual(set(CATALOG_DOMAINS) - C17_DOMAIN_CODES, set(EXPECTED))
        self.assertEqual(
            set(CATALOG_MODULES) - C17_MODULE_CODES, set(C18_CATALOG_MODULES)
        )
        self.assertEqual(len(C18_CATALOG_MODULES), 5)
        self.assertEqual(C18_RESTRICTED_MODULES, {"school_history", "document_records"})
        self.assertEqual(C18_RESTRICTED_DOMAINS,
                         {"school_history", "documents_metadata"})
        self.assertEqual(C18_INDIVIDUAL_LINK_DOMAINS,
                         {"school_history", "documents_metadata"})

    def test_all_eight_catalogs_read_from_existing_select_engine(self):
        for kind, wanted in EXPECTED.items():
            with self.subTest(kind=kind):
                answer = self.reader.search(kind)
                self.assertEqual({row.id for row in answer.rows}, wanted)
                self.assertFalse(answer.truncated)
                self.assertTrue(all(row.kind == kind for row in answer.rows))

    def test_school_and_classes_show_source_values_without_inference(self):
        ecole = next(row for row in self.reader.search("schools").rows if row.id == 201)
        self.assertEqual(ecole.value("name"), "École fictive des Ajoncs")
        self.assertEqual(ecole.value("sectors"), "1,3")
        groups = self.reader.search("school_classes", year=2027).rows
        self.assertEqual({r.id for r in groups}, {403})
        levels = self.reader.search("school_levels").rows
        self.assertEqual({r.value("short") for r in levels}, {"PS", "CP", "CE1"})

    def test_individual_school_filter_is_numeric_and_exact(self):
        rows = self.reader.search("school_history", individual_id=10).rows
        self.assertEqual({r.id for r in rows}, {5011})
        self.assertEqual(rows[0].value("school"), "École fictive des Ajoncs")
        self.assertEqual(rows[0].value("individual"), 10)
        self.assertEqual(
            {r.id for r in self.reader.search("school_history", year=2027).rows},
            {5013},
        )

    def test_products_are_source_quantities_not_available_stock(self):
        entries = {r.id: r for r in self.reader.search("product_inventory").rows}
        self.assertEqual(entries[1].value("quantity"), 17)
        self.assertEqual(entries[1].value("sharing"), 1)
        self.assertEqual(entries[2].value("amount"), "1000.0003")
        self.assertEqual(entries[3].value("quantity"), 0)
        self.assertEqual(
            {r.id for r in self.reader.search("product_categories").rows},
            {71, 72, 73},
        )

    def test_decimal_display_preserves_stored_amount_text(self):
        rows = self.reader.search("product_inventory").rows
        model = CatalogTableModel("product_inventory")
        model.replace_rows(rows)
        i = next(i for i, row in enumerate(rows) if row.id == 2)
        self.assertEqual(model.data(model.index(i, 4)), "1000,0003")

    def test_document_types_do_not_emit_file_bodies(self):
        types = self.reader.search("document_types").rows
        entry = next(row for row in types if row.id == 802)
        self.assertEqual(entry.value("public"), "famille")
        self.assertEqual(entry.value("duration"), "6 mois")
        self.assertEqual(len(entry.values), 5)

    def test_document_family_and_individual_ids_not_merged(self):
        self.assertEqual(
            {r.id for r in self.reader.search("documents_metadata", family_id=100).rows},
            {9012, 9014},
        )
        self.assertEqual(
            {r.id for r in self.reader.search("documents_metadata", individual_id=10).rows},
            {9011},
        )
        self.assertEqual(
            {r.id for r in self.reader.search(
                "documents_metadata", family_id=100, individual_id=13
            ).rows}, {9014},
        )
        self.assertEqual(
            self.reader.search(
                "documents_metadata", family_id=100, individual_id=10
            ).rows, (),
        )

    def test_document_dates_are_stored_not_expiration_verdict(self):
        rows = self.reader.search("documents_metadata", year=2027).rows
        self.assertEqual({r.id for r in rows}, {9013})
        entry = rows[0]
        self.assertEqual(entry.value("end"), "2028-01-01")
        self.assertEqual(entry.value("family"), 101)
        self.assertEqual(entry.value("individual"), 11)

    def test_disallowed_family_filter_never_opens_connection(self):
        with patch.object(
            self.reader.editor_repository, "_connect",
            side_effect=AssertionError("SQL connection forbidden"),
        ):
            for kind, opts in (
                ("school_history", {"family_id": 100}),
                ("schools", {"individual_id": 10}),
                ("document_types", {"individual_id": 10}),
                ("product_inventory", {"activity_id": 1}),
                ("documents_metadata", {"individual_id": True}),
                ("school_history", {"individual_id": 0}),
                ("school_history", {"individual_id": "10"}),
                ("school_history", {"individual_id": -1}),
                ("school_history", {"year": 2099}),
                ("product_categories", {"limit": 251}),
            ):
                with self.subTest(kind=kind, opts=opts):
                    with self.assertRaises(ValueError):
                        self.reader.search(kind, **opts)

    def test_restricted_sql_requires_flag_before_connect(self):
        reader = CatalogRepository(self.fixture.repository.editor_repository)
        with patch.object(
            reader.editor_repository, "_connect",
            side_effect=AssertionError("Sensitive SQL must not be reached"),
        ):
            for domain in C18_RESTRICTED_DOMAINS:
                with self.subTest(domain=domain):
                    with self.assertRaises(PermissionError):
                        reader.search(domain)

    def test_parameterized_search_sqlite_and_mysql(self):
        statement, params = build_catalog_query(
            "documents_metadata", family_id=100, individual_id=13,
            year=2026, text="Pièce", limit=5,
        )
        self.assertEqual(statement.count("?"), len(params))
        self.assertNotIn("Pièce", statement)
        self.assertEqual(params[:4], (100, 13, "2026-01-01", "2027-01-01"))
        self.assertEqual(params[-1], 6)
        mysql, bindings = build_catalog_query(
            "school_history", individual_id=10, text="fictive",
            placeholder="%s",
        )
        self.assertEqual(mysql.count("%s"), len(bindings))
        self.assertIn("ESCAPE '!'", mysql)
        self.assertEqual(
            self.reader.search("schools", text="' OR 1=1 --").rows, ()
        )
        # C14 contient intentionnellement un produit avec les caracteres
        # litteraux %_ : la recherche doit le retrouver, sans wildcard SQL.
        self.assertEqual(
            {r.id for r in self.reader.search("product_inventory", text="%_").rows},
            {1},
        )
        self.assertEqual(self.reader.search("product_inventory", text="absent%_").rows, ())

    def test_limit_plus_one_signals_truncation(self):
        result = self.reader.search("schools", limit=1)
        self.assertEqual(len(result.rows), 1)
        self.assertTrue(result.truncated)

    def test_sensitive_guard_requires_real_temporary_marker(self):
        self.assertTrue(require_c18_synthetic_source(
            self.fixture.path, read_only_demo=True, c18_enabled=True
        ))
        # SQLite Connection.__exit__ ne ferme PAS la connexion sous
        # Windows. closing() est indispensable avant le cleanup de
        # TemporaryDirectory (sinon WinError 32 en CI).
        with closing(sqlite3.connect(self.fixture.path)) as conn:
            marker = conn.execute("SELECT token FROM c18_marker").fetchone()
        self.assertEqual(marker, (C18_MARKER,))

    def test_sensitive_guard_rejects_normal_execution(self):
        for options in (
            {"read_only_demo": False, "c18_enabled": True},
            {"read_only_demo": True, "c18_enabled": False},
        ):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    require_c18_synthetic_source(self.fixture.path, **options)

    def test_sensitive_guard_rejects_unmarked_temporary_file(self):
        with tempfile.TemporaryDirectory(prefix="noethys-qt-c8-fictif-unmarked-") as tmp:
            fake = Path(tmp) / "C8_DEMONSTRATION_FICTIVE.sqlite"
            # Transaction commitée puis HANDLE explicitement fermé ;
            # un simple "with sqlite3.connect" n'appelle pas close().
            with closing(sqlite3.connect(fake)) as conn, conn:
                conn.execute("CREATE TABLE c18_marker(token TEXT)")
                conn.execute("INSERT INTO c18_marker VALUES ('UNTRUSTED')")
            with self.assertRaises(ValueError):
                require_c18_synthetic_source(
                    fake, read_only_demo=True, c18_enabled=True
                )

    def test_readonly_all_domains_leave_source_byte_for_byte(self):
        before = self.fixture.dump()
        for kind in CATALOG_DOMAINS:
            self.reader.search(kind)
        self.assertEqual(before, self.fixture.dump())


class C18QtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.fixture = C18FictiveRegistryDatabase()
        self.addCleanup(self.fixture.close)
        self.config = tempfile.TemporaryDirectory(prefix="c18-qt-settings-")
        self.addCleanup(self.config.cleanup)
        settings = QSettings(
            str(Path(self.config.name) / "c18.ini"), QSettings.Format.IniFormat
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
                badge_logs_enabled=False,
                source_label="C18 — DONNÉES FICTIVES",
            )
        self.addCleanup(self.window.close)
        self.window.show()
        self.app.processEvents()

    def _wait(self, predicate, name, seconds=6):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            self.app.processEvents()
            if predicate():
                return
            QTest.qWait(20)
        self.fail("C18 Qt timeout: " + name)

    def test_navigation_has_28_entries_not_duplicate_shell(self):
        self.assertEqual(len(C18_NAVIGATION), 5)
        self.assertEqual(self.window.navigation.count(), 28)
        for code in C18_CATALOG_MODULES:
            with self.subTest(code=code):
                self.window.navigate(code)
                self.assertIs(
                    self.window.stack.currentWidget(),
                    self.window.catalog_pages[code],
                )

    def test_all_eight_catalog_tables_are_non_editable(self):
        for code in C18_CATALOG_MODULES:
            hub = self.window.catalog_pages[code]
            self.window.navigate(code)
            for kind, page in hub.pages.items():
                with self.subTest(kind=kind):
                    hub.tabs.setCurrentWidget(page)
                    page.activate()
                    self.assertEqual({r.id for r in page.model.rows}, EXPECTED[kind])
                    self.assertEqual(
                        page.table.editTriggers(),
                        QAbstractItemView.EditTrigger.NoEditTriggers,
                    )

    def test_individual_context_uses_exact_key_and_is_reset_by_global_menu(self):
        self.window.catalog_pages["school_history"].set_individual_context(10)
        self.window.navigate("school_history")
        page = self.window.catalog_pages["school_history"].current_page
        # Direct menu navigation intentionally clears any existing context.
        self.assertIsNone(page._individual_id)
        self.window.catalog_pages["school_history"].set_individual_context(10)
        self.assertEqual({r.id for r in page.model.rows}, {5011})
        self.window.navigate("home")
        self.window.navigate("school_history")
        self.assertIsNone(page._individual_id)
        self.assertEqual({r.id for r in page.model.rows}, EXPECTED["school_history"])

    def test_family_context_uses_exact_foreign_key(self):
        self.window.navigate("document_records")
        hub = self.window.catalog_pages["document_records"]
        hub.set_family_context(100)
        self.assertEqual(
            {r.id for r in hub.current_page.model.rows}, {9012, 9014}
        )
        self.window.navigate("home")
        self.window.navigate("document_records")
        self.assertEqual(
            {r.id for r in hub.current_page.model.rows}, EXPECTED["documents_metadata"]
        )

    def test_fiche_individu_shortcut_school_history_is_reversible(self):
        self.window._individual_requested(10)
        self._wait(
            lambda: self.window.details_page.loaded_kind == "individual"
            and self.window.details_page.current_id == 10,
            "fiche individu",
        )
        self.window.details_page.individual_catalog_buttons["school_history"].click()
        target = self.window.catalog_pages["school_history"].current_page
        self.assertIs(
            self.window.stack.currentWidget(),
            self.window.catalog_pages["school_history"],
        )
        self.assertEqual(target._individual_id, 10)
        self.assertEqual({r.id for r in target.model.rows}, {5011})
        self.window.return_to_context()
        self._wait(
            lambda: self.window.details_page.loaded_kind == "individual"
            and self.window.details_page.current_id == 10,
            "retour individu",
        )

    def test_individual_link_from_school_history_preserves_selection(self):
        self.window.navigate("school_history")
        page = self.window.catalog_pages["school_history"].current_page
        i = next(i for i, row in enumerate(page.model.rows) if row.id == 5012)
        page.table.selectRow(i)
        self.assertTrue(page.individual_button.isEnabled())
        page.individual_button.click()
        self._wait(
            lambda: self.window.details_page.loaded_kind == "individual"
            and self.window.details_page.current_id == 11,
            "fiche individu liée",
        )
        self.window.return_to_context()
        self.assertEqual(page.selected_row().id, 5012)

    def test_document_row_exact_family_and_individual_link(self):
        self.window.navigate("document_records")
        page = self.window.catalog_pages["document_records"].current_page
        i = next(i for i, row in enumerate(page.model.rows) if row.id == 9014)
        page.table.selectRow(i)
        self.assertTrue(page.family_button.isEnabled())
        self.assertTrue(page.individual_button.isEnabled())
        page.family_button.click()
        self._wait(
            lambda: self.window.details_page.loaded_kind == "family"
            and self.window.details_page.current_id == 100,
            "famille via document",
        )
        self.window.return_to_context()
        self.assertEqual(page.selected_row().id, 9014)

    def test_product_selection_does_not_enable_person_buttons(self):
        self.window.navigate("product_registry")
        page = self.window.catalog_pages["product_registry"].current_page
        page.table.selectRow(0)
        self.assertFalse(page.family_button.isVisible())
        self.assertFalse(page.individual_button.isVisible())
        self.assertFalse(page.activity_button.isVisible())

    def test_normal_configuration_hides_all_personal_modules(self):
        settings = QSettings(
            str(Path(self.config.name) / "no-sensitive.ini"),
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
            )
        self.addCleanup(safe.close)
        self.assertEqual(safe.navigation.count(), 28)
        self.assertEqual(
            set(safe.catalog_pages) & C18_RESTRICTED_MODULES, set()
        )
        for code in C18_RESTRICTED_MODULES:
            self.assertFalse(safe.catalog_actions[code].isEnabled())
            self.assertNotIn(code, safe.catalog_pages)
        with self.assertRaises(PermissionError):
            safe.catalog_repository.search("documents_metadata")

    def test_guard_cannot_be_overridden_on_real_profile(self):
        with self.assertRaises(ValueError):
            NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path,
                read_only_demo=False, background_queries=False,
                c18_enabled=True, c18_sensitive_enabled=True,
            )

    def test_c17_overview_and_c16_states_remain_valid(self):
        self.window.navigate("activity_overview")
        self.assertEqual(
            {r.id for r in self.window.catalog_pages[
                "activity_overview"
            ].current_page.model.rows}, {1, 2}
        )
        self.window.navigate("consumption_reports")
        self.window.report_page.year_spin.setValue(2026)
        self.assertEqual(self.window.report_page.last_result.total, 112)

    def test_c14_product_location_remains_linked_by_id(self):
        self.window.navigate("rentals")
        self.assertEqual(
            {r.id for r in self.window.catalog_pages["rentals"].current_page.model.rows},
            {4001, 4002, 4003},
        )
        self.window.navigate("product_registry")
        self.assertEqual(
            {r.id for r in self.window.catalog_pages["product_registry"].current_page.model.rows},
            {1, 2, 3},
        )

    def test_sqlite_is_not_altered_by_tabs_or_detail_links(self):
        before = self.fixture.dump()
        for code in C18_CATALOG_MODULES:
            self.window.navigate(code)
            hub = self.window.catalog_pages[code]
            for page in hub.pages.values():
                hub.tabs.setCurrentWidget(page)
                page.activate()
        self.window.navigate("home")
        self.assertEqual(before, self.fixture.dump())
        self.assertFalse(self.window.activities_action.isEnabled())


if __name__ == "__main__":
    unittest.main()
