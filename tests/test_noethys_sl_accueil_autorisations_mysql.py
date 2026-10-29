# -*- coding: utf-8 -*-
"""#436 : contre-epreuves de permissions/consentements MySQL 5.7 JETABLE.

Ne travaille que sur une base zz_test_adh_* creee par le banc officiel.
Aucune adresse externe, aucune donnee de famille reelle.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: F401
import test_noethys_sl_adhesions_concurrence as concurrence
import GestionDB
from Utils import UTILS_Accueil_autorisations as A


def preuve(typ="piscine_baignade", valeur=1, reference="piece-test-1"):
    return {
        "type": typ, "valeur": valeur, "perimetre": "alsh-test-2026",
        "date_debut": "2026-09-01", "date_fin": "2027-08-31",
        "date_signature": "2026-10-10", "IDsignataire": 101,
        "autorite_verifiee": True, "texte_version": "fiche-test",
        "source": "pieces", "reference_preuve": reference,
    }


@unittest.skipUnless(os.environ.get("NOETHYS_TEST_MYSQL_HOST"),
                     "Serveur MySQL jetable non configure")
class RegistreMySQL(unittest.TestCase):
    _nom = concurrence.ConcurrenceMySQLTests._nom

    def setUp(self):
        concurrence.ConcurrenceMySQLTests.setUp(self)
        self.addCleanup(concurrence.ConcurrenceMySQLTests.tearDown, self)

    def connexion(self):
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)
        self.assertEqual(db.echec, 0, getattr(db, "erreur", ""))
        return db

    def enregistre(self, db, choix, attendu, utilisateur=9):
        return A.EnregistrerLot(100, utilisateur, [choix],
            {("piscine_baignade", "alsh-test-2026"): attendu},
            DB=db, autorise=True)

    def test_schema_mysql_innodb_cree_explicitement_une_fois(self):
        db = self.connexion()
        try:
            with self.assertRaises(A.AutorisationRefusee):
                A.InitialiserRegistre(db, administrateur=True)
            self.assertTrue(A.InitialiserRegistre(
                db, administrateur=True, sauvegarde_confirmee=True))
            self.assertFalse(A.InitialiserRegistre(
                db, administrateur=True, sauvegarde_confirmee=True))
            self.assertTrue(A.VerifierRegistre(db, autorise=True))
            db.cursor.execute(
                "SELECT ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='accueil_autorisations'")
            self.assertEqual(db.cursor.fetchone()[0].lower(), "innodb")
        finally:
            db.Close()

    def test_deux_connexions_meme_preuve_aucune_duplication(self):
        a, b = self.connexion(), self.connexion()
        try:
            A.InitialiserRegistre(a, administrateur=True, sauvegarde_confirmee=True)
            premiere = self.enregistre(a, preuve(), None, utilisateur=9)
            deuxieme = self.enregistre(b, preuve(), None, utilisateur=10)
            self.assertEqual(premiere, deuxieme)
            db = self.connexion()
            try:
                db.cursor.execute("SELECT COUNT(*) FROM accueil_autorisations")
                self.assertEqual(db.cursor.fetchone()[0], 1)
            finally:
                db.Close()
        finally:
            b.Close()
            a.Close()

    def test_revision_obsolete_refusee_deux_connexions(self):
        a, b = self.connexion(), self.connexion()
        try:
            A.InitialiserRegistre(a, administrateur=True, sauvegarde_confirmee=True)
            self.enregistre(a, preuve(), None)
            with self.assertRaises(A.ConflitConcurrent):
                self.enregistre(b, preuve(valeur=0, reference="piece-test-2"), None)
            self.assertEqual(len(A.LireHistorique(100, DB=a, autorise=True)), 1)
        finally:
            b.Close()
            a.Close()

    def test_verrou_preparateur_retenu_par_autre_connexion(self):
        a, b = self.connexion(), self.connexion()
        try:
            b.cursor.execute(
                "SELECT GET_LOCK(CONCAT('nsl_acc_', LEFT(MD5(DATABASE()), 16)),0)")
            self.assertEqual(b.cursor.fetchone()[0], 1)
            with self.assertRaises(A.ConflitConcurrent):
                A.InitialiserRegistre(
                    a, administrateur=True, sauvegarde_confirmee=True)
            b.cursor.execute(
                "SELECT RELEASE_LOCK(CONCAT('nsl_acc_', LEFT(MD5(DATABASE()), 16)))")
            self.assertEqual(b.cursor.fetchone()[0], 1)
            self.assertTrue(A.InitialiserRegistre(
                a, administrateur=True, sauvegarde_confirmee=True))
        finally:
            b.Close()
            a.Close()

    def test_une_autorisation_enfant_n_altere_aucune_autre_table(self):
        db = self.connexion()
        try:
            A.InitialiserRegistre(db, administrateur=True, sauvegarde_confirmee=True)
            db.cursor.execute("SELECT nom, prenom FROM individus WHERE IDindividu=100")
            avant = db.cursor.fetchone()
            self.enregistre(db, preuve(), None)
            db.cursor.execute("SELECT nom, prenom FROM individus WHERE IDindividu=100")
            self.assertEqual(db.cursor.fetchone(), avant)
            db.cursor.execute("SELECT COUNT(*) FROM historique")
            self.assertEqual(db.cursor.fetchone()[0], 0)
        finally:
            db.Close()


if __name__ == "__main__":
    unittest.main()
