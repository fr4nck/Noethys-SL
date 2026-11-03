# -*- coding: utf-8 -*-
"""#436 - Lecture des champs medicaux existants, sans ecriture ni fuite."""
import sqlite3
import unittest
from unittest.mock import patch
from Utils import UTILS_Accueil_sources as S
try:
    from Utils import UTILS_Repas_questionnaire as Q
except ImportError:
    Q = None  # Le sous-lot questionnaire repas n'est pas encore porte sur main.

ADMIN = {"IDutilisateur": 3, "actif": 1, "profil": "administrateur"}


class Base:
    isNetwork = False
    def __init__(self):
        self.connexion = sqlite3.connect(":memory:")
        self.cursor = self.connexion.cursor()
        self.connexion.executescript("""
            CREATE TABLE individus (
              IDindividu INTEGER PRIMARY KEY, IDmedecin INTEGER);
            CREATE TABLE medecins (
              IDmedecin INTEGER PRIMARY KEY, nom TEXT, prenom TEXT, tel_cabinet TEXT);
            CREATE TABLE vaccins (
              IDvaccin INTEGER PRIMARY KEY, IDindividu INTEGER);
            CREATE TABLE questionnaire_reponses (
              IDreponse INTEGER PRIMARY KEY, IDindividu INTEGER,
              IDquestion INTEGER, reponse TEXT);
            CREATE TABLE categories_medicales (IDcategorie INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE problemes_sante (
              IDprobleme INTEGER PRIMARY KEY, IDindividu INTEGER, IDtype INTEGER,
              intitule TEXT, date_debut TEXT, date_fin TEXT, description TEXT,
              traitement_medical INTEGER, description_traitement TEXT,
              date_debut_traitement TEXT, date_fin_traitement TEXT);
        """)
        self.connexion.executemany(
            "INSERT INTO individus VALUES (?,?)", [(10, 23), (11, None)])
        self.connexion.execute(
            "INSERT INTO medecins VALUES (23,'FICTIF','Docteur','0000000000')")
        self.connexion.executemany(
            "INSERT INTO vaccins VALUES (?,?)", [(1,10),(2,10)])
        self.connexion.execute(
            "INSERT INTO categories_medicales VALUES (8,'Autre')")
        self.connexion.execute("""INSERT INTO problemes_sante VALUES
            (4,10,8,'PAI-fictif','2026-09-01',NULL,
            'Renseignements de test',1,'Consignes fictives',NULL,NULL)""")
        self.connexion.commit()

    def Close(self):
        self.connexion.close()


class SourceMedicaleTests(unittest.TestCase):
    def setUp(self):
        self.db = Base()
        self.addCleanup(self.db.Close)

    def test_refus_avant_toute_consultation(self):
        for utilisateur in (
            None, {}, {"IDutilisateur": 3, "profil": "administrateur"},
            {"IDutilisateur": 3, "actif": 1, "profil": "perso:3",
             "droits": {("fiche_accueil_autorisations", "consulter"): "autorisation"}},
        ):
            with self.subTest(user=utilisateur):
                with self.assertRaises(S.LectureMedicaleRefusee):
                    S.LireMedicalExistant(10, utilisateur, DB=self.db)

    def test_refus_ne_lit_aucun_champ(self):
        appels = []
        self.db.connexion.set_trace_callback(lambda sql: appels.append(sql))
        with self.assertRaises(S.LectureMedicaleRefusee):
            S.LireMedicalExistant(10, None, DB=self.db)
        self.assertEqual(appels, [])

    def test_medecin_vaccins_et_sante_source_unique(self):
        data = S.LireMedicalExistant(10, ADMIN, DB=self.db)
        self.assertEqual(data["medecin"]["nom"], "FICTIF")
        self.assertEqual(data["vaccins_enregistres"], 2)
        self.assertEqual(len(data["problemes"]), 1)
        self.assertEqual(data["problemes"][0]["intitule"], "PAI-fictif")
        self.assertEqual(data["problemes"][0]["description_traitement"],
                         "Consignes fictives")
        self.assertEqual(data["problemes"][0]["categorie"], "Autre")

    def test_reprise_pai_allergie_et_traitement_de_l_onglet_existant(self):
        self.db.connexion.execute(
            "INSERT INTO categories_medicales VALUES (4,'Allergie')")
        self.db.connexion.execute("""INSERT INTO problemes_sante VALUES
            (5,10,4,'Arachides','2026-09-01',NULL,
             'Consigne alimentaire fictive',0,'',NULL,NULL)""")
        donnees = S.LireMedicalExistant(10, ADMIN, DB=self.db)
        resume = S.PreparerRubriquesMedicales(donnees, "2026-11-03")
        self.assertIn("PAI-fictif", resume["pai"])
        self.assertIn("Arachides", resume["allergies"])
        self.assertIn("Consignes fictives", resume["traitement"])
        self.assertEqual(len(resume["medical"]), 2)

    def test_absence_de_pai_ne_devient_pas_un_refus_ou_une_validation(self):
        data = S.LireMedicalExistant(11, ADMIN, DB=self.db)
        resume = S.PreparerRubriquesMedicales(data, "2026-11-03")
        self.assertEqual(resume["pai"], "Non renseigné dans Noethys")
        self.assertEqual(resume["allergies"], "Non renseigné dans Noethys")
        self.assertEqual(resume["traitement"], "Non renseigné dans Noethys")

    def test_categories_heritees_alimentation_et_medicamentation_non_confondus(self):
        self.db.connexion.executemany(
            "INSERT INTO categories_medicales VALUES (?,?)",
            ((2, "Alimentation"), (3, "Médicamentation")))
        self.db.connexion.executemany(
            """INSERT INTO problemes_sante VALUES
               (?,10,?,?, '2026-01-01',NULL,?,0,NULL,NULL,NULL)""",
            ((6,2,"Régime particulier","Commentaire fictif"),
             (7,3,"Traitement courant","Suivi fictif")))
        d = S.LireMedicalExistant(10, ADMIN, DB=self.db)
        r = S.PreparerRubriquesMedicales(d, "2026-11-03")
        self.assertEqual(r["allergies"], "Non renseigné dans Noethys")
        self.assertIn("PAI-fictif", r["pai"])
        self.assertEqual(len(r["medical"]), 3)

    def test_pas_de_traitement_expire_pour_accueil_actuel(self):
        historique = {"problemes": [
            {"intitule": "Allergie fictive ancienne", "categorie": "Allergie",
             "date_debut": "2024-01-01", "date_fin": "2024-12-31",
             "traitement_medical": True, "description_traitement": "Ancien médicament"},
            {"intitule": "Asthme", "categorie": "Maladie",
             "date_debut": "2026-01-01", "date_fin": None,
             "traitement_medical": True, "description_traitement": "Traitement terminé",
             "date_fin_traitement": "2026-10-01"},
        ]}
        r = S.PreparerRubriquesMedicales(historique, "2026-11-03")
        self.assertEqual(r["allergies"], "Non renseigné dans Noethys")
        self.assertEqual(r["traitement"], "Non renseigné dans Noethys")
        self.assertEqual(len(r["medical"]), 1)

    def test_categories_saisie_libre_ne_creent_pas_pai_imaginaire(self):
        historique = {"problemes": [
            {"categorie": "Maladie", "intitule": "Asthme",
             "description": "PAI à envisager avec la famille"}
        ]}
        r = S.PreparerRubriquesMedicales(historique, "2026-11-03")
        self.assertEqual(r["pai"], "Non renseigné dans Noethys")
        self.assertEqual(r["allergies"], "Non renseigné dans Noethys")

    def test_pas_d_ajout_ni_de_modification(self):
        avant = self.db.connexion.total_changes
        S.LireMedicalExistant(10, ADMIN, DB=self.db)
        self.assertEqual(self.db.connexion.total_changes, avant)

    def test_individu_sans_medecin_et_sans_medical(self):
        data = S.LireMedicalExistant(11, ADMIN, DB=self.db)
        self.assertIsNone(data["medecin"])
        self.assertEqual(data["vaccins_enregistres"], 0)
        self.assertEqual(data["problemes"], [])

    def test_pas_de_fusion_avec_AEEH_ou_questionnaires(self):
        data = S.LireMedicalExistant(10, ADMIN, DB=self.db)
        self.assertNotIn("aeeh", data)
        self.assertNotIn("questionnaire_reponses", data)

    def test_enfant_inexistant_refuse(self):
        with self.assertRaises(ValueError):
            S.LireMedicalExistant(42, ADMIN, DB=self.db)



@unittest.skipIf(Q is None, "Questionnaire repas non integre a cette branche")
class QuestionnaireRepasExistant(unittest.TestCase):
    def setUp(self):
        self.db = Base()
        self.addCleanup(self.db.Close)
        self.config = {"etat": "pret", "question": 3,
                       "choix": {"standard": 50, "sans_porc": 51,
                                 "vegetarien": 52, "sans_repas_pmsl": 53}}
    def lire(self):
        with patch.object(Q, "ExaminerQuestionnaire", return_value=self.config):
            return S.LireRepasExistant(10, ADMIN, DB=self.db)
    def test_absence_ne_devient_pas_standard(self):
        self.assertEqual(self.lire(), "non_renseigne")
    def test_quatre_reponses_proviennent_du_questionnaire(self):
        for id_choix, attendu in ((50, "standard"), (51, "sans_porc"),
                                   (52, "vegetarien"), (53, "sans_repas_pmsl")):
            self.db.connexion.execute("DELETE FROM questionnaire_reponses")
            self.db.connexion.execute(
                "INSERT INTO questionnaire_reponses VALUES (1,10,3,?)",
                (str(id_choix),))
            self.db.connexion.commit()
            self.assertEqual(self.lire(), attendu)
    def test_reponse_inconnue_refusee(self):
        self.db.connexion.execute(
            "INSERT INTO questionnaire_reponses VALUES (1,10,3,'999')")
        self.assertEqual(self.lire(), "a_verifier")
    def test_deux_reponses_meme_enfant_refusees(self):
        self.db.connexion.executemany(
            "INSERT INTO questionnaire_reponses VALUES (?,?,?,?)",
            [(1,10,3,"50"), (2,10,3,"51")])
        self.assertEqual(self.lire(), "a_verifier")
    def test_questionnaire_incomplet_signale(self):
        with patch.object(Q, "ExaminerQuestionnaire",
                          return_value={"etat": "absent"}):
            self.assertEqual(S.LireRepasExistant(10, ADMIN, DB=self.db),
                             "non_configure")
        with patch.object(Q, "ExaminerQuestionnaire",
                          return_value={"etat": "conflit"}):
            self.assertEqual(S.LireRepasExistant(10, ADMIN, DB=self.db),
                             "a_verifier")
    def test_lecture_sans_habilitation_refusee(self):
        with self.assertRaises(S.LectureMedicaleRefusee):
            S.LireRepasExistant(10, {}, DB=self.db)


if __name__ == "__main__":
    unittest.main()
