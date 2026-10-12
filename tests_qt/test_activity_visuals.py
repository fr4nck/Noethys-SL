import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QToolBar

from noethys_qt.activities_prototype import ActivitiesWindow, ActivityRepository
from noethys_qt.activity_visuals import apply_activity_visuals


class EmptyRepository(ActivityRepository):
    def fetch(self, only_open: bool = False):
        return []


class ActivityVisualsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_visual_pass_keeps_dense_native_table_and_semantic_theme(self):
        window = ActivitiesWindow(EmptyRepository(), requested_theme="dark")
        self.addCleanup(window.close)

        apply_activity_visuals(window)

        toolbar = window.findChild(QToolBar)
        self.assertIsNotNone(toolbar)
        self.assertEqual(
            toolbar.toolButtonStyle(),
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon,
        )
        self.assertFalse(window.table.showGrid())
        self.assertEqual(window.export_text_action.text(), "Exporter texte")
        self.assertEqual(window.export_excel_action.text(), "Exporter Excel")
        self.assertEqual(window.theme_combo.itemText(0), "Système")
        self.assertIn("QTableView", self.app.styleSheet())
        self.assertIn("selection-background-color", self.app.styleSheet())

    def test_theme_change_reapplies_semantic_stylesheet(self):
        window = ActivitiesWindow(EmptyRepository(), requested_theme="dark")
        self.addCleanup(window.close)
        apply_activity_visuals(window)

        dark_stylesheet = self.app.styleSheet()
        window.theme_combo.setCurrentIndex(window.theme_combo.findData("light"))
        self.app.processEvents()
        light_stylesheet = self.app.styleSheet()

        self.assertNotEqual(dark_stylesheet, light_stylesheet)


if __name__ == "__main__":
    unittest.main()
