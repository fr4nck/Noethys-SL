# -*- coding: utf-8 -*-
"""Simulation UI de l'encadrement sans modifier de donnees."""
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
try:
    import wx
except ImportError:
    wx = None


@unittest.skipIf(wx is None, "wxPython absent")
class SimulationDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)
        from Dlg import DLG_Encadrement
        cls.module = DLG_Encadrement

    def setUp(self):
        colonnes = [{"IDcolonne": 5, "nom_colonne": "Repas enfants A",
                     "categorie": "numerique_avec_suggestion",
                     "parametres": {"unites": [(2, 9)]}}]
        self.dialog = self.module.Dialog(None, colonnes=colonnes,
                                         date_debut=date(2026, 10, 19), date_fin=date(2026, 10, 19))
        self.dialog.ctrl_site.SetValue("Site A")
        self.addCleanup(self.dialog.Destroy)

    def test_affiche_les_animateurs_sans_comptabiliser_l_adulte(self):
        lignes = [{"IDindividu": 1, "IDgroupe": 2, "IDunite": 9, "date": "2026-10-19", "etat": "present"},
                  {"IDindividu": 2, "IDgroupe": 2, "IDunite": 9, "date": "2026-10-19", "etat": "present"},
                  {"IDindividu": 3, "IDgroupe": 2, "IDunite": 9, "date": "2026-10-19", "etat": "present"}]
        personnes = {1: {"date_naiss": "2021-01-01"},
                     2: {"date_naiss": "2016-01-01"},
                     3: {"date_naiss": "1985-01-01"}}
        with patch.object(self.dialog, "ChargerConsommations", return_value=(lignes, personnes)) as charge:
            self.dialog.OnCalculer()
        self.assertIn("2 animateur(s)", self.dialog.ctrl_resultats.GetValue())
        self.assertIn("1 moins de 6 ans", self.dialog.ctrl_resultats.GetValue())
        self.assertEqual(charge.call_args.args[0], {(2, 9)})

    def test_chargement_filtre_les_groupes_et_ne_fait_que_du_select(self):
        fake = type("Db", (), {})()
        fake.requete = None
        fake.ferme = False
        def executer(req):
            fake.requete = req
            return True
        def resultat():
            return [(1, "2026-10-19", 2, 9, "present", "2021-01-01"),
                    (2, "2026-10-19", 3, 9, "present", "2020-01-01")]
        fake.ExecuterReq = executer
        fake.ResultatReq = resultat
        fake.Close = lambda: setattr(fake, "ferme", True)
        with patch.object(self.module.GestionDB, "DB", return_value=fake):
            lignes, personnes = self.dialog.ChargerConsommations({(2, 9)})
        self.assertEqual(len(lignes), 1)
        self.assertEqual(set(personnes), {1})
        self.assertTrue(fake.requete.lstrip().startswith("SELECT"))
        self.assertTrue(fake.ferme)


if __name__ == "__main__":
    unittest.main()
