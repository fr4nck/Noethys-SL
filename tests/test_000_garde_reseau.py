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


    def test_serveur_local_autorise_seul(self):
        import os
        from unittest import mock
        import GestionDB
        env = {"NOETHYS_TEST_MYSQL_HOST": "127.0.0.1", "NOETHYS_TEST_MYSQL_PORT": "3307",
               "NOETHYS_TEST_MYSQL_USER": "test", "NOETHYS_TEST_MYSQL_PASSWORD": "x"}
        with mock.patch.dict(os.environ, env):
            with _garde_reseau.ServeurMySQLDeTest():
                for autre in (u"3306;10.0.0.5;u;p[RESEAU]autre", u"3307;192.168.1.10;u;p[RESEAU]autre",
                              u"3306;127.0.0.1;u;p[RESEAU]autre"):
                    db = GestionDB.DB(nomFichier=autre, suffixe=None)
                    self.assertEqual(db.echec, 1, autre)
                    self.assertIsInstance(db.erreur, _garde_reseau.ConnexionReseauInterdite)
            # Hors du bloc, même le serveur local de test est refusé.
            db = GestionDB.DB(nomFichier=u"3307;127.0.0.1;u;p[RESEAU]autre", suffixe=None)
            self.assertIsInstance(db.erreur, _garde_reseau.ConnexionReseauInterdite)
        with mock.patch.dict(os.environ, dict(env, NOETHYS_TEST_MYSQL_HOST="203.0.113.10")):
            with self.assertRaises(_garde_reseau.ConnexionReseauInterdite):
                with _garde_reseau.ServeurMySQLDeTest():
                    pass


if __name__ == "__main__":
    unittest.main()
