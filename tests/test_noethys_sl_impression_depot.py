# -*- coding: utf-8 -*-
"""Menus reels wx, import sans sys.path Outils, dessin en memoire uniquement.

Aucun pilote d'impression, spool, PDF, email ni profil de production utilise.
"""
import subprocess
import datetime
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import _garde_reseau
from _fixtures_noethys_db import BaseTest, RedirectionGestionDB
import wx
from Ctrl.CTRL_ObjectListView import ColumnDefn
from Ol import OL_Reglements_depots as Depot
from Utils import UTILS_Printer as P, UTILS_Adaptations
from ObjectListView.ListCtrlPrinter import ListCtrlPrintout as PrintoutModerne


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
        self.liste.donnees = [
            SimpleNamespace(
                nom='Famille fictive %d' % i,
                nomTitulaires='Famille fictive %d' % i,
                IDmode=1, nom_mode='Chèque', montant=50.0 if i < 48 else 859.75,
                date=datetime.date(2026, 10, 20), nom_emetteur='Emetteur test',
                numero_piece='C-%03d' % i, nom_payeur='Payeur fictif',
                observations='Observation fictive', inclus=True,
            )
            for i in range(49)
        ]
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
                vue = appel.args[0]
                self.assertIsInstance(vue, Depot._VueImpressionDepot)
                self.assertEqual(vue.GetItemCount(), 49)
                self.assertEqual(vue.GetColumnCount(), 8)
                self.assertIn('Famille fictive 0', vue.GetItem(0, 4).GetText())
                self.assertEqual(vue.GetColumn(6).GetText(), 'Montant')
                self.assertFalse(vue.useExpansionColumn)
                self.assertEqual(appel.kwargs['orientation'], wx.LANDSCAPE)
                self.assertIn('3259.75', appel.kwargs['total'])
                self.assertIn('49', appel.kwargs['total'])

    def test_parametres_et_rendu_reel_49_reglements_sans_imprimante(self):
        with BaseTest() as base, RedirectionGestionDB(base.chemin), \
                patch.object(P.DLG_Options_impression_listes.Dialog, 'ShowModal', return_value=wx.ID_OK), \
                patch.object(P.ObjectListViewPrinter, 'GetNomOrganisateur', return_value='Organisme fictif'):
            avant = list(base.db.connexion.execute('SELECT * FROM prestations'))
            vrai_dialogue = P.DLG_Options_impression_listes.Dialog
            vue = Depot._VueImpressionDepot(self.liste, self.liste.donnees)
            with patch.object(P.DLG_Options_impression_listes, 'Dialog', wraps=vrai_dialogue) as constructeur:
                imprimante = P.ObjectListViewPrinter(vue, **self.liste.GetParametresImpression())
                self.assertTrue(imprimante.InitParametres())
            self.assertIs(imprimante.printer.engine.listCtrls[0][0], vue)
            self.assertEqual(vue.GetItemCount(), 49)
            self.assertIs(constructeur.call_args.args[0], self.frame)
            self.assertIn('3259.75', P.ListCtrlPrinter.LISTFOOTER)
            bitmap = wx.Bitmap(1100, 750)
            dc = wx.MemoryDC(bitmap)
            textes_lignes = []
            textes_entetes = []
            classe_ligne = P.ListCtrlPrinter.RowBlock
            classe_entete = P.ListCtrlPrinter.ColumnHeaderBlock
            original_ligne = classe_ligne.GetTexts
            original_entete = classe_entete.GetTexts

            def lire_ligne(bloc):
                textes = original_ligne(bloc)
                textes_lignes.append(textes)
                return textes

            def lire_entete(bloc):
                textes = original_entete(bloc)
                textes_entetes.append(textes)
                return textes
            try:
                dc.SetBackground(wx.WHITE_BRUSH)
                dc.Clear()
                bounds = wx.Rect(10, 10, 1080, 730)
                with patch.object(classe_ligne, 'GetTexts', lire_ligne), \
                     patch.object(classe_entete, 'GetTexts', lire_entete):
                    pages = imprimante.printer.CalculateTotalPages(dc, bounds)
                    self.assertGreater(pages, 0)
                    imprimante.printer.StartPrinting()
                    for page in range(1, pages + 1):
                        encore = imprimante.printer.PrintPage(dc, page, bounds)
                    self.assertFalse(encore)  # False signifie derniere page, pas une erreur.
                    self.assertEqual(imprimante.printer.engine.currentPage, pages)
                    # Le meme rendu via le callback wx doit reussir jusqu'a la
                    # derniere page : False ici annulerait le travail natif.
                    printout = imprimante.printer.printout
                    printout.bounds = bounds
                    with patch.object(printout, 'GetDC', return_value=dc), patch.object(printout, 'SetScaleAndBounds'):
                        for page in range(1, pages + 1):
                            self.assertTrue(printout.OnPrintPage(page))
            finally:
                dc.SelectObject(wx.NullBitmap)
            pixels = bytes(bitmap.ConvertToImage().GetData())
            self.assertTrue(any(pixel != 255 for pixel in pixels))
            # Le titre ne suffit plus : le moteur doit avoir reellement lu
            # des en-tetes ET des valeurs de reglements fictifs.
            self.assertTrue(any('Montant' in entete for entete in textes_entetes))
            self.assertTrue(any('Famille fictive 0' in ligne for ligne in textes_lignes))
            self.assertTrue(any('3259.75' in texte for ligne in textes_lignes for texte in ligne))
            self.assertEqual(list(base.db.connexion.execute('SELECT * FROM prestations')), avant)


    def test_snapshot_ne_depend_pas_des_colonnes_graphiques_ni_du_retri(self):
        vue = Depot._VueImpressionDepot(self.liste, self.liste.donnees)
        self.assertEqual(vue.GetColumnCount(), 8)
        self.assertEqual(vue.GetItemCount(), 49)
        self.assertEqual(vue.GetColumn(4).GetText(), 'Famille')
        self.assertEqual(vue.GetItem(0, 4).GetText(), 'Famille fictive 0')
        self.assertEqual(vue.GetItem(48, 6).GetText(), '859.75 €')
        self.assertIs(vue.GetTopLevelParent(), self.frame)
        self.liste.SetObjects([])
        self.assertEqual(vue.GetItemCount(), 49)
        self.assertEqual(vue.GetItem(0, 4).GetText(), 'Famille fictive 0')

    def test_depot_sans_reglements_interdit_un_apercu_vide(self):
        self.liste.donnees = []
        self.liste.SetObjects([])
        with patch.object(Depot.wx, 'MessageDialog') as alerte, \
             patch.object(P, 'ObjectListViewPrinter') as constructeur:
            self.assertFalse(self.liste.Apercu())
            constructeur.assert_not_called()
            alerte.return_value.ShowModal.assert_called_once_with()
            self.assertIn('Aucun règlement', alerte.call_args.args[1])

    def test_epaisseurs_fractionnaires_acceptables_par_wx(self):
        for largeur, attendu in ((.25, 0), (.75, 1), (1.5, 2), (2, 2)):
            self.assertEqual(P._PenImpression(wx.BLACK, largeur).GetWidth(), attendu)

    def test_callback_wx_succes_independant_des_pages_restantes(self):
        for classe in (P.ListCtrlPrinter.ListCtrlPrintout, PrintoutModerne):
            for pages_restantes in (True, False):
                with self.subTest(moteur=classe.__module__, pages_restantes=pages_restantes):
                    moteur, dc = Mock(), Mock()
                    moteur.PrintPage.return_value = pages_restantes
                    objet = SimpleNamespace(GetDC=lambda: dc, SetScaleAndBounds=lambda _: None,
                                            olvPrinter=moteur, bounds=(0, 0, 100, 100))
                    self.assertTrue(classe.OnPrintPage(objet, 1))
                    moteur.PrintPage.assert_called_once_with(dc, 1, objet.bounds)

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
