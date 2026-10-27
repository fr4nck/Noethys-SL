"""C9 : domaines métier familiers sur base temporaire C8, jamais un profil réel."""
from __future__ import annotations

import os
import unittest
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tools.qt_c8_fixture import C8FictiveDatabase
from tools.qt_c8_windows_demo import C8DemoWindow


class C9NavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = C8FictiveDatabase()
        self.addCleanup(self.db.close)
        self.window = C8DemoWindow(
            self.db.repository, fictive_db=self.db, background=False
        )
        self.addCleanup(self.window.close)
        self.window.show()
        self.window.activate_demo()
        self.app.processEvents()

    def test_familiar_tabs_and_default_consumptions_are_available(self):
        self.assertEqual(self.window.tabs.count(), 2)
        self.assertIs(self.window.tabs.currentWidget(), self.window.page)
        self.assertEqual(self.window.page.list_page.model.rowCount(), 4)
        self.assertTrue(self.window.banner.isVisible())

    def test_family_individual_activity_registration_domains(self):
        before = self.db.dump()
        page = self.window.business_page
        for domain, count in (
            ("familles", 2), ("individus", 4),
            ("activites", 2), ("inscriptions", 4),
        ):
            with self.subTest(domain=domain):
                page.show_domain(domain)
                self.assertEqual(page.domain, domain)
                self.assertEqual(page.table.rowCount(), count)
                self.assertEqual(
                    page.table.editTriggers(), page.table.EditTrigger.NoEditTriggers
                )
        self.assertEqual(self.db.dump(), before)

    def test_double_click_drills_to_related_domain_then_consumptions(self):
        page = self.window.business_page
        self.window.tabs.setCurrentWidget(page)
        page.show_domain("familles")
        page._open_related(0, 0)
        self.assertEqual(page.domain, "individus")
        page._open_related(0, 0)
        self.assertEqual(page.domain, "inscriptions")
        page._open_related(0, 0)
        self.assertIs(self.window.tabs.currentWidget(), self.window.page)

    def test_no_business_table_has_editable_items(self):
        page = self.window.business_page
        for domain, _label, _cols in page.DOMAINS:
            page.show_domain(domain)
            for row in range(page.table.rowCount()):
                for col in range(page.table.columnCount()):
                    cell = page.table.item(row, col)
                    self.assertFalse(bool(cell.flags() & cell.flags().ItemIsEditable))

    def test_c8_without_fixture_stays_compatible(self):
        standalone = C8DemoWindow(self.db.repository, background=False)
        self.addCleanup(standalone.close)
        self.assertIsNone(standalone.tabs)
        self.assertIsNone(standalone.business_page)


if __name__ == "__main__":
    unittest.main()
