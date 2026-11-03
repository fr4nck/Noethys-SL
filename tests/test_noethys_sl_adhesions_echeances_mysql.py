# -*- coding: utf-8 -*-
"""Qualification de la preparation des cotisations sur serveur MySQL 5.7 jetable.

Ne s'execute qu'avec les variables NOETHYS_TEST_MYSQL_* pointant vers
127.0.0.1 ou localhost. Utilise une base fictive a nom aleatoire,
creee et detruite exclusivement par la fixture des adhesions.
"""
import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau
from _fixtures_noethys_db import RedirectionGestionDB
import test_noethys_sl_adhesions_concurrence as concurrence
import GestionDB
from Utils import UTILS_Adhesions as A
from Utils import UTILS_Adhesions_echeances as E

JOUR = datetime.date(2026, 10, 19)


@unittest.skipUnless(_garde_reseau.ParametresMySQLDeTest(),
                     "serveur MySQL local jetable non declare")
class FacturationAdhesionsMySQLTests(unittest.TestCase):
    setUp = concurrence.ConcurrenceMySQLTests.setUp
    tearDown = concurrence.ConcurrenceMySQLTests.tearDown
    _nom = concurrence.ConcurrenceMySQLTests._nom
    _compter = concurrence.ConcurrenceMySQLTests._compter

    def proposer(self):
        return E.Proposer(
            datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
            date_reference=JOUR, liste_activites=[1],
            IDcompte_payeur=None)

    def test_apercu_puis_creation_unique_sur_mysql(self):
        with RedirectionGestionDB(self._nom(self.base)):
            proposition = self.proposer()
            self.assertEqual(proposition["a_verifier"], [])
            self.assertEqual(len(proposition["propositions"]), 1)
            self.assertEqual(proposition["propositions"][0]["montant"], 7.5)
            self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 0)
            self.assertEqual(self._compter("SELECT COUNT(*) FROM prestations;"), 0)

            retours = E.Executer(proposition, confirmation=True)
            self.assertEqual([item["statut"] for item in retours], [A.STATUT_CREE])
            self.assertEqual(self.proposer()["propositions"], [])

        self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 1)
        self.assertEqual(self._compter(
            "SELECT COUNT(*) FROM prestations WHERE categorie='cotisation';"), 1)
        self.assertEqual(self._compter(
            "SELECT COUNT(*) FROM historique WHERE IDcategorie=21;"), 1)

    def test_sql_invalide_ne_suggere_pas_zero_cotisation(self):
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)
        try:
            db.cursor.execute("DROP TABLE cotisations_activites;")
            db.Commit()
        finally:
            db.Close()
        with RedirectionGestionDB(self._nom(self.base)):
            with self.assertRaisesRegex(RuntimeError, "Lecture SQL"):
                self.proposer()
        self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 0)
        self.assertEqual(self._compter(
            "SELECT COUNT(*) FROM prestations WHERE categorie='cotisation';"), 0)


if __name__ == "__main__":
    unittest.main()
