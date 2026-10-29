# -*- coding: utf-8 -*-
"""Optional inclusion of unjustified absences: synthetic, read-only tests."""
import csv
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'noethys'))
from Utils.UTILS_Frequentation_collectivites import (
    ErreurFrequentation, calculer, consolider_export_consommations,
    modele, exporter_csv, exporter_pdf, exporter_xlsx,
)
from Utils.UTILS_Frequentation_collectivites_db import importer_journees, lister_unites


class FakeDB:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
            CREATE TABLE activites (IDactivite INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE unites (IDunite INTEGER PRIMARY KEY, IDactivite INTEGER, nom TEXT);
            CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, adresse_auto INTEGER, ville_resid TEXT);
            CREATE TABLE consommations (IDconso INTEGER PRIMARY KEY, IDindividu INTEGER,
                       date TEXT, IDactivite INTEGER, IDunite INTEGER, etat TEXT);
            INSERT INTO activites VALUES (1,'ALSH fictif');
            INSERT INTO unites VALUES (10,1,'Journee');
            INSERT INTO unites VALUES (11,1,'Journee absenti seulement');
            INSERT INTO individus VALUES (1,NULL,'Bais');
            INSERT INTO individus VALUES (2,NULL,'Bais');
            INSERT INTO individus VALUES (3,NULL,'Moutiers');
            INSERT INTO consommations VALUES (1,1,'2026-03-01',1,10,'present');
            INSERT INTO consommations VALUES (2,2,'2026-03-02',1,10,'absenti');
            INSERT INTO consommations VALUES (3,2,'2026-03-03',1,10,'absentj');
            INSERT INTO consommations VALUES (4,2,'2026-03-04',1,10,'attente');
            INSERT INTO consommations VALUES (5,2,'2026-03-05',1,10,'refus');
            INSERT INTO consommations VALUES (6,1,'2026-11-01',1,10,'reservation');
            INSERT INTO consommations VALUES (7,3,'2026-03-01',1,10,'absenti');
            INSERT INTO consommations VALUES (8,2,'2026-03-06',1,11,'absenti');
            INSERT INTO consommations VALUES (9,2,'2026-11-03',1,10,'absenti');
        ''')
        self.cursor = None
        self.queries = []

    def ExecuterReq(self, sql):
        self.queries.append(sql)
        self.cursor = self.db.execute(sql)
        return True

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.db.close()


def report_for_import(imported, opt):
    d = modele('Bais', 2026, '2026-10-29')
    d['options_etats']['absenti'] = opt
    d['jours'] = imported['jours']
    d['controles'] = dict.fromkeys(d['controles'], True)
    d['conventions'][0]['tarif_confirme'] = True
    d['import_noethys'] = {
        'absenti_selectionne':opt,
        'perimetre_unites_confirme': True,
        'domiciles_indetermines': 0,
        'domiciliation_historique_verifiee': True,
    }
    return d, calculer(d)


class StatusChoiceTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.mapping = {'1:10':{'convention':'ALSH-2025-2026','poids':'1'}}

    def tearDown(self):
        self.db.Close()

    def test_default_excludes_absenti_and_preserves_real(self):
        found = importer_journees(2026,'2026-10-29','Bais',self.mapping,db=self.db)
        d, r = report_for_import(found, False)
        self.assertEqual(r['totaux']['journees_reelles'],1)
        self.assertEqual(r['totaux']['journees_absences_injustifiees'],0)
        self.assertEqual(r['totaux']['journees_prevues'],1)
        self.assertEqual(r['totaux']['participation_estimee'],2308)
        self.assertIsNone(r['totaux']['solde_verifie'])  # seconde convention non confirmee
        self.assertFalse(d['options_etats']['absenti'])

    def test_explicit_opt_in_counts_absenti_separately_only_past(self):
        found = importer_journees(2026,'2026-10-29','Bais',self.mapping,db=self.db,
                                  inclure_absenti=True)
        d, r = report_for_import(found,True)
        t=r['totaux']
        self.assertEqual(t['journees_reelles'],1)
        self.assertEqual(t['journees_absences_injustifiees'],1)
        self.assertEqual(t['journees_retenues'],2)
        self.assertEqual(t['journees_prevues'],1)
        self.assertEqual(t['participation_reelle'],1154)
        self.assertEqual(t['participation_absences_injustifiees'],1154)
        self.assertEqual(t['participation_estimee'],3462)
        self.assertEqual(t['solde_indicatif'],3462)
        self.assertIsNone(t['solde_verifie'])
        self.assertIn('PROVISOIRE',r['statut'])
        self.assertTrue(any('accord communal' in x.lower() for x in r['alertes']))
        self.assertEqual(found['exclusions']['absences'],4)
        self.assertTrue(all(sql.lstrip().upper().startswith('SELECT') for sql in self.db.queries))

    def test_absenti_only_units_appear_only_when_opted_in(self):
        no=lister_unites(2026,db=self.db)
        yes=lister_unites(2026,db=self.db,inclure_absenti=True)
        self.assertEqual([x['IDunite'] for x in no],[10])
        self.assertEqual([x['IDunite'] for x in yes],[10,11])

    def test_unrecognised_and_conflicting_status_never_silently_counted(self):
        base={'IDindividu':12,'date':'2026-04-03','IDactivite':1,
              'IDunite':10,'commune_residence':'Bais'}
        rules={'1:10':{'convention':'ALSH-2025-2026','poids':'1'}}
        cases=[dict(base,IDconso=1,etat='present'),dict(base,IDconso=2,etat='absenti')]
        with self.assertRaises(ErreurFrequentation):
            consolider_export_consommations(cases,rules,'Bais',2026,'2026-10-29',inclure_absenti=True)
        with self.assertRaises(ErreurFrequentation):
            consolider_export_consommations([dict(base,IDconso=3,etat='x')],rules,'Bais',2026,'2026-10-29')

    def test_selection_validation_old_records_and_stale_source(self):
        old=modele()
        del old['options_etats']
        self.assertFalse(calculer(old)['options_etats']['absenti'])
        d=modele()
        d['options_etats']={'absenti':1}
        with self.assertRaises(ErreurFrequentation):calcule=calculer(d)
        found=importer_journees(2026,'2026-10-29','Bais',self.mapping,db=self.db)
        d,_=report_for_import(found,False)
        d['options_etats']['absenti']=True
        with self.assertRaises(ErreurFrequentation):calculer(d)

    def test_manual_absence_requires_explicit_choice(self):
        d=modele()
        d['jours']=[{'id':'TEST','convention':'ALSH-2025-2026','mois':1,
                    'nature':'absence_injustifiee','nombre':'2','justificatif':'releve fictif'}]
        with self.assertRaises(ErreurFrequentation):calculer(d)
        d['options_etats']['absenti']=True
        self.assertEqual(calculer(d)['totaux']['journees_absences_injustifiees'],2)
        self.assertIsNone(calculer(d)['totaux']['solde_verifie'])

    def test_all_exports_label_absences_and_excel_amounts(self):
        data=importer_journees(2026,'2026-10-29','Bais',self.mapping,db=self.db,
                              inclure_absenti=True)
        dossier,r=report_for_import(data,True)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            exporter_csv(r,p/'t.csv')
            with (p/'t.csv').open(encoding='utf-8-sig') as f:
                rows=list(csv.reader(f,delimiter=';'))
            self.assertIn(['journees_absences_injustifiees','1'],rows)
            self.assertIn(['participation_absences_injustifiees','11.54'],rows)
            self.assertIn(['OPTION ABSENCES INJUSTIFIEES','INCLUSES'],rows)
            exporter_xlsx(r,p/'t.xlsx',dossier)
            with ZipFile(p/'t.xlsx') as archive:
                sheet1=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
                ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                def cell(x):
                    c=sheet1.find('.//s:c[@r="'+x+'"]',ns)
                    self.assertIsNotNone(c,x)
                    f=c.find('s:f',ns)
                    v=c.find('s:v',ns)
                    return ((f.text if f is not None else None),(v.text if v is not None else None))
                self.assertEqual(cell('M9')[1],'1')
                self.assertEqual(cell('N9')[1],'11.54')
                self.assertIn('N9',cell('H9')[0])
                self.assertEqual(cell('H9')[1],'34.62')
                self.assertEqual(cell('J11')[1],'34.62')
            exporter_pdf(r,p/'t.pdf',fictif=True)
            self.assertTrue((p/'t.pdf').read_bytes().startswith(b'%PDF'))

    def test_ui_exposes_checkbox_and_refresh_on_change(self):
        source=(ROOT/'noethys/Dlg/DLG_Frequentation_collectivites.py').read_text(encoding='utf-8')
        self.assertIn('self.inclure_absenti = wx.CheckBox',source)
        self.assertIn('def OnChoixAbsenti(self, event):',source)
        self.assertIn('inclure_absenti=self.inclure_absenti.GetValue()',source)

if __name__ == '__main__':unittest.main()