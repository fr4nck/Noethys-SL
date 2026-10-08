# -*- coding: utf-8 -*-
"""Contrat de sécurité du bouton Ajouter de la fiche Famille."""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Dlg" / "DLG_Famille.py"


class FamilleAjoutContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texte = SOURCE.read_text(encoding="utf-8")

    def test_un_seul_binding_du_bouton_ajouter(self):
        bindings = re.findall(
            r"self\.Bind\(wx\.EVT_BUTTON,\s*self\.(\w+),\s*self\.bouton_ajouter\)",
            self.texte,
        )
        self.assertEqual(bindings, ["OnBoutonAjouter"])

    def test_aucun_handler_ajout_individu_legacy(self):
        self.assertNotIn("def OnBoutonAjouterIndividu", self.texte)
        self.assertNotIn("IDindividu = 5", self.texte)
        self.assertNotIn("IDcategorie = 2", self.texte)

    def test_chemin_normal_passe_par_ctrl_composition(self):
        motif = (
            r"def OnBoutonAjouter\(self, event\):\s*"
            r"self\.ctrl_composition\.Ajouter\(\)"
        )
        self.assertRegex(self.texte, motif)

    def test_bouton_ajouter_ne_fait_aucun_insert_direct_rattachements(self):
        debut = self.texte.index("def OnBoutonAjouter(self, event):")
        fin = self.texte.index("def OnBoutonModifier", debut)
        bloc = self.texte[debut:fin]
        self.assertNotIn("ReqInsert", bloc)
        self.assertNotIn("rattachements", bloc)


if __name__ == "__main__":
    unittest.main()
