from __future__ import annotations

import datetime as dt
import inspect
import unittest

from noethys_qt.activity_calendar import (
    ActivityCalendarPage,
    CalendarEditorDialog,
    CalendarEvent,
    _event_counts_by_cell,
    _event_counts_by_period,
)


def _event(day: int, group_id: int, unit_id: int) -> CalendarEvent:
    return CalendarEvent(
        event_id=None,
        activity_id=7,
        unit_id=unit_id,
        group_id=group_id,
        date=dt.date(2026, 9, day),
        name=f"Évènement {day}-{group_id}-{unit_id}",
    )


class ActivityCalendarAggregationTests(unittest.TestCase):
    def test_event_counts_by_cell_aggregate_once_per_calendar_cell(self) -> None:
        events = (
            _event(2, 11, 21),
            _event(2, 11, 21),
            _event(3, 11, 21),
            _event(2, 12, 21),
            _event(2, 11, 22),
        )

        counts = _event_counts_by_cell(events)

        self.assertEqual(counts[(dt.date(2026, 9, 2), 11, 21)], 2)
        self.assertEqual(counts[(dt.date(2026, 9, 3), 11, 21)], 1)
        self.assertEqual(counts[(dt.date(2026, 9, 2), 12, 21)], 1)
        self.assertEqual(counts[(dt.date(2026, 9, 2), 11, 22)], 1)

    def test_event_counts_by_period_aggregate_all_dates_of_same_month(self) -> None:
        events = (
            _event(2, 11, 21),
            _event(2, 11, 21),
            _event(18, 11, 21),
            _event(2, 12, 21),
        )

        counts = _event_counts_by_period(events)

        self.assertEqual(counts[(2026, 9, 11, 21)], 3)
        self.assertEqual(counts[(2026, 9, 12, 21)], 1)

    def test_calendar_hot_paths_keep_preaggregated_lookups(self) -> None:
        monthly_source = inspect.getsource(CalendarEditorDialog._build_table)
        summary_source = inspect.getsource(ActivityCalendarPage.refresh)

        self.assertIn("_event_counts_by_cell(self.events)", monthly_source)
        self.assertNotIn("sum(1 for event in self.events", monthly_source)
        self.assertIn("_event_counts_by_period(events)", summary_source)
        self.assertNotIn("for opening in openings if", summary_source)


if __name__ == "__main__":
    unittest.main()
