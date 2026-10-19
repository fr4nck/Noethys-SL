# -*- coding: utf-8 -*-
"""RC8 #430 : contrat explicite de preference alimentaire, sans acces reseau."""
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils.UTILS_Repas_alimentaires import ConfigurationSansPorc, EstSansPorc, CompterSansPorc


class RepasSansPorcTests(unittest.TestCase):
    def setUp(self):
        self.jour = date(2026, 10, 19)
        self.unites = [(1, 10), (2, 10)]
        self.consos = [
            {"date": self.jour, "IDindividu": 1, "IDgroupe": 1, "IDunite": 10, "etat": "reservation"},
            {"date": self.jour, "IDindividu": 1, "IDgroupe": 2, "IDunite": 10, "etat": "present"},
            {"date": self.jour, "IDindividu": 2, "IDgroupe": 1, "IDunite": 10, "etat": "present"},
            {"date": self.jour, "IDindividu": 3, "IDgroupe": 1, "IDunite": 10, "etat": "absent"},
            {"date": self.jour, "IDindividu": 4, "IDgroupe": 8, "IDunite": 14, "etat": "present"},
        ]

    def test_choix_exact_sans_sous_chaine(self):
        self.assertTrue(EstSansPorc("12;34", 12, "liste_coches"))
        self.assertFalse(EstSansPorc("112;34", 12, "liste_coches"))
        self.assertFalse(EstSansPorc("Sans porc", 12, "liste_coches"))
        self.assertFalse(EstSansPorc(None, 12, "liste_coches"))
        self.assertTrue(EstSansPorc("12", 12, "liste_deroulante"))

    def test_case_coche_oui_explicitement(self):
        self.assertTrue(EstSansPorc("1", 1, "case_coche"))
        self.assertFalse(EstSansPorc("0", 1, "case_coche"))
        self.assertFalse(EstSansPorc("", 1, "case_coche"))
        self.assertFalse(EstSansPorc("oui", 1, "case_coche"))

    def test_ne_deduit_pas_du_texte(self):
        with self.assertRaises(ValueError):
            EstSansPorc("sans porc", 1, "bloc_texte")

    def test_parametrage_choisi(self):
        self.assertEqual(ConfigurationSansPorc(25, 17, "liste_coches"), (25, 17, "liste_coches"))
        self.assertEqual(ConfigurationSansPorc(24, 1, "case_coche"), (24, 1, "case_coche"))
        for x in [(None, 1, "case_coche"), (1, 0, "liste_coches"),
                  (1, 2, "case_coche"), (1, 1, "bloc_texte")]:
            with self.subTest(x=x), self.assertRaises(ValueError):
                ConfigurationSansPorc(*x)

    def test_doublons_absences_et_site_non_selectionne(self):
        result = CompterSansPorc(self.consos, {1: "12;34", 2: "7", 3: "12", 4: "12"},
                                self.unites, 12, "liste_coches")
        self.assertEqual(result[self.jour], {"sans_porc": 1, "repas": 2, "non_renseignes": 0})

    def test_reponse_non_renseignee(self):
        result = CompterSansPorc(self.consos, {1: "12"}, self.unites, 12, "liste_deroulante")
        self.assertEqual(result[self.jour], {"sans_porc": 1, "repas": 2, "non_renseignes": 1})

    def test_vacances_et_service_distinct(self):
        other = date(2026, 10, 20)
        ligne = dict(self.consos[0], date=other)
        result = CompterSansPorc(self.consos + [ligne], {1: "12", 2: "12"},
                                self.unites, 12, "liste_deroulante")
        self.assertEqual(result[self.jour]["sans_porc"], 2)
        self.assertEqual(result[other]["sans_porc"], 1)

    def test_jour_invalide_non_interprete(self):
        with self.assertRaises(ValueError):
            CompterSansPorc([dict(self.consos[0], date=None)], {}, self.unites, 1, "case_coche")


if __name__ == "__main__":
    unittest.main()
