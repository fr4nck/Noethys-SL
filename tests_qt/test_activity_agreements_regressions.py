from __future__ import annotations

import datetime as dt
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from noethys_qt.activity_agreements import (
    ActivityAgreementsRepository,
    ActivityEditorDialog,
    Agreement,
    AgreementState,
)


class _Tabs:
    def __init__(self) -> None:
        self.current = None

    def setCurrentWidget(self, widget) -> None:  # noqa: N802 - API Qt simulée
        self.current = widget


class _GroupPage:
    def __init__(self, count: int) -> None:
        self.count = count

    def group_count(self) -> int:
        return self.count


class _PricingPage:
    def __init__(self, has_categories: bool) -> None:
        self._has_categories = has_categories

    def has_categories(self) -> bool:
        return self._has_categories


class _EditorHarness:
    def __init__(self, group_count: int, has_categories: bool) -> None:
        self.tabs = _Tabs()
        self.group_page = _GroupPage(group_count)
        self.pricing_page = _PricingPage(has_categories)


class ActivityAgreementsRegressionTests(unittest.TestCase):
    def test_multiple_rejects_inverted_period(self) -> None:
        state = AgreementState(
            "multiple",
            "",
            (
                Agreement(
                    None,
                    7,
                    "JS-2026",
                    dt.date(2026, 12, 31),
                    dt.date(2026, 1, 1),
                ),
            ),
        )

        with self.assertRaisesRegex(ValueError, "date de fin"):
            ActivityAgreementsRepository.validate(state)

    def test_final_editor_still_blocks_missing_group(self) -> None:
        editor = _EditorHarness(group_count=0, has_categories=True)

        with patch("noethys_qt.activity_agreements.QMessageBox.warning") as warning:
            result = ActivityEditorDialog._validate_composed_editor(editor)

        self.assertFalse(result)
        self.assertIs(editor.tabs.current, editor.group_page)
        warning.assert_called_once()

    def test_final_editor_still_confirms_missing_pricing_category(self) -> None:
        editor = _EditorHarness(group_count=1, has_categories=False)

        with patch(
            "noethys_qt.activity_agreements.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as question:
            result = ActivityEditorDialog._validate_composed_editor(editor)

        self.assertFalse(result)
        self.assertIs(editor.tabs.current, editor.pricing_page)
        question.assert_called_once()

    def test_final_editor_can_continue_without_pricing_category_after_confirmation(self) -> None:
        editor = _EditorHarness(group_count=1, has_categories=False)

        with patch(
            "noethys_qt.activity_agreements.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            result = ActivityEditorDialog._validate_composed_editor(editor)

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
