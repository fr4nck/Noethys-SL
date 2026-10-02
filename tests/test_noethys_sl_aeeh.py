# -*- coding: utf-8 -*-
"""
Tests ciblés pour le statut Bénéficiaire AEEH de l'individu.

Contexte : la donnée AEEH devient un champ dédié de la table `individus`
(colonne "aeeh"), distinct de `problemes_sante`/`categories_medicales` et
du mécanisme Questionnaire.

wx n'est pas installé dans tous les environnements de test : les modules
qui en dépendent directement (GestionDB, UpgradeDB) sont stubbés (pour
exécuter réellement la migration), conformément aux conventions déjà en
place dans ce dépôt (voir tests/test_noethys_sl_periodes_saison.py pour le
chargement direct d'un module par chemin, et tests/test_vanilla_identite_noethys_sl.py
pour la vérification de la version interne alimentée par Versions.txt).
"""

import importlib.util
import sqlite3
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))


def _charger_module(chemin_relatif, nom):
    spec = importlib.util.spec_from_file_location(nom, str(ROOT / chemin_relatif))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lire_source(chemin_relatif):
    return (ROOT / chemin_relatif).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1) Présence du champ AEEH dans le schéma actuel
# ---------------------------------------------------------------------------

class Test_SchemaContientAeeh(unittest.TestCase):
    def test_colonne_aeeh_presente_dans_individus(self):
        Tables = _charger_module("noethys/Data/DATA_Tables.py", "DATA_Tables_test_aeeh")
        colonnes = {champ[0]: champ for champ in Tables.DB_DATA["individus"]}
        self.assertIn("aeeh", colonnes)
        nom, type_champ, commentaire = colonnes["aeeh"]
        self.assertEqual(type_champ, "INTEGER")

    def test_colonne_aeeh_absente_des_tables_medicales_et_questionnaire(self):
        """ Garde-fou : l'AEEH ne doit pas se retrouver dans le sous-système santé ni dans le Questionnaire générique. """
        Tables = _charger_module("noethys/Data/DATA_Tables.py", "DATA_Tables_test_aeeh_bis")
        for table in ("problemes_sante", "categories_medicales", "questionnaire_questions", "questionnaire_reponses"):
            colonnes = [champ[0] for champ in Tables.DB_DATA[table]]
            self.assertNotIn("aeeh", colonnes)


# ---------------------------------------------------------------------------
# 2) et 4) Migration additive + conservation stricte NULL / 0 / 1
# ---------------------------------------------------------------------------

_ABSENT = object()

NOMS_MODULES_STUBBES = ("wx", "six", "Chemins", "GestionDB", "Utils", "Utils.UTILS_Traduction")


class _RedirectionModules(object):
    """ Stubbe des entrées de sys.modules le temps du bloc, puis les restaure
    EXACTEMENT à leur état antérieur (même objet si la clé existait déjà,
    clé de nouveau absente sinon) -- même principe que RedirectionGestionDB
    (tests/_fixtures_noethys_db.py), qui mute puis restaure un attribut du
    vrai module GestionDB au lieu de le remplacer sans jamais revenir en
    arrière.

    Avant cette correction, le nettoyage ne supprimait que les clés
    NOUVELLEMENT ajoutées à sys.modules : "GestionDB" et "wx" sont presque
    toujours déjà importés par un autre fichier de test collecté dans le
    même process, donc la clé restait pointée vers le faux module pour le
    reste du process -- exposant tout code de production faisant un import
    GestionDB tardif (résolu au moment de l'appel, pas à l'import du
    fichier), comme Utils/UTILS_Convention_champs.GetIndividusRattaches()
    ou Utils/UTILS_Impression_reservations.GetDonnees(), au faux
    _FakeGestionDB (sans .cursor) dès qu'un test de ce fichier avait tourné
    plus tôt dans le même process pytest. """

    def __init__(self, noms=NOMS_MODULES_STUBBES):
        self.noms = tuple(noms)

    def __enter__(self):
        self._sauvegarde = {nom: sys.modules.get(nom, _ABSENT) for nom in self.noms}
        return self

    def __exit__(self, *exc_info):
        for nom, valeur in self._sauvegarde.items():
            if valeur is _ABSENT:
                sys.modules.pop(nom, None)
            else:
                sys.modules[nom] = valeur
        return False


def _installer_stubs():
    """ Stubbe les dépendances non nécessaires au test (wx absent de l'environnement).
    N'installe rien dans sys.modules de façon durable : à utiliser uniquement
    à l'intérieur d'un bloc _RedirectionModules (voir Test_MigrationAdditive). """
    wx = types.ModuleType("wx")
    sys.modules["wx"] = wx

    six = types.ModuleType("six")
    six.PY2 = False
    six.PY3 = True
    sys.modules["six"] = six

    sys.modules["Chemins"] = types.ModuleType("Chemins")

    class _FakeGestionDB(object):
        isNetwork = False

        def __init__(self, *args, **kwargs):
            pass

        def IsTableExists(self, nom_table):
            self.cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nom_table,)
            )
            return self.cursor.fetchone() is not None

        def ExecuterReq(self, req):
            self.cursor.execute(req)
            return 1

        def ResultatReq(self):
            return self.cursor.fetchall()

        def Commit(self):
            self.connexion.commit()

        def AjoutChamp(self, nomTable="", nomChamp="", typeChamp=""):
            req = "ALTER TABLE %s ADD %s %s;" % (nomTable, nomChamp, typeChamp)
            self.ExecuterReq(req)
            self.Commit()

        def SupprChamp(self, nomTable="", nomChamp=""):
            pass

        def CreationTable(self, nomTable, dicoDB):
            pass

    gestion = types.ModuleType("GestionDB")
    gestion.DB = _FakeGestionDB
    sys.modules["GestionDB"] = gestion

    utils_pkg = types.ModuleType("Utils")
    utils_pkg.__path__ = []
    sys.modules["Utils"] = utils_pkg

    traduction = types.ModuleType("Utils.UTILS_Traduction")
    traduction._ = lambda value: value
    sys.modules["Utils.UTILS_Traduction"] = traduction
    utils_pkg.UTILS_Traduction = traduction

    return _FakeGestionDB


class Test_MigrationAdditive(unittest.TestCase):
    def setUp(self):
        self._redirection = _RedirectionModules()
        self._redirection.__enter__()
        self.FakeGestionDB = _installer_stubs()

        # Charge le vrai module de migration (celui qui sera exécuté en production)
        self.UpgradeDB = _charger_module("noethys/UpgradeDB.py", "UpgradeDB_test_aeeh")

        # Simule une base existante "ancienne" (avant migration), avec une ligne réelle
        self.db = self.UpgradeDB.DB()
        self.db.connexion = sqlite3.connect(":memory:")
        self.db.cursor = self.db.connexion.cursor()
        self.db.cursor.execute(
            "CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, nom TEXT, deces INTEGER)"
        )
        self.db.cursor.execute("INSERT INTO individus (IDindividu, nom, deces) VALUES (1, 'DUPONT', 0)")
        self.db.connexion.commit()

    def tearDown(self):
        self.db.connexion.close()
        # Restaure sys.modules EXACTEMENT à son état d'avant setUp (voir _RedirectionModules)
        self._redirection.__exit__(None, None, None)

    def _colonnes_individus(self):
        self.db.cursor.execute("PRAGMA table_info(individus)")
        return [ligne[1] for ligne in self.db.cursor.fetchall()]

    def test_migration_ajoute_la_colonne_aeeh(self):
        self.assertNotIn("aeeh", self._colonnes_individus())
        resultat = self.db.Upgrade(versionFichier=(1, 3, 4, 2))
        self.assertIs(resultat, True)
        self.assertIn("aeeh", self._colonnes_individus())

    def test_individu_existant_devient_non_renseigne_apres_migration(self):
        self.db.Upgrade(versionFichier=(1, 3, 4, 2))
        self.db.cursor.execute("SELECT aeeh FROM individus WHERE IDindividu=1")
        valeur = self.db.cursor.fetchone()[0]
        self.assertIsNone(valeur, "Une ligne existante doit rester à NULL (Non renseigné), jamais convertie en 0")

    def test_conservation_stricte_null_0_1(self):
        self.db.Upgrade(versionFichier=(1, 3, 4, 2))
        self.db.cursor.execute("INSERT INTO individus (IDindividu, nom, deces, aeeh) VALUES (2, 'MARTIN', 0, 0)")
        self.db.cursor.execute("INSERT INTO individus (IDindividu, nom, deces, aeeh) VALUES (3, 'DURAND', 0, 1)")
        self.db.connexion.commit()

        self.db.cursor.execute("SELECT IDindividu, aeeh FROM individus ORDER BY IDindividu")
        resultats = dict(self.db.cursor.fetchall())
        self.assertIsNone(resultats[1])  # Non renseigné, jamais touché par la migration
        self.assertEqual(resultats[2], 0)  # Non bénéficiaire
        self.assertEqual(resultats[3], 1)  # Bénéficiaire

    def test_migration_est_idempotente_sur_base_deja_a_jour(self):
        """ Une base déjà migrée ne doit pas provoquer d'erreur (colonne déjà existante géré en amont). """
        self.db.Upgrade(versionFichier=(1, 3, 4, 2))
        # Rejouer avec une version déjà à jour ne doit pas re-déclencher le filtre
        resultat = self.db.Upgrade(versionFichier=(1, 3, 4, 3))
        self.assertIs(resultat, True)

    def test_filtre_de_migration_ne_reutilise_pas_une_version_deja_livree(self):
        """ Garde-fou anti-régression : 1.3.4.2 est déjà la version livrée de Noethys SL
        (cf. Versions.txt) ; le filtre AEEH doit être strictement postérieur, sinon la
        migration ne se déclencherait jamais pour les bases déjà en 1.3.4.2. """
        versions_txt = _lire_source("noethys/Versions.txt")
        premiere_ligne = versions_txt.splitlines()[0]
        self.assertNotIn("1.3.4.2", premiere_ligne,
                          "Versions.txt doit avoir été bumpé au-delà de 1.3.4.2 pour ce lot AEEH")


# ---------------------------------------------------------------------------
# 2bis) Non-régression : isolation de sys.modules entre tests
# ---------------------------------------------------------------------------

class Test_IsolationSysModules(unittest.TestCase):
    """ Garde-fou anti-régression : Test_MigrationAdditive stubbe wx/GestionDB
    pour exécuter réellement UpgradeDB.py sans wx installé. Avant correction,
    son tearDown ne supprimait que les clés NOUVELLEMENT ajoutées à
    sys.modules ; comme "GestionDB" et "wx" sont presque toujours déjà
    importés par un autre fichier de test collecté dans le même process, la
    clé restait pointée vers le faux module pour le reste du process --
    exposant tout code de production faisant un import GestionDB tardif
    (résolu au moment de l'appel, pas à l'import du fichier), comme
    Utils/UTILS_Convention_champs.GetIndividusRattaches() ou
    Utils/UTILS_Impression_reservations.GetDonnees(), au faux
    _FakeGestionDB (sans .cursor) dès qu'un test de migration AEEH avait
    tourné plus tôt dans le même process pytest.

    Ce test exécute réellement un test de Test_MigrationAdditive (setUp +
    test + tearDown), puis vérifie que sys.modules est revenu EXACTEMENT
    (même objet, pas juste "une valeur quelconque") à son état d'avant, et
    qu'un import ultérieur de GestionDB ne renvoie jamais _FakeGestionDB. """

    def test_gestiondb_et_wx_restaures_exactement_apres_migration_additive(self):
        import GestionDB as gestiondb_avant
        import wx as wx_avant

        resultat = unittest.TestResult()
        Test_MigrationAdditive("test_migration_ajoute_la_colonne_aeeh").run(resultat)
        self.assertEqual(resultat.errors, [])
        self.assertEqual(resultat.failures, [])

        # Restauration EXACTE : le même objet module qu'avant, pas un autre GestionDB
        self.assertIs(sys.modules["GestionDB"], gestiondb_avant)
        self.assertIs(sys.modules["wx"], wx_avant)

        # Un import ultérieur (fraîchement résolu) ne renvoie jamais le faux GestionDB
        import GestionDB as gestiondb_apres
        self.assertIs(gestiondb_apres, gestiondb_avant)
        self.assertNotEqual(gestiondb_apres.DB.__name__, "_FakeGestionDB")
        self.assertTrue(
            hasattr(gestiondb_apres.DB, "OuvertureFichierLocal"),
            "GestionDB.DB doit rester la vraie classe de production, pas le stub de test",
        )

    def test_utils_restaure_exactement_apres_mapping_tri_etat(self):
        """ Même garde-fou pour Test_MappingTriEtat, qui stubbe "Utils"/
        "Utils.UTILS_Traduction" (utilisé par ex. par OL_Etat_nomin_champs.py
        pour ses libellés de champs STANDARD, dont INDIVIDU_AEEH). """
        import Utils as utils_avant

        resultat = unittest.TestResult()
        Test_MappingTriEtat("test_index_par_defaut_est_non_renseigne").run(resultat)
        self.assertEqual(resultat.errors, [])
        self.assertEqual(resultat.failures, [])

        self.assertIs(sys.modules["Utils"], utils_avant)


# ---------------------------------------------------------------------------
# 3) Mapping tri-état pur (UTILS_Aeeh) - valeur par défaut = Non renseigné
# ---------------------------------------------------------------------------

class Test_MappingTriEtat(unittest.TestCase):
    def setUp(self):
        self._redirection = _RedirectionModules(("Utils", "Utils.UTILS_Traduction"))
        self._redirection.__enter__()
        utils_pkg = types.ModuleType("Utils")
        utils_pkg.__path__ = []
        sys.modules["Utils"] = utils_pkg
        traduction = types.ModuleType("Utils.UTILS_Traduction")
        traduction._ = lambda value: value
        sys.modules["Utils.UTILS_Traduction"] = traduction
        utils_pkg.UTILS_Traduction = traduction

        self.UTILS_Aeeh = _charger_module("noethys/Utils/UTILS_Aeeh.py", "UTILS_Aeeh_test")

    def tearDown(self):
        # Restaure sys.modules EXACTEMENT à son état d'avant setUp (voir _RedirectionModules)
        self._redirection.__exit__(None, None, None)

    def test_index_par_defaut_est_non_renseigne(self):
        self.assertEqual(self.UTILS_Aeeh.ValeurVersIndex(None), 0)
        self.assertEqual(self.UTILS_Aeeh.IndexVersValeur(0), None)

    def test_non_renseigne_distinct_de_non(self):
        index_non_renseigne = self.UTILS_Aeeh.ValeurVersIndex(None)
        index_non = self.UTILS_Aeeh.ValeurVersIndex(0)
        index_oui = self.UTILS_Aeeh.ValeurVersIndex(1)
        self.assertNotEqual(index_non_renseigne, index_non)
        self.assertNotEqual(index_non_renseigne, index_oui)
        self.assertNotEqual(index_non, index_oui)

    def test_aller_retour_valeur_index(self):
        for valeur in (None, 0, 1):
            index = self.UTILS_Aeeh.ValeurVersIndex(valeur)
            self.assertEqual(self.UTILS_Aeeh.IndexVersValeur(index), valeur)

    def test_formatage_texte_pour_etat_nominatif(self):
        self.assertEqual(self.UTILS_Aeeh.ValeurVersTexte(1), "Oui")
        self.assertEqual(self.UTILS_Aeeh.ValeurVersTexte(0), "Non")
        self.assertEqual(self.UTILS_Aeeh.ValeurVersTexte(None), u"")


# ---------------------------------------------------------------------------
# 5) Présence du champ AEEH parmi les champs STANDARD de l'Etat Nominatif
# ---------------------------------------------------------------------------

class Test_EtatNominatifExposeAeeh(unittest.TestCase):
    def test_champ_standard_declare(self):
        source = _lire_source("noethys/Ol/OL_Etat_nomin_champs.py")
        self.assertIn('"INDIVIDU_AEEH"', source)
        self.assertIn("LISTE_CHAMPS_STANDARDS", source)

    def test_track_peuple_attribut_aeeh(self):
        source = _lire_source("noethys/Ol/OL_Etat_nomin_resultats.py")
        self.assertIn("self.INDIVIDU_AEEH", source)
        self.assertIn('"aeeh"', source)
        self.assertIn("UTILS_Aeeh.ValeurVersTexte", source)


# ---------------------------------------------------------------------------
# 6) Contrat de câblage dans le dossier individuel (sans import GUI lourd)
# ---------------------------------------------------------------------------

class Test_DossierIndividuelCablageAeeh(unittest.TestCase):
    def test_lecture_et_ecriture_referencent_aeeh(self):
        source = _lire_source("noethys/Dlg/DLG_Individu_identite.py")
        self.assertIn("aeeh FROM individus", source)
        self.assertIn('("aeeh", dictDonnees["aeeh"])', source)
        self.assertIn("UTILS_Aeeh.ValeurVersIndex(individu[14])", source)
        self.assertIn("UTILS_Aeeh.IndexVersValeur(self.ctrl_aeeh.GetSelection())", source)

    def test_libelle_et_choix_conformes(self):
        source = _lire_source("noethys/Dlg/DLG_Individu_identite.py")
        self.assertIn(u"Bénéficiaire AEEH", source)

    def test_aucune_ecriture_dans_les_zones_hors_perimetre(self):
        """ Garde-fou anti-doublon : ce lot ne doit toucher ni AFAS, ni ajouter la colonne aeeh au Questionnaire. """
        for chemin in (
            "noethys/Dlg/DLG_Individu_identite.py",
            "noethys/Data/DATA_Tables.py",
            "noethys/UpgradeDB.py",
            "noethys/Ol/OL_Etat_nomin_champs.py",
            "noethys/Ol/OL_Etat_nomin_resultats.py",
            "noethys/Utils/UTILS_Aeeh.py",
        ):
            source = _lire_source(chemin)
            self.assertNotIn("AFAS", source)
            # Le champ "aeeh" ne doit jamais être ajouté comme colonne du mécanisme Questionnaire
            self.assertNotIn('"aeeh", "questionnaire', source)

    def test_fichiers_medicaux_non_modifies_par_ce_lot(self):
        """ Vérifie que les écrans/tables santé existants n'ont pas été altérés pour porter l'AEEH. """
        for chemin in (
            "noethys/Dlg/DLG_Individu_medical.py",
            "noethys/Dlg/DLG_Saisie_pb_sante.py",
        ):
            source = _lire_source(chemin)
            self.assertNotIn("aeeh", source.lower())


if __name__ == "__main__":
    unittest.main()
