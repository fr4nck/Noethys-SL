# -*- coding: utf-8 -*-
"""Qualification du chargeur de regimes : SQLite et MySQL jetable (#430).

Meme jeu fictif charge par la vraie chaine GestionDB -> UTILS_Repas_source
sur une base SQLite temporaire et, si NOETHYS_TEST_MYSQL_* est declare
(workflow « Noethys SL - repas regimes MySQL »), sur une base
`zz_test_repas_<alea>` creee puis supprimee par le test. Aucune donnee reelle.
"""
import os
import sys
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for chemin in (ROOT / "noethys", ROOT / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import _garde_reseau  # noqa: E402
from _fixtures_noethys_db import RedirectionGestionDB  # noqa: E402
import GestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
from Utils import UTILS_Repas_source  # noqa: E402
from Utils import UTILS_Repas_questionnaire  # noqa: E402

PREFIXE_MYSQL = "zz_test_repas_"
JOUR = date(2026, 11, 4)
CHOIX = {"standard": 11, "sans_porc": 12, "vegetarien": 13}
CHOIX_QUATRE = {"standard": 21, "sans_porc": 22, "vegetarien": 23, "sans_repas_pmsl": 24}
SERVICES_OPTIN = {(1, 10): ("Site A", "midi"), (1, 20): ("Site A", "soir")}
SERVICES = {(1, 10): ("Site A", "midi"), (1, 20): ("Site A", "soir"), (2, 30): ("Site B", "midi")}
TABLES = ("questionnaire_categories", "questionnaire_questions", "questionnaire_choix",
          "questionnaire_reponses", "individus", "consommations", "unites")


def Peupler(db):
    for table in TABLES:
        db.CreationTable(table, Tables.DB_DATA)
    db.ReqInsert("questionnaire_categories", [("IDcategorie", 1), ("ordre", 1),
                                            ("type", "individu"), ("visible", 1),
                                            ("label", u"Alimentation")])
    db.ReqInsert("questionnaire_questions", [("IDquestion", 5), ("IDcategorie", 1), ("ordre", 1),
                                             ("label", u"Régime"), ("controle", "liste_deroulante"),
                                             ("visible", 1)])
    for IDchoix, label in ((11, u"Standard"), (12, u"Sans porc"), (13, u"Végétarien")):
        db.ReqInsert("questionnaire_choix", [("IDchoix", IDchoix), ("IDquestion", 5),
                                              ("ordre", IDchoix), ("label", label), ("visible", 1)])
    db.ReqInsert("questionnaire_questions", [("IDquestion", 6), ("IDcategorie", 1),
                                             ("ordre", 2), ("label", u"Type de repas"),
                                             ("controle", "liste_deroulante"), ("visible", 1)])
    for IDchoix, label in ((21, u"Standard"), (22, u"Sans porc"),
                           (23, u"Végétarien"),
                           (24, u"Repas apporté par la famille (sans repas PMSL)")):
        db.ReqInsert("questionnaire_choix", [("IDchoix", IDchoix), ("IDquestion", 6),
                                              ("ordre", IDchoix), ("label", label), ("visible", 1)])
    for ident, debut, fin in ((10, "08:30", "17:30"),
                              (20, "17:30", "18:30"),
                              (30, "08:30", "17:30")):
        db.ReqInsert("unites", [("IDunite", ident), ("heure_debut", debut),
                                 ("heure_fin", fin)])
    IDconso = 0
    # Site A midi : 50 enfants (40 standard, 7 sans porc, 3 vegetariens),
    # doublons d'etat et une annulation (absenti) qui ne compte pas.
    for i in range(1, 61):
        naissance = date(2022, 1, 1) if i <= 18 else date(2017, 1, 1)
        if i == 55:
            naissance = date(1990, 1, 1)  # adulte avec consommation
        db.ReqInsert("individus", [("IDindividu", i), ("nom", "FICTIF"), ("prenom", "Enfant %d" % i),
                                   ("date_naiss", naissance)])
        if i <= 50:
            reponse = "11" if i <= 40 else ("12" if i <= 47 else "13")
            db.ReqInsert("questionnaire_reponses", [("IDquestion", 5), ("IDindividu", i), ("reponse", reponse),
                                                    ("type", "individu"), ("IDdonnee", i)])
        if i <= 49:
            quatre = "21" if i <= 39 else ("22" if i <= 46 else ("23" if i <= 48 else "24"))
            db.ReqInsert("questionnaire_reponses", [("IDquestion", 6), ("IDindividu", i),
                                                     ("reponse", quatre), ("type", "individu"),
                                                     ("IDdonnee", i)])
    lignes = [(i, 1, 10, "reservation") for i in range(1, 51)]
    lignes += [(1, 1, 10, "present"), (51, 1, 10, "absenti"), (52, 1, 10, "reservation"), (55, 1, 10, "present")]
    lignes += [(1, 1, 20, "present"), (41, 1, 20, "reservation")]
    lignes += [(48, 2, 30, "reservation"), (2, 2, 30, "present")]
    for individu, groupe, unite, etat in lignes:
        IDconso += 1
        db.ReqInsert("consommations", [("IDconso", IDconso), ("date", JOUR), ("IDgroupe", groupe),
                                       ("IDunite", unite), ("IDindividu", individu), ("etat", etat)])


def Charger(nom):
    with RedirectionGestionDB(nom):
        return UTILS_Repas_source.ChargerRepartitionRegimes(5, CHOIX, SERVICES, JOUR, JOUR)


def ChargerQuatreChoix(nom, services=SERVICES_OPTIN, repas_pmsl_prevu=True):
    with RedirectionGestionDB(nom):
        return UTILS_Repas_source.ChargerRepartitionRegimes(
            6, CHOIX_QUATRE, services, JOUR, JOUR,
            plage_midi=("12:00", "13:00"), repas_pmsl_prevu=repas_pmsl_prevu)


class _Scenario(object):
    def test_repartition_reference(self):
        resultat = Charger(self.nom)
        midi = resultat[(JOUR, "Site A", "midi")]
        self.assertEqual((midi["standard"], midi["sans_porc"], midi["vegetarien"], midi["non_renseignes"],
                          midi["total_repas"], midi["adultes_avec_conso"], midi["multisites"]),
                         (40, 7, 3, 1, 51, 1, 2))
        soir = resultat[(JOUR, "Site A", "soir")]
        self.assertEqual((soir["standard"], soir["sans_porc"], soir["total_repas"]), (1, 1, 2))
        site_b = resultat[(JOUR, "Site B", "midi")]
        self.assertEqual((site_b["standard"], site_b["vegetarien"], site_b["total_repas"]), (1, 1, 2))

    def test_parametrage_et_listes(self):
        with RedirectionGestionDB(self.nom):
            self.assertEqual(UTILS_Repas_source.ListerQuestionsRegime(),
                             [(5, u"Régime"), (6, u"Type de repas")])
            self.assertEqual([c for c, _l in UTILS_Repas_source.ListerChoixQuestion(5)], [11, 12, 13])
            self.assertEqual(UTILS_Repas_source.VerifierParametrageRegimes(5, CHOIX), (5, CHOIX))
            with self.assertRaises(ValueError):
                UTILS_Repas_source.VerifierParametrageRegimes(5, dict(CHOIX, vegetarien=99))
            self.assertEqual(UTILS_Repas_source.VerifierParametrageRegimes(
                6, CHOIX_QUATRE), (6, CHOIX_QUATRE))

    def test_quatre_choix_preparateur_idempotent(self):
        with RedirectionGestionDB(self.nom):
            db = GestionDB.DB()
            try:
                diagnostic = UTILS_Repas_questionnaire.ExaminerQuestionnaire(db)
                self.assertEqual(diagnostic["etat"], "pret")
                self.assertEqual(diagnostic["choix"], CHOIX_QUATRE)
                self.assertEqual(UTILS_Repas_questionnaire.PreparerQuestionnaire(db), diagnostic)
                self.assertEqual(UTILS_Repas_questionnaire.PreparerQuestionnaire(db), diagnostic)
            finally:
                db.Close()

    def test_panier_quatre_choix_plage_midi_et_defaut(self):
        r = ChargerQuatreChoix(self.nom)
        self.assertEqual(set(r), {(JOUR, "Site A", "midi")})
        ligne = r[(JOUR, "Site A", "midi")]
        self.assertEqual(
            (ligne["standard"], ligne["sans_porc"], ligne["vegetarien"],
             ligne["non_renseignes"], ligne["repas_apportes"], ligne["total_repas"],
             ligne["enfants_presents_midi_classes"], ligne["adultes_avec_conso"]),
            (41, 7, 2, 0, 1, 50, 51, 1))
        self.assertEqual(ligne["repas_apportes_six_plus"], 1)

    def test_quatre_choix_blocage_multisite(self):
        with self.assertRaisesRegex(ValueError, "Presence midi sur plusieurs sites"):
            ChargerQuatreChoix(self.nom, services=dict(SERVICES))

    def test_quatre_choix_sans_offre_refuse_repas_fournisseur(self):
        with self.assertRaises(ValueError):
            ChargerQuatreChoix(self.nom, repas_pmsl_prevu=False)


class SQLiteRegimesTests(_Scenario, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._dossier = tempfile.TemporaryDirectory(prefix="repas-regimes-")
        cls.nom = os.path.join(cls._dossier.name, "repas_fictif.dat")
        db = GestionDB.DB(nomFichier=cls.nom, suffixe=None, modeCreation=True)
        Peupler(db)
        db.Close()

    @classmethod
    def tearDownClass(cls):
        cls._dossier.cleanup()


@unittest.skipUnless(_garde_reseau.ParametresMySQLDeTest(), "serveur MySQL local jetable non déclaré")
class MySQLRegimesTests(_Scenario, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = _garde_reseau.ServeurMySQLDeTest()
        p = cls.serveur.__enter__()
        cls.base = PREFIXE_MYSQL + uuid.uuid4().hex[:12]
        cls.racine = "%d;%s;%s;%s[RESEAU]" % (p["port"], p["hote"], p["utilisateur"], GestionDB.EncodeMdpReseau(p["motdepasse"]))
        cls.nom = cls.racine + cls.base
        db = GestionDB.DB(nomFichier=cls.racine, suffixe=None)
        assert db.echec == 0, getattr(db, "erreur", "")
        db.cursor.execute("SHOW DATABASES;")
        assert cls.base not in [ligne[0] for ligne in db.cursor.fetchall()]  # jamais une base existante
        db.Close()
        db = GestionDB.DB(nomFichier=cls.nom, suffixe=None, modeCreation=True)
        assert db.echec == 0, getattr(db, "erreur", "")
        cls.cree = True
        db.cursor.execute("SELECT VERSION();")
        print("Repas regimes : MySQL %s, base fictive %s" % (db.cursor.fetchall()[0][0], cls.base))
        Peupler(db)
        db.Close()
        cls._dossier = tempfile.TemporaryDirectory(prefix="repas-regimes-")
        cls.nom_sqlite = os.path.join(cls._dossier.name, "repas_fictif.dat")
        db = GestionDB.DB(nomFichier=cls.nom_sqlite, suffixe=None, modeCreation=True)
        Peupler(db)
        db.Close()

    @classmethod
    def tearDownClass(cls):
        try:
            if getattr(cls, "cree", False) and cls.base.startswith(PREFIXE_MYSQL):
                db = GestionDB.DB(nomFichier=cls.racine, suffixe=None)
                db.cursor.execute("DROP DATABASE %s;" % cls.base)  # uniquement la base creee ici
                db.Close()
        finally:
            cls._dossier.cleanup()
            cls.serveur.__exit__(None, None, None)

    def test_resultats_identiques_a_sqlite(self):
        self.assertEqual(Charger(self.nom), Charger(self.nom_sqlite))

    def test_quatre_choix_identiques_a_sqlite(self):
        self.assertEqual(ChargerQuatreChoix(self.nom),
                         ChargerQuatreChoix(self.nom_sqlite))


if __name__ == "__main__":
    unittest.main()
