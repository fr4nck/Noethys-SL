"""C13 : six grands domaines financiers Qt sur base fictive, lecture seule."""
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
from noethys_qt.finance_readonly_core import (
    FINANCE_DOMAINS, FinanceRepository, FinanceResult,
    build_finance_query, display_finance_value,
)
from noethys_qt.finance_readonly_ui import FinanceHubPage
from noethys_qt.noethys_native import NoethysQtWindow
from noethys_qt.people_search import PeopleSearchRepository
from tools.qt_c13_finance_fixture import C13FictiveFinanceDatabase


class C13CoreTests(unittest.TestCase):
    def setUp(self):
        self.db = C13FictiveFinanceDatabase()
        self.addCleanup(self.db.close)
        self.repo = FinanceRepository(self.db.repository.editor_repository)

    def test_all_six_domains_are_readable_and_complete_on_synthetic_sqlite(self):
        expected = {
            "invoices": 4, "services": 6, "payments": 4,
            "allocations": 5, "treasury": 3, "deposits": 2,
        }
        for kind, count in expected.items():
            with self.subTest(kind=kind):
                result = self.repo.search(kind)
                self.assertFalse(result.truncated)
                self.assertEqual(len(result.rows), count)
                self.assertTrue(all(record.kind == kind for record in result.rows))

    def test_family_ids_are_exact_and_do_not_leak_other_families(self):
        counts = {
            "invoices": (2, 2), "services": (3, 3),
            "payments": (2, 2), "allocations": (2, 2),
        }
        for kind, pair in counts.items():
            for family_id, expected in ((100, pair[0]), (101, pair[1])):
                with self.subTest(kind=kind, family=family_id):
                    records = self.repo.search(kind, family_id=family_id).rows
                    self.assertEqual(len(records), expected)
                    self.assertTrue(all(
                        row.value("family") == family_id for row in records
                    ))

    def test_orphan_allocation_never_inherits_family_from_service(self):
        # 705 désigne la prestation 304 (famille 101), mais un règlement
        # #999 inexistant : interdiction d'inférer une famille à partir
        # du dossier prestation en l'absence de paiement identifiable.
        orphan = next(
            row for row in self.repo.search("allocations").rows
            if row.id == 705
        )
        self.assertEqual(orphan.value("payment"), 999)
        self.assertIsNone(orphan.value("family"))
        self.assertNotIn(
            705,
            {row.id for row in self.repo.search("allocations", family_id=101).rows}
        )
        self.assertNotIn(
            705,
            {row.id for row in self.repo.search("allocations", family_id=100).rows}
        )

    def test_invoice_to_services_is_the_exact_id_relation(self):
        row = self.repo.search("services", related_id=501).rows
        self.assertEqual({item.id for item in row}, {301, 305})
        self.assertEqual({item.value("invoice") for item in row}, {501})
        self.assertEqual(
            self.repo.search("services", related_id=501, family_id=101).rows,
            (),
        )

    def test_payment_to_allocations_is_exact_and_includes_fractional_amount(self):
        rows = self.repo.search("allocations", related_id=401).rows
        self.assertEqual({r.id for r in rows}, {701, 702})
        self.assertEqual({r.value("amount") for r in rows}, {"9.99", "0.005"})
        self.assertTrue(all(r.value("payment") == 401 for r in rows))

    def test_deposit_to_payments_is_exact(self):
        rows = self.repo.search("payments", related_id=2).rows
        self.assertEqual({r.id for r in rows}, {402, 404})
        self.assertTrue(all(r.value("deposit") == 2 for r in rows))

    def test_year_filters_apply_only_where_date_is_defined(self):
        self.assertEqual(
            {r.id for r in self.repo.search("invoices", family_id=100, year=2026).rows},
            {501},
        )
        self.assertEqual(
            {r.id for r in self.repo.search("invoices", family_id=100, year=2027).rows},
            {503},
        )
        self.assertEqual(
            {r.id for r in self.repo.search("treasury", year=2026).rows},
            {801, 802},
        )
        with self.assertRaises(ValueError):
            self.repo.search("allocations", year=2026)

    def test_raw_decimals_are_never_rounded_or_summed(self):
        self.assertEqual(display_finance_value("12.005", amount=True), "12,005")
        self.assertEqual(display_finance_value("1000.0003", amount=True), "1000,0003")
        self.assertEqual(display_finance_value("-1.005", amount=True), "-1,005")
        self.assertEqual(display_finance_value(None, amount=True), "")
        invoice = next(r for r in self.repo.search("invoices").rows if r.id == 501)
        self.assertEqual(
            tuple(invoice.value(x) for x in ("total", "paid", "balance")),
            ("19.995", "9.99", "10.005"),
        )

    def test_like_escapes_quotes_wildcards_and_uses_parameters(self):
        for marker in ("?", "%s"):
            with self.subTest(marker=marker):
                for kind in FINANCE_DOMAINS:
                    sql, args = build_finance_query(
                        kind, text="x%'_! OR 1=1", placeholder=marker
                    )
                    self.assertIn(" ESCAPE '!'", sql)
                    self.assertNotIn("x%'_!", sql)
                    self.assertTrue(any("!%" in str(x) for x in args))
                    self.assertEqual(args[-1], 251)

    def test_unsupported_context_does_not_connect(self):
        with patch.object(
            self.repo.editor_repository, "_connect",
            side_effect=AssertionError("Must validate first"),
        ):
            cases = [
                ("invoices", {"family_id": 0}),
                ("payments", {"family_id": True}),
                ("treasury", {"family_id": 100}),
                ("deposits", {"related_id": 2}),
                ("invoices", {"related_id": 501}),
                ("allocations", {"year": 2026}),
                ("invoices", {"text": "x" * 121}),
                ("payments", {"limit": 251}),
                ("treasury", {"year": "2026"}),
            ]
            for kind, kw in cases:
                with self.subTest(kind=kind, kw=kw):
                    with self.assertRaises(ValueError):
                        self.repo.search(kind, **kw)

    def test_sqlite_connection_is_query_only_and_closed(self):
        # Un garde de connexion pour empêcher toute écriture SQL,
        # même si quelqu'un ajoutait une modification par erreur.
        native = self.repo.editor_repository._connect
        observed = []
        def connection():
            db, marker = native()
            observed.append(db)
            return db, marker
        with patch.object(self.repo.editor_repository, "_connect", side_effect=connection):
            self.repo.search("payments")
        self.assertEqual(len(observed), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            observed[0].execute("SELECT 1")

    def test_bounded_results_do_not_claim_global_financial_totals(self):
        limited = self.repo.search("services", limit=2)
        self.assertEqual(len(limited.rows), 2)
        self.assertTrue(limited.truncated)
        self.assertEqual(len(self.repo.search("services").rows), 6)

    def test_search_by_source_identifier_is_not_person_name_search(self):
        result = self.repo.search("invoices", text="101")
        self.assertEqual({row.id for row in result.rows}, {501})
        self.assertEqual(
            {row.id for row in self.repo.search("services", text="Correction").rows},
            {305},
        )
        self.assertEqual(
            {row.id for row in self.repo.search("payments", text="CARTE-FAKE-1").rows},
            {401},
        )


class C13NativeFinancialPagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self):
        self.db = C13FictiveFinanceDatabase()
        self.addCleanup(self.db.close)
        self.settings = tempfile.TemporaryDirectory(prefix="noethys-qt-c13-settings-")
        self.addCleanup(self.settings.cleanup)
        setting = QSettings(
            str(Path(self.settings.name) / "c13.ini"), QSettings.Format.IniFormat
        )
        with patch(
            "noethys_qt.noethys_native.QSettings", return_value=setting
        ):
            self.window = NoethysQtWindow(
                PeopleSearchRepository(self.db.repository.editor_repository),
                SqliteActivityRepository(self.db.path),
                editor_sqlite_path=self.db.path,
                source_label="C13 - DONNÉES FICTIVES",
                background_queries=False, read_only_demo=True,
                requested_theme="light",
            )
        self.addCleanup(self.window.close)
        self.window.show()
        self.app.processEvents()

    def _wait(self, condition, label="Qt signal", duration=4.0):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            self.app.processEvents()
            if condition():
                return
            QTest.qWait(20)
        self.fail("Délai C13 dépassé : " + label)

    def _family(self, ident=100):
        self.window._family_requested(ident)
        self._wait(lambda: self.window.details_page.loaded_kind == "family"
                   and self.window.details_page.current_id == ident)
        return self.window.details_page

    def test_three_finance_modules_are_enabled_in_main_menu(self):
        self.assertEqual(self.window.navigation.count(), 8)
        for code in ("billing", "payments", "accounting"):
            row = next(i for i in range(8) if
                       self.window.navigation.item(i).data(
                           Qt.ItemDataRole.UserRole) == code)
            self.assertTrue(self.window.navigation.item(row).flags()
                            & Qt.ItemFlag.ItemIsEnabled)
            self.window.navigate(code)
            self.assertIs(
                self.window.stack.currentWidget(), self.window.finance_pages[code]
            )
            self.assertFalse(self.window.finance_pages[code].current_page.table
                             .editTriggers() != QAbstractItemView.EditTrigger.NoEditTriggers)

    def test_six_lists_render_from_real_main_shell(self):
        expected = {
            "invoices": 4, "services": 6, "payments": 4,
            "allocations": 5, "treasury": 3, "deposits": 2,
        }
        for module, hub in self.window.finance_pages.items():
            self.window.navigate(module)
            for kind, page in hub.pages.items():
                with self.subTest(module=module, kind=kind):
                    hub.tabs.setCurrentWidget(page)
                    page.activate()
                    self.assertEqual(page.model.rowCount(), expected[kind])
                    self.assertEqual(
                        page.table.editTriggers(),
                        QAbstractItemView.EditTrigger.NoEditTriggers,
                    )

    def test_family_invoice_shortcut_restricts_exact_ids(self):
        before = self.db.dump()
        detail = self._family()
        self.assertTrue(detail.family_invoices_button.isVisible())
        detail.family_invoices_button.click()
        hub = self.window.finance_pages["billing"]
        self.assertIs(self.window.stack.currentWidget(), hub)
        self.assertEqual(hub.pages["invoices"]._family_id, 100)
        self.assertEqual({x.id for x in hub.pages["invoices"].model.rows}, {501, 503})
        self.assertIn("Famille #100", hub.current_page.context_label.text())
        self.assertTrue(self.window.context_back_button.isVisible())
        self.window.return_to_context()
        self._wait(lambda: self.window.details_page.loaded_kind == "family"
                   and self.window.details_page.current_id == 100)
        self.assertEqual(self.db.dump(), before)

    def test_family_payments_shortcut_and_return(self):
        detail = self._family(101)
        detail.family_payments_button.click()
        hub = self.window.finance_pages["payments"]
        self.assertIs(self.window.stack.currentWidget(), hub)
        self.assertEqual(
            {row.id for row in hub.pages["payments"].model.rows}, {402, 404}
        )
        self.window.return_to_context()
        self._wait(lambda: self.window.details_page.loaded_kind == "family"
                   and self.window.details_page.current_id == 101)

    def test_invoice_to_services_keeps_family_scope(self):
        self._family(100).family_invoices_button.click()
        hub = self.window.finance_pages["billing"]
        index = next(i for i, row in enumerate(hub.pages["invoices"].model.rows)
                     if row.id == 501)
        hub.pages["invoices"].table.selectRow(index)
        hub.pages["invoices"].related_button.click()
        self.assertIs(hub.current_page, hub.pages["services"])
        self.assertEqual({row.id for row in hub.current_page.model.rows}, {301, 305})
        self.assertIn("facture #501", hub.current_page.context_label.text())
        self.assertEqual(hub.current_page._family_id, 100)

    def test_payment_to_allocations_keeps_family_scope(self):
        self._family(100).family_payments_button.click()
        hub = self.window.finance_pages["payments"]
        row = next(i for i, item in enumerate(hub.pages["payments"].model.rows)
                   if item.id == 401)
        hub.pages["payments"].table.selectRow(row)
        hub.pages["payments"].related_button.click()
        self.assertEqual(hub.current_page.kind, "allocations")
        self.assertEqual({x.id for x in hub.current_page.model.rows}, {701, 702})
        self.assertEqual(hub.current_page._family_id, 100)

    def test_accounting_deposit_links_to_payments_with_return(self):
        self.window.navigate("accounting")
        hub = self.window.finance_pages["accounting"]
        hub.tabs.setCurrentWidget(hub.pages["deposits"])
        deposits = hub.pages["deposits"]
        deposits.table.selectRow(0)
        ident = deposits.selected_row().id
        deposits.related_button.click()
        self.assertIs(
            self.window.stack.currentWidget(), self.window.finance_pages["payments"]
        )
        current = self.window.finance_pages["payments"].current_page
        self.assertEqual(current._related_id, ident)
        self.assertTrue(all(item.value("deposit") == ident
                            for item in current.model.rows))
        self.window.return_to_context()
        self.assertIs(self.window.stack.currentWidget(), hub)
        self.assertEqual(hub.current_page.kind, "deposits")

    def test_global_module_after_drilldown_reopens_primary_list(self):
        self.window.navigate("billing")
        hub = self.window.finance_pages["billing"]
        hub.pages["invoices"].table.selectRow(0)
        hub.pages["invoices"].related_button.click()
        self.assertEqual(hub.current_page.kind, "services")
        self.window.navigate("home")
        self.window.navigate("billing")
        self.assertEqual(hub.current_page.kind, "invoices")
        self.assertEqual(hub.current_page.model.rowCount(), 4)
        self.assertIsNone(hub.current_page._related_id)

    def test_direct_global_module_navigation_clears_family_context(self):
        self._family(100).family_invoices_button.click()
        self.assertEqual(
            self.window.finance_pages["billing"].current_page._family_id, 100
        )
        self.window.navigate("home")
        self.window.navigate("billing")
        page = self.window.finance_pages["billing"].pages["invoices"]
        self.assertIsNone(page._family_id)
        self.assertEqual(page.model.rowCount(), 4)
        self.assertFalse(self.window.context_back_button.isVisible())

    def test_ctrl_f_targets_finance_page_current_tab(self):
        self.window.navigate("payments")
        hub = self.window.finance_pages["payments"]
        hub.tabs.setCurrentWidget(hub.pages["allocations"])
        self.window.focus_current_search()
        self.assertIs(
            self.app.focusWidget(), hub.pages["allocations"].search_edit
        )

    def test_finance_list_selection_is_preserved_and_no_model_reset_on_refresh(self):
        self.window.navigate("billing")
        page = self.window.finance_pages["billing"].current_page
        page.table.selectRow(1)
        chosen = page.selected_row().id
        resets = QSignalSpy(page.model.modelReset)
        for _ in range(8):
            page.refresh()
        self.assertEqual(resets.count(), 0)
        self.assertEqual(page.selected_row().id, chosen)

    def test_amount_shown_at_recorded_precision_not_rounded(self):
        self.window.navigate("billing")
        page = self.window.finance_pages["billing"].pages["invoices"]
        row = next(i for i, value in enumerate(page.model.rows) if value.id == 501)
        self.assertEqual(
            page.model.data(page.model.index(row, 5), Qt.ItemDataRole.DisplayRole),
            "19,995",
        )
        self.assertEqual(
            page.model.data(page.model.index(row, 7), Qt.ItemDataRole.DisplayRole),
            "10,005",
        )

    def test_year_search_and_reload_use_one_query_each(self):
        self.window.navigate("treasury") if False else None
        self.window.navigate("accounting")
        page = self.window.finance_pages["accounting"].pages["treasury"]
        with patch.object(
            self.window.finance_repository, "search",
            wraps=self.window.finance_repository.search,
        ) as spy:
            page.year_spin.setValue(2026)
            self.assertEqual(spy.call_count, 1)
            self.assertEqual({r.id for r in page.model.rows}, {801, 802})
            page.search_edit.setText("Achat")
            page.timer.stop()
            page.refresh()
            self.assertEqual(spy.call_count, 2)
            self.assertEqual({r.id for r in page.model.rows}, {801})

    def test_invalid_finance_navigation_does_not_mutate_fixture(self):
        before = self.db.dump()
        self.window.navigate("billing")
        page = self.window.finance_pages["billing"].pages["services"]
        for item in (0, True, -1):
            with self.assertRaises(ValueError):
                page.set_context(related_id=item)
        self.assertEqual(self.db.dump(), before)

    def test_finance_modules_are_readonly_and_disable_activity_editor(self):
        self.window.navigate("accounting")
        self.window.open_activities()
        self.assertIsNone(self.window._activities_window)
        self.assertFalse(self.window.activities_action.isEnabled())
        before = self.db.dump()
        for hub in self.window.finance_pages.values():
            for page in hub.pages.values():
                page.activate()
                self.assertEqual(
                    page.table.editTriggers(),
                    QAbstractItemView.EditTrigger.NoEditTriggers,
                )
        self.assertEqual(self.db.dump(), before)


if __name__ == "__main__":
    unittest.main()
