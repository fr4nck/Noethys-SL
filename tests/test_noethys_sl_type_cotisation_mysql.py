# -*- coding: utf-8 -*-
"""Recette MySQL 5.7 isolée : enregistrement d'un type de cotisation, de
ses unités et de son mode d'association dans une seule transaction.

Exécuté uniquement avec un serveur MySQL local jetable déclaré par
NOETHYS_TEST_MYSQL_* (workflow noethys-sl-rc9-qualification) ; chaque test
crée puis supprime sa propre base zz_test_adh_*. Aucune base Noethys réelle.
Les vraies méthodes du dialogue sont exécutées sur un hôte sans fenêtre.
"""
import os
import re
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: F401
from _fixtures_noethys_db import RedirectionGestionDB
import test_noethys_sl_adhesions_concurrence as concurrence
import test_noethys_sl_type_cotisation_erreurs as erreurs
import GestionDB
import wx
from Utils import UTILS_Adhesions as A

CAT = A.CATEGORIE_MODE_ASSOCIATION


class _ConnexionEnPanneApresEcriture(erreurs._ConnexionEnPanne):
    """Commit / rollback en panne seulement une fois des écritures émises sur
    la connexion : le commit qui suit les écritures (et non la validation
    préalable de lecture faite avant toute écriture sous MySQL)."""

    def __init__(self, connexion, pannes, requetes):
        erreurs._ConnexionEnPanne.__init__(self, connexion, pannes)
        self._requetes = requetes

    def _ecritures(self):
        return any(re.match(r"\s*(INSERT|UPDATE|DELETE)\b", r, re.I) for r in self._requetes)

    def commit(self):
        if "commit" in self._pannes and self._ecritures():
            raise erreurs.sqlite3.OperationalError("panne injectée au commit")
        return self._connexion.commit()

    def rollback(self):
        if "rollback" in self._pannes and self._ecritures():
            raise erreurs.sqlite3.OperationalError("panne injectée au rollback")
        return self._connexion.rollback()


@unittest.skipUnless(os.environ.get("NOETHYS_TEST_MYSQL_HOST"), "MySQL local jetable non configure")
class TypeCotisationMySQLTests(unittest.TestCase):
    _nom = concurrence.ConcurrenceMySQLTests._nom

    def setUp(self):
        concurrence.ConcurrenceMySQLTests.setUp(self)
        self.addCleanup(concurrence.ConcurrenceMySQLTests.tearDown, self)
        self.executer(
            # Un autre type réel (ID 2) et son paramétrage : jamais modifiés.
            "INSERT INTO types_cotisations (IDtype_cotisation, nom, type, carte, defaut) "
            "VALUES (2, 'Autre type', 'individu', 0, 0);",
            "INSERT INTO parametres (categorie, nom, parametre) VALUES ('%s', 'type_1', 'inscriptions');" % CAT,
            "INSERT INTO parametres (categorie, nom, parametre) VALUES ('%s', 'type_2', 'participations');" % CAT,
            "INSERT INTO parametres (categorie, nom, parametre) VALUES ('autre_categorie', 'type_1', 'x');",
        )
        self.redirection = RedirectionGestionDB(self._nom(self.base))
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.panne = None
        self.pannes_connexion = set()
        self.messages = []
        classe = GestionDB.DB
        test = self

        def instrumentee(*args, **kwargs):
            db = classe(*args, **kwargs)
            requetes = []
            db.cursor = erreurs._CurseurEnPanne(db.cursor, test.panne, requetes)
            db.connexion = _ConnexionEnPanneApresEcriture(db.connexion, test.pannes_connexion, requetes)
            return db
        for cible, nom, valeur in ((GestionDB, "DB", mock.Mock(side_effect=instrumentee)),
                                   (wx, "MessageDialog", mock.Mock(side_effect=self._message)),
                                   (wx, "CallAfter", mock.Mock())):
            p = mock.patch.object(cible, nom, valeur)
            p.start()
            self.addCleanup(p.stop)

    def _message(self, parent, texte, *args, **kwargs):
        self.messages.append(texte)
        return mock.Mock()

    def connexion(self):
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)
        self.assertEqual(db.echec, 0, getattr(db, "erreur", ""))
        return db

    def executer(self, *requetes):
        db = self.connexion()
        try:
            for req in requetes:
                db.cursor.execute(req)
            db.Commit()
        finally:
            db.Close()

    def lignes(self, req):
        db = self.connexion()
        try:
            db.cursor.execute(req)
            return [tuple(ligne) for ligne in db.cursor.fetchall()]
        finally:
            db.Close()

    def etat(self):
        return tuple(self.lignes(req) for req in (
            "SELECT * FROM types_cotisations ORDER BY IDtype_cotisation",
            "SELECT * FROM unites_cotisations ORDER BY IDunite_cotisation",
            "SELECT * FROM parametres ORDER BY IDparametre",
            "SELECT * FROM cotisations ORDER BY IDcotisation",
            "SELECT * FROM prestations ORDER BY IDprestation",
        ))

    def modes(self, nom):
        return [r[0] for r in self.lignes("SELECT parametre FROM parametres WHERE categorie='%s' AND nom='%s' "
                                          "ORDER BY IDparametre" % (CAT, nom))]

    def ouvrir(self):
        h = erreurs.hote(1)
        h.Importation()
        return h

    def ok(self, h):
        h.EndModal.reset_mock()
        h.OnBoutonOk(None)
        return h.EndModal.called

    def modifier_tout(self, h):
        h.ctrl_nom.SetValue(u"Nom modifié")
        unites = h.ctrl_unites.GetListeDonnees()
        unites[0].update(montant=9.5, etat="MODIF")
        unites.append(erreurs.unite(u"Semestrielle"))
        h.ctrl_mode_adhesion.SetSelection(1)

    def test_sauvegarde_complete(self):
        h = self.ouvrir()
        self.modifier_tout(h)
        self.assertTrue(self.ok(h))
        self.assertEqual(self.lignes("SELECT IDtype_cotisation, nom FROM types_cotisations ORDER BY IDtype_cotisation"),
                         [(1, u"Nom modifié"), (2, u"Autre type")])
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM unites_cotisations")[0][0], 2)
        self.assertEqual(self.modes("type_1"), ["participations"])
        self.assertEqual(self.modes("type_2"), ["participations"])
        self.assertEqual(self.lignes("SELECT parametre FROM parametres WHERE categorie='autre_categorie'"), [("x",)])

    def test_creation_avec_participations(self):
        h = erreurs.hote()
        h.ctrl_mode_adhesion.SetSelection(1)
        h.ctrl_unites.SetListeDonnees([erreurs.unite(u"Annuelle")])
        self.assertTrue(self.ok(h))
        self.assertEqual(self.modes("type_%d" % h.IDtype_cotisation), ["participations"])

    def test_panne_a_chaque_etape_rollback_exact(self):
        etapes = (r"UPDATE\s+types_cotisations", r"UPDATE\s+unites_cotisations", r"INSERT\s+INTO\s+unites_cotisations",
                  r"UPDATE\s+parametres")
        for motif in etapes:
            with self.subTest(etape=motif):
                h = self.ouvrir()
                self.modifier_tout(h)
                avant = self.etat()
                self.panne = motif
                self.messages[:] = []
                self.assertFalse(self.ok(h))
                self.panne = None
                self.assertEqual(self.etat(), avant)
                self.assertIn(u"Rien n'a été modifié", self.messages[-1])
                self.assertEqual([u["etat"] for u in h.ctrl_unites.GetListeDonnees()], ["MODIF", "MODIF"])

    def test_panne_a_la_creation_et_au_mode(self):
        for motif in (r"INSERT\s+INTO\s+types_cotisations", r"INSERT\s+INTO\s+parametres"):
            with self.subTest(etape=motif):
                h = erreurs.hote()
                h.ctrl_mode_adhesion.SetSelection(1)
                h.ctrl_unites.SetListeDonnees([erreurs.unite(u"Annuelle")])
                avant = self.etat()
                self.panne = motif
                self.assertFalse(self.ok(h))
                self.panne = None
                self.assertEqual(self.etat(), avant)
                self.assertIsNone(h.IDtype_cotisation)

    def test_echec_du_commit_issue_incertaine(self):
        h = self.ouvrir()
        self.modifier_tout(h)
        avant = self.etat()
        self.pannes_connexion.add("commit")
        self.assertFalse(self.ok(h))
        self.pannes_connexion.clear()
        self.assertIn(u"indéterminée", self.messages[-1])
        self.assertNotIn(u"Rien n'a été modifié", self.messages[-1])
        self.assertEqual(self.etat(), avant)  # commit non effectué : transaction abandonnée à la fermeture
        self.assertTrue(h.issue_incertaine)
        self.assertFalse(self.ok(h))

    def test_reparation_d_un_mode_en_double_et_panne_pendant_la_reparation(self):
        self.executer("INSERT INTO parametres (categorie, nom, parametre) VALUES ('%s', 'type_1', 'participations');" % CAT)
        h = self.ouvrir()
        self.assertIsNotNone(h.mode_association_invalide)
        h.ctrl_mode_adhesion.SetSelection(1)
        avant = self.etat()
        self.panne = r"DELETE\s+FROM\s+parametres"
        self.assertFalse(self.ok(h))
        self.panne = None
        self.assertEqual(self.etat(), avant)
        with self.assertRaises(A.ConfigurationAdhesionInvalide):
            A.LireModeAssociation(1)  # toujours bloquant : aucun mode arbitraire retenu
        premier = self.lignes("SELECT MIN(IDparametre) FROM parametres WHERE categorie='%s' AND nom='type_1'" % CAT)
        self.assertTrue(self.ok(h))
        self.assertEqual(self.lignes("SELECT IDparametre, parametre FROM parametres WHERE categorie='%s' AND nom='type_1'"
                                     % CAT), [(premier[0][0], "participations")])
        self.assertEqual(self.modes("type_2"), ["participations"])

    def test_deux_fenetres_concurrentes_aucune_modification_perdue(self):
        premiere, seconde = self.ouvrir(), self.ouvrir()
        premiere.ctrl_nom.SetValue(u"Premier poste")
        premiere.ctrl_mode_adhesion.SetSelection(1)
        self.assertTrue(self.ok(premiere))
        seconde.ctrl_nom.SetValue(u"Second poste")
        avant = self.etat()
        self.assertFalse(self.ok(seconde))
        self.assertEqual(self.etat(), avant)
        self.assertIn(u"modifié ailleurs", self.messages[-1])
        self.assertEqual(self.lignes("SELECT COUNT(*) FROM unites_cotisations")[0][0], 1)

    def test_verrou_tenu_par_une_autre_connexion(self):
        autre = self.connexion()
        self.addCleanup(autre.Close)
        autre.cursor.execute("SELECT GET_LOCK(CONCAT('noethys_type_cotisation_', LEFT(MD5(DATABASE()), 12), '_1'), 0);")
        self.assertEqual(autre.cursor.fetchall()[0][0], 1)
        h = self.ouvrir()
        h.ctrl_nom.SetValue(u"Bloqué")
        avant = self.etat()
        with mock.patch.object(A, "DELAI_VERROU", 1):
            self.assertFalse(self.ok(h))
        self.assertEqual(self.etat(), avant)
        self.assertIn(u"autre poste", self.messages[-1])

    def test_deux_enregistrements_simultanes_serialises(self):
        # Deux créations simultanées : deux types distincts, chacun complet.
        resultats = []

        def creer(nom):
            h = erreurs.hote()
            h.ctrl_nom.SetValue(nom)
            h.ctrl_unites.SetListeDonnees([erreurs.unite(nom)])
            resultats.append(self.ok(h))
        fils = [threading.Thread(target=creer, args=(u"Poste %d" % i,)) for i in (1, 2)]
        for f in fils:
            f.start()
        for f in fils:
            f.join(30)
        self.assertEqual(resultats, [True, True])
        types = self.lignes("SELECT IDtype_cotisation FROM types_cotisations WHERE nom LIKE 'Poste %'")
        self.assertEqual(len(types), 2)
        for (ID,) in types:
            self.assertEqual(self.lignes("SELECT COUNT(*) FROM unites_cotisations WHERE IDtype_cotisation=%d" % ID)[0][0], 1)
            self.assertEqual(self.modes("type_%d" % ID), ["inscriptions"])

    def test_table_myisam_refusee_avant_toute_ecriture(self):
        self.executer("ALTER TABLE unites_cotisations ENGINE=MyISAM;")
        h = self.ouvrir()
        self.modifier_tout(h)
        avant = self.etat()
        self.assertFalse(self.ok(h))
        self.assertEqual(self.etat(), avant)
        self.assertIn(u"unites_cotisations (myisam)", self.messages[-1])
        moteur = self.lignes("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() "
                             "AND TABLE_NAME='unites_cotisations'")
        self.assertEqual(moteur[0][0].lower(), "myisam")  # aucune conversion automatique


class SelectionParLeWorkflowTests(unittest.TestCase):
    """Un workflow MySQL vert ne qualifie ce parcours que s'il exécute ces tests."""

    def test_workflow_mysql_execute_ces_tests(self):
        texte = (Path(__file__).resolve().parents[1] / ".github" / "workflows" /
                 "noethys-sl-rc9-qualification.yml").read_text(encoding="utf-8")
        commande = next(l for l in texte.splitlines() if "python -m unittest" in l)
        self.assertIn("tests.test_noethys_sl_type_cotisation_mysql", commande.split())
        self.assertIn("NOETHYS_TEST_MYSQL_EXIGER: '1'", texte)
        self.assertIn("- 'tests/test_noethys_sl_type_cotisation_mysql.py'", texte)


if __name__ == "__main__":
    unittest.main()
