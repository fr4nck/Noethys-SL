# -*- coding: utf-8 -*-
"""Contrats de l'inventaire statique UI-432J, sans import applicatif."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ui432_audit_transversal as outil  # noqa: E402


class AnalyseTransversaleTests(unittest.TestCase):
    def test_signaux_reels_sans_fausse_pretention_de_causalite(self):
        code = """
def OnEnvoyer(self):
    dlg = wx.ProgressDialog('Envoi', 'Preparation', parent=None)
    resultat = mailer.Connecter()
    time.sleep(1)
    self.DB.ExecuterReq('SELECT valeur FROM fixture')
    dlg.ShowModal()
def OnChoisir(self):
    dlg = wx.Dialog(self)
    dlg.ShowModal()
"""
        resultats = outil.analyser_source(code, "Dlg/fictif.py")
        categories = {(o["fonction"], o["risque"]) for o in resultats}
        self.assertIn(("OnEnvoyer", "progression_sans_proprietaire"), categories)
        self.assertIn(("OnEnvoyer", "pause_ui_potentielle"), categories)
        self.assertIn(("OnEnvoyer", "sql_handler_potentiel"), categories)
        self.assertIn(("OnEnvoyer", "reseau_handler_potentiel"), categories)
        self.assertFalse(any(o["fonction"] == "OnChoisir" for o in resultats))
        self.assertTrue(all("SELECT" not in str(o) for o in resultats))

    def test_attente_parentee_non_signalee(self):
        source = """
def MAJ(self):
    with UTILS_Attente.BusyInfo('Texte', self):
        pass
def MAJancienne(self):
    with UTILS_Attente.BusyInfo('Texte', None):
        pass
"""
        resultats = outil.analyser_source(source, "Dlg/fictif.py")
        self.assertEqual([(r["fonction"], r["risque"]) for r in resultats],
                         [("MAJancienne", "attente_sans_proprietaire")])

    def test_analyse_compatible_avec_scripts_qui_ont_des_fonctions_internes(self):
        source = """
def OnBouton(self):
    def executer():
        return sql.ExecuterReq('fic')
    return executer()
"""
        resultats = outil.analyser_source(source, "fictif.py")
        # Le SQL d'un worker imbrique n'est pas automatiquement attribue au handler.
        self.assertEqual(resultats, [])


if __name__ == "__main__":
    unittest.main()
