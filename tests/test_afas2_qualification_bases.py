# -*- coding: utf-8 -*-
"""AFAS V2 -- qualification de bout en bout sur base FICTIVE, SQLite et MySQL.

Le même jeu fictif (tests/afas2_base_fictive.py, résultats attendus calculés
à la main) est chargé par la vraie chaîne GestionDB -> UTILS_AFAS2_Donnees ->
moteur -> déclaration -> exports -> historique.

- SQLite : toujours exécuté (base temporaire).
- MySQL : seulement avec un serveur LOCAL jetable déclaré par
  NOETHYS_TEST_MYSQL_* (workflow « Noethys SL - AFAS V2 MySQL ») ; la base
  `zz_test_afas2_<aléa>` est créée puis supprimée par le test, et les
  résultats sont comparés à ceux de SQLite.
"""
import csv
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
for chemin in (RACINE / "noethys", RACINE / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import _garde_reseau  # noqa: E402
import afas2_base_fictive as F  # noqa: E402
from _fixtures_noethys_db import RedirectionGestionDB  # noqa: E402
import GestionDB  # noqa: E402
from Utils import UTILS_AFAS as AFAS  # noqa: E402
from Utils import UTILS_AFAS2_Declaration as DECL  # noqa: E402
from Utils import UTILS_AFAS2_Presets as P  # noqa: E402
from Utils import UTILS_AFAS2_Referentiel as R  # noqa: E402

PREFIXE_MYSQL = "zz_test_afas2_"


def _comparable(rapport):
    """Contenu métier du rapport, indépendant de la base (dates en texte)."""
    return json.loads(json.dumps({
        "indicateurs": rapport["indicateurs"], "validable": rapport["validable"],
        "motifs": rapport["motifs_non_validable"],
        "anomalies": sorted((str(a["date"]), str(a["IDconso"]), a["nature"], a["bloquante"]) for a in rapport["anomalies"]),
        "jours": sorted((str(j["date"]), j["IDindividu"], j["heures_realisees"], j["heures_facturees"], j["plages_ouverture"],
                         j["justification_facture"]) for j in rapport["jours"]),
    }, default=str))


class _Scenario(object):
    """Scénarios communs ; la sous-classe fournit self.nom (nomFichier GestionDB)."""

    def executer(self, preset):
        with RedirectionGestionDB(self.nom):
            referentiel = R.ChargerReferentiel()
            return DECL.Executer(preset, referentiel, F.ANNEE, AFAS.PHASE_REEL, date_reference=F.DATE_REFERENCE)

    def indicateurs(self, rapport):
        return {l["cle"]: l["realise"] for l in rapport["indicateurs"]}

    def test_periscolaire_bais(self):
        peri, extra, minicamps = self.presets
        r = self.executer(peri)
        self.assertEqual(self.indicateurs(r), F.ATTENDU_PERI)
        self.assertTrue(r["validable"], r["motifs_non_validable"])
        self.assertEqual(r["anomalies"], [])

    def test_extrascolaire_bais(self):
        peri, extra, minicamps = self.presets
        r = self.executer(extra)
        self.assertEqual(self.indicateurs(r), F.ATTENDU_EXTRA)
        self.assertTrue(r["validable"], r["motifs_non_validable"])
        justifications = {(str(j["date"]), j["IDindividu"]): j["justification_facture"] for j in r["jours"]}
        self.assertEqual(justifications[("2026-10-19", 9001)], "journée P90001 F9001")
        self.assertEqual(justifications[("2026-10-20", 9005)], "")  # annulée par l'avoir qualifié
        self.assertEqual(justifications[("2026-10-20", 9004)], "")  # facture annulée
        self.assertEqual({j["plages_ouverture"] for j in r["jours"] if j["justification_facture"]}, {"08:30-17:30"})

    def test_minicamps_integres_non_validables(self):
        peri, extra, minicamps = self.presets
        r = self.executer(minicamps)
        valeurs = self.indicateurs(r)
        self.assertEqual(valeurs["heures_sejours"], F.ATTENDU_SEJOURS["heures_sejours"])
        self.assertEqual(valeurs["heures_realisees"], F.ATTENDU_EXTRA["heures_realisees"] + valeurs["heures_sejours"])
        self.assertEqual(valeurs["heures_facturees"], F.ATTENDU_EXTRA["heures_facturees"] + valeurs["heures_sejours"])
        self.assertFalse(r["validable"])
        self.assertEqual([m for m in r["motifs_non_validable"] if "rubrique AFAS" in m], [
            "heures de séjours intégrées aux actes : rubrique AFAS des séjours non confirmée par la Caf"])

    def test_avoir_non_qualifie_bloque(self):
        peri, extra, minicamps = self.presets
        with RedirectionGestionDB(self.nom):
            referentiel = R.ChargerReferentiel()
            referentiel["regularisations"] = {}
            r = DECL.Executer(extra, referentiel, F.ANNEE, AFAS.PHASE_REEL, date_reference=F.DATE_REFERENCE)
        self.assertFalse(r["validable"])
        self.assertTrue(any(a["nature"].startswith("Régularisation négative non rattachée à une consommation (prestation 90090")
                            for a in r["anomalies"]))

    def test_exports_et_historique(self):
        peri, extra, minicamps = self.presets
        r = self.executer(extra)
        with tempfile.TemporaryDirectory() as dossier:
            chemins = DECL.ExporterDeclaration(dossier, r, "AFAS_fictif")
            with open(chemins["synthese"], encoding="utf-8-sig") as fichier:
                textes = {l[0]: l[1:] for l in csv.reader(fichier, delimiter=";") if l}
            self.assertEqual(textes["Heures facturées CAF"], ["déclaratif", "28,00", "0,00", "28,00"])
        with RedirectionGestionDB(self.nom):
            IDhisto = DECL.EnregistrerHistorique(r)
            archive = DECL.ChargerHistorique(IDhisto)
        self.assertTrue(archive["integrite"])
        self.assertEqual(archive["empreinte"], r["empreinte"])

    def test_persistance_presets_et_texte_long(self):
        peri, extra, minicamps = self.presets
        with RedirectionGestionDB(self.nom):
            IDprofil, enregistre = P.EnregistrerPreset(dict(minicamps, nom="Copie é à ç (fictif)"))
            self.assertEqual(P.ChargerPreset(IDprofil), enregistre)
            texte = {"texte": "é" * 27000}  # proche de la limite de l'historique, caractères accentués
            ID = R.CreerProfil("afas_v2_essai", "Essai")
            R.EcrireJSONProfil(ID, "essai_json", texte)
            self.assertEqual(R.LireJSONProfil(ID, "essai_json"), texte)


class SQLiteQualificationTests(_Scenario, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._dossier = tempfile.TemporaryDirectory(prefix="afas2-fictif-")
        cls.nom = os.path.join(cls._dossier.name, "afas2_fictif.dat")
        db = GestionDB.DB(nomFichier=cls.nom, suffixe=None, modeCreation=True)
        F.Peupler(db, creer_tables=True)
        db.Close()
        with RedirectionGestionDB(cls.nom):
            R.EnregistrerReferentiel(F.Referentiel())
        cls.presets = F.Presets()

    @classmethod
    def tearDownClass(cls):
        cls._dossier.cleanup()


class OutilsRecetteTests(unittest.TestCase):
    """Extraction pseudonymisée et rapprochement chiffré (tests/recette_afas2.py) sur le jeu fictif."""

    def setUp(self):
        import recette_afas2
        self.outils = recette_afas2
        self.dossier = tempfile.TemporaryDirectory(prefix="afas2-outils-")
        self.addCleanup(self.dossier.cleanup)
        self.source = os.path.join(self.dossier.name, "source.dat")
        db = GestionDB.DB(nomFichier=self.source, suffixe=None, modeCreation=True)
        F.Peupler(db, creer_tables=True)
        db.Close()
        with RedirectionGestionDB(self.source):
            R.EnregistrerReferentiel(F.Referentiel())
            for preset in F.Presets():
                P.EnregistrerPreset(preset)

    def empreinte_source(self):
        import hashlib
        with open(self.source, "rb") as fichier:
            return hashlib.sha256(fichier.read()).hexdigest()

    def test_extraction_pseudonymisee_sans_ecriture_et_resultats_identiques(self):
        avant = self.empreinte_source()
        extrait = os.path.join(self.dossier.name, "extrait.dat")
        effectifs = self.outils.Extraire(self.source, extrait, F.ANNEE)
        self.assertEqual(self.empreinte_source(), avant)  # source jamais modifiée
        self.assertEqual(effectifs["consommations"], len(F.CONSOMMATIONS))
        db = GestionDB.DB(nomFichier=extrait, suffixe=None)
        db.cursor.execute("SELECT DISTINCT nom FROM individus;")
        self.assertEqual(db.cursor.fetchall(), [("ENFANT",)])
        db.cursor.execute("SELECT DISTINCT montant FROM prestations ORDER BY montant;")
        self.assertEqual([m for (m,) in db.cursor.fetchall()], [-1.0, 0.0, 1.0])  # montants réduits au signe
        db.cursor.execute("SELECT COUNT(*) FROM prestations WHERE label<>'';")
        self.assertEqual(db.cursor.fetchall()[0][0], 0)
        db.Close()
        for preset in F.Presets():
            with self.subTest(preset=preset["nom"]):
                with RedirectionGestionDB(self.source):
                    attendu = DECL.Executer(preset, R.ChargerReferentiel(), F.ANNEE, AFAS.PHASE_REEL,
                                            date_reference=F.DATE_REFERENCE)
                with RedirectionGestionDB(extrait):
                    obtenu = DECL.Executer(preset, R.ChargerReferentiel(), F.ANNEE, AFAS.PHASE_REEL,
                                           date_reference=F.DATE_REFERENCE)
                self.assertEqual(json.loads(json.dumps(obtenu["indicateurs"])), json.loads(json.dumps(attendu["indicateurs"])))
                self.assertEqual(obtenu["validable"], attendu["validable"])
        with self.assertRaises(SystemExit):
            self.outils.Extraire(self.source, extrait, F.ANNEE)  # jamais d'écrasement

    def test_rapprochement_chiffre(self):
        extrait = os.path.join(self.dossier.name, "extrait.dat")
        self.outils.Extraire(self.source, extrait, F.ANNEE)
        attendus = os.path.join(self.dossier.name, "attendus.csv")
        with open(attendus, "w", encoding="utf-8") as fichier:
            fichier.write("indicateur;heures\n# références fictives\nheures_facturees;30\nheures_realisees;39,00\n")
        sortie = os.path.join(self.dossier.name, "sortie")
        rapport, chemins = self.outils.ExecuterRapprochement(extrait, F.ANNEE, AFAS.PHASE_REEL, "Bais extrascolaire (fictif)",
                                                             self.outils.LireAttendus(attendus), sortie,
                                                             date_reference=F.DATE_REFERENCE)
        with open(chemins["rapprochement"], encoding="utf-8-sig") as fichier:
            lignes = {l[0]: l for l in csv.reader(fichier, delimiter=";")}
        self.assertEqual(lignes["heures_facturees"][2:], ["28,00", "30,00", "-2,00", "-6,67"])
        self.assertEqual(lignes["heures_realisees"][2:], ["39,00", "39,00", "0,00", "0,00"])
        with open(chemins["ventilation"], encoding="utf-8-sig") as fichier:
            ventilation = list(csv.reader(fichier, delimiter=";"))
        self.assertEqual(ventilation[1:], [["2026-10", "Bais +6 ans", "39,00", "20,00", "5"],
                                           ["2026-10", "Bais -6 ans", "0,00", "8,00", "1"]])


@unittest.skipUnless(_garde_reseau.ParametresMySQLDeTest(), "serveur MySQL local jetable non déclaré")
class MySQLQualificationTests(_Scenario, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = _garde_reseau.ServeurMySQLDeTest()
        p = cls.serveur.__enter__()
        cls.base = PREFIXE_MYSQL + uuid.uuid4().hex[:12]
        racine = "%d;%s;%s;%s[RESEAU]" % (p["port"], p["hote"], p["utilisateur"], GestionDB.EncodeMdpReseau(p["motdepasse"]))
        cls.racine = racine
        cls.nom = racine + cls.base
        db = GestionDB.DB(nomFichier=racine, suffixe=None)
        assert db.echec == 0, getattr(db, "erreur", "")
        db.cursor.execute("SHOW DATABASES;")
        assert cls.base not in [ligne[0] for ligne in db.cursor.fetchall()]  # jamais une base existante
        db.Close()
        db = GestionDB.DB(nomFichier=cls.nom, suffixe=None, modeCreation=True)
        assert db.echec == 0, getattr(db, "erreur", "")
        cls.cree = True
        db.cursor.execute("SELECT VERSION();")
        print("AFAS V2 : MySQL %s, base fictive %s" % (db.cursor.fetchall()[0][0], cls.base))
        F.Peupler(db, creer_tables=True)
        db.Close()
        with RedirectionGestionDB(cls.nom):
            R.EnregistrerReferentiel(F.Referentiel())
        cls.presets = F.Presets()
        # Même jeu en SQLite pour la comparaison ligne à ligne.
        cls._dossier = tempfile.TemporaryDirectory(prefix="afas2-fictif-")
        cls.nom_sqlite = os.path.join(cls._dossier.name, "afas2_fictif.dat")
        db = GestionDB.DB(nomFichier=cls.nom_sqlite, suffixe=None, modeCreation=True)
        F.Peupler(db, creer_tables=True)
        db.Close()
        with RedirectionGestionDB(cls.nom_sqlite):
            R.EnregistrerReferentiel(F.Referentiel())

    @classmethod
    def tearDownClass(cls):
        try:
            if getattr(cls, "cree", False) and cls.base.startswith(PREFIXE_MYSQL):
                db = GestionDB.DB(nomFichier=cls.racine, suffixe=None)
                db.cursor.execute("DROP DATABASE %s;" % cls.base)  # uniquement la base créée ici
                db.Close()
        finally:
            cls._dossier.cleanup()
            cls.serveur.__exit__(None, None, None)

    def test_resultats_identiques_a_sqlite(self):
        for preset in self.presets:
            with self.subTest(preset=preset["nom"]):
                mysql = self.executer(preset)
                nom, self.nom = self.nom, self.nom_sqlite
                try:
                    sqlite = self.executer(preset)
                finally:
                    self.nom = nom
                self.assertEqual(_comparable(mysql), _comparable(sqlite))
                self.assertEqual(mysql["empreinte"], sqlite["empreinte"])


if __name__ == "__main__":
    unittest.main()
