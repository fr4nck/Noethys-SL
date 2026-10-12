import datetime as dt
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox


class CalendarWidgetPropertyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_python_tuple_property_roundtrip(self):
        widget = QCheckBox()
        self.addCleanup(widget.close)
        key = (dt.date(2026, 9, 1), 1, 2)
        widget.setProperty("calendar_key", key)
        self.assertEqual(widget.property("calendar_key"), key)
        self.assertIsInstance(widget.property("calendar_key"), tuple)


if __name__ == "__main__":
    unittest.main()
