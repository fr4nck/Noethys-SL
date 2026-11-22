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
        self.assertEqual(len(rubriques['assiduite']['pages']),4)
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


    def test_native_school_year_page_and_print_markup(self):
        self.dlg.baseHTML.SetParametres(self.parameters)
        with mock.patch.object(self.MODELES.GestionDB,'DB',return_value=self.db):
            self.dlg.baseHTML.MAJ(page='assiduite_scolaires')
            html=self.dlg.baseHTML.GetHTML(page='assiduite_scolaires')
            rubric=next(x for x in self.dlg.listeObjets if x['code']=='assiduite')
            page=next(x for x in rubric['pages'] if x['code']=='assiduite_scolaires')
            selected=['assiduite',page['code']]+[o.code for o in page['objets']]
            printed=self.dlg.baseHTML.GetHTML(
                mode='impression', rubrique='assiduite',
                page=page['code'], selectionsCodes=selected)
        self.assertIn('2025-2026',html)
        self.assertIn('2026-2027',html)
        self.assertIn('memory:image-',html)
        self.assertIn('memory:image-',printed)

    def test_legacy_stats_pages_not_removed(self):
        original={r['code']:r for r in self.dlg.listeObjets}
        self.assertIn('familles_qf',{x['code'] for x in original['familles']['pages']})
        self.assertIn('individus_nombre',{x['code'] for x in original['individus']['pages']})


    def _exporter_sans_dialogue_reel(self, type_index, extension):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory(prefix='assiduite-wx-export-') as temp:
            self.dlg.dictParametres = self.parameters
            target=Path(temp)/('assiduite'+extension)
            file_dialog=mock.Mock()
            file_dialog.ShowModal.return_value=self.wx.ID_OK
            file_dialog.GetPath.return_value=str(target)
            file_dialog.GetFilterIndex.return_value=type_index
            with mock.patch.object(self.wx, 'FileDialog', return_value=file_dialog), \
                 mock.patch('GestionDB.DB', return_value=self.db):
                self.dlg.OnBoutonExporterAssiduite(None)
            file_dialog.Destroy.assert_called_once()
            self.assertTrue(target.exists(), 'No export file produced')
            self.assertGreater(target.stat().st_size, 150)
            return target.read_bytes()

    def test_native_export_csv_is_anonymous(self):
        data=self._exporter_sans_dialogue_reel(0,'.csv').decode('utf-8-sig')
        self.assertIn('Synthese generale',data)
        self.assertIn('Non reconstructibles',data)
        self.assertNotIn('IDindividu',data)

    def test_native_export_xlsx_real_workbook(self):
        import io
        import zipfile
        data=self._exporter_sans_dialogue_reel(1,'.xlsx')
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            self.assertIn('xl/workbook.xml',book.namelist())
            self.assertIn('xl/worksheets/sheet2.xml',book.namelist())

    def test_native_export_zip_summary_without_unverified_sites(self):
        import io
        import zipfile
        data=self._exporter_sans_dialogue_reel(2,'.zip')
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            self.assertEqual(book.namelist(),['01_synthese.csv'])

    def test_invalid_mode_does_not_open_a_database(self):
        self.dlg.dictParametres=dict(self.parameters,mode='inscrits')
        message=mock.Mock()
        with mock.patch.object(self.wx,'MessageDialog',return_value=message), \
             mock.patch('GestionDB.DB',side_effect=AssertionError('SQL forbidden')):
            self.dlg.OnBoutonExporterAssiduite(None)
        message.Destroy.assert_called_once()


if __name__=='__main__':
    unittest.main()
