# -*- coding: utf-8 -*-
"""Contrats mécaniques du dialogue de rattachement.

Ces tests ne remplacent pas une recette visuelle Windows : ils verrouillent
les causes connues du lien invisible à l'ouverture.
"""
from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Dlg" / "DLG_Rattachement.py"


class RattachementDialogContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texte = SOURCE.read_text(encoding="utf-8")

    def test_lien_nest_plus_precede_de_licone_attention(self):
        self.assertNotIn('Attention2.png', self.texte)
        self.assertIn('Saisir un nouvel individu', self.texte)

    def test_zone_html_garde_une_hauteur_minimale_visible(self):
        self.assertIn('hauteur=52', self.texte)
        self.assertNotIn('hauteur=31', self.texte)

    def test_dialogue_reste_redimensionnable_et_borne_a_lecran(self):
        self.assertIn('wx.RESIZE_BORDER', self.texte)
        self.assertIn('wx.GetClientDisplayRect()', self.texte)
        self.assertIn('zone_ecran.GetHeight() - 40', self.texte)


if __name__ == "__main__":
    unittest.main()
