# -*- coding: utf-8 -*-
"""Recette graphique Connecthys, vraie fenetre wx sur runner Windows isole.

Les widgets et methodes de production sont utilises. La source des comptes
est une fixture fictive lue sans connexion reseau ni ecriture SQL. Cette
recette prouve l'affichage et le fonctionnement du dialogue SOURCE, PAS du
binaire installe chez le directeur.
"""
import datetime
import faulthandler
import os
import sys
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "noethys", ROOT / "tests"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

SUR_RUNNER = sys.platform == "win32" and os.getenv("GITHUB_ACTIONS") == "true"


@unittest.skipUnless(SUR_RUNNER, "Affichage reserve au runner Windows isole")
class RecetteConnecthysGraphique(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import _garde_reseau  # noqa: F401 - interdire toute connexion de test
        import wx
        from Dlg import DLG_Saisie_portail_demande as Module
        from test_noethys_sl_etat_global_historique import application_wx

        cls.wx = wx
        cls.module = Module
        cls.app = application_wx(wx)
        cls.repertoire = Path(os.getenv("NOETHYS_SL_RECETTE_SORTIE")
                             or tempfile.mkdtemp(prefix="recette-connecthys-gui-"))
        cls.repertoire.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.garde = threading.Timer(75, self._blocage)
        self.garde.daemon = True
        self.garde.start()
        self.track = NS(IDaction=41, IDfamille=3, IDindividu=77,
                        categorie="reservations", etat="attente")

        # Construction de la VRAIE fenetre Dialog, sans installer de fichier,
        # connexion portail, reception de donnees ni dialogue modal.
        wx = self.wx
        Module = self.module
        self.mock_db1 = mock.patch.object(Module.Dialog, "Importation", return_value=None)
        self.mock_db2 = mock.patch.object(Module.Dialog, "MAJ", return_value=None)
        self.mock_modele = mock.patch.object(Module.CTRL_Choix_modele, "MAJ", return_value=None)
        self.mock_grille = mock.patch.object(
            Module.DLG_Badgeage_grille, "CTRL", side_effect=lambda parent: wx.Panel(parent))
        self.mock_preferences = mock.patch.object(
            Module.UTILS_Dialogs, "AjusteSizePerso", return_value=None)
        self.mock_diag = mock.patch.object(
            Module.UTILS_Diagnostic_ui, "Diagnostic", return_value=mock.Mock())
        for patcher in (self.mock_db1, self.mock_db2, self.mock_modele,
                        self.mock_grille, self.mock_preferences, self.mock_diag):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.dialogue = Module.Dialog(None, track=self.track, tracks=[self.track])
        self.addCleanup(self._detruire)
        self.dialogue.ctrl_famille.SetValue("FAMILLE FICTIVE - LEA")
        self.dialogue.ctrl_solde.SetSolde(Decimal("-135.50"))
        self.dialogue.SetSize((1180, 940))
        self.dialogue.Show()
        self._tour_events()

    def tearDown(self):
        self.garde.cancel()

    def _detruire(self):
        if self.dialogue:
            self.dialogue.Destroy()
            self._tour_events()
            self.dialogue = None

    def _blocage(self):
        print("BLOCAGE RECETTE CONNECTHYS - echec explicite", file=sys.stderr)
        faulthandler.dump_traceback(all_threads=True)
        sys.stderr.flush()
        os._exit(3)

    @classmethod
    def _tour_events(cls):
        for _ in range(8):
            cls.wx.YieldIfNeeded()
            cls.wx.MilliSleep(15)

    @staticmethod
    def _situation_fictive(famille=3):
        date = datetime.date(2026, 11, 9)
        if famille == 4:
            return dict(
                date=date, solde_du_jour=Decimal("20.00"),
                factures_impayees=[], total_factures=Decimal("0.00"),
                adhesion={"statut": "expiree", "nom": "Adhesion fictive",
                          "debut": datetime.date(2025, 1, 1),
                          "fin": datetime.date(2025, 12, 31)},
                historique_annulations=dict(
                    reservations=5, annulations=0, taux=Decimal("0.0"),
                    perimetre="connecthys_traites_conserves",
                    premiere_demande=datetime.date(2025, 1, 1),
                    annulations_non_appariees=0, lignes_inexploitables=0))
        return dict(
            date=date, solde_du_jour=Decimal("-83.50"),
            factures_impayees=[
                {"IDfacture": 100, "numero": 100, "prefixe": "F",
                 "date_debut": datetime.date(2026, 9, 1),
                 "date_fin": datetime.date(2026, 9, 30),
                 "montant": Decimal("80.00"), "reste": Decimal("30.00")},
                {"IDfacture": 101, "numero": 101, "prefixe": "",
                 "date_debut": datetime.date(2026, 10, 1),
                 "date_fin": datetime.date(2026, 10, 31),
                 "montant": Decimal("90.00"), "reste": Decimal("70.00")},
            ], total_factures=Decimal("100.00"),
            adhesion={"statut": "en_cours", "nom": "Adhesion annuelle fictive",
                      "portee": "famille", "debut": datetime.date(2026, 9, 1),
                      "fin": datetime.date(2027, 8, 31),
                      "montant": Decimal("12.00")},
            historique_annulations=dict(
                reservations=24, annulations=3, taux=Decimal("12.5"),
                perimetre="connecthys_traites_conserves",
                premiere_demande=datetime.date(2024, 9, 1),
                annulations_non_appariees=0, lignes_inexploitables=0))

    def _capturer(self, titre):
        wx = self.wx
        self.dialogue.Update()
        self._tour_events()
        largeur, hauteur = self.dialogue.GetSize()
        image = wx.Bitmap(largeur, hauteur)
        memoire = wx.MemoryDC(image)
        try:
            import ctypes
            from ctypes import wintypes
            imprimer = ctypes.windll.user32.PrintWindow
            imprimer.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
            resultat = imprimer(
                self.dialogue.GetHandle(), memoire.GetHandle(), 2)
            self.assertNotEqual(resultat, 0, "PrintWindow a echoue")
        finally:
            memoire.SelectObject(wx.NullBitmap)
        fichier = self.repertoire / titre
        self.assertTrue(image.SaveFile(str(fichier), wx.BITMAP_TYPE_PNG))
        self.assertGreater(fichier.stat().st_size, 1500)
        return fichier

    def _verifier_geometrie(self):
        d = self.dialogue
        self.assertFalse(d.ctrl_solde.IsShown(), "Ancien solde rouge visible")
        self.assertFalse(hasattr(d, "label_solde"), "Etiquette solde en doublon")
        self.assertIs(d.panel_situation.GetParent(), d.scroll_contenu)
        self.assertIs(d.box_traitement_staticbox.GetParent(), d.scroll_contenu)

        # Sur un ecran bas, faire defiler la zone metier en gardant toujours
        # les boutons de traitement dans la partie fixe du dialogue.
        zone = d.scroll_contenu
        zone.Layout()
        zone.FitInside()
        self._tour_events()
        y = d.panel_situation.GetPosition().y
        hauteur = zone.GetClientSize().height
        cible = max(0, y - max(0, (hauteur - d.panel_situation.GetSize().height) // 2))
        zone.Scroll(0, cible // 14)
        self._tour_events()

        cartes = [d.situation_solde_carte, d.situation_factures_carte,
                  d.situation_adhesion_carte]
        positions = [c.GetScreenRect() for c in cartes]
        self.assertTrue(all(c.IsShownOnScreen() for c in cartes))
        self.assertLess(positions[0].GetRight(), positions[1].GetLeft())
        self.assertLess(positions[1].GetRight(), positions[2].GetLeft())
        self.assertEqual(len(set(x.GetTop() for x in positions)), 1)
        self.assertGreater(min(x.GetWidth() for x in positions), 180)

        viewport = zone.GetScreenRect()
        for c in cartes:
            rect = c.GetScreenRect()
            self.assertGreaterEqual(rect.GetLeft(), viewport.GetLeft() - 2)
            self.assertLessEqual(rect.GetRight(), viewport.GetRight() + 2)
            self.assertGreaterEqual(rect.GetTop(), viewport.GetTop() - 2)
            self.assertLessEqual(rect.GetBottom(), viewport.GetBottom() + 2)

        client_left, client_top = d.ClientToScreen((0, 0))
        client_width, client_height = d.GetClientSize()
        for c in (d.bouton_automatique, d.bouton_manuel, d.bouton_fermer):
            rect = c.GetScreenRect()
            self.assertIs(c.GetParent(), d, "Bouton embarque dans la zone defilante")
            self.assertGreaterEqual(rect.GetLeft(), client_left - 2)
            self.assertLessEqual(rect.GetRight(), client_left + client_width + 2)
            self.assertGreaterEqual(rect.GetTop(), client_top - 2)
            self.assertLessEqual(rect.GetBottom(), client_top + client_height + 2)
        self.assertTrue(d.bouton_automatique.IsEnabled())
        self.assertTrue(d.bouton_manuel.IsEnabled())

    def test_01_afficher_la_vraie_fenetre_trois_cartes(self):
        d = self.dialogue
        with mock.patch.object(self.module.UTILS_Portail_situation, "LireSituation",
                               return_value=self._situation_fictive()) as lire:
            d.MAJ_situation()
        lire.assert_called_once_with(3, 77)
        self._tour_events()
        self._verifier_geometrie()
        self.assertIn("83,50", d.situation_solde_jour.GetLabel())
        self.assertIn("135.50", d.situation_solde_global.GetLabel())
        self.assertEqual(d.situation_factures_table.GetItemCount(), 2)
        self.assertIn("100,00", d.situation_factures_total.GetLabel())
        self.assertIn("Adhésion en cours", d.situation_adhesion_statut.GetLabel())
        self.assertIn("12,5", d.situation_solde_annulations.GetLabel())
        self.assertIn("3 annulation(s) / 24 réservation(s)",
                      d.situation_solde_historique.GetLabel())
        self._capturer("01_situation_famille_fictive.png")

    def test_02_changer_de_famille_sans_valeurs_anciennes(self):
        d = self.dialogue
        self.track.IDfamille = 4
        self.track.IDindividu = 78
        d.ctrl_solde.SetSolde(Decimal("20.00"))
        with mock.patch.object(self.module.UTILS_Portail_situation, "LireSituation",
                               return_value=self._situation_fictive(4)) as lire:
            d.MAJ_situation()
        lire.assert_called_once_with(4, 78)
        self._tour_events()
        self.assertEqual(d.situation_factures_table.GetItemCount(), 0)
        self.assertIn("Aucune facture", d.situation_factures_total.GetLabel())
        self.assertIn("20,00", d.situation_solde_jour.GetLabel())
        self.assertIn("Adhésion expirée", d.situation_adhesion_statut.GetLabel())
        self.assertIn("0,0", d.situation_solde_annulations.GetLabel())
        self._verifier_geometrie()
        self._capturer("02_autre_famille_fictive.png")

    def test_03_lecture_comptable_indisponible_pas_de_verrou(self):
        d = self.dialogue
        with mock.patch.object(self.module.UTILS_Portail_situation, "LireSituation",
                               side_effect=RuntimeError("panne lecture fictive")), \
                mock.patch.object(self.module.wx, "MessageDialog",
                                  side_effect=AssertionError("Boite bloquante")):
            d.MAJ_situation()
        self._tour_events()
        self.assertIn("indisponible", d.situation_solde_jour.GetLabel())
        self.assertIn("indisponible", d.situation_factures_total.GetLabel().lower())
        self.assertEqual(d.situation_factures_table.GetItemCount(), 0)
        self._verifier_geometrie()
        self._capturer("03_lecture_indisponible.png")

    def test_05_calendrier_en_zone_defilante_sauvegarde_par_dialogue(self):
        """La correction petit ecran ne perd pas les evenements calendrier."""
        d = self.dialogue
        self.assertIs(d.ctrl_date_validation.GetParent(), d.scroll_contenu)
        with mock.patch.object(d, "Sauvegarde", return_value=True) as enregistrer:
            d.ctrl_date_validation.OnDateChanged(None)
        enregistrer.assert_called_once_with()
        self.assertIs(d.bouton_automatique.GetParent(), d)
        self.assertIs(d.bouton_manuel.GetParent(), d)

    def test_04_autre_categorie_cache_la_synthese(self):
        d = self.dialogue
        self.track.categorie = "reglements"
        with mock.patch.object(self.module.UTILS_Portail_situation, "LireSituation",
                               side_effect=AssertionError("Lecture non necessaire")):
            d.MAJ_situation()
        self.assertFalse(d.panel_situation.IsShown())
        self.assertTrue(d.bouton_automatique.IsEnabled())
        self.assertTrue(d.bouton_manuel.IsEnabled())
        self._capturer("04_autre_categorie.png")


if __name__ == "__main__":
    unittest.main()
