# -*- coding: utf-8 -*-
"""Facturation : recette du service sur MySQL 5.7 local et jetable.

Ces tests ne ciblent jamais un profil utilisateur ou une base de production.
La garde de ConcurrenceMySQLTests impose le serveur local de recette
(NOETHYS_TEST_MYSQL_HOST=127.0.0.1), cree une base zz_test_adh_* unique et
ne supprime que cette base creee par le test.
"""
import datetime
import os
import unittest
from unittest import mock

from tests.test_noethys_sl_adhesions_concurrence import ConcurrenceMySQLTests
from tests._fixtures_noethys_db import RedirectionGestionDB
import GestionDB
from Utils import UTILS_Adhesions as A
from Utils import UTILS_Adhesions_echeances as E

D = datetime.date


@unittest.skipUnless(os.environ.get("NOETHYS_TEST_MYSQL_HOST") == "127.0.0.1",
                     "serveur MySQL de recette exclusivement local non declare")
class FacturationCotisationsMySQLTests(unittest.TestCase):
    setUp = ConcurrenceMySQLTests.setUp
    tearDown = ConcurrenceMySQLTests.tearDown
    _nom = ConcurrenceMySQLTests._nom
    _compter = ConcurrenceMySQLTests._compter

    def _proposer(self):
        return E.Proposer(
            date_debut=D(2026, 10, 1), date_fin=D(2026, 10, 31),
            date_reference=D(2026, 10, 19), liste_activites=[1])

    def test_selection_individuelle_mysql_reel_sans_cotisation_pour_dispense(self):
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)
        try:
            self.assertEqual(db.echec, 0, getattr(db, "erreur", ""))
            for sql in (
                "INSERT INTO familles (IDfamille) VALUES (2);",
                "INSERT INTO comptes_payeurs (IDcompte_payeur, IDfamille) VALUES (12, 2);",
                "INSERT INTO individus (IDindividu, nom, prenom, IDcivilite) VALUES (200, 'TEST', 'Camille', 1);",
                "INSERT INTO rattachements (IDrattachement, IDfamille, IDindividu, IDcategorie, titulaire) VALUES (2, 2, 200, 2, 0);",
                "INSERT INTO consommations (IDconso, IDindividu, IDactivite, date, IDunite, etat, IDcompte_payeur) VALUES (1002, 200, 1, '2026-10-08', 1, 'reservation', 12);",
            ):
                db.cursor.execute(sql)
            db.Commit()
        finally:
            db.Close()

        with RedirectionGestionDB(self._nom(self.base)):
            propositions = self._proposer()
            self.assertEqual(
                {p["IDtitulaire"] for p in propositions["propositions"]},
                {100, 200})
            self.assertEqual(E.Executer(propositions, confirmation=True,
                                        selection_titulaires=[]), [])
            self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 0)
            self.assertEqual(self._compter(
                "SELECT COUNT(*) FROM prestations WHERE categorie='cotisation';"), 0)
            resultats = E.Executer(propositions, confirmation=True,
                                  selection_titulaires=[100])
            self.assertEqual([r["statut"] for r in resultats], [A.STATUT_CREE])
            restant = self._proposer()
            self.assertEqual(
                [p["IDtitulaire"] for p in restant["propositions"]], [200])
            self.assertEqual(self._compter(
                "SELECT COUNT(*) FROM cotisations WHERE IDindividu=100;"), 1)
            self.assertEqual(self._compter(
                "SELECT COUNT(*) FROM cotisations WHERE IDindividu=200;"), 0)
            self.assertEqual(self._compter(
                "SELECT COUNT(*) FROM prestations WHERE categorie='cotisation';"), 1)

    def test_2005_initial_repris_par_une_connexion_mysql_reelle(self):
        class ErreurDNS(Exception):
            errno = 2005

        class ConnexionInterrompue:
            isNetwork = True
            echec = 1
            erreur = ErreurDNS(2005, "Unknown server host (11001)")
            derniere_erreur_sql = None
            fermetures = 0
            def Close(self):
                self.fermetures += 1

        with RedirectionGestionDB(self._nom(self.base)):
            ouvrir_reel = GestionDB.DB
            premier = ConnexionInterrompue()
            compteur = []
            def ouvrir(*args, **kwargs):
                compteur.append(kwargs)
                if len(compteur) == 1:
                    return premier
                return ouvrir_reel(*args, **kwargs)
            with mock.patch.object(GestionDB, "DB", side_effect=ouvrir):
                valeurs = A._lire("SELECT IDtype_cotisation FROM types_cotisations;")
        self.assertEqual(valeurs[0][0], 1)
        self.assertEqual(len(compteur), 2)
        self.assertEqual(compteur[1], {"pooling": False})
        self.assertEqual(premier.fermetures, 1)
        self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 0)


if __name__ == "__main__":
    unittest.main()
