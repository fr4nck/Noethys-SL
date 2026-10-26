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

PREFIXE_MYSQL = "zz_test_repas_"
JOUR = date(2026, 11, 4)
CHOIX = {"standard": 11, "sans_porc": 12, "vegetarien": 13}
SERVICES = {(1, 10): ("Site A", "midi"), (1, 20): ("Site A", "soir"), (2, 30): ("Site B", "midi")}
TABLES = ("questionnaire_categories", "questionnaire_questions", "questionnaire_choix",
          "questionnaire_reponses", "individus", "consommations")


def Peupler(db):
    for table in TABLES:
        db.CreationTable(table, Tables.DB_DATA)
    db.ReqInsert("questionnaire_categories", [("IDcategorie", 1), ("ordre", 1), ("type", "individu")])
    db.ReqInsert("questionnaire_questions", [("IDquestion", 5), ("IDcategorie", 1), ("ordre", 1),
                                             ("label", u"Régime"), ("controle", "liste_deroulante")])
    for IDchoix, label in ((11, u"Standard"), (12, u"Sans porc"), (13, u"Végétarien")):
        db.ReqInsert("questionnaire_choix", [("IDchoix", IDchoix), ("IDquestion", 5), ("ordre", IDchoix), ("label", label)])
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
            self.assertEqual(UTILS_Repas_source.ListerQuestionsRegime(), [(5, u"Régime")])
            self.assertEqual([c for c, _l in UTILS_Repas_source.ListerChoixQuestion(5)], [11, 12, 13])
            self.assertEqual(UTILS_Repas_source.VerifierParametrageRegimes(5, CHOIX), (5, CHOIX))
            with self.assertRaises(ValueError):
                UTILS_Repas_source.VerifierParametrageRegimes(5, dict(CHOIX, vegetarien=99))


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


if __name__ == "__main__":
    unittest.main()
