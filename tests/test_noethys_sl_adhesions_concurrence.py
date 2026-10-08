# -*- coding: utf-8 -*-
"""Adhésions automatiques : deux postes sauvegardant simultanément ne créent
qu'une adhésion, et un échec d'écriture ne laisse rien de partiel.

Scénario concurrent reproductible : deux PROCESSUS indépendants (chacun ses
connexions, comme deux postes). Le poste A s'arrête dans la section protégée
après son contrôle d'existant ; le poste B démarre alors sur la même
personne. Sans protection, les deux créent ; avec, B attend la fin de A puis
constate l'adhésion existante.

SQLite : fichier temporaire. MySQL : uniquement le serveur LOCAL de test
déclaré par NOETHYS_TEST_MYSQL_* (sinon test ignoré), dans une base fictive
créée et supprimée par le test ; les bases existantes ne sont jamais touchées.
"""
import datetime
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import _garde_reseau  # noqa: E402

from test_noethys_sl_adhesions import Env  # noqa: E402
from _fixtures_noethys_db import RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
import GestionDB  # noqa: E402
from Utils import UTILS_Adhesions as A  # noqa: E402

D = datetime.date
JOUR = D(2026, 10, 1)
AIDE = str(TESTS / "_aide_concurrence_adhesions.py")
PREFIXE_BASE_MYSQL = "zz_test_adh_"


def _attendre(condition, delai=30):
    limite = time.time() + delai
    while time.time() < limite:
        if condition():
            return True
        time.sleep(0.05)
    return False


class _Concurrence(object):
    """ Lance A, attend qu'il soit dans la section protégée, lance B, vérifie
    que B est bloqué, libère A, puis lit les résultats. """

    def lancer(self, mode, cible):
        barriere = Path(tempfile.mkdtemp(prefix="barriere-adhesions-"))
        poste_a = subprocess.Popen([sys.executable, AIDE, mode, cible, "A", str(barriere)])
        try:
            self.assertTrue(_attendre(lambda: (barriere / "A_dans_section").exists()), "A n'a pas atteint la section protégée")
            poste_b = subprocess.Popen([sys.executable, AIDE, mode, cible, "B", str(barriere)])
            time.sleep(2.0)
            b_bloque = poste_b.poll() is None and not (barriere / "B.json").exists()
            (barriere / "A_continuer").write_text("1")
            self.assertEqual(poste_a.wait(60), 0)
            self.assertEqual(poste_b.wait(60), 0)
        finally:
            for processus in [poste_a] + ([poste_b] if "poste_b" in locals() else []):
                if processus.poll() is None:
                    processus.kill()
        import json
        resultats = {role: json.loads((barriere / ("%s.json" % role)).read_text()) for role in ("A", "B")}
        return b_bloque, resultats

    def verifier(self, b_bloque, resultats, compter):
        self.assertTrue(b_bloque, "le poste B n'a pas attendu le poste A")
        self.assertEqual(resultats["A"]["statut"], A.STATUT_CREE)
        self.assertEqual((resultats["B"]["statut"], resultats["B"]["motif"]), (A.STATUT_RIEN, "adhesion_deja_valide"))  # constaté sous verrou, après la validation de A
        self.assertEqual(resultats["B"]["creees"], [])
        self.assertEqual(compter("SELECT COUNT(*) FROM cotisations;"), 1)
        self.assertEqual(compter("SELECT COUNT(*) FROM prestations WHERE categorie='cotisation';"), 1)
        self.assertEqual(compter("SELECT COUNT(*) FROM historique WHERE IDcategorie=21;"), 1)


class ConcurrenceSQLiteTests(_Concurrence, unittest.TestCase):

    def test_deux_postes_simultanes_une_seule_adhesion(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 7))
            b_bloque, resultats = self.lancer("sqlite", e.base.chemin)
            self.verifier(b_bloque, resultats, lambda req: e.lire(req)[0][0])


class EchecEcritureTests(unittest.TestCase):

    def _echec_sur(self, table):
        original = A._AccesStrict.Inserer

        def inserer(acces, nom, donnees):
            if nom == table:
                raise RuntimeError("échec simulé sur %s" % table)
            return original(acces, nom, donnees)
        return mock.patch.object(A._AccesStrict, "Inserer", inserer)

    def test_aucune_ecriture_partielle(self):
        for table in ("prestations", "historique"):
            with self.subTest(table=table), Env() as e:
                e.conso(100, D(2026, 10, 7))
                with self._echec_sur(table), mock.patch("traceback.print_exc"):
                    res = A.ReconcilierIndividu(100, date_reference=JOUR, depuis=D(2026, 10, 7))
                self.assertEqual((res["statut"], res["motif"]), (A.STATUT_A_VERIFIER, "echec_ecriture"))
                self.assertEqual(e.compte("cotisations"), 0)
                self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 0)
                self.assertEqual(e.compte("historique"), 0)
                # Une nouvelle sauvegarde, sans échec, crée normalement (une seule fois).
                A.ReconcilierIndividu(100, date_reference=JOUR, depuis=D(2026, 10, 7))
                A.ReconcilierIndividu(100, date_reference=JOUR, depuis=D(2026, 10, 7))
                self.assertEqual(e.compte("cotisations"), 1)
                self.assertEqual(e.compte("prestations", "categorie='cotisation'"), 1)

    def test_lecture_en_echec_ne_vaut_jamais_absence(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 7))
            original = A._AccesStrict.ExecuterReq

            def lecture(acces, req):
                if "FROM cotisations" in req:
                    raise RuntimeError("lecture impossible")
                return original(acces, req)
            with mock.patch.object(A._AccesStrict, "ExecuterReq", lecture):
                with self.assertRaises(RuntimeError):
                    A.CreerAdhesion(100, {"date": D(2026, 10, 7), "source": "consommation", "id": 1,
                                          "IDcompte_payeur": 11, "IDinscription": None},
                                    A.ResoudreConfiguration(), date_reference=JOUR)
            self.assertEqual(e.compte("cotisations"), 0)

    def test_verrou_occupe_signale_sans_creer(self):
        with Env() as e:
            e.conso(100, D(2026, 10, 7))
            with mock.patch.object(A, "_Verrouiller", side_effect=A.VerrouIndisponible()):
                res = A.ReconcilierIndividu(100, date_reference=JOUR, depuis=D(2026, 10, 7))
            self.assertEqual((res["statut"], res["motif"]), (A.STATUT_A_VERIFIER, "verrou_indisponible"))
            self.assertEqual(e.compte("cotisations"), 0)
            self.assertIn(u"une autre sauvegarde", A.MessagesAVerifier({100: res})[0])


TABLES_MYSQL = ("individus", "familles", "rattachements", "comptes_payeurs", "activites", "inscriptions",
                "consommations", "prestations", "ventilation", "types_cotisations", "unites_cotisations",
                "cotisations", "cotisations_activites", "periodes_gestion", "historique")


@unittest.skipUnless(os.environ.get("NOETHYS_TEST_MYSQL_HOST"), "serveur MySQL local de test non déclaré (NOETHYS_TEST_MYSQL_*)")
class ConcurrenceMySQLTests(_Concurrence, unittest.TestCase):

    def setUp(self):
        self.base = "%s%s" % (PREFIXE_BASE_MYSQL, uuid.uuid4().hex[:10])
        self.serveur = _garde_reseau.ServeurMySQLDeTest()
        self.parametres = self.serveur.__enter__()
        self.cree = False
        racine = GestionDB.DB(nomFichier=self._nom(""), suffixe=None)
        self.assertEqual(racine.echec, 0, getattr(racine, "erreur", ""))
        racine.cursor.execute("SHOW DATABASES;")
        existantes = [ligne[0] for ligne in racine.cursor.fetchall()]
        racine.Close()
        self.assertNotIn(self.base, existantes)  # ne jamais réutiliser une base existante
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None, modeCreation=True)
        self.assertEqual(db.echec, 0, getattr(db, "erreur", ""))
        self.cree = True
        for table in TABLES_MYSQL:
            db.CreationTable(table, dicoDB=Tables.DB_DATA)
        for req in (
            "INSERT INTO familles (IDfamille) VALUES (1);",
            "INSERT INTO comptes_payeurs (IDcompte_payeur, IDfamille) VALUES (11, 1);",
            "INSERT INTO individus (IDindividu, nom, prenom, IDcivilite) VALUES (100, 'DUPUIS', 'Jean', 1);",
            "INSERT INTO rattachements (IDrattachement, IDfamille, IDindividu, IDcategorie, titulaire) VALUES (1, 1, 100, 2, 0);",
            "INSERT INTO activites (IDactivite, nom) VALUES (1, 'Activite A');",
            "INSERT INTO types_cotisations (IDtype_cotisation, nom, type, carte, defaut) VALUES (1, 'Adhesion annuelle', 'individu', 0, 1);",
            "INSERT INTO unites_cotisations (IDunite_cotisation, IDtype_cotisation, nom, montant, defaut, duree) VALUES (11, 1, 'Adhesion individuelle', 7.5, 1, 'j0-m0-a1');",
            "INSERT INTO cotisations_activites (IDactivite, IDtype_cotisation) VALUES (1, 1);",
            "INSERT INTO consommations (IDconso, IDindividu, IDactivite, date, IDunite, etat, IDcompte_payeur) VALUES (1001, 100, 1, '2026-10-07', 1, 'reservation', 11);",
        ):
            db.cursor.execute(req)
        db.Commit()
        db.Close()

    def tearDown(self):
        try:
            if self.cree and self.base.startswith(PREFIXE_BASE_MYSQL):
                racine = GestionDB.DB(nomFichier=self._nom(""), suffixe=None)
                racine.cursor.execute("DROP DATABASE %s;" % self.base)  # uniquement la base créée par ce test
                racine.Close()
        finally:
            self.serveur.__exit__(None, None, None)

    def _nom(self, base):
        p = self.parametres
        return u"%d;%s;%s;%s[RESEAU]%s" % (p["port"], p["hote"], p["utilisateur"], GestionDB.EncodeMdpReseau(p["motdepasse"]), base)

    def _compter(self, req):
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)
        try:
            db.cursor.execute(req)
            return db.cursor.fetchall()[0][0]
        finally:
            db.Close()

    def test_deux_postes_simultanes_une_seule_adhesion(self):
        b_bloque, resultats = self.lancer("mysql", self.base)
        self.verifier(b_bloque, resultats, self._compter)

    def test_tables_non_transactionnelles_refusees(self):
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)
        db.cursor.execute("ALTER TABLE historique ENGINE=MyISAM;")
        db.Close()
        with RedirectionGestionDB(self._nom(self.base)):
            res = A.ReconcilierIndividu(100, date_reference=JOUR, depuis=D(2026, 10, 7))
        self.assertEqual((res["statut"], res["motif"]), (A.STATUT_A_VERIFIER, "transactions_non_supportees"))
        self.assertEqual(self._compter("SELECT COUNT(*) FROM cotisations;"), 0)


if __name__ == "__main__":
    unittest.main()
