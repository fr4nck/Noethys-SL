# -*- coding: utf-8 -*-
"""Chargé en premier par « python -m unittest discover -s tests » (ordre
alphabétique) : installe la garde réseau avant l'import des autres modules
de test, dont certains lisent la base dès l'import (valeurs par défaut
calculées par FonctionsPerso.GenerationNomDoc)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402


class GardeReseauTests(unittest.TestCase):

    def test_connexion_reseau_interdite(self):
        import GestionDB
        db = GestionDB.DB(nomFichier=u"3306;127.0.0.1;test;motdepasse[RESEAU]garde", suffixe=None)
        self.assertEqual(db.echec, 1)
        self.assertIsInstance(db.erreur, _garde_reseau.ConnexionReseauInterdite)

    def test_configuration_de_test_explicite(self):
        import os
        from Utils import UTILS_Config
        chemin = os.path.abspath(UTILS_Config.GetNomFichierConfig())
        self.assertTrue(chemin.startswith(os.path.abspath(_garde_reseau.PROFIL_TEST)), chemin)
        self.assertNotIn("Portable", chemin)
        self.assertEqual(UTILS_Config.FichierConfig().GetItemConfig("nomFichier"), "")


if __name__ == "__main__":
    unittest.main()
