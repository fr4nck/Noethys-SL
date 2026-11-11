# -*- coding: utf-8 -*-
"""Tests for XLSX, CSV and a safe multi-site CSV ZIP."""
import csv
import importlib.util
import io
import unittest
import zipfile
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
from tests.test_stats_assiduite_synthetic import fixture,conf,DB,MOD

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'noethys'/'Utils'/'UTILS_Stats_assiduite_exports.py'
SPEC=importlib.util.spec_from_file_location('assiduite_exports',FILE)
import sys
EXPORTS=importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name]=EXPORTS
SPEC.loader.exec_module(EXPORTS)


class ExportsTests(unittest.TestCase):
    def setUp(self):
        self.cn=fixture()
        self.addCleanup(self.cn.close)
        self.report=MOD.Lecteur(DB(self.cn),conf()).lire('2024-01-01','2026-12-31')
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)

    def test_csv_annual_monthly_and_three_sites(self):
        f=self.path/'stats.csv'
        rows=EXPORTS.export_csv(self.report,f)
        self.assertGreater(rows,12)
        s=f.read_text(encoding='utf-8-sig')
        data=list(csv.DictReader(io.StringIO(s),delimiter=';'))
        self.assertEqual(data[0]['Perimetre'],'Synthese generale')
        self.assertEqual(sum(row['Perimetre']=='Annee' for row in data),3)
        self.assertEqual(sum(row['Perimetre']=='Mois' for row in data),36)
        self.assertEqual(sum(row['Perimetre'].startswith('Site ') and 'au' in row['Periode'] for row in data),3)
        self.assertIn('Non reconstructibles',s)

    def test_csv_formula_injection_in_site_label_is_text(self):
        import copy
        data=copy.deepcopy(self.report)
        data['sites']['=HYPERLINK("https://x", "open")']=data['sites'].pop('Moutiers')
        data['sites_annees']['=HYPERLINK("https://x", "open")']=data['sites_annees'].pop('Moutiers')
        f=self.path/'injection.csv'
        EXPORTS.export_csv(data,f)
        rows=list(csv.reader(io.StringIO(f.read_text(encoding='utf-8-sig')),delimiter=';'))
        self.assertTrue(any('Site =HYPERLINK' in row[0] for row in rows))
        self.assertFalse(any(row[0].lstrip().startswith(('=', '+', '-', '@')) for row in rows))

    def test_csv_does_not_include_personal_identity_or_amount(self):
        f=self.path/'private.csv'
        EXPORTS.export_csv(self.report,f)
        data=f.read_text(encoding='utf-8-sig')
        for label in ('IDindividu','IDfamille','montant','quotient','nom enfant'):
            self.assertNotIn(label,data)

    def test_xlsx_multiple_sheets_and_charts(self):
        f=self.path/'stats.xlsx'
        rows=EXPORTS.export_xlsx(self.report,f)
        self.assertGreater(rows,12)
        with zipfile.ZipFile(f) as book:
            paths=book.namelist()
            xml=ET.fromstring(book.read('xl/workbook.xml'))
            n='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
            tabs=[x.attrib['name'] for x in xml.findall('.//{%s}sheet'%n)]
            self.assertEqual(tabs,['Bilan','Annees','Mois','Activites','Sites','Sites par an'])
            self.assertGreaterEqual(sum('/chart' in p and p.endswith('.xml') for p in paths),4)
            self.assertFalse(any(p.endswith('vbaProject.bin') for p in paths))

    def test_zip_has_summary_and_per_site(self):
        f=self.path/'stats.zip'
        count=EXPORTS.export_zip_csv(self.report,f)
        self.assertEqual(count,4)
        with zipfile.ZipFile(f) as z:
            self.assertEqual(len(z.namelist()),4)
            self.assertEqual(z.namelist()[0],'01_synthese.csv')
            for name in z.namelist():
                self.assertTrue(name.endswith('.csv'))
                self.assertTrue(z.read(name).startswith(b'\xef\xbb\xbf'))

    def test_xlsx_cancellation_number_cannot_be_fabricated(self):
        import copy
        wrong=copy.deepcopy(self.report)
        wrong['annulations']['nombre']=0
        with self.assertRaises(ValueError):
            EXPORTS.export_xlsx(wrong,self.path/'no.xlsx')

    def test_aggregate_denominator_check(self):
        import copy
        wrong=copy.deepcopy(self.report)
        wrong['global']['journees_enfants']['present']+=1
        with self.assertRaises(ValueError):
            EXPORTS.export_csv(wrong,self.path/'invalid.csv')

    def test_csv_empty_month_has_no_invented_absence_rate(self):
        f=self.path/'stats.csv'
        EXPORTS.export_csv(self.report,f)
        rows=list(csv.DictReader(io.StringIO(f.read_text(encoding='utf-8-sig')),delimiter=';'))
        jan_2025=next(x for x in rows if x['Perimetre']=='Mois' and x['Periode']=='2025-01')
        self.assertEqual(jan_2025['Taux absence (%) hors mixtes'],'')
        self.assertEqual(jan_2025['Jours pointes'],'0')


if __name__=='__main__':
    unittest.main()
