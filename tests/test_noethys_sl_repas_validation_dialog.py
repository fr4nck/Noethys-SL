# -*- coding: utf-8 -*-
"""#430 : contrat de controle avant impression et creation mail."""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
try:
    import wx
except ImportError:
    wx = None


@unittest.skipIf(wx is None, "wxPython absent")
class ControleEmissionUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)
        from Dlg import DLG_Saisie_commande
        cls.module = DLG_Saisie_commande

    def test_annulation_bloque_impression(self):
        faux = MagicMock()
        faux.ControleAvantEmission.return_value = False
        self.assertIs(self.module.Dialog.Imprimer(faux), False)
        faux.CreationPDF.assert_not_called()

    def test_annulation_bloque_email(self):
        faux = MagicMock()
        faux.ctrl_repas.GetDonnees.return_value = {"restaurateur_mail": "restaurateur@example.invalid"}
        faux.ControleAvantEmission.return_value = False
        with patch("Utils.UTILS_Envoi_email.EnvoiEmailFamille") as envoi:
            self.assertIs(self.module.Dialog.OnBoutonEmail(faux, None), False)
            envoi.assert_not_called()

    def test_confirmation_puis_impression(self):
        faux = MagicMock()
        faux.ControleAvantEmission.return_value = True
        self.module.Dialog.Imprimer(faux)
        faux.CreationPDF.assert_called_once_with()

    def test_dialogue_controle_avec_donnees_fictives(self):
        from Dlg import DLG_Controle_repas
        from datetime import date
        class Case:
            def __init__(self, value):
                self.value = value
            def GetValeur(self):
                return self.value
            def SetValeur(self, v):
                self.value = v
        entree = {"liste_dates": [date(2026, 10, 19), "Total"],
                  "liste_colonnes": [{"nom_colonne": "Petits", "categorie": "numerique_avec_suggestion",
                      "parametres": {"role_repas": "moins_6", "site_directeur": "A", "service_directeur": "midi"}}],
                  "cases": {(0, 0): Case(5)}, "erreurs_sans_porc": {}}
        dlg = DLG_Controle_repas.Dialog(None, entree)
        try:
            self.assertEqual(dlg.grid.GetNumberRows(), 1)
            self.assertEqual(dlg.grid.GetCellValue(0, 11), "5")
            dlg.grid.SetCellValue(0, 3, "6")
            dlg.LireValeurs()
            self.assertEqual(dlg.grid.GetCellValue(0, 11), "6")
        finally:
            dlg.Destroy()


if __name__ == "__main__":
    unittest.main()
