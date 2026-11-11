# -*- coding: utf-8 -*-
"""Windows native wx/HTML statistics against synthetic SQLite only."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT / 'tests', ROOT / 'noethys'):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('GITHUB_ACTIONS') == 'true',
                     'Real native wx integration only on isolated Windows CI')
class AssiduiteWxWindows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import _garde_reseau
        import wx
        from Dlg import DLG_Stats
        from Utils import UTILS_Stats_modeles as MODELES
        from tests.test_stats_assiduite_synthetic import fixture,DB
        cls.wx=wx
        cls.DLG_Stats=DLG_Stats
        cls.MODELES=MODELES
        cls.fixture=staticmethod(fixture)
        cls.DB=DB
        cls.app=wx.App(False)

    @classmethod
    def tearDownClass(cls):
        cls.app.Destroy()

    def setUp(self):
        self.sqlite=self.fixture()
        self.addCleanup(self.sqlite.close)
        self.db=self.DB(self.sqlite)
        self.db.Close=lambda:None
        self.main=self.wx.Frame(None,title='NOETHYS ASSIDUITE FICTIF')
        self.main.Show()
        self.addCleanup(self.main.Destroy)
        self.dlg=self.DLG_Stats.Dialog(self.main)
        self.addCleanup(self.dlg.Destroy)
        self.parameters={
            'mode':'presents','listeActivites':[10],
            'dictActivites':{10:'Activite fictive'},
            'periode':{'date_debut':'2024-01-01','date_fin':'2026-12-31',
                       'label':'2024-2026'},
        }

    def test_real_stats_dialog_registers_attendance_rubric(self):
        rubriques={r['code']:r for r in self.dlg.listeObjets}
        self.assertIn('individus',rubriques)
        self.assertIn('familles',rubriques)
        self.assertIn('assiduite',rubriques)
        self.assertEqual(len(rubriques['assiduite']['pages']),3)
        self.assertIsInstance(self.dlg.bouton_export_assiduite,self.wx.Button)

    def test_real_stats_html_page_and_print_markup(self):
        self.dlg.baseHTML.SetParametres(self.parameters)
        with mock.patch.object(self.MODELES.GestionDB,'DB',return_value=self.db):
            self.dlg.baseHTML.MAJ(page='assiduite_bilan')
            html=self.dlg.baseHTML.GetHTML(page='assiduite_bilan')
            rubrique=next(r for r in self.dlg.listeObjets if r['code']=='assiduite')
            page=rubrique['pages'][0]
            selected=['assiduite',page['code']]+[x.code for x in page['objets']]
            printing=self.dlg.baseHTML.GetHTML(mode='impression',rubrique='assiduite',
                page=page['code'],selectionsCodes=selected)
        self.assertIn('2024',html)
        self.assertIn('2025',html)
        self.assertIn('2026',html)
        self.assertIn('memory:image-',html)
        self.assertIn('memory:image-',printing)
        self.assertGreater(len(printing),200)

    def test_legacy_stats_pages_not_removed(self):
        original={r['code']:r for r in self.dlg.listeObjets}
        self.assertIn('familles_qf',{x['code'] for x in original['familles']['pages']})
        self.assertIn('individus_nombre',{x['code'] for x in original['individus']['pages']})


if __name__=='__main__':
    unittest.main()
