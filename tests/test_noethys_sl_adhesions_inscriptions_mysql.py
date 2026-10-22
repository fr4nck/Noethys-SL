# -*- coding: utf-8 -*-
"""Recette MySQL 5.7 isolee : activites associees aux adhesions automatiques.

Utilise exclusivement NOETHYS_TEST_MYSQL_HOST=127.0.0.1, cree puis supprime
sa propre base zz_test_adh_*, sans aucune base Noethys de production.
"""
import datetime
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: F401
from _fixtures_noethys_db import RedirectionGestionDB
from test_noethys_sl_adhesions_concurrence import ConcurrenceMySQLTests
import GestionDB
from Data import DATA_Tables as Tables
from Utils import UTILS_Adhesions as A

D = datetime.date
JOUR = D(2026, 10, 15)


@unittest.skipUnless(os.environ.get("NOETHYS_TEST_MYSQL_HOST"),
                     "MySQL local jetable non configure")
class AssociationsMySQLTests(unittest.TestCase):
    setUp = ConcurrenceMySQLTests.setUp
    tearDown = ConcurrenceMySQLTests.tearDown
    _nom = ConcurrenceMySQLTests._nom
    _compter = ConcurrenceMySQLTests._compter

    def _ouvrir(self):
        return GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)

    def _preparer(self, avec_participation=True):
        db = self._ouvrir()
        try:
            db.CreationTable("parametres", dicoDB=Tables.DB_DATA)
            for sql in [
                "INSERT INTO activites (IDactivite,nom) VALUES (2,'Activite B');",
                "INSERT INTO activites (IDactivite,nom) VALUES (3,'Activite C');",
                "INSERT INTO inscriptions (IDinscription,IDindividu,IDfamille,IDcompte_payeur,IDactivite,date_inscription,statut) VALUES (101,100,1,11,1,'2026-09-01','ok');",
                "INSERT INTO inscriptions (IDinscription,IDindividu,IDfamille,IDcompte_payeur,IDactivite,date_inscription,statut) VALUES (102,100,1,11,2,'2026-09-15','ok');",
            ]:
                db.cursor.execute(sql)
            if not avec_participation:
                db.cursor.execute("DELETE FROM consommations;")
            db.Commit()
        finally:
            db.Close()

    def _activites(self):
        db = self._ouvrir()
        try:
            db.cursor.execute("SELECT activites FROM cotisations WHERE IDindividu=100;")
            return [row[0] for row in db.cursor.fetchall()]
        finally:
            db.Close()

    def test_creation_fiscale_une_fois_pour_deux_inscriptions(self):
        self._preparer(avec_participation=True)
        with RedirectionGestionDB(self._nom(self.base)):
            self.assertEqual(A.LireModeAssociation(1), A.MODE_ASSOCIATION_INSCRIPTIONS)
            resultat = A.ReconcilierIndividu(
                100, date_reference=JOUR, depuis=D(2026, 10, 7))
        self.assertEqual(resultat["statut"], A.STATUT_CREE)
        self.assertEqual(self._activites(), ["1;2"])
        self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 1)
        self.assertEqual(self._compter(
            "SELECT COUNT(*) FROM prestations WHERE categorie='cotisation';"), 1)

    def test_inscriptions_sans_reservation_n_engendrent_aucun_montant(self):
        self._preparer(avec_participation=False)
        with RedirectionGestionDB(self._nom(self.base)):
            resultat = A.ReconcilierIndividu(
                100, date_reference=JOUR, depuis=D(2026, 10, 7))
        self.assertEqual(resultat["cotisations_creees"], [])
        self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 0)
        self.assertEqual(self._compter("SELECT COUNT(*) FROM prestations;"), 0)

    def test_activite_ajoutee_apres_facturation_sans_doublon(self):
        self._preparer(avec_participation=True)
        with RedirectionGestionDB(self._nom(self.base)):
            resultat = A.ReconcilierIndividu(
                100, date_reference=JOUR, depuis=D(2026, 10, 7))
        self.assertEqual(resultat["statut"], A.STATUT_CREE)
        db = self._ouvrir()
        try:
            db.cursor.execute("""INSERT INTO inscriptions
                (IDinscription,IDindividu,IDfamille,IDcompte_payeur,IDactivite,date_inscription,statut)
                VALUES (103,100,1,11,3,'2026-11-01','ok');""")
            db.Commit()
        finally:
            db.Close()
        with RedirectionGestionDB(self._nom(self.base)):
            modifiees = A.ActualiserActivitesApresInscription(103, JOUR)
            reessai = A.ActualiserActivitesApresInscription(103, JOUR)
        self.assertEqual(len(modifiees), 1)
        self.assertEqual(reessai, [])
        self.assertEqual(self._activites(), ["1;2;3"])
        self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 1)
        self.assertEqual(self._compter(
            "SELECT COUNT(*) FROM prestations WHERE categorie='cotisation';"), 1)

    def test_parametrage_my_sql_par_type_sans_ecritures_comptables(self):
        self._preparer(avec_participation=False)
        with RedirectionGestionDB(self._nom(self.base)):
            self.assertTrue(A.EnregistrerModeAssociation(
                1, A.MODE_ASSOCIATION_PARTICIPATIONS))
            self.assertEqual(A.LireModeAssociation(1), A.MODE_ASSOCIATION_PARTICIPATIONS)
            self.assertTrue(A.EnregistrerModeAssociation(
                1, A.MODE_ASSOCIATION_INSCRIPTIONS))
            self.assertEqual(A.LireModeAssociation(1), A.MODE_ASSOCIATION_INSCRIPTIONS)
        self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 0)
        self.assertEqual(self._compter("SELECT COUNT(*) FROM prestations;"), 0)


if __name__ == "__main__":
    unittest.main()
