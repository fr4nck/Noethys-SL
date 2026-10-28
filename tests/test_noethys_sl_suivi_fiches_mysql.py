# -*- coding: utf-8 -*-
"""#436 : chemin SQL MySQL simule sur une base SQLite fictive.

Ce test ne revendique pas une recette sur un serveur MySQL reel.
Il exerce les adaptations de parametres, FOR UPDATE et le rollback
sur les deux methodes du service commun, sans reseau et sans PMSL.
"""
import sqlite3
import unittest

from tests.test_noethys_sl_suivi_fiches import BaseFictive
from Utils import UTILS_AEEH_Periodes as aeeh
from Utils import UTILS_Suivi_fiches as suivi


class CurseurMySQLSimule(object):
    """Simule seulement la syntaxe du connecteur, pas les verrous InnoDB."""
    def __init__(self, cur):
        self.original = cur
        self.requetes = []
        self.echec_historique = False

    def execute(self, requete, valeurs=()):
        self.requetes.append((requete, tuple(valeurs)))
        if self.echec_historique and "INSERT INTO historique" in requete:
            raise sqlite3.OperationalError("Panne historique fictive")
        if "%s" in requete:
            requete = requete.replace("%s", "?")
        if " FOR UPDATE" in requete:
            requete = requete.replace(" FOR UPDATE", "")
        return self.original.execute(requete, valeurs)

    @property
    def lastrowid(self):
        return self.original.lastrowid

    def fetchone(self):
        return self.original.fetchone()

    def fetchall(self):
        return self.original.fetchall()


class ConnexionMySQLSimulee(object):
    isNetwork = True

    def __init__(self):
        self.sqlite = BaseFictive()
        self.connexion = self.sqlite.connexion
        self.cursor = CurseurMySQLSimule(self.sqlite.cursor)
        self.commits = 0

    def ExecuterReq(self, requete):
        self.cursor.execute(requete)
        return 1

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Commit(self):
        self.commits += 1
        self.connexion.commit()

    def Close(self):
        self.sqlite.Close()

    def lire(self, table):
        return self.sqlite.lire(table)


class SimulationReseau(unittest.TestCase):
    def setUp(self):
        self.db = ConnexionMySQLSimulee()

    def tearDown(self):
        self.db.Close()

    def _periode(self, identite=1, debut="2026-01-01", fin="2026-12-31"):
        return suivi.EnregistrerPeriodeVerifiee(
            identite, 9, debut, fin, justificatif_verifie=True,
            source="pieces", DB=self.db,
        )

    def _confirmation(self):
        return suivi.EnregistrerConfirmationParentale(
            1, 9, ["vaccinations", "pai"], source="pieces",
            fiche_signee=True, document_relu=True, date_parent="2026-10-20",
            IDpiece=18, DB=self.db,
        )

    def test_periode_avec_verrou_et_parametres_mysql(self):
        IDperiode = self._periode()
        self.assertEqual(IDperiode, 1)
        self.assertEqual(len(self.db.lire("aeeh_periodes")), 1)
        self.assertEqual(len(self.db.lire("historique")), 1)
        self.assertEqual(self.db.commits, 1)
        requetes = [req for req, _ in self.db.cursor.requetes]
        self.assertTrue(any("FOR UPDATE" in req for req in requetes))
        self.assertTrue(any(
            "INSERT INTO aeeh_periodes" in req and req.count("%s") == 3
            for req in requetes
        ))
        self.assertTrue(any(
            "INSERT INTO historique" in req and req.count("%s") == 8
            for req in requetes
        ))

    def test_second_enfant_et_trietat_preserves(self):
        self._periode()
        self._periode(identite=2)
        self.assertEqual(len(self.db.lire("aeeh_periodes")), 2)
        ligne = self.db.connexion.execute(
            "SELECT aeeh FROM individus WHERE IDindividu=1"
        ).fetchone()
        self.assertIsNone(ligne[0])

    def test_chevauchement_refuse_avant_second_insert(self):
        self._periode()
        with self.assertRaises(aeeh.PeriodeAEEHInvalide):
            self._periode(debut="2026-06-01", fin="2026-08-31")
        self.assertEqual(len(self.db.lire("aeeh_periodes")), 1)
        self.assertEqual(len(self.db.lire("historique")), 1)

    def test_echec_historique_annule_la_periode(self):
        self.db.cursor.echec_historique = True
        with self.assertRaises(sqlite3.OperationalError):
            self._periode()
        self.assertEqual(self.db.lire("aeeh_periodes"), [])
        self.assertEqual(self.db.lire("historique"), [])
        self.assertEqual(self.db.commits, 0)

    def test_echec_lecture_des_periodes_interdit_l_ecriture(self):
        self.db.cursor.original.execute("DROP TABLE aeeh_periodes")
        self.db.connexion.commit()
        with self.assertRaises(sqlite3.OperationalError):
            self._periode()
        self.assertEqual(self.db.lire("historique"), [])
        self.assertEqual(self.db.commits, 0)

    def test_confirmation_parentale_et_piece_referencee(self):
        self.assertTrue(self._confirmation())
        self.assertEqual(self.db.commits, 1)
        h = self.db.lire("historique")[0]
        self.assertEqual(h[6], suivi.CATEGORIE_CONFIRMATION_PARENT)
        self.assertEqual(h[8], 18)
        self.assertIn("justificatifs non validés", h[7])
        info = suivi.GetDerniereConfirmationParentale(1, DB=self.db)
        self.assertEqual(info["IDpiece"], 18)
        self.assertEqual(info["IDutilisateur"], 9)

    def test_reception_non_signee_refusee_sans_verrou_ni_insert(self):
        with self.assertRaises(suivi.ControleFicheInvalide):
            suivi.EnregistrerConfirmationParentale(
                1, 9, ["allergies"], source="pieces", fiche_signee=False,
                document_relu=True, DB=self.db,
            )
        self.assertEqual(self.db.cursor.requetes, [])
        self.assertEqual(self.db.lire("historique"), [])

    def test_echec_historique_parentale_rollback(self):
        self.db.cursor.echec_historique = True
        with self.assertRaises(sqlite3.OperationalError):
            self._confirmation()
        self.assertEqual(self.db.lire("historique"), [])
        self.assertEqual(self.db.commits, 0)

    def test_id_enfant_inconnu_refuse(self):
        with self.assertRaises(suivi.ControleFicheInvalide):
            self._periode(identite=999)
        self.assertEqual(self.db.lire("aeeh_periodes"), [])

    def test_les_parametres_sont_toujours_lies(self):
        self._confirmation()
        self.assertTrue(any("%s" in sql for sql, _ in self.db.cursor.requetes))
        self.assertFalse(any(
            "SELECT date, heure" in sql and "IDindividu=%s" in sql
            for sql, _ in self.db.cursor.requetes
        ))  # Une écriture ne doit pas appeler silencieusement la requête de lecture.
        info = suivi.GetDerniereConfirmationParentale(1, DB=self.db)
        self.assertIsNotNone(info)
        self.assertTrue(any(
            "SELECT date, heure" in sql and "IDindividu=%s" in sql
            for sql, _ in self.db.cursor.requetes
        ))


if __name__ == "__main__":
    unittest.main()
