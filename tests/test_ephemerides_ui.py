# -*- coding: utf-8 -*-
"""Vrais contrôles wx ; réseau et base remplacés par des données déterministes."""
import datetime as dt
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'noethys'))
import wx
from Ctrl import CTRL_Ephemeride as ui
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ephemerides import forecast

_APP = None


class EphemeridesUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global _APP
        _APP = wx.GetApp() or wx.App(False)

    def setUp(self):
        self.frame = wx.Frame(None)
        self.panel = ui.CTRL(self.frame)
        self.panel._key = 'ephemerides:test'
        self.panel._generation = 1
        self.result = dict(settings=dict(city='Bais', postcode='35240', zone='B', events=[], territories='Bais',
                                        prefecture=ui.data.PREFECTURE_35, agenda=ui.data.AGENDA_35),
                           rows=ui.data.aggregate_weather(forecast()), cache=dict(fetched='2026-10-03T08:00:00+00:00'),
                           weather_error='', alert_error='Source préfectorale indisponible', bulletins=[], checked='03/10/2026 10:00',
                           planning=[('Toussaint', '2026-10-18', '2026-11-01')])

    def tearDown(self):
        self.frame.Destroy()
        _APP.Yield()

    def publish(self):
        with patch.object(ui.UTILS_Config, 'SetParametre') as save:
            self.panel._publish(1, self.result)
        return save

    def test_real_panel_displays_three_days_and_unavailable_source(self):
        self.publish()
        self.assertIn('2026-10-05', self.panel.weather.GetLabel())
        self.assertNotIn('2026-10-06', self.panel.weather.GetLabel())
        self.assertTrue(self.panel.detail.IsEnabled())
        self.assertEqual(self.panel.book.GetPageCount(), 3)
        texts = [child.GetLabel() for child in self.panel.GetChildren() if isinstance(child, wx.StaticText)]
        self.assertTrue(any('Source préfectorale indisponible' in ' '.join(text.split()) for text in texts))
        self.frame.SetSize((460, 650))
        self.frame.Show()
        _APP.Yield()

    def test_seven_or_ten_days_use_same_forecast(self):
        dialog = ui.WeatherDetails(self.frame, self.result['rows'], '03/10/2026')
        try:
            self.assertIn('2026-10-09', dialog.text.GetValue())
            self.assertNotIn('2026-10-10', dialog.text.GetValue())
            dialog.days.SetSelection(1)
            dialog.render()
            self.assertIn('2026-10-12', dialog.text.GetValue())
        finally:
            dialog.Destroy()

    def test_settings_round_trip_keeps_events_and_territories(self):
        dialog = ui.Settings(self.frame, dict(self.result['settings'], latitude='47.94', longitude='-1.23'))
        try:
            values = dialog.values()
            self.assertEqual(values['territories'], 'Bais')
            self.assertEqual(values['zone'], 'B')
            self.assertEqual(values['latitude'], '47.94')
        finally:
            dialog.Destroy()

    def test_late_results_do_not_write_config_or_touch_destroyed_ui(self):
        self.panel._generation = 2
        self.assertFalse(self.publish().called)
        self.panel._generation = 1
        self.panel._alive = False
        self.assertFalse(self.publish().called)

    def test_no_forecast_disables_details_and_reports_error(self):
        self.result.update(rows=[], weather_error='Météo indisponible', cache={})
        self.publish()
        self.assertFalse(self.panel.detail.IsEnabled())
        self.assertIn('Météo indisponible', self.panel.weather.GetLabel())

    def test_school_dates_do_not_replace_noethys_sunday_dates(self):
        self.publish()
        self.panel.render_calendar(self.result, today=dt.date(2026, 10, 3))
        text = self.panel.vacation.GetLabel()
        self.assertIn('17/10/2026', text)
        self.assertIn('18/10/2026', text)
        self.assertIn('01/11/2026', text)

    def test_stop_invalidates_pending_result(self):
        self.panel.StopTicker()
        self.assertFalse(self.publish().called)


if __name__ == '__main__':
    unittest.main()
