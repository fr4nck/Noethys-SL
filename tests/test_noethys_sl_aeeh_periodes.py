# -*- coding: utf-8 -*-
"""Tests ciblés pour l'historisation des périodes de droit AEEH.

Contexte : `individus.aeeh` (tri-état NULL/0/1, cf. test_noethys_sl_aeeh.py)
reste inchangé dans ce lot. Ce fichier caractérise uniquement la nouvelle
table `aeeh_periodes` (schéma + migration additive) et les fonctions
non-wx de lecture/validation associées (Utils.UTILS_AEEH_Periodes) --
aucune UI, aucun GetControleAEEH(annee, phase), aucun calcul d'heures
AEEH, aucune synchronisation automatique avec individus.aeeh.

wx n'est pas installé dans tous les environnements de test : le test de
migration stubbe wx/GestionDB (même principe que test_noethys_sl_aeeh.py)
pour exécuter réellement UpgradeDB.py sans wx installé.
"""

import datetime
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

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

from Utils import UTILS_AEEH_Periodes  # noqa: E402


def _charger_module(chemin_relatif, nom):
    spec = importlib.util.spec_from_file_location(nom, str(ROOT / chemin_relatif))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lire_source(chemin_relatif):
    return (ROOT / chemin_relatif).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1) Schéma
# ---------------------------------------------------------------------------

class SchemaAeehPeriodesTests(unittest.TestCase):
    def test_table_presente_avec_les_colonnes_exactes(self):
        colonnes = [champ[0] for champ in Tables.DB_DATA["aeeh_periodes"]]
        self.assertEqual(colonnes, ["IDperiode", "IDindividu", "date_debut", "date_fin"])

    def test_aucune_autre_colonne_ni_donnee_medicale(self):
        for champ in Tables.DB_DATA["aeeh_periodes"]:
            nom = champ[0]
            self.assertNotIn("medic", nom.lower())
            self.assertNotIn("sante", nom.lower())
            self.assertNotIn("handicap", nom.lower())


# ---------------------------------------------------------------------------
# 2) Migration additive (stub wx/GestionDB, même principe que
#    test_noethys_sl_aeeh.py, avec un CreationTable qui exécute réellement
#    la création de table -- nécessaire ici puisqu'il s'agit d'une
#    nouvelle table, pas d'un simple AjoutChamp).
# ---------------------------------------------------------------------------

_ABSENT = object()
NOMS_MODULES_STUBBES = ("wx", "Chemins", "GestionDB", "Utils", "Utils.UTILS_Traduction")


class _RedirectionModules(object):
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
    wx = types.ModuleType("wx")
    sys.modules["wx"] = wx

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

        def CreationTable(self, nomTable="", dicoDB=None):
            """ Reproduit GestionDB.DB.CreationTable (adaptations SQLite
            uniquement, cf. GestionDB.py) -- contrairement au stub de
            test_noethys_sl_aeeh.py, exécute réellement la création,
            nécessaire pour vérifier la création d'une nouvelle table. """
            colonnes = []
            for nom_champ, type_champ, _commentaire in dicoDB[nomTable]:
                if type_champ == "LONGBLOB":
                    type_champ = "BLOB"
                if type_champ == "BIGINT":
                    type_champ = "INTEGER"
                colonnes.append("%s %s" % (nom_champ, type_champ))
            req = "CREATE TABLE %s (%s);" % (nomTable, ", ".join(colonnes))
            self.ExecuterReq(req)
            self.Commit()

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


class MigrationAdditiveAeehPeriodesTests(unittest.TestCase):
    def setUp(self):
        self._redirection = _RedirectionModules()
        self._redirection.__enter__()
        self.addCleanup(self._redirection.__exit__, None, None, None)
        self._installer_stubs_et_charger()

    def _installer_stubs_et_charger(self):
        _installer_stubs()
        self.UpgradeDB = _charger_module("noethys/UpgradeDB.py", "UpgradeDB_test_aeeh_periodes")

        self.db = self.UpgradeDB.DB()
        self.db.connexion = sqlite3.connect(":memory:")
        self.db.cursor = self.db.connexion.cursor()
        # Schéma "bare" (avant même l'ajout de la colonne aeeh en 1.3.4.3) :
        # AjoutChamp ferait échouer un ALTER TABLE ADD sur une colonne déjà
        # présente, donc on part toujours d'avant 1.3.4.3 ici.
        self.db.cursor.execute(
            "CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, nom TEXT)"
        )
        self.db.cursor.execute("INSERT INTO individus (IDindividu, nom) VALUES (1, 'DUPONT')")
        self.db.connexion.commit()
        self.addCleanup(self.db.connexion.close)

    def _table_existe(self, nom_table):
        self.db.cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nom_table,)
        )
        return self.db.cursor.fetchone() is not None

    def _colonnes(self, nom_table):
        self.db.cursor.execute("PRAGMA table_info(%s)" % nom_table)
        return [ligne[1] for ligne in self.db.cursor.fetchall()]

    def test_migration_cree_la_table_avec_les_bonnes_colonnes(self):
        self.assertFalse(self._table_existe("aeeh_periodes"))
        resultat = self.db.Upgrade(versionFichier=(1, 3, 4, 2))
        self.assertIs(resultat, True)
        self.assertTrue(self._table_existe("aeeh_periodes"))
        self.assertEqual(self._colonnes("aeeh_periodes"), ["IDperiode", "IDindividu", "date_debut", "date_fin"])

    def test_migration_est_idempotente(self):
        self.db.Upgrade(versionFichier=(1, 3, 4, 2))
        resultat = self.db.Upgrade(versionFichier=(1, 3, 4, 4))
        self.assertIs(resultat, True)
        self.assertTrue(self._table_existe("aeeh_periodes"))

    def test_aucune_periode_creee_automatiquement_meme_si_aeeh_vaut_1(self):
        """ Même un individu marqué aeeh=1 (après migration, comme le ferait
        l'UI existante) ne doit jamais se voir attribuer de période
        historique automatiquement -- aucune synchronisation individus.aeeh
        -> aeeh_periodes dans ce lot. """
        self.db.Upgrade(versionFichier=(1, 3, 4, 2))
        self.db.cursor.execute("UPDATE individus SET aeeh=1 WHERE IDindividu=1")
        self.db.connexion.commit()
        self.db.cursor.execute("SELECT COUNT(*) FROM aeeh_periodes")
        self.assertEqual(self.db.cursor.fetchone()[0], 0)

    def test_filtre_de_migration_ne_reutilise_pas_une_version_deja_livree(self):
        versions_txt = _lire_source("noethys/Versions.txt")
        premiere_ligne = versions_txt.splitlines()[0]
        self.assertNotIn("1.3.4.3", premiere_ligne,
                          "Versions.txt doit avoir été bumpé au-delà de 1.3.4.3 pour ce lot aeeh_periodes")


# ---------------------------------------------------------------------------
# 3) Lecture / actif-à-date / chevauchement (base SQLite réelle, sans wx)
# ---------------------------------------------------------------------------

class PeriodesAeehTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.base.db.CreationTable("aeeh_periodes", dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.base.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite"],
                           [(1, "DUPONT", "Enfant A", 1), (2, "MARTIN", "Enfant B", 1)])
        self.base.db.Commit()

        self._redirection = RedirectionGestionDB(self.base.chemin)
        self._redirection.__enter__()
        self.addCleanup(self._redirection.__exit__)
        self.addCleanup(self.base.fermer)

    def _inserer_periode(self, IDperiode, IDindividu, date_debut, date_fin):
        self.base.inserer("aeeh_periodes", ["IDperiode", "IDindividu", "date_debut", "date_fin"],
                           [(IDperiode, IDindividu, date_debut, date_fin)])

    # --- GetPeriodes --------------------------------------------------

    def test_get_periodes_triees_chronologiquement(self):
        self._inserer_periode(1, 1, "2026-07-01", "2026-12-31")
        self._inserer_periode(2, 1, "2026-01-01", "2026-06-30")
        periodes = UTILS_AEEH_Periodes.GetPeriodes(1)
        self.assertEqual([p["date_debut"] for p in periodes], ["2026-01-01", "2026-07-01"])

    def test_get_periodes_isole_les_individus(self):
        self._inserer_periode(1, 1, "2026-01-01", "2026-12-31")
        self._inserer_periode(2, 2, "2026-01-01", "2026-12-31")
        self.assertEqual(len(UTILS_AEEH_Periodes.GetPeriodes(1)), 1)
        self.assertEqual(len(UTILS_AEEH_Periodes.GetPeriodes(2)), 1)

    # --- EstAEEHActif : bornes ------------------------------------------

    def test_jour_avant_debut_est_faux(self):
        self._inserer_periode(1, 1, "2026-03-10", "2026-06-30")
        self.assertFalse(UTILS_AEEH_Periodes.EstAEEHActif(1, "2026-03-09"))

    def test_jour_du_debut_est_vrai(self):
        self._inserer_periode(1, 1, "2026-03-10", "2026-06-30")
        self.assertTrue(UTILS_AEEH_Periodes.EstAEEHActif(1, "2026-03-10"))

    def test_jour_entre_les_bornes_est_vrai(self):
        self._inserer_periode(1, 1, "2026-03-10", "2026-06-30")
        self.assertTrue(UTILS_AEEH_Periodes.EstAEEHActif(1, "2026-05-01"))

    def test_jour_de_fin_est_vrai(self):
        self._inserer_periode(1, 1, "2026-03-10", "2026-06-30")
        self.assertTrue(UTILS_AEEH_Periodes.EstAEEHActif(1, "2026-06-30"))

    def test_jour_apres_fin_est_faux(self):
        self._inserer_periode(1, 1, "2026-03-10", "2026-06-30")
        self.assertFalse(UTILS_AEEH_Periodes.EstAEEHActif(1, "2026-07-01"))

    def test_date_fin_null_actif_indefiniment_apres_debut(self):
        self._inserer_periode(1, 1, "2026-03-10", None)
        self.assertFalse(UTILS_AEEH_Periodes.EstAEEHActif(1, "2026-03-09"))
        self.assertTrue(UTILS_AEEH_Periodes.EstAEEHActif(1, "2026-03-10"))
        self.assertTrue(UTILS_AEEH_Periodes.EstAEEHActif(1, "2099-01-01"))

    def test_accepte_un_objet_date_comme_un_texte_iso(self):
        self._inserer_periode(1, 1, "2026-03-10", "2026-06-30")
        self.assertTrue(UTILS_AEEH_Periodes.EstAEEHActif(1, datetime.date(2026, 5, 1)))


# ---------------------------------------------------------------------------
# 4) Validation / chevauchement (pure, sans DB)
# ---------------------------------------------------------------------------

class ValiderPeriodeTests(unittest.TestCase):
    def setUp(self):
        self.base = BaseTest()
        self.base.db.CreationTable("aeeh_periodes", dicoDB=Tables.DB_DATA)
        self.base.db.Commit()
        self.base.inserer("individus", ["IDindividu", "nom", "prenom", "IDcivilite"],
                           [(1, "DUPONT", "Enfant A", 1), (2, "MARTIN", "Enfant B", 1)])
        self.base.db.Commit()

        self._redirection = RedirectionGestionDB(self.base.chemin)
        self._redirection.__enter__()
        self.addCleanup(self._redirection.__exit__)
        self.addCleanup(self.base.fermer)

    def _inserer_periode(self, IDperiode, IDindividu, date_debut, date_fin):
        self.base.inserer("aeeh_periodes", ["IDperiode", "IDindividu", "date_debut", "date_fin"],
                           [(IDperiode, IDindividu, date_debut, date_fin)])

    def test_date_debut_obligatoire(self):
        with self.assertRaises(UTILS_AEEH_Periodes.PeriodeAEEHInvalide):
            UTILS_AEEH_Periodes.ValiderPeriode(1, None, "2026-06-30")

    def test_date_fin_inferieure_a_date_debut_refusee(self):
        with self.assertRaises(UTILS_AEEH_Periodes.PeriodeAEEHInvalide):
            UTILS_AEEH_Periodes.ValiderPeriode(1, "2026-06-30", "2026-01-01")

    def test_date_fin_facultative(self):
        # Ne doit pas lever : aucune autre période existante.
        UTILS_AEEH_Periodes.ValiderPeriode(1, "2026-01-01", None)

    def test_periodes_successives_sans_chevauchement_autorisees(self):
        self._inserer_periode(1, 1, "2026-01-01", "2026-06-30")
        # Ne doit pas lever.
        UTILS_AEEH_Periodes.ValiderPeriode(1, "2026-07-01", "2026-12-31")

    def test_periodes_disjointes_avec_trou_autorisees(self):
        self._inserer_periode(1, 1, "2026-01-01", "2026-03-31")
        # Ne doit pas lever (trou d'avril à août).
        UTILS_AEEH_Periodes.ValiderPeriode(1, "2026-09-01", "2026-12-31")

    def test_chevauchement_d_un_jour_refuse(self):
        self._inserer_periode(1, 1, "2026-01-01", "2026-06-30")
        with self.assertRaises(UTILS_AEEH_Periodes.PeriodeAEEHInvalide):
            UTILS_AEEH_Periodes.ValiderPeriode(1, "2026-06-30", "2026-12-31")

    def test_periode_incluse_dans_une_autre_refusee(self):
        self._inserer_periode(1, 1, "2026-01-01", "2026-12-31")
        with self.assertRaises(UTILS_AEEH_Periodes.PeriodeAEEHInvalide):
            UTILS_AEEH_Periodes.ValiderPeriode(1, "2026-03-01", "2026-04-01")

    def test_periode_ouverte_plus_periode_future_refusee(self):
        self._inserer_periode(1, 1, "2026-01-01", None)
        with self.assertRaises(UTILS_AEEH_Periodes.PeriodeAEEHInvalide):
            UTILS_AEEH_Periodes.ValiderPeriode(1, "2027-01-01", "2027-06-30")

    def test_isolation_entre_deux_individus(self):
        self._inserer_periode(1, 1, "2026-01-01", "2026-12-31")
        # Même plage de dates, mais individu différent : ne doit pas lever.
        UTILS_AEEH_Periodes.ValiderPeriode(2, "2026-01-01", "2026-12-31")

    def test_edition_ignore_sa_propre_periode_via_idperiode_exclue(self):
        self._inserer_periode(1, 1, "2026-01-01", "2026-06-30")
        # Sans exclusion : chevauche elle-même (mêmes bornes) -> refusé.
        with self.assertRaises(UTILS_AEEH_Periodes.PeriodeAEEHInvalide):
            UTILS_AEEH_Periodes.ValiderPeriode(1, "2026-01-01", "2026-06-30")
        # Avec exclusion de son propre IDperiode : ne doit pas lever.
        UTILS_AEEH_Periodes.ValiderPeriode(1, "2026-01-01", "2026-06-30", IDperiode_exclue=1)


if __name__ == "__main__":
    unittest.main()
