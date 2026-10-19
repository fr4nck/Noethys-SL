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

    def test_nouveau_modele_invalide_bloque_pdf(self):
        from Dlg import DLG_Controle_repas
        faux = MagicMock()
        faux.ctrl_repas.GetDonnees.return_value = {
            "liste_colonnes": [{"parametres": {"role_repas": "sans_porc"}}],
            "erreurs_sans_porc": {5: "Question alimentaire invalide"},
        }
        with patch.object(DLG_Controle_repas, "Dialog", side_effect=ValueError("Question invalide")), \
                patch.object(wx, "MessageBox", return_value=wx.YES) as message:
            self.assertIs(self.module.Dialog.ControleAvantEmission(faux), False)
        message.assert_called_once()
        self.assertEqual(message.call_args.args[2] & wx.YES_NO, 0)

    def test_ancien_modele_demande_confirmation(self):
        from Dlg import DLG_Controle_repas
        faux = MagicMock()
        faux.ctrl_repas.GetDonnees.return_value = {
            "liste_colonnes": [{"parametres": None}],
        }
        with patch.object(DLG_Controle_repas, "Dialog", side_effect=ValueError("Pas de roles")), \
                patch.object(wx, "MessageBox", return_value=wx.YES) as message:
            self.assertTrue(self.module.Dialog.ControleAvantEmission(faux))
        self.assertTrue(message.call_args.args[2] & wx.YES_NO)

    def test_sans_reponse_alimentaire_exige_acquittement(self):
        from Dlg import DLG_Controle_repas
        from datetime import date
        jour = date(2026, 10, 19)
        classe = MagicMock()
        classe.GetValeur.return_value = 2
        donnees = {
            "liste_dates": [jour, "Total"],
            "liste_colonnes": [{"IDcolonne": 6, "nom_colonne": "Sans porc",
                "categorie": "numerique_avec_suggestion",
                "parametres": {"role_repas": "sans_porc", "site_directeur": "A",
                               "service_directeur": "midi"}}],
            "cases": {(0, 0): classe},
            "sans_porc": {6: {jour: {"sans_porc": 2, "repas": 4,
                                       "non_renseignes": 1}}},
            "erreurs_sans_porc": {},
        }
        dlg = DLG_Controle_repas.Dialog(None, donnees)
        try:
            self.assertEqual(len(dlg.sans_reponse), 1)
            with patch.object(wx, "MessageBox", return_value=wx.NO) as confirmation, \
                    patch.object(dlg, "EndModal") as fin:
                dlg.OnValider(None)
                fin.assert_not_called()
                confirmation.assert_called_once()
            with patch.object(wx, "MessageBox", return_value=wx.YES), \
                    patch.object(dlg, "EndModal") as fin:
                dlg.OnValider(None)
                fin.assert_called_once_with(wx.ID_OK)
        finally:
            dlg.Destroy()

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
