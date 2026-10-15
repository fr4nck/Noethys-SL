# -*- coding: utf-8 -*-
"""Menus reels wx, import sans sys.path Outils, dessin en memoire uniquement.

Aucun pilote d'impression, spool, PDF, email ni profil de production utilise.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import _garde_reseau
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
import wx
from Ctrl.CTRL_ObjectListView import ColumnDefn
from Ol import OL_Reglements_depots as Depot
from Utils import UTILS_Printer as P, UTILS_Adaptations


class ImpressionDepotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)

    def setUp(self):
        self.frame = wx.Frame(None, name='DLG_Saisie_depot')
        self.addCleanup(self.frame.Destroy)
        self.frame.GetLabelParametres = lambda: 'Dépôt fictif | 15/10/2026'
        panel = wx.Panel(self.frame)
        with patch.object(Depot.UTILS_Titulaires, 'GetTitulaires', return_value={}):
            self.liste = Depot.ListView(panel, style=wx.LC_REPORT)
        self.liste.SetColumns([ColumnDefn('Famille', 'left', 180, 'nom'), ColumnDefn('Montant', 'right', 90, 'montant')])
        self.liste.donnees = [SimpleNamespace(nom='Famille fictive %d' % i, IDmode=1, nom_mode='Chèque',
                                             montant=50.0 if i < 48 else 859.75, inclus=True)
                               for i in range(49)]
        self.liste.SetObjects(self.liste.donnees)

    def test_import_sans_repertoire_outils_sur_sys_path(self):
        code = '''
import sys, pathlib, importlib.util
sys.path[:0] = [str(pathlib.Path('tests').resolve()), str(pathlib.Path('noethys').resolve())]
import _garde_reseau
outils = pathlib.Path('noethys/Outils').resolve()
sys.path[:] = [p for p in sys.path if pathlib.Path(p or '.').resolve() != outils]
sys.modules.pop('WordWrapRenderer', None)
assert importlib.util.find_spec('WordWrapRenderer') is None
from Utils import UTILS_Printer
assert UTILS_Printer.ListCtrlPrinter.WordWrapRenderer.__module__ == 'Outils.WordWrapRenderer'
'''
        resultat = subprocess.run([sys.executable, '-c', code], cwd=str(ROOT), capture_output=True, timeout=30)
        self.assertEqual(resultat.returncode, 0, resultat.stderr.decode(errors='replace'))

    def menu(self):
        menu = UTILS_Adaptations.Menu()
        self.addCleanup(menu.Destroy)
        self.liste.GenerationContextMenu(menu, dictParametres=self.liste.GetParametresImpression())
        return menu

    def test_deux_entrees_menu_declenchent_le_bon_parcours(self):
        menu = self.menu()
        with patch.object(P, 'ObjectListViewPrinter') as classe:
            for item in menu.GetMenuItems():
                if item.GetItemLabelText() in ('aperçu avant impression', 'Imprimer'):
                    evenement = wx.CommandEvent(wx.EVT_MENU.typeId, item.GetId())
                    self.assertTrue(self.liste.GetEventHandler().ProcessEvent(evenement))
            classe.return_value.Preview.assert_called_once_with()
            classe.return_value.Print.assert_called_once_with()
            self.assertEqual(classe.call_count, 2)
            for appel in classe.call_args_list:
                self.assertEqual(appel.kwargs['orientation'], wx.LANDSCAPE)
                self.assertIn('3259.75', appel.kwargs['total'])
                self.assertIn('49', appel.kwargs['total'])

    def test_parametres_et_rendu_reel_49_reglements_sans_imprimante(self):
        with BaseTest() as base, RedirectionGestionDB(base.chemin), \
                patch.object(P.DLG_Options_impression_listes.Dialog, 'ShowModal', return_value=wx.ID_OK), \
                patch.object(P.ObjectListViewPrinter, 'GetNomOrganisateur', return_value='Organisme fictif'):
            avant = list(base.db.connexion.execute('SELECT * FROM prestations'))
            vrai_dialogue = P.DLG_Options_impression_listes.Dialog
            with patch.object(P.DLG_Options_impression_listes, 'Dialog', wraps=vrai_dialogue) as constructeur:
                imprimante = P.ObjectListViewPrinter(self.liste, **self.liste.GetParametresImpression())
                self.assertTrue(imprimante.InitParametres())
                self.assertIs(constructeur.call_args.args[0], self.frame)
            self.assertIn('3259.75', P.ListCtrlPrinter.LISTFOOTER)
            bitmap = wx.Bitmap(1100, 750)
            dc = wx.MemoryDC(bitmap)
            try:
                dc.SetBackground(wx.WHITE_BRUSH)
                dc.Clear()
                bounds = wx.Rect(10, 10, 1080, 730)
                pages = imprimante.printer.CalculateTotalPages(dc, bounds)
                self.assertGreater(pages, 0)
                imprimante.printer.StartPrinting()
                for page in range(1, pages + 1):
                    encore = imprimante.printer.PrintPage(dc, page, bounds)
                self.assertFalse(encore)  # False signifie derniere page, pas une erreur.
                self.assertEqual(imprimante.printer.engine.currentPage, pages)
            finally:
                dc.SelectObject(wx.NullBitmap)
            pixels = bytes(bitmap.ConvertToImage().GetData())
            self.assertTrue(any(pixel != 255 for pixel in pixels))
            self.assertEqual(list(base.db.connexion.execute('SELECT * FROM prestations')), avant)

    def test_epaisseurs_fractionnaires_acceptables_par_wx(self):
        for largeur, attendu in ((.25, 0), (.75, 1), (1.5, 2), (2, 2)):
            self.assertEqual(P._PenImpression(wx.BLACK, largeur).GetWidth(), attendu)

    def test_annulation_parametres_n_imprime_pas(self):
        with BaseTest() as base, RedirectionGestionDB(base.chemin), \
                patch.object(P.DLG_Options_impression_listes.Dialog, 'ShowModal', return_value=wx.ID_CANCEL), \
                patch.object(P.ListCtrlPrinter, 'ListCtrlPrinter') as constructeur:
            self.liste.Imprimer()
            constructeur.assert_not_called()

    def test_exception_visible_au_lieu_de_clic_silencieux(self):
        for action in (self.liste.Apercu, self.liste.Imprimer):
            with patch.object(P, 'ObjectListViewPrinter', side_effect=ImportError('module fictif absent')), \
                    patch('traceback.print_exc') as journal, patch('wx.MessageDialog') as dialogue:
                self.assertFalse(action())
                journal.assert_called_once()
                dialogue.return_value.ShowModal.assert_called_once()
                dialogue.return_value.Destroy.assert_called_once()
                self.assertIn('journal', dialogue.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
