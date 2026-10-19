# -*- coding: utf-8 -*-
"""Recette sur vraie SQLite en memoire : aucun fichier PMSL, aucun reseau."""
import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_Repas_source


class BaseFictive:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.requetes = []
        self.closed = False
        self.results = []
        self.db.executescript("""
            CREATE TABLE questionnaire_categories (IDcategorie INTEGER PRIMARY KEY, type TEXT);
            CREATE TABLE questionnaire_questions (IDquestion INTEGER PRIMARY KEY,
                                                 IDcategorie INTEGER, controle TEXT);
            CREATE TABLE questionnaire_choix (IDchoix INTEGER PRIMARY KEY, IDquestion INTEGER);
            CREATE TABLE questionnaire_reponses (IDreponse INTEGER PRIMARY KEY,
                                                 IDquestion INTEGER, IDindividu INTEGER, reponse TEXT);
            CREATE TABLE consommations (date TEXT, IDgroupe INTEGER, IDunite INTEGER,
                                        IDindividu INTEGER, etat TEXT);
            INSERT INTO questionnaire_categories VALUES (7, 'Individu');
            INSERT INTO questionnaire_questions VALUES (5, 7, 'liste_coches');
            INSERT INTO questionnaire_choix VALUES (12, 5);
            INSERT INTO questionnaire_choix VALUES (13, 5);
            INSERT INTO questionnaire_reponses VALUES (1, 5, 1, '12;13');
            INSERT INTO questionnaire_reponses VALUES (2, 5, 2, '13');
            INSERT INTO questionnaire_reponses VALUES (3, 5, 4, '12');
            INSERT INTO questionnaire_reponses VALUES (4, 5, 5, '12');
            INSERT INTO consommations VALUES ('2026-10-19', 1, 10, 1, 'reservation');
            INSERT INTO consommations VALUES ('2026-10-19', 1, 10, 1, 'present');
            INSERT INTO consommations VALUES ('2026-10-19', 1, 10, 2, 'present');
            INSERT INTO consommations VALUES ('2026-10-19', 1, 10, 3, 'present');
            INSERT INTO consommations VALUES ('2026-10-19', 2, 10, 4, 'present');
            INSERT INTO consommations VALUES ('2026-10-19', 1, 10, 5, 'absent');
            INSERT INTO consommations VALUES ('2026-10-20', 1, 10, 1, 'present');
        """)

    def ExecuterReq(self, req):
        self.requetes.append(req)
        self.results = self.db.execute(req).fetchall()
        return True

    def ResultatReq(self):
        return self.results

    def Close(self):
        self.closed = True

    def dispose(self):
        self.db.close()


class RecetteSQLiteRepasTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseFictive()
        self.addCleanup(self.base.dispose)

    def charger(self, unites):
        with patch.object(UTILS_Repas_source.GestionDB, "DB", return_value=self.base):
            return UTILS_Repas_source.ChargerRepartition(
                5, 12, unites, date(2026, 10, 19), date(2026, 10, 20))

    def test_question_reelle_doublons_absences_et_preference_inconnue(self):
        rep = self.charger([(1, 10)])
        self.assertEqual(rep[date(2026, 10, 19)],
                         {"sans_porc": 1, "repas": 3, "non_renseignes": 1})
        self.assertEqual(rep[date(2026, 10, 20)],
                         {"sans_porc": 1, "repas": 1, "non_renseignes": 0})
        self.assertTrue(self.base.closed)
        self.assertEqual(len(self.base.requetes), 4)
        self.assertTrue(all(q.lstrip().startswith("SELECT") for q in self.base.requetes))
        self.assertNotIn("nom", " ".join(self.base.requetes).lower())

    def test_deux_groupes_meme_unite_sont_deux_perimetres(self):
        rep = self.charger([(1, 10), (2, 10)])
        self.assertEqual(rep[date(2026, 10, 19)],
                         {"sans_porc": 2, "repas": 4, "non_renseignes": 1})

    def test_question_famille_refusee_sans_requetes_consommations(self):
        self.base.db.execute("UPDATE questionnaire_categories SET type='Famille'")
        with self.assertRaises(ValueError):
            self.charger([(1, 10)])
        self.assertEqual(len(self.base.requetes), 1)

    def test_deux_reponses_pour_un_meme_enfant_refusees(self):
        self.base.db.execute("INSERT INTO questionnaire_reponses VALUES (20, 5, 1, '13')")
        with self.assertRaises(ValueError):
            self.charger([(1, 10)])

    def test_aucun_echange_externe_et_aucune_ecriture(self):
        self.charger([(1, 10)])
        # Seuls SELECT ont ete emis par le module sous test.
        self.assertTrue(all("UPDATE " not in req.upper() and "INSERT " not in req.upper()
                            for req in self.base.requetes))


if __name__ == "__main__":
    unittest.main()
