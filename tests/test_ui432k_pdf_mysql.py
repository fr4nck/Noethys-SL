# -*- coding: utf-8 -*-
"""UI-432K : vrai Noedoc sur MySQL 5.7 local jetable, contre SQLite fictif.

La classe est SKIP hors des runners de recette avec serveur MySQL explicite.
Ne contacte jamais la base d'une association et ne genere aucun email.
"""
import faulthandler
import os
import re
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for chemin in (ROOT, ROOT / "tests", ROOT / "noethys"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))
import _garde_reseau  # noqa: E402
import GestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402
from _fixtures_noethys_db import RedirectionGestionDB  # noqa: E402

PREFIXE = "zz_test_ui432k_"


@unittest.skipUnless(_garde_reseau.ParametresMySQLDeTest(),
                     "Serveur MySQL 5.7 local fictif non declare")
class FacturePDFMySQLFictif(unittest.TestCase):
    @classmethod
    def _nettoyer_mysql(cls):
        if not getattr(cls, "cree", False):
            return
        if not cls.base.startswith(PREFIXE):
            raise AssertionError("Nettoyage MySQL hors prefixe de recette refuse")
        admin = GestionDB.DB(nomFichier=cls.racine, suffixe=None, pooling=False)
        try:
            # Un SELECT ou worker en echec peut laisser une connexion ouverte.
            # Le nettoyage de la fixture ne doit jamais attendre 7 minutes.
            admin.cursor.execute("SET SESSION lock_wait_timeout=5;")
            admin.cursor.execute("DROP DATABASE `%s`;" % cls.base)
        finally:
            admin.Close()

    @classmethod
    def setUpClass(cls):
        faulthandler.enable()
        faulthandler.dump_traceback_later(70, repeat=False)
        print("UI432K_MYSQL_PHASE fixture_preparation", flush=True)
        import wx
        from tests.test_vanilla_facture_prestation_sans_activite import (
            _creer_base_facture_avec_prestation_sans_activite)
        cls.app = wx.GetApp() or wx.App(False)
        cls.garde = _garde_reseau.ServeurMySQLDeTest()
        infos = cls.garde.__enter__()
        cls.addClassCleanup(cls.garde.__exit__, None, None, None)
        cls.base = PREFIXE + uuid.uuid4().hex[:12] + "_data"
        cls.racine = "%d;%s;%s;%s[RESEAU]" % (
            infos["port"], infos["hote"], infos["utilisateur"],
            GestionDB.EncodeMdpReseau(infos["motdepasse"]))
        cls.source = cls.racine + cls.base
        cls.cree = False
        cls.addClassCleanup(cls._nettoyer_mysql)

        verification = GestionDB.DB(nomFichier=cls.racine, suffixe=None)
        try:
            if verification.echec:
                raise AssertionError("Serveur MySQL jetable indisponible")
            verification.cursor.execute("SHOW DATABASES")
            noms = [str(x[0]).lower() for x in verification.cursor.fetchall()]
            if cls.base.lower() in noms:
                raise AssertionError("Base deja presente : refus de creation")
        finally:
            verification.Close()

        cls.sqlite, cls.modele = _creer_base_facture_avec_prestation_sans_activite()
        cls.addClassCleanup(cls.sqlite.fermer)
        print("UI432K_MYSQL_PHASE sqlite_pret", flush=True)
        # Reproduire les tables lues par la vraie chaine de facturation :
        # SQLite peut masquer une lecture SQL echouee, mais MySQL ne peut
        # pas fournir un fetchall() apres l'absence de table. Le test doit
        # exercer un schema reeel coherent, sans affaiblir la validation.
        with sqlite3.connect(cls.sqlite.chemin) as controle:
            presentes = set(row[0] for row in controle.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"))
        for table in ("questionnaire_reponses", "inscriptions"):
            if table not in presentes:
                cls.sqlite.db.CreationTable(table, Tables.DB_DATA)
        cls.sqlite.db.Commit()

        mysql = GestionDB.DB(
            nomFichier=cls.source, suffixe=None, modeCreation=True, pooling=False)
        try:
            if mysql.echec:
                raise AssertionError("Creation MySQL jetable impossible")
            cls.cree = True
            with sqlite3.connect(cls.sqlite.chemin) as src:
                tables = [row[0] for row in src.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                for table in tables:
                    if table not in Tables.DB_DATA:
                        raise AssertionError("Table fictive hors schema Noethys")
                    mysql.CreationTable(table, Tables.DB_DATA)
                for table in tables:
                    colonnes = [row[1] for row in src.execute(
                        "PRAGMA table_info(`%s`)" % table)]
                    lignes = src.execute("SELECT * FROM `%s`" % table).fetchall()
                    if lignes:
                        stmt = "INSERT INTO `%s` (%s) VALUES (%s)" % (
                            table, ",".join("`%s`" % c for c in colonnes),
                            ",".join(["%s"] * len(colonnes)))
                        mysql.cursor.executemany(stmt, lignes)
                mysql.Commit()
        finally:
            mysql.Close()
        print("UI432K_MYSQL_PHASE mysql_pret", flush=True)

    def test_mysql_noedoc_identique_en_pages_au_rendu_historique(self):
        from tests.test_vanilla_facture_prestation_sans_activite import _dict_options_minimal
        from Utils import (UTILS_Facturation, UTILS_Impression_facture,
                           UTILS_PDF_processus, UTILS_PDF_securise)
        options = _dict_options_minimal(self.modele)
        print("UI432K_MYSQL_PHASE facturation_debut", flush=True)
        with RedirectionGestionDB(self.source):
            fac = UTILS_Facturation.Facturation()
            resultat = fac.GetDonneesImpression(
                listeFactures=[1], dictOptions=options, parent=None)
        self.assertIsNot(resultat, False)
        print("UI432K_MYSQL_PHASE facturation_ok", flush=True)
        comptes = resultat[0]
        self.assertTrue(UTILS_PDF_processus.SourceCompatible(self.source))
        with tempfile.TemporaryDirectory(prefix="ui432k-mysql-pdf-") as rep:
            a = str(Path(rep) / "historique.pdf")
            b = str(Path(rep) / "enfant.pdf")
            print("UI432K_MYSQL_PHASE reference_debut", flush=True)
            with RedirectionGestionDB(self.source):
                UTILS_Impression_facture.Impression(
                    comptes, options, IDmodele=self.modele,
                    ouverture=False, nomFichier=a)
            print("UI432K_MYSQL_PHASE reference_ok", flush=True)
            c, o = UTILS_PDF_processus.Preparer(comptes, options)
            print("UI432K_MYSQL_PHASE processus_debut", flush=True)
            with mock.patch.dict(os.environ, {"NOETHYS_SL_PDF_TEST_ISOLE": "1"}):
                UTILS_PDF_securise.Generer(
                    b, lambda chemin: UTILS_PDF_processus.Generer(
                        c, o, self.modele, chemin, self.source,
                        delai=90, donnees_pretes=True))
            print("UI432K_MYSQL_PHASE processus_ok", flush=True)
            historique, enfant = Path(a).read_bytes(), Path(b).read_bytes()
            for document in (historique, enfant):
                self.assertTrue(document.startswith(b"%PDF-"))
                self.assertIn(b"%%EOF", document[-2048:])
            pages = lambda pdf: len(re.findall(rb"/Type\\s*/Page\\b", pdf))
            self.assertGreater(pages(historique), 0)
            self.assertEqual(pages(historique), pages(enfant))
            self.assertLess(abs(len(historique) - len(enfant)),
                            max(2000, int(len(historique) * 0.10)))
            self.assertEqual(sorted(os.listdir(rep)),
                             ["enfant.pdf", "historique.pdf"])
        print("UI432K_MYSQL_PDF_PASS", flush=True)


if __name__ == "__main__":
    unittest.main()
