# -*- coding: utf-8 -*-
"""J4: calendar/school-year parity and incomplete/ongoing year controls.

Only wholly synthetic, anonymised SQLite data. No production DB or new schema.
"""
import copy
import csv
from datetime import date
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

from tests.test_stats_assiduite_synthetic import fixture, conf, DB, MOD
from tests.test_stats_assiduite_exports import EXPORTS


class SchoolYearStatistics(unittest.TestCase):
    def setUp(self):
        self.cn = fixture()
        self.addCleanup(self.cn.close)
        self.db = DB(self.cn)
        self.config = conf()

    def read(self, start='2024-01-01', end='2026-12-31', asof='2026-11-12'):
        return MOD.Lecteur(self.db, self.config).lire(start, end, date_reference=asof)

    def test_school_year_keys_and_cross_year_aggregation(self):
        data = self.read()
        self.assertEqual(list(data['annees_scolaires']),
            ['2023-2024', '2024-2025', '2025-2026', '2026-2027'])
        for school, calendar in [('2023-2024','2024'), ('2024-2025','2025'),
                                 ('2025-2026','2026')]:
            self.assertEqual(data['annees_scolaires'][school]['journees_enfants'],
                             data['annees'][calendar]['journees_enfants'])
        self.assertEqual(data['annees_scolaires']['2026-2027']['journees_pointees'],0)
        self.assertIsNone(data['annees_scolaires']['2026-2027']['taux_absence_pct'])

    def test_all_four_school_year_boundaries(self):
        for ident, day, expected in (
            (101, '2025-08-31', '2024-2025'),
            (102, '2025-09-01', '2025-2026'),
            (103, '2026-08-31', '2025-2026'),
            (104, '2026-09-01', '2026-2027')):
            with self.subTest(day=day):
                self.cn.execute('INSERT INTO consommations VALUES (?,?,?,?,?,?,?)',
                                (ident,day,999,10,1,101,'present'))
                report=self.read(day,day)
                self.assertEqual(report['annees_scolaires'][expected]
                                 ['journees_enfants']['present'],1)
                self.assertEqual(report['global']['journees_pointees'],1)

    def test_school_year_full_while_two_calendar_years_partial(self):
        r=self.read('2025-09-01','2026-08-31')
        self.assertEqual(list(r['annees_scolaires']),['2025-2026'])
        self.assertTrue(r['annees_scolaires']['2025-2026']
                        ['comparable_annee_entiere'])
        self.assertFalse(r['annees']['2025']['annee_complete_dans_periode'])
        self.assertFalse(r['annees']['2026']['annee_complete_dans_periode'])

    def test_ongoing_school_year_not_mislabeled_as_complete(self):
        r=self.read('2025-09-01','2026-08-31', asof='2026-04-01')
        a=r['annees_scolaires']['2025-2026']
        self.assertTrue(a['annee_scolaire_complete_dans_periode'])
        self.assertFalse(a['annee_scolaire_terminee'])
        self.assertFalse(a['comparable_annee_entiere'])

    def test_ongoing_calendar_year_not_mislabeled_as_complete(self):
        r=self.read('2026-01-01','2026-12-31', asof='2026-11-12')
        a=r['annees']['2026']
        self.assertTrue(a['annee_complete_dans_periode'])
        self.assertFalse(a['annee_terminee'])
        self.assertFalse(a['comparable_annee_entiere'])

    def test_empty_school_year_is_zero_not_missing(self):
        r=self.read('2021-09-01','2026-08-31')
        self.assertIn('2022-2023',r['annees_scolaires'])
        self.assertEqual(r['annees_scolaires']['2022-2023']['journees_pointees'],0)
        self.assertIsNone(r['annees_scolaires']['2022-2023']['taux_absence_pct'])

    def test_site_and_global_school_year_are_consistent(self):
        r=self.read()
        self.assertEqual(r['sites_annees_scolaires']['Moutiers']['2025-2026']
                         ['journees_enfants']['present'],1)
        self.assertEqual(r['sites_annees_scolaires']['Moutiers']['2026-2027']
                         ['journees_pointees'],0)
        for school in r['annees_scolaires']:
            self.assertEqual(
                sum(scope[school]['lignes_total']
                    for scope in r['sites_annees_scolaires'].values()),
                r['annees_scolaires'][school]['lignes_total'])

    def test_no_fabricated_cancellations_and_one_select(self):
        r=self.read()
        self.assertIsNone(r['annulations']['nombre'])
        self.assertEqual(r['requetes_sql'],1)
        self.assertEqual(len(self.db.sql),1)
        self.assertTrue(all(q.startswith('SELECT ') for q in self.db.sql))

    def test_invalid_observation_date_rejected(self):
        with self.assertRaises(ValueError):
            self.read(asof='not-a-date')
        self.assertEqual(self.db.sql,[])

    def test_csv_school_years_and_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'annual.csv'
            EXPORTS.export_csv(self.read(),out)
            data=list(csv.DictReader(io.StringIO(out.read_text(encoding='utf-8-sig')),
                                     delimiter=';'))
            school=[row for row in data if row['Perimetre']=='Annee scolaire']
            self.assertEqual(len(school),4)
            self.assertEqual(next(row for row in school if row['Periode']=='2025-2026')
                             ['Couverture'],'Complete')
            self.assertEqual(next(row for row in school if row['Periode']=='2026-2027')
                             ['Couverture'],'Partielle')
            self.assertEqual(next(row for row in data
                if row['Perimetre']=='Annee' and row['Periode']=='2026')
                ['Couverture'],'En cours')

    def test_xlsx_school_year_sheets_and_charts(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'annual.xlsx'
            EXPORTS.export_xlsx(self.read(),out)
            with zipfile.ZipFile(out) as z:
                root=ET.fromstring(z.read('xl/workbook.xml'))
                ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
                names=[x.attrib['name'] for x in root.iter(ns+'sheet')]
                self.assertIn('Annees scolaires',names)
                self.assertIn('Sites scolaires',names)
                self.assertGreaterEqual(len([x for x in z.namelist()
                    if x.startswith('xl/charts/chart') and x.endswith('.xml')]),6)

    def test_zip_per_site_school_year_retains_anonymity(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'by-site.zip'
            EXPORTS.export_zip_csv(self.read(),out)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(len(z.namelist()),4)
                entries=[z.read(n).decode('utf-8-sig') for n in z.namelist()]
                self.assertTrue(any('2025-2026' in x for x in entries))
                self.assertTrue(all('IDindividu' not in x for x in entries))

    def test_export_rejects_missing_school_year_counts(self):
        data=self.read()
        data=copy.deepcopy(data)
        data['annees_scolaires']['2025-2026']['journees_enfants']['present']+=1
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                EXPORTS.export_csv(data,Path(d)/'invalid.csv')


if __name__=='__main__':
    unittest.main()
