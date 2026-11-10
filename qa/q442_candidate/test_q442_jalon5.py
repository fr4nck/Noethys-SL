#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q442 J5 exports and UI gating - strictly fictional SQLite fixtures.

Only AST-exported functions from the candidate code are executed; wx and the
PMSL production database are never imported or opened in these tests.
"""
import ast
import csv
import io
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use('Agg', force=True)
from matplotlib import pyplot as plt
import re
import xml.etree.ElementTree as ET

from q442_j4_lecteur import LecteurMultisite, ConfigurationMultisite
from q442_j4_objets import export_csv_aggreges
from test_q442_jalon4 import configuration, facture_schema_realiste, DB, params

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'noethys' / 'Utils' / 'UTILS_Stats_qf_objets.py'


def load_candidate():
    syntax=ast.parse(SOURCE.read_text(encoding='utf-8'))
    wanted={'est_disponible','export_xlsx_aggreges','export_csv_lot_aggreges',
            'construire_classes'}
    functions=[n for n in syntax.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    if {n.name for n in functions} != wanted:
        raise AssertionError('J5 candidate function missing')
    subset=ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[]))
    env={'ConfigurationMultisite':ConfigurationMultisite,'csv':csv,
         'export_csv_aggreges':export_csv_aggreges, 'date':date,
         '_vue':lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('No read in invalid mode'))}
    exec(compile(subset,str(SOURCE),'exec'),env)
    return env


class Cell:
    def __init__(self, value=None, data_type='n'):
        self.value=value
        self.data_type=data_type


class Sheet:
    def __init__(self, rows, charts):
        self.rows=rows
        self._charts=[object()] * charts

    def iter_rows(self,min_row=1,values_only=False):
        for row in self.rows[min_row-1:]:
            yield tuple(c.value for c in row) if values_only else tuple(row)

    def __iter__(self):
        return iter(self.rows)


class MiniWorkbook:
    def __init__(self,names,sheets):
        self.sheetnames=names
        self.worksheets=sheets
    def close(self):
        pass


def load_workbook(path):
    """Inspect XLSX using only the Python stdlib: no test-only dependency.

    This deliberately does not load or execute any workbook formula or macro.
    """
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    cn='http://schemas.openxmlformats.org/drawingml/2006/chart'
    with zipfile.ZipFile(path) as z:
        workbook=ET.fromstring(z.read('xl/workbook.xml'))
        names=[x.attrib['name'] for x in workbook.findall('.//{%s}sheet' % ns)]
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall('{%s}si' % ns):
                shared.append(''.join((t.text or '') for t in si.findall('.//{%s}t' % ns)))
        sheets=[]
        for ix in range(1,len(names)+1):
            root=ET.fromstring(z.read('xl/worksheets/sheet%d.xml' % ix))
            rows=[]
            for xmlrow in root.findall('.//{%s}sheetData/{%s}row' % (ns,ns)):
                cells=[Cell() for _ in range(7)]
                for c in xmlrow.findall('{%s}c' % ns):
                    match=re.match(r'([A-Z]+)',c.attrib.get('r',''))
                    if match is None:continue
                    col=0
                    for ch in match.group(1):
                        col=col*26+ord(ch)-64
                    col-=1
                    if col>=len(cells): continue
                    formula=c.find('{%s}f' % ns)
                    raw=c.find('{%s}v' % ns)
                    typ=c.attrib.get('t','n')
                    if formula is not None:
                        cells[col]=Cell(formula.text,'f')
                    elif raw is None:
                        cells[col]=Cell(None,typ)
                    elif typ=='s':
                        cells[col]=Cell(shared[int(raw.text)],'s')
                    else:
                        try:
                            n=float(raw.text)
                            val=int(n) if n.is_integer() else n
                        except (TypeError,ValueError):
                            val=raw.text
                        cells[col]=Cell(val,typ)
                rows.append(cells)
            draw='xl/drawings/drawing%d.xml' % ix
            charts=0
            if draw in z.namelist():
                drawing=ET.fromstring(z.read(draw))
                charts=len(drawing.findall('.//{%s}chart' % cn))
            sheets.append(Sheet(rows,charts))
    return MiniWorkbook(names,sheets)


class Tableau:
    def __init__(self):
        self.lignes=[]; self.colonnes=[]; self.totaux=[]


class Graphe:
    def __init__(self):
        self.taille=(100,100)


class Q442J5Tests(unittest.TestCase):
    def setUp(self):
        cn=facture_schema_realiste()
        try:
            self.data=LecteurMultisite(DB(cn),configuration()).lire('2026-07-01','2026-07-31')
        finally:
            cn.close()
        self.env=load_candidate()
        self.temp=tempfile.TemporaryDirectory(prefix='q442-j5-tests-')
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)

    def test_xlsx_tabs_include_summary_and_sites(self):
        file=self.folder/'stats.xlsx'
        rows=self.env['export_xlsx_aggreges'](self.data,file)
        self.assertGreater(rows,0)
        wb=load_workbook(file)
        self.addCleanup(wb.close)
        self.assertEqual(len(wb.sheetnames),4)
        self.assertEqual(wb.sheetnames[0],'Synthese generale')
        self.assertIn('Bais',wb.sheetnames)
        self.assertIn('La Guerche',wb.sheetnames)
        self.assertIn('Moutiers',wb.sheetnames)

    def test_xlsx_9_families_and_11_children_global(self):
        file=self.folder/'stats.xlsx'
        self.env['export_xlsx_aggreges'](self.data,file)
        wb=load_workbook(file)
        ws=wb.worksheets[0]
        entries=list(ws.iter_rows(min_row=5,values_only=True))
        for pop,total in (('familles',9),('enfants',11)):
            for kind in ('qf','tarifs_indicatifs'):
                self.assertEqual(sum(row[4] for row in entries if row[1]==pop and row[2]==kind),total)
        self.assertEqual(next(row[4] for row in entries if row[1]=='familles' and row[2]=='qf' and row[3]=='QF non communique'),2)
        wb.close()

    def test_xlsx_4_charts_for_two_people_and_two_natures(self):
        file=self.folder/'stats.xlsx'
        self.env['export_xlsx_aggreges'](self.data,file)
        wb=load_workbook(file)
        for ws in wb.worksheets:
            self.assertEqual(len(ws._charts),8)
        wb.close()

    def test_xlsx_only_categories_no_price_name_or_identifiers(self):
        file=self.folder/'stats.xlsx'
        self.env['export_xlsx_aggreges'](self.data,file)
        wb=load_workbook(file)
        values=[str(cell.value) for ws in wb.worksheets for row in ws for cell in row if cell.value is not None]
        txt=' '.join(values)
        for forbidden in ('IDprestation','IDfamille','IDindividu','montant','nom de famille'):
            self.assertNotIn(forbidden,txt)
        self.assertIn('Tarif indicatif',txt)
        wb.close()

    def test_xlsx_zero_category_preserved(self):
        file=self.folder/'stats.xlsx'
        self.env['export_xlsx_aggreges'](self.data,file)
        wb=load_workbook(file)
        ws=wb.worksheets[0]
        self.assertTrue(any(row[3]=='E historique' and row[4]==0 for row in ws.iter_rows(min_row=5,values_only=True)))
        wb.close()

    def test_xlsx_formula_injection_escaped_to_plain_text(self):
        import copy
        data=copy.deepcopy(self.data)
        view=data['global']['familles']
        view['qf']['=HYPERLINK("https://attacker", "go")']=0
        view['pourcentages_qf']['=HYPERLINK("https://attacker", "go")']=0
        file=self.folder/'stats.xlsx'
        self.env['export_xlsx_aggreges'](data,file)
        wb=load_workbook(file)
        ws=wb.worksheets[0]
        formulas=[c for row in ws for c in row if c.data_type=='f']
        self.assertEqual(formulas,[])
        wb.close()

    def test_xlsx_reject_inconsistent_denominator(self):
        import copy
        data=copy.deepcopy(self.data)
        data['global']['familles']['qf']['A']+=1
        with self.assertRaises(ValueError):
            self.env['export_xlsx_aggreges'](data,self.folder/'bad.xlsx')

    def test_xlsx_sheet_name_sanitization_and_collision(self):
        import copy
        data=copy.deepcopy(self.data)
        data['sites']['Bais/A']=data['sites'].pop('Bais')
        data['sites']['Bais?A']=data['sites'].pop('Moutiers')
        path=self.folder/'xlsx.xlsx'
        self.env['export_xlsx_aggreges'](data,path)
        wb=load_workbook(path)
        self.assertEqual(len(wb.sheetnames),4)
        self.assertEqual(len(set(ws.lower() for ws in wb.sheetnames)),4)
        wb.close()

    def test_csv_zip_four_different_csv(self):
        path=self.folder/'qf_csv.zip'
        n=self.env['export_csv_lot_aggreges'](self.data,path)
        self.assertGreater(n,0)
        with zipfile.ZipFile(path) as z:
            self.assertEqual(len(z.namelist()),4)
            self.assertTrue(all(nm.endswith('.csv') for nm in z.namelist()))
            self.assertIn('Synthese_generale.csv',z.namelist()[0])

    def test_csv_zip_global_dedup(self):
        path=self.folder/'qf_csv.zip'
        self.env['export_csv_lot_aggreges'](self.data,path)
        with zipfile.ZipFile(path) as z:
            first=z.read(z.namelist()[0]).decode('utf-8-sig')
            rows=list(csv.DictReader(io.StringIO(first),delimiter=';'))
        self.assertEqual(sum(int(r['effectif']) for r in rows if r['population']=='familles' and r['representation']=='qf'),9)
        self.assertEqual(sum(int(r['effectif']) for r in rows if r['population']=='enfants' and r['representation']=='qf'),11)

    def test_csv_zip_strips_formula_like_category(self):
        import copy
        data=copy.deepcopy(self.data)
        data['global']['familles']['qf']['=1+1']=0
        data['global']['familles']['pourcentages_qf']['=1+1']=0
        path=self.folder/'qf_csv.zip'
        self.env['export_csv_lot_aggreges'](data,path)
        with zipfile.ZipFile(path) as z:
            first=z.read(z.namelist()[0]).decode('utf-8-sig')
        self.assertIn("'=1+1",first)

    def test_disabled_in_inscrits_even_with_mapping(self):
        self.assertFalse(self.env['est_disponible'](params(mode='inscrits')))

    def test_disabled_if_no_explicit_mapping(self):
        p=params();p.pop('q442_configuration')
        self.assertFalse(self.env['est_disponible'](p))

    def test_disabled_when_activities_diverge(self):
        p=params();p['listeActivites']=[77]
        self.assertFalse(self.env['est_disponible'](p))

    def test_available_when_presents_mapping_consistent(self):
        self.assertTrue(self.env['est_disponible'](params()))

    def test_unavailable_table_does_not_query(self):
        T,B,C=self.env['construire_classes'](SimpleNamespace(Tableau=Tableau,Graphe=Graphe))
        o=T('familles','qf')
        self.assertIs(o.MAJ(DB=None,dictParametres=params(mode='inscrits')),o)
        self.assertEqual(o.lignes,[])

    def test_unavailable_graphs_do_not_query(self):
        T,B,C=self.env['construire_classes'](SimpleNamespace(Tableau=Tableau,Graphe=Graphe))
        for typ in (B,C):
            fig=plt.figure()
            try:
                self.assertIs(fig,typ('enfants','qf').MAJ(figure=fig,DB=None,dictParametres=params(mode='inscrits')))
                self.assertEqual(len(fig.axes),1)
            finally:
                plt.close(fig)


if __name__=='__main__':
    unittest.main()
