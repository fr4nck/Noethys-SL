# -*- coding: utf-8 -*-
"""Édition d'un devis pour une famille sans adresse complète.

Régression : la rue du titulaire (None) était passée telle quelle à
Grid.SetCellValue, que wxPython Phoenix refuse : le dialogue plantait à
l'ouverture. Base SQLite temporaire, sans donnée réelle.
"""

import os
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau

NOETHYS = TESTS.parent / "noethys"
import wx  # noqa: E402

APP = wx.GetApp() or wx.App(False)

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402


class DevisAdresseIncompleteTests(unittest.TestCase):

    def setUp(self):
        self.base = BaseTest()
        for nom in Tables.DB_DATA:
            if not self.base.db.IsTableExists(nom):
                self.base.db.CreationTable(nom, dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.base.inserer("organisateur", ["IDorganisateur", "nom"], [(1, u"Association témoin")])
        self.base.inserer("familles", ["IDfamille", "IDcompte_payeur"], [(1, 1)])
        self.base.inserer("comptes_payeurs", ["IDcompte_payeur", "IDfamille"], [(1, 1)])
        self.base.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite"], [(1, u"TEMOIN", u"Alex", 1)])
        self.base.inserer("rattachements", ["IDrattachement", "IDindividu", "IDfamille", "IDcategorie", "titulaire"], [(1, 1, 1, 1, 1)])
        self.redirection = RedirectionGestionDB(self.base.chemin)
        self.redirection.__enter__()
        self.cwd = os.getcwd()
        os.chdir(str(NOETHYS))

    def tearDown(self):
        os.chdir(self.cwd)
        self.redirection.__exit__(None, None, None)
        self.base.fermer()

    def test_ouverture_sans_rue_ni_ville(self):
        from Dlg import DLG_Impression_devis
        hote = wx.Frame(None)
        dlg = DLG_Impression_devis.Dialog(hote, IDfamille=1)
        try:
            donnees = dlg.ctrl_donnees
            self.assertEqual(donnees.GetValeur("rue"), u"")
            self.assertEqual(donnees.GetValeur("ville"), u"")
            self.assertIn(u"TEMOIN Alex", donnees.GetValeur("nom"))
        finally:
            dlg.Destroy()
            hote.Destroy()


if __name__ == "__main__":
    unittest.main()
