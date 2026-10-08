# -*- coding: utf-8 -*-
"""Saisie d'un règlement : les boutons de paramétrage Mode et Émetteur
ouvrent leurs dialogues et permettent d'ajouter un mode et un émetteur.

Régression : TAILLE_IMAGE valait (132/2.0, 72/2.0). wx.ImageList refuse les
float sous Phoenix : l'exception, levée dans le gestionnaire du bouton,
empêchait toute ouverture sans aucun message.

Base SQLite temporaire uniquement (RedirectionGestionDB), sans donnée réelle.
"""

import os
import sqlite3
import sys
import traceback
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

import wx  # noqa: E402

APP = wx.GetApp() or wx.App(False)

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402


TABLES = ("modes_reglements", "emetteurs", "familles", "comptes_payeurs", "payeurs",
          "reglements", "depots", "comptes_bancaires", "ventilation", "prestations",
          "individus", "rattachements", "titulaires_helios", "parametres")


class ParametrageReglementTests(unittest.TestCase):

    def setUp(self):
        self.base = BaseTest()
        for nom in TABLES:
            if nom in Tables.DB_DATA and not self.base.db.IsTableExists(nom):
                self.base.db.CreationTable(nom, dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.base.inserer("modes_reglements", ["IDmode", "label", "numero_piece"], [(1, u"Chèque", "ALPHA")])
        self.base.inserer("emetteurs", ["IDemetteur", "IDmode", "nom"], [(1, 1, u"Banque témoin")])
        self.base.inserer("familles", ["IDfamille", "IDcompte_payeur"], [(1, 1)])
        self.base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(1, 1)])
        self.base.inserer("payeurs", ["IDpayeur", "IDcompte_payeur", "nom"], [(1, 1, u"Payeur témoin")])
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.cwd = os.getcwd()
        os.chdir(str(NOETHYS))
        self.erreurs = []
        self.hook = sys.excepthook
        sys.excepthook = lambda t, v, tb: self.erreurs.append("".join(traceback.format_exception(t, v, tb)))
        self.vus = []

    def tearDown(self):
        sys.excepthook = self.hook
        os.chdir(self.cwd)
        self.redirection.__exit__(None, None, None)
        self.base.fermer()

    def _modal_courant(self):
        for fenetre in reversed(list(wx.GetTopLevelWindows())):
            if isinstance(fenetre, wx.Dialog) and fenetre.IsModal():
                return fenetre
        return None

    def _piloter(self):
        """ Ajoute un élément dans le dialogue de paramétrage puis le ferme. """
        fenetre = self._modal_courant()
        if fenetre is None:
            return
        nom = type(fenetre).__module__.split(".")[-1]
        self.vus.append(nom)
        try:
            if nom == "DLG_Modes_reglements" and "ajout_mode" not in self.vus:
                self.vus.append("ajout_mode")
                wx.CallLater(200, self._piloter)
                fenetre.ctrl_listview.Ajouter(None)
                wx.CallLater(200, self._piloter)
                return
            if nom == "DLG_Emetteurs" and "ajout_emetteur" not in self.vus:
                self.vus.append("ajout_emetteur")
                wx.CallLater(200, self._piloter)
                fenetre.ctrl_emetteurs.Ajouter(None)
                wx.CallLater(200, self._piloter)
                return
            if nom == "DLG_Saisie_mode_reglement":
                fenetre.ctrl_label.SetValue(u"Virement témoin")
                fenetre.OnBoutonOk(None)
                return
            if nom == "DLG_Saisie_emetteur":
                fenetre.ctrl_nom.SetValue(u"Banque ajoutée")
                fenetre.OnBoutonOk(None)
                return
            fenetre.EndModal(wx.ID_CANCEL)
        except Exception:
            self.erreurs.append(traceback.format_exc())
            fenetre.EndModal(wx.ID_CANCEL)

    def _cliquer(self, bouton):
        wx.CallLater(300, self._piloter)
        evt = wx.CommandEvent(wx.wxEVT_BUTTON, bouton.GetId())
        evt.SetEventObject(bouton)
        bouton.GetEventHandler().ProcessEvent(evt)

    def test_tailles_d_image_entieres(self):
        from Ol import OL_Modes_reglements, OL_Emetteurs
        from Dlg import DLG_Emetteurs
        for module in (OL_Modes_reglements, OL_Emetteurs, DLG_Emetteurs):
            for valeur in module.TAILLE_IMAGE:
                self.assertIsInstance(valeur, int, module.__name__)
        self.assertEqual(OL_Modes_reglements.TAILLE_IMAGE, (66, 36))

    def test_boutons_mode_et_emetteur_ajoutent_en_base(self):
        from Dlg import DLG_Saisie_reglement
        frame = wx.Frame(None)
        dlg = DLG_Saisie_reglement.Dialog(frame, IDcompte_payeur=1, IDreglement=None)
        try:
            self.assertTrue(dlg.bouton_mode.IsEnabled())
            self.assertTrue(dlg.bouton_emetteur.IsEnabled())
            self._cliquer(dlg.bouton_mode)
            self._cliquer(dlg.bouton_emetteur)
        finally:
            dlg.Destroy()
            frame.Destroy()

        self.assertEqual(self.erreurs, [])
        for nom in ("DLG_Modes_reglements", "DLG_Saisie_mode_reglement", "DLG_Emetteurs", "DLG_Saisie_emetteur"):
            self.assertIn(nom, self.vus)
        connexion = sqlite3.connect(self.base.chemin)
        try:
            modes = connexion.execute("SELECT label FROM modes_reglements ORDER BY IDmode;").fetchall()
            emetteurs = connexion.execute("SELECT IDmode, nom FROM emetteurs ORDER BY IDemetteur;").fetchall()
        finally:
            connexion.close()
        self.assertEqual(modes, [(u"Chèque",), (u"Virement témoin",)])
        self.assertEqual(emetteurs, [(1, u"Banque témoin"), (1, u"Banque ajoutée")])


if __name__ == "__main__":
    unittest.main()
