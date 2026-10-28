# -*- coding: utf-8 -*-
"""Questionnaire repas : idempotence SQLite et absence de migration implicite."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys"))
from Utils import UTILS_Repas_questionnaire as Q  # noqa: E402


SCHEMA = """
CREATE TABLE questionnaire_categories (
    IDcategorie INTEGER PRIMARY KEY AUTOINCREMENT,
    ordre INTEGER, visible INTEGER, type TEXT, couleur TEXT, label TEXT);
CREATE TABLE questionnaire_questions (
    IDquestion INTEGER PRIMARY KEY AUTOINCREMENT,
    IDcategorie INTEGER, ordre INTEGER, visible INTEGER,
    label TEXT, controle TEXT, defaut TEXT, options TEXT);
CREATE TABLE questionnaire_choix (
    IDchoix INTEGER PRIMARY KEY AUTOINCREMENT,
    IDquestion INTEGER, ordre INTEGER, visible INTEGER, label TEXT);
"""


class Base:
    isNetwork = False

    def __init__(self, connexion):
        self.connexion = connexion
        self.cursor = connexion.cursor()

    def Close(self):
        self.connexion.close()


class QuestionnaireRepasTests(unittest.TestCase):
    def setUp(self):
        self.db = Base(sqlite3.connect(":memory:", timeout=0.01))
        self.addCleanup(self.db.Close)
        self.db.connexion.executescript(SCHEMA)

    def categorie(self, label="Alimentation", type_="individu"):
        self.db.cursor.execute("""
            INSERT INTO questionnaire_categories
            (ordre,visible,type,couleur,label) VALUES (1,1,?,'(220, 238, 252)',?)
        """, (type_, label))
        self.db.connexion.commit()
        return self.db.cursor.lastrowid

    def question(self, categorie, label="Type de repas",
                 controle="liste_deroulante", defaut=None):
        self.db.cursor.execute("""
            INSERT INTO questionnaire_questions
            (IDcategorie,ordre,visible,label,controle,defaut,options)
            VALUES (?,1,1,?,?,?,'')
        """, (categorie, label, controle, defaut))
        self.db.connexion.commit()
        return self.db.cursor.lastrowid

    def choix(self, question, labels):
        self.db.cursor.executemany("""
            INSERT INTO questionnaire_choix (IDquestion,ordre,visible,label)
            VALUES (?,?,1,?)
        """, [(question, i, label) for i, label in enumerate(labels)])
        self.db.connexion.commit()

    def nombres(self):
        return tuple(self.db.connexion.execute(
            "SELECT COUNT(*) FROM " + table).fetchone()[0] for table in
            ("questionnaire_categories", "questionnaire_questions", "questionnaire_choix"))

    def test_inspection_absente_ne_modifie_rien(self):
        avant = self.db.connexion.total_changes
        self.assertEqual(Q.ExaminerQuestionnaire(self.db)["etat"], "absent")
        self.assertEqual(self.db.connexion.total_changes, avant)

    def test_creation_exactement_quatre_choix_et_une_categorie(self):
        resultat = Q.PreparerQuestionnaire(self.db)
        self.assertEqual(resultat["etat"], "pret")
        self.assertEqual(set(resultat["choix"]), set(k for k, _ in Q.REGIMES))
        self.assertEqual(len(set(resultat["choix"].values())), 4)
        self.assertEqual(self.nombres(), (1, 1, 4))
        self.assertEqual(self.db.connexion.execute(
            "SELECT controle,defaut FROM questionnaire_questions"
        ).fetchone(), ("liste_deroulante", None))

    def test_deux_passages_reutilisent_exactement_memes_ids(self):
        a = Q.PreparerQuestionnaire(self.db)
        ancien = self.db.connexion.total_changes
        b = Q.PreparerQuestionnaire(self.db)
        self.assertEqual(a, b)
        self.assertEqual(self.nombres(), (1, 1, 4))
        self.assertEqual(ancien, self.db.connexion.total_changes)

    def test_categorie_alimentation_existante_reutilisee(self):
        identifiant = self.categorie()
        resultat = Q.PreparerQuestionnaire(self.db)
        self.assertEqual(self.nombres(), (1, 1, 4))
        self.assertEqual(self.db.connexion.execute(
            "SELECT IDcategorie FROM questionnaire_questions"
        ).fetchone()[0], identifiant)
        self.assertEqual(resultat["etat"], "pret")

    def test_question_complete_existante_reutilisee(self):
        categorie = self.categorie()
        identifiant = self.question(categorie, label="Régime repas")
        self.choix(identifiant, [label for _key, label in Q.REGIMES])
        ancien = self.db.connexion.total_changes
        resultat = Q.PreparerQuestionnaire(self.db)
        self.assertEqual(resultat["question"], identifiant)
        self.assertEqual(self.db.connexion.total_changes, ancien)
        self.assertEqual(self.nombres(), (1, 1, 4))

    def test_synonymes_non_ambigus_compatibles(self):
        categorie = self.categorie()
        q = self.question(categorie)
        self.choix(q, ("Repas standard", "Repas sans porc",
                       "Repas végétarien", "Panier apporté par la famille"))
        self.assertEqual(Q.ExaminerQuestionnaire(self.db)["etat"], "pret")

    def test_trois_choix_existants_refuses_sans_completion(self):
        categorie = self.categorie()
        q = self.question(categorie)
        self.choix(q, ("Standard", "Sans porc", "Végétarien"))
        avant = self.nombres()
        with self.assertRaises(Q.QuestionnaireRepasIncompatible):
            Q.PreparerQuestionnaire(self.db)
        self.assertEqual(self.nombres(), avant)

    def test_doublon_de_question_homonyme_refuse(self):
        cat = self.categorie()
        a = self.question(cat)
        self.choix(a, (x for _, x in Q.REGIMES))
        b = self.question(cat, "Régime repas")
        self.choix(b, (x for _, x in Q.REGIMES))
        self.assertEqual(Q.ExaminerQuestionnaire(self.db)["etat"], "conflit")
        with self.assertRaises(Q.QuestionnaireRepasIncompatible):
            Q.PreparerQuestionnaire(self.db)

    def test_question_a_choix_multiples_refusee(self):
        cat = self.categorie()
        q = self.question(cat, controle="liste_coches")
        self.choix(q, (x for _, x in Q.REGIMES))
        with self.assertRaises(Q.QuestionnaireRepasIncompatible):
            Q.PreparerQuestionnaire(self.db)

    def test_defaut_existant_refuse_pour_eviter_un_repas_implicite(self):
        cat = self.categorie()
        q = self.question(cat, defaut="1")
        self.choix(q, (x for _, x in Q.REGIMES))
        self.assertEqual(Q.ExaminerQuestionnaire(self.db)["etat"], "conflit")

    def test_type_famille_n_est_pas_question_individuelle(self):
        cat = self.categorie(type_="famille")
        q = self.question(cat)
        self.choix(q, (x for _, x in Q.REGIMES))
        result = Q.PreparerQuestionnaire(self.db)
        self.assertNotEqual(q, result["question"])
        self.assertEqual(self.nombres(), (2, 2, 8))

    def test_categorie_ambigue_refusee_avant_ecriture(self):
        self.categorie()
        self.categorie("Alimentation ")
        with self.assertRaises(Q.QuestionnaireRepasIncompatible):
            Q.PreparerQuestionnaire(self.db)
        self.assertEqual(self.nombres(), (2, 0, 0))

    def test_echec_au_quatrieme_choix_annule_toutes_les_ecritures(self):
        self.db.connexion.execute("""
            CREATE TRIGGER refuse_panier BEFORE INSERT ON questionnaire_choix
            WHEN NEW.label LIKE 'Repas apporté%' BEGIN SELECT RAISE(ABORT, 'interdit'); END
        """)
        with self.assertRaises(sqlite3.IntegrityError):
            Q.PreparerQuestionnaire(self.db)
        self.assertEqual(self.nombres(), (0, 0, 0))

    def test_deux_connexions_sans_double_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            fichier = str(Path(tmp) / "questionnaire.sqlite")
            conn_a = sqlite3.connect(fichier, timeout=0.02)
            conn_b = sqlite3.connect(fichier, timeout=0.02)
            try:
                conn_a.executescript(SCHEMA)
                base_b = Base(conn_b)
                conn_a.execute("BEGIN IMMEDIATE")
                with self.assertRaises(sqlite3.OperationalError):
                    Q.PreparerQuestionnaire(base_b)
                conn_a.rollback()
                premier = Q.PreparerQuestionnaire(Base(conn_a))
                deuxieme = Q.PreparerQuestionnaire(base_b)
                self.assertEqual(premier, deuxieme)
            finally:
                conn_b.close()
                conn_a.close()


if __name__ == "__main__":
    unittest.main()
