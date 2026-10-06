# -*- coding: utf-8 -*-
import datetime as dt
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'noethys'))
from Utils import UTILS_Ephemerides as data
from Utils import UTILS_VacancesScolaires as school


def forecast(days=10):
    times = [dt.datetime(2026, 10, 3) + dt.timedelta(hours=i) for i in range(days * 24)]
    hourly = {'time': [value.isoformat() for value in times]}
    for field in data.FIELDS:
        hourly[field] = [0 if field == 'weather_code' else 1.0] * len(times)
    return {'hourly': hourly}


class EphemeridesTests(unittest.TestCase):
    def test_ten_days_and_six_hour_periods(self):
        rows = data.aggregate_weather(forecast())
        self.assertEqual(len(rows), 20)
        self.assertTrue(all(row['samples'] == 6 for row in rows))
        self.assertEqual(rows[0]['period'], data.PERIODS[0][0])
        self.assertEqual(rows[0]['precipitation'], 6)

    def test_period_boundaries_and_worst_weather(self):
        payload = forecast(1)
        payload['hourly']['weather_code'][5] = 99
        payload['hourly']['weather_code'][12] = 95
        payload['hourly']['precipitation'][11] = 10
        payload['hourly']['precipitation'][18] = 50
        morning, afternoon = data.aggregate_weather(payload)
        self.assertEqual(morning['weather_code'], 0)
        self.assertEqual(afternoon['weather_code'], 95)
        self.assertEqual(morning['precipitation'], 15)
        self.assertEqual(afternoon['precipitation'], 6)

    def test_missing_rain_is_not_zero(self):
        payload = forecast(1)
        payload['hourly']['precipitation'][6] = None
        payload['hourly']['temperature_2m'][7] = float('nan')
        morning = data.aggregate_weather(payload)[0]
        self.assertIsNone(morning['precipitation'])
        self.assertIsNone(morning['temperature_2m'])
        self.assertIn('Pluie —', data.weather_text(morning))

    def test_missing_hours_are_not_complete(self):
        payload = forecast(1)
        for values in payload['hourly'].values():
            del values[7]
        self.assertIsNone(data.aggregate_weather(payload)[0]['precipitation'])

    def test_dst_date_is_aggregated_by_local_time(self):
        payload = forecast(1)
        payload['hourly']['time'] = [stamp.replace('2026-10-03', '2026-10-25') for stamp in payload['hourly']['time']]
        self.assertEqual(data.aggregate_weather(payload)[0]['date'], '2026-10-25')

    def test_missing_forecast_is_rejected(self):
        with self.assertRaises(ValueError):
            data.aggregate_weather({})

    def test_gps_validation(self):
        for lat, lon in [('nan', '1'), ('91', '1'), ('1', '181'), ('', '')]:
            with self.subTest(lat=lat), self.assertRaises(ValueError):
                data.coordinates(lat, lon)
        self.assertEqual(data.coordinates('47.94', '-1.23'), (47.94, -1.23))

    def test_geocode_requires_postcode_match_and_unique_result(self):
        with patch.object(data, 'read_url', return_value=json.dumps({'results': [dict(country_code='FR', postcodes=['35000'], latitude=48, longitude=-1)]}).encode()):
            self.assertEqual(data.geocode('Rennes', '35000'), (48, -1))
            with self.assertRaises(ValueError):
                data.geocode('Rennes', '35240')

    def test_geocode_fr_accepts_hyphens_accents_and_persists_safe_coordinates(self):
        payload = [dict(nom='La Guerche-de-Bretagne',
                        codesPostaux=['35130'],
                        centre={'coordinates': [-1.229722, 47.941389]})]
        with patch.object(data, 'read_url', return_value=json.dumps(payload).encode()) as read:
            self.assertEqual(data.geocode('LA GUERCHE DE BRETAGNE', '35130'),
                             (47.941389, -1.229722))
            self.assertIn('geo.api.gouv.fr/communes?', read.call_args.args[0])

    def test_dashboard_layout_defaults_and_custom_columns(self):
        layout = data.normalize_dashboard_layout()
        self.assertEqual(layout['columns'], 3)
        self.assertEqual(data.dashboard_columns(layout), [['weather'], ['alerts', 'vacations'], ['events']])

        custom = data.normalize_dashboard_layout({
            'columns': 2,
            'blocks': {
                'weather': {'visible': True, 'column': 2, 'order': 2},
                'alerts': {'visible': False, 'column': 1, 'order': 1},
                'vacations': {'visible': True, 'column': 1, 'order': 1},
                'events': {'visible': True, 'column': 2, 'order': 1},
            },
        })
        self.assertEqual(data.dashboard_columns(custom), [['vacations'], ['events', 'weather']])

    def test_dashboard_layout_is_bounded_and_completed(self):
        layout = data.normalize_dashboard_layout({
            'columns': 99,
            'blocks': {'weather': {'column': 12, 'order': 0, 'visible': False}},
        })
        self.assertEqual(layout['columns'], 4)
        self.assertEqual(layout['blocks']['weather'], {'visible': False, 'column': 4, 'order': 1})
        self.assertIn('events', layout['blocks'])

    def test_cache_is_scoped_and_expires(self):
        now = dt.datetime(2026, 10, 3, tzinfo=dt.timezone.utc)
        cache = dict(key='site-a', fetched=(now - dt.timedelta(minutes=29)).isoformat())
        self.assertTrue(data.cache_valid(cache, 'site-a', now))
        self.assertFalse(data.cache_valid(cache, 'site-b', now))
        self.assertFalse(data.cache_valid(cache, 'site-a', now + dt.timedelta(minutes=2)))
        self.assertFalse(data.cache_valid(dict(key='site-a', fetched='bad'), 'site-a', now))

    def test_urls_cannot_impersonate_official_sites(self):
        self.assertTrue(data.official_url(data.PREFECTURE_35))
        for url in ['http://test.gouv.fr/a', 'https://test.gouv.fr.evil.org/a', 'https://user@a.gouv.fr/', 'javascript:alert(1)']:
            self.assertFalse(data.official_url(url))

    def test_rss_filters_age_keywords_and_external_links(self):
        now = dt.datetime(2026, 10, 3, tzinfo=dt.timezone.utc)
        raw = b'''<rss><channel>
          <item><title>Vigilance orages</title><link>https://www.ille-et-vilaine.gouv.fr/a</link><pubDate>Fri, 02 Oct 2026 10:00:00 GMT</pubDate></item>
          <item><title>Alerte ancienne</title><link>/b</link><pubDate>Fri, 02 Jan 2026 10:00:00 GMT</pubDate></item>
          <item><title>Alerte externe</title><link>https://evil.org/</link><pubDate>Fri, 02 Oct 2026 10:00:00 GMT</pubDate></item>
          <item><title>Inauguration</title><link>/c</link><pubDate>Fri, 02 Oct 2026 10:00:00 GMT</pubDate></item>
          </channel></rss>'''
        items = data.parse_bulletins(raw, data.PREFECTURE_35, now)
        self.assertEqual([item['title'] for item in items], ['Vigilance orages'])
        with self.assertRaises(ValueError):
            data.parse_bulletins(b'<html/>', data.PREFECTURE_35, now)

    def test_feed_discovery_keeps_official_host(self):
        html = b'<a href="https://evil.org/x.rss">RSS</a><a href="/syndication/export/1">RSS</a>'
        with patch.object(data, 'read_url', side_effect=[html, b'<rss><channel/></rss>']) as read:
            self.assertEqual(data.fetch_bulletins(data.PREFECTURE_35), [])
            self.assertEqual(read.call_args.args[0], 'https://www.ille-et-vilaine.gouv.fr/syndication/export/1')
        with patch.object(data, 'read_url', return_value=b'<html/>'), self.assertRaises(ValueError):
            data.fetch_bulletins(data.PREFECTURE_35)

    def test_school_zone_and_countdown(self):
        self.assertEqual(school.GetZoneDepuisCodePostal('35240'), 'B')
        self.assertIsNone(school.GetZoneDepuisCodePostal('20000'))
        self.assertIsNone(school.GetZoneDepuisCodePostal('35'))
        date = dt.date(2026, 10, 3)
        self.assertEqual((school.GetProchainePeriode('B', date)['debut'] - date).days, 14)
        self.assertEqual(school.GetProchainePeriode('B', dt.date(2026, 11, 2))['nom'], 'Noël')
        self.assertIsNone(school.GetProchainePeriode('B', dt.date(2028, 1, 1)))

    def test_first_friday_changes_each_year(self):
        for year, expected in [(2026, '2026-10-02'), (2027, '2027-10-01')]:
            events = data.upcoming_events([], today=dt.date(year, 10, 1))
            self.assertEqual(next(e['date'] for e in events if e['title'] == 'World Smile Day'), expected)

    def test_local_filters_do_not_filter_national_events(self):
        custom = [dict(title='Fête de village', date='2026-10-10', kind='Local', territory=territory,
                       source='https://www.vitrecommunaute.org/') for territory in ['Bais', 'Moutiers']]
        events = data.upcoming_events(custom, 'bais', dt.date(2026, 10, 3))
        self.assertEqual([e['territory'] for e in events if e['kind'] == 'Local'], ['Bais'])
        self.assertTrue(any(e['kind'] == 'Officiel' for e in events))

    def test_invalid_events_are_rejected(self):
        with self.assertRaises(ValueError):
            data.validate_event(dict(title='Fête', date='2026-13-01', kind='Local', source='https://example.org'))
        self.assertEqual(len(data.upcoming_events([{}], today=dt.date(2026, 10, 3))), 3)


if __name__ == '__main__':
    unittest.main()
