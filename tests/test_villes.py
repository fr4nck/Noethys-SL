# -*- coding: utf-8 -*-
"""Tests des règles de sélection ville / code postal."""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))

from Utils import UTILS_Villes


class VillesTests(unittest.TestCase):
    def test_couple_existant_est_reconnu_sans_sensibilite_a_la_casse(self):
        villes = [("VITRÉ", "35500")]
        self.assertTrue(UTILS_Villes.CoupleExiste(villes, " vitré ", "35500"))
        self.assertFalse(UTILS_Villes.CoupleExiste(villes, "VITRÉ", "79370"))

    def test_codes_pour_ville_dedoublonne_sans_perdre_les_homonymes(self):
        villes = [
            ("VITRÉ", "35500"),
            ("VITRÉ", "35500"),
            ("VITRÉ", "79370"),
            ("AUTRE", "35500"),
        ]
        self.assertEqual(
            UTILS_Villes.CodesPourVille(villes, "vitré"),
            ["35500", "79370"],
        )

    def test_autocompletion_accepte_un_couple_reellement_unique(self):
        villes = [
            ("CHASSELAY", "69380"),
            ("CHASSELAY", "69380"),
            ("VITRÉ", "35500"),
        ]
        self.assertEqual(
            UTILS_Villes.AutocompletionUnique(villes, "chass"),
            ("CHASSELAY", "69380"),
        )

    def test_autocompletion_refuse_une_ville_homonyme(self):
        villes = [
            ("VITRÉ", "35500"),
            ("VITRÉ", "79370"),
        ]
        self.assertIsNone(UTILS_Villes.AutocompletionUnique(villes, "vitré"))

    def test_autocompletion_refuse_un_prefixe_ambigu(self):
        villes = [
            ("SAINT-MALO", "35400"),
            ("SAINT-MALO-DE-PHILY", "35480"),
        ]
        self.assertIsNone(UTILS_Villes.AutocompletionUnique(villes, "saint-malo"))


if __name__ == "__main__":
    unittest.main()
