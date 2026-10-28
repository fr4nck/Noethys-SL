"""C15 : SQL et coque Qt sur fixtures temporaires entièrement inventées.

Aucun utilisateur ni fichier Noethys réel. Toutes les requêtes métier C15
sont des SELECT ; chiffres d'effectifs = comptages bruts, pas statistiques.
"""
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
from PySide6.QtWidgets import QApplication, QAbstractItemView

from noethys_qt.activities_prototype import SqliteActivityRepository
from noethys_qt.catalog_readonly_core import (
    CATALOG_DOMAINS, CATALOG_MODULES, C14_DOMAIN_CODES, C14_MODULE_CODES,
    C15_ACTIVITY_MODULES, C15_ACTIVITY_LINK_DOMAINS, CatalogRepository,
    build_catalog_query,
)
from noethys_qt.catalog_readonly_ui import CatalogTableModel
from noethys_qt.noethys_native import C15_NAVIGATION, NAVIGATION, NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c15_modules_fixture import C15FictiveModulesDatabase


C15_EXPECTED = {
    "membership_expiries": {1001, 1002, 1003},
    "membership_units": {1, 2},
    "certificates": {7001, 7002, 7003},
    "activity_units": {11, 12, 13},
    "activity_groups": {21, 22, 23},
    "activity_tariff_categories": {1, 2, 3},
    "enrollment_counts": {1, 2},
    "consumption_counts": {1, 2},
}
C15_MODULES_EXPECTED = {
    "renewals", "certificates", "activity_settings", "headcounts"
}


class C15SqlModuleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = C15FictiveModulesDatabase()
        self.addCleanup(self.fixture.close)
        self.reader = CatalogRepository(self.fixture.repository.editor_repository)

    def test_c15_declares_exactly_eight_new_domains(self):
        self.assertEqual(set(CATALOG_DOMAINS) - C14_DOMAIN_CODES, set(C15_EXPECTED))
        self.assertEqual(set(CATALOG_MODULES) - C14_MODULE_CODES, C15_MODULES_EXPECTED)
        self.assertEqual(len(CATALOG_MODULES), 10)

    def test_read_all_new_tables_using_existing_reader(self):
        for code, expected in C15_EXPECTED.items():
            with self.subTest(code=code):
                result = self.reader.search(code)
                self.assertEqual({row.id for row in result.rows}, expected)
                self.assertFalse(result.truncated)
                self.assertTrue(all(row.kind == code for row in result.rows))

    def test_family_scopes_are_exact_and_never_inferred(self):
        self.assertEqual(
            {r.id for r in self.reader.search("membership_expiries", family_id=100).rows},
            {1001, 1003},
        )
        self.assertEqual(
            {r.id for r in self.reader.search("certificates", family_id=101).rows},
            {7002},
        )
        with self.assertRaises(ValueError):
            self.reader.search("enrollment_counts", family_id=100)
        with self.assertRaises(ValueError):
            self.reader.search("activity_units", family_id=100)
        with self.assertRaises(ValueError):
            self.reader.search("membership_units", family_id=100)

    def test_annual_filter_is_based_only_on_stored_dates(self):
        self.assertEqual(
            {r.id for r in self.reader.search("membership_expiries", year=2027).rows},
            {1001, 1003},
        )
        self.assertEqual(
            {r.id for r in self.reader.search("certificates", year=2027).rows},
            {7003},
        )
        self.assertEqual(
            {r.id for r in self.reader.search("activity_units", year=2027).rows},
            {13},
        )
        with self.assertRaises(ValueError):
            self.reader.search("enrollment_counts", year=2027)
        with self.assertRaises(ValueError):
            self.reader.search("membership_units", year=2027)

    def test_activity_filter_uses_exact_sql_key(self):
        expected = {
            "activity_units": {11, 13},
            "activity_groups": {21, 23},
            "activity_tariff_categories": {1, 3},
            "enrollment_counts": {1},
            "consumption_counts": {1},
        }
        for code, ids in expected.items():
            with self.subTest(code=code):
                rows = self.reader.search(code, activity_id=1).rows
                self.assertEqual({row.id for row in rows}, ids)
                self.assertTrue(rows)
        for code in ("certificates", "membership_expiries", "membership_units"):
            with self.assertRaises(ValueError):
                self.reader.search(code, activity_id=1)

    def test_count_is_technical_rows_not_distinct_children_or_priced_services(self):
        inscriptions = {r.id: r for r in self.reader.search("enrollment_counts").rows}
        self.assertEqual(inscriptions[1].value("enrollments"), 2)
        self.assertEqual(inscriptions[1].value("status_ok"), 2)
        self.assertEqual(inscriptions[2].value("enrollments"), 3)
        self.assertEqual(inscriptions[2].value("status_ok"), 2)
        consumptions = {r.id: r for r in self.reader.search("consumption_counts").rows}
        self.assertEqual(consumptions[1].value("consumptions"), 56)
        self.assertEqual(consumptions[2].value("consumptions"), 56)
        self.assertEqual(consumptions[1].value("present"), 8)
        self.assertEqual(consumptions[2].value("present"), 8)

    def test_source_precision_is_never_recalculated_or_rounded(self):
        units = self.reader.search("membership_units").rows
        model = CatalogTableModel("membership_units")
        model.replace_rows(units)
        r1 = next(i for i, x in enumerate(units) if x.id == 1)
        self.assertEqual(model.data(model.index(r1, 4)), "12,005")
        r2 = next(i for i, x in enumerate(units) if x.id == 2)
        self.assertEqual(model.data(model.index(r2, 4)), "1000,0003")
        records = self.reader.search("certificates", family_id=100).rows
        self.assertEqual(
            next(r for r in records if r.id == 7003).value("balance"), "995.0003"
        )
        self.assertEqual(
            next(r for r in records if r.id == 7003).value("total"), "1000.0003"
        )

    def test_sql_parameters_and_literal_wildcards_prevent_broadening(self):
        statement, params = build_catalog_query(
            "activity_units", activity_id=1, year=2027,
            text="Séance", limit=7,
        )
        self.assertEqual(
            params,
            (1, "2027-01-01", "2028-01-01", "%Séance%", "%Séance%",
             "%Séance%", 8),
        )
        self.assertEqual(statement.count("?"), len(params))
        self.assertNotIn("Séance", statement)
        injection = "' OR 1=1 --"
        self.assertEqual(
            self.reader.search("certificates", text=injection).rows, ()
        )
        self.assertEqual(
            self.reader.search("activity_units", text="%_").rows, ()
        )
        mysql, bindings = build_catalog_query(
            "certificates", family_id=100, year=2027,
            text="ATT", placeholder="%s",
        )
        self.assertEqual(mysql.count("%s"), len(bindings))
        self.assertIn("ESCAPE '!'", mysql)

    def test_invalid_filters_refused_before_opening_connection(self):
        with patch.object(self.reader.editor_repository, "_connect",
                          side_effect=AssertionError("connexion interdite")):
            for code, options in (
                ("activity_units", {"activity_id": True}),
                ("activity_units", {"activity_id": 0}),
                ("activity_units", {"activity_id": -3}),
                ("activity_units", {"activity_id": "1"}),
                ("activity_units", {"family_id": 100}),
                ("certificates", {"activity_id": 1}),
                ("headcounts", {}),
                ("membership_expiries", {"year": 2099}),
                ("certificates", {"text": "X" * 121}),
                ("enrollment_counts", {"limit": 251}),
            ):
                with self.subTest(code=code, options=options):
                    with self.assertRaises(ValueError):
                        self.reader.search(code, **options)

    def test_no_one_shot_full_table_read_is_mislabeled_complete(self):
        result = self.reader.search("certificates", limit=1)
        self.assertEqual(len(result.rows), 1)
        self.assertTrue(result.truncated)
        self.assertTrue(all(row.id in C15_EXPECTED["certificates"] for row in result.rows))

    def test_activity_configuration_keeps_source_rows_and_links(self):
        unit = next(
            r for r in self.reader.search("activity_units").rows if r.id == 13
        )
        self.assertEqual(unit.value("activity_id"), 1)
        self.assertEqual(unit.value("name"), "Séance fictive")
        group = next(
            r for r in self.reader.search("activity_groups").rows if r.id == 22
        )
        self.assertEqual(group.value("activity_id"), 2)
        self.assertEqual(group.value("capacity"), 16)
        categories = self.reader.search("activity_tariff_categories", activity_id=1).rows
        self.assertEqual({r.value("name") for r in categories},
                         {"Tarif foyer fictif", "Tarif social fictif"})
        self.assertTrue(set(C15_ACTIVITY_LINK_DOMAINS).issubset(CATALOG_DOMAINS))

    def test_read_only_source_unchanged_after_all_new_and_old_domains(self):
        before = self.fixture.dump()
        for code in CATALOG_DOMAINS:
            with self.subTest(code=code):
                self.reader.search(code)
        self.assertEqual(before, self.fixture.dump())


class C15NativeModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.fixture = C15FictiveModulesDatabase()
        self.addCleanup(self.fixture.close)
        holder = tempfile.TemporaryDirectory(prefix="noethys-c15-qt-settings-")
        self.addCleanup(holder.cleanup)
        settings = QSettings(
            str(Path(holder.name) / "c15.ini"), QSettings.Format.IniFormat
        )
        with patch("noethys_qt.noethys_native.QSettings", return_value=settings):
            self.window = NoethysQtWindow(
                PeopleSearchRepository(self.fixture.repository.editor_repository),
                SqliteActivityRepository(self.fixture.path),
                editor_sqlite_path=self.fixture.path,
                requested_theme="light", source_label="C15 FAKE DATA ONLY",
                read_only_demo=True, background_queries=False,
                catalog_enabled=True, c15_enabled=True,
            )
        self.addCleanup(self.window.close)
        self.window.show()
        self.app.processEvents()

    def _wait(self, predicate, message="interface Qt", seconds=5):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.app.processEvents()
            if predicate():
                return
            QTest.qWait(20)
        self.fail("C15 Qt attente : " + message)

    def _family(self, identity=100):
        self.window._family_requested(identity)
        self._wait(
            lambda: self.window.details_page.loaded_kind == "family"
            and self.window.details_page.current_id == identity,
            "fiche famille",
        )
        return self.window.details_page

    def test_four_modules_are_real_native_navigation_entries(self):
        self.assertEqual(len(C15_NAVIGATION), 4)
        self.assertEqual(len(NAVIGATION), 14)  # Compatibilité C14 inchangée
        self.assertEqual(self.window.navigation.count(), 18)
        for code in C15_MODULES_EXPECTED:
            with self.subTest(code=code):
                index = next(
                    x for x in range(self.window.navigation.count())
                    if self.window.navigation.item(x).data(Qt.ItemDataRole.UserRole) == code
                )
                self.assertTrue(
                    self.window.navigation.item(index).flags()
                    & Qt.ItemFlag.ItemIsEnabled
                )
                self.window.navigate(code)
                self.assertIs(
                    self.window.stack.currentWidget(), self.window.catalog_pages[code]
                )

    def test_eight_new_lists_are_noneditable(self):
        for code in C15_MODULES_EXPECTED:
            self.window.navigate(code)
            panel = self.window.catalog_pages[code]
            for kind, page in panel.pages.items():
                with self.subTest(code=code, kind=kind):
                    panel.tabs.setCurrentWidget(page)
                    page.activate()
                    self.assertEqual({r.id for r in page.model.rows}, C15_EXPECTED[kind])
                    self.assertEqual(
                        page.table.editTriggers(),
                        QAbstractItemView.EditTrigger.NoEditTriggers,
                    )
                    self.assertFalse(page.model.rows and
                                     page.model.rowCount() > 250)

    def test_family_shortcuts_are_exact_and_reversible(self):
        page = self._family()
        for code, expected in (("renewals", {1001, 1003}),
                               ("certificates", {7001, 7003})):
            with self.subTest(code=code):
                page.catalog_buttons[code].click()
                hub = self.window.catalog_pages[code]
                self.assertIs(self.window.stack.currentWidget(), hub)
                self.assertEqual(hub.current_page._family_id, 100)
                self.assertEqual(
                    {r.id for r in hub.current_page.model.rows}, expected
                )
                self.window.return_to_context()
                self._wait(
                    lambda: self.window.details_page.loaded_kind == "family"
                    and self.window.details_page.current_id == 100,
                    "retour fiche famille",
                )

    def test_global_menu_clears_previous_family_context(self):
        self._family().catalog_buttons["renewals"].click()
        panel = self.window.catalog_pages["renewals"]
        self.assertEqual(panel.current_page._family_id, 100)
        self.window.navigate("home")
        self.window.navigate("renewals")
        self.assertIsNone(panel.current_page._family_id)
        self.assertEqual(
            {r.id for r in panel.current_page.model.rows}, {1001, 1002, 1003}
        )

    def test_activity_filters_are_numeric_and_do_not_leak_between_modules(self):
        self.window.navigate("activity_settings")
        hub = self.window.catalog_pages["activity_settings"]
        unit = hub.current_page
        self.assertTrue(unit.activity_spin.isVisible())
        unit.activity_spin.setValue(1)
        self.assertEqual({r.id for r in unit.model.rows}, {11, 13})
        hub.tabs.setCurrentIndex(1)
        group = hub.current_page
        group.activity_spin.setValue(2)
        self.assertEqual({r.id for r in group.model.rows}, {22})
        self.window.navigate("headcounts")
        counts = self.window.catalog_pages["headcounts"].current_page
        self.assertIsNone(counts._activity_id)
        self.assertEqual({r.id for r in counts.model.rows}, {1, 2})

    def test_activity_row_opens_existing_inscription_reader(self):
        self.window.navigate("activity_settings")
        page = self.window.catalog_pages["activity_settings"].current_page
        index = next(i for i, row in enumerate(page.model.rows) if row.id == 11)
        page.table.selectRow(index)
        self.assertTrue(page.activity_button.isEnabled())
        page.activity_button.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.inscriptions_page)
        self.assertEqual(self.window.inscriptions_page._filters["activity_id"], 1)
        self.assertEqual(
            {r.id for r in self.window.inscriptions_page.model.rows}, {501, 503}
        )
        self.window.return_to_context()
        self.assertIs(
            self.window.stack.currentWidget(),
            self.window.catalog_pages["activity_settings"]
        )

    def test_headcounts_activity_link_uses_exact_primary_id(self):
        self.window.navigate("headcounts")
        page = self.window.catalog_pages["headcounts"].current_page
        index = next(i for i, row in enumerate(page.model.rows) if row.id == 2)
        page.table.selectRow(index)
        self.assertTrue(page.activity_button.isEnabled())
        page.activity_button.click()
        self.assertEqual(self.window.inscriptions_page._filters["activity_id"], 2)
        self.assertEqual(
            {r.id for r in self.window.inscriptions_page.model.rows}, {502, 504, 505}
        )
        self.window.return_to_context()
        self.assertIs(
            self.window.stack.currentWidget(),
            self.window.catalog_pages["headcounts"]
        )

    def test_family_opened_from_certificate_returns_to_same_selected_row(self):
        self.window.navigate("certificates")
        page = self.window.catalog_pages["certificates"].current_page
        index = next(i for i, row in enumerate(page.model.rows) if row.id == 7003)
        page.table.selectRow(index)
        page.family_button.click()
        self._wait(lambda: self.window.details_page.loaded_kind == "family"
                   and self.window.details_page.current_id == 100)
        self.window.return_to_context()
        self.assertEqual(page.selected_row().id, 7003)

    def test_unchanged_requery_keeps_model_selection_and_no_reset(self):
        self.window.navigate("headcounts")
        page = self.window.catalog_pages["headcounts"].current_page
        spy = QSignalSpy(page.model.modelReset)
        page.table.selectRow(0)
        previous = page.selected_row().id
        page.refresh()
        self.assertEqual(spy.count(), 0)
        self.assertEqual(page.selected_row().id, previous)

    def test_sqlite_source_is_unchanged_after_every_module(self):
        before = self.fixture.dump()
        for code in C15_MODULES_EXPECTED:
            self.window.navigate(code)
            for page in self.window.catalog_pages[code].pages.values():
                self.window.catalog_pages[code].tabs.setCurrentWidget(page)
                page.activate()
        self.window.navigate("home")
        self.assertEqual(before, self.fixture.dump())
        self.assertTrue(self.window.read_only_demo)
        self.assertFalse(self.window.activities_action.isEnabled())

    def test_c14_and_c13_are_not_regressed(self):
        self.window.navigate("memberships")
        self.assertEqual(
            {r.id for r in self.window.catalog_pages["memberships"].current_page.model.rows},
            {1001, 1002, 1003},
        )
        self.window.navigate("billing")
        self.assertEqual(
            {r.id for r in self.window.finance_pages["billing"].current_page.model.rows},
            {501, 502, 503, 990},
        )


if __name__ == "__main__":
    unittest.main()
