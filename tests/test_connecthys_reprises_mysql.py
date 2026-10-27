# -*- coding: utf-8 -*-
"""Recette MySQL 5.7 isolée : suivi local des confirmations Connecthys.

Serveur MySQL local jetable déclaré par NOETHYS_TEST_MYSQL_* (workflow
noethys-sl-rc9-qualification) ; base zz_test_adh_* créée puis supprimée.
Transporteur factice : aucun email, adresses fictives.
"""
import os
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _garde_reseau  # noqa: F401
from _fixtures_noethys_db import RedirectionGestionDB
import test_noethys_sl_adhesions_concurrence as concurrence
import test_connecthys_reprises as reprises
import GestionDB
from Data import DATA_Tables as Tables
from Utils import UTILS_Emails_acceptes as Suivis

A, B = reprises.A, reprises.B
CLE = reprises.CLE


@unittest.skipUnless(os.environ.get("NOETHYS_TEST_MYSQL_HOST"), "MySQL local jetable non configure")
class SuiviConnecthysMySQLTests(unittest.TestCase):
    _nom = concurrence.ConcurrenceMySQLTests._nom

    def setUp(self):
        concurrence.ConcurrenceMySQLTests.setUp(self)
        self.addCleanup(concurrence.ConcurrenceMySQLTests.tearDown, self)
        db = self.connexion()
        try:
            db.CreationTable("portail_actions", dicoDB=Tables.DB_DATA)
            for req in ("INSERT INTO portail_actions (IDaction, IDfamille, etat) VALUES (7, 1, 'attente');",
                        "INSERT INTO parametres (categorie, nom, parametre) VALUES ('portail', 'type_1', 'x');"):
                db.cursor.execute(req)
            db.Commit()
        finally:
            db.Close()
        self.redirection = RedirectionGestionDB(self._nom(self.base))
        self.redirection.__enter__()
        self.addCleanup(self.redirection.__exit__)
        self.panne = None
        classe = GestionDB.DB
        test = self

        def instrumentee(*args, **kwargs):
            db = classe(*args, **kwargs)
            db.cursor = reprises._CurseurEnPanne(db.cursor, test)
            return db
        p = mock.patch.object(GestionDB, "DB", side_effect=instrumentee)
        p.start()
        self.addCleanup(p.stop)

    def connexion(self):
        db = GestionDB.DB(nomFichier=self._nom(self.base), suffixe=None)
        self.assertEqual(db.echec, 0, getattr(db, "erreur", ""))
        return db

    def lignes(self, req):
        db = self.connexion()
        try:
            db.cursor.execute(req)
            return [tuple(l) for l in db.cursor.fetchall()]
        finally:
            db.Close()

    def suivi_brut(self, cle=CLE):
        return self.lignes("SELECT parametre FROM parametres WHERE categorie='%s' AND nom='%s'" % (Suivis.CATEGORIE, cle))

    def test_435_marqueur_durable_mysql_cycle_sans_rejeu(self):
        """Un même IDaction ne peut pas créer deux tentatives durables."""
        from Utils import UTILS_Portail_reconciliation as Marqueurs
        self.assertFalse(Marqueurs.EnAttente(7))
        jeton = Marqueurs.Commencer(7)
        self.assertRegex(jeton, r"^[0-9a-f]{32}$")
        self.assertTrue(Marqueurs.EnAttente(7))
        self.assertEqual(Marqueurs.LireReprise(7), (jeton, "attente"))
        with self.assertRaises(Marqueurs.ReconciliationRequise):
            Marqueurs.Commencer(7)
        self.assertEqual(self.lignes("SELECT etat FROM portail_actions WHERE IDaction=7"),
                         [("attente",)])
        Marqueurs.Terminer(7, jeton)
        self.assertFalse(Marqueurs.EnAttente(7))

    def test_435_verrou_mysql_tenu_par_un_second_poste(self):
        """Le verrou de début de tentative s'applique à deux connexions."""
        from Utils import UTILS_Portail_reconciliation as Marqueurs
        autre = self.connexion()
        self.addCleanup(autre.Close)
        expression = "CONCAT('noethys_resa_', LEFT(MD5(DATABASE()), 12), '_7')"
        autre.cursor.execute("SELECT GET_LOCK(%s, 0)" % expression)
        self.assertEqual(autre.cursor.fetchall()[0][0], 1)
        try:
            with self.assertRaises(Marqueurs.ReconciliationRequise):
                Marqueurs.Commencer(7)
            self.assertFalse(Marqueurs.EnAttente(7))
        finally:
            autre.cursor.execute("SELECT RELEASE_LOCK(%s)" % expression)
            self.assertEqual(autre.cursor.fetchall()[0][0], 1)
        jeton = Marqueurs.Commencer(7)
        self.assertEqual(Marqueurs.LireReprise(7), (jeton, "attente"))
        Marqueurs.Terminer(7, jeton)

    def test_435_mauvais_jeton_ne_supprime_pas_le_marqueur_mysql(self):
        from Utils import UTILS_Portail_reconciliation as Marqueurs
        jeton = Marqueurs.Commencer(7)
        autre_jeton = "0" * 32 if jeton != "0" * 32 else "f" * 32
        with self.assertRaises(Marqueurs.ReconciliationRequise):
            Marqueurs.Terminer(7, autre_jeton)
        self.assertEqual(Marqueurs.LireReprise(7), (jeton, "attente"))
        Marqueurs.Terminer(7, jeton)
        self.assertFalse(Marqueurs.EnAttente(7))

    def test_435_reprise_apres_validation_sql_sans_modifier_les_conso(self):
        from Utils import UTILS_Portail_reconciliation as Marqueurs
        jeton = Marqueurs.Commencer(7)
        db = self.connexion()
        try:
            db.cursor.execute("UPDATE portail_actions SET etat='validation' WHERE IDaction=7")
            db.Commit()
        finally:
            db.Close()
        self.assertEqual(Marqueurs.LireReprise(7), (jeton, "validation"))
        Marqueurs.Terminer(7, jeton)
        self.assertFalse(Marqueurs.EnAttente(7))
        self.assertEqual(self.lignes("SELECT etat FROM portail_actions WHERE IDaction=7"),
                         [("validation",)])

    def test_tables_transactionnelles(self):
        moteurs = dict((n.lower(), m.lower()) for n, m in self.lignes(
            "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() "
            "AND TABLE_NAME IN ('parametres', 'portail_actions')"))
        self.assertEqual(moteurs, {"parametres": "innodb", "portail_actions": "innodb"})

    def test_enregistrer_panne_apres_suppression_conserve_le_suivi(self):
        Suivis.Enregistrer(CLE, [A])
        avant = self.suivi_brut()
        self.panne = r"INSERT\s+INTO\s+parametres"
        with self.assertRaises(Exception):
            Suivis.Enregistrer(CLE, [A, B])
        self.panne = None
        self.assertEqual(self.suivi_brut(), avant)
        self.assertEqual(Suivis.Lire(CLE), {A})

    def test_reservation_entre_deux_connexions(self):
        # Un autre poste tient le verrou nommé de cette confirmation.
        autre = self.connexion()
        self.addCleanup(autre.Close)
        autre.cursor.execute("SELECT GET_LOCK(CONCAT('noethys_suivi_email_', LEFT(MD5(DATABASE()), 12), '_%s'), 0);"
                             % CLE)
        self.assertEqual(autre.cursor.fetchall()[0][0], 1)
        with self.assertRaises(Suivis.EnvoiEnCours):
            with Suivis.Reserver(CLE):
                pass
        autre.cursor.execute("SELECT RELEASE_LOCK(CONCAT('noethys_suivi_email_', LEFT(MD5(DATABASE()), 12), '_%s'));"
                             % CLE)
        autre.cursor.fetchall()
        # Réservation tenue par ce poste : l'autre connexion ne l'obtient pas.
        with Suivis.Reserver(CLE):
            autre.cursor.execute("SELECT GET_LOCK(CONCAT('noethys_suivi_email_', LEFT(MD5(DATABASE()), 12), '_%s'), 0);"
                                 % CLE)
            self.assertEqual(autre.cursor.fetchall()[0][0], 0)
        with Suivis.Reserver(CLE):  # libérée à la sortie
            pass

    def test_finalisation_atomique_de_la_demande(self):
        Suivis.Enregistrer(CLE, Suivis.Suivi([A, B], [], None, True))
        Suivis.Enregistrer("portail_action_7_recu", Suivis.Suivi([A], [], None, False))
        from Dlg import DLG_Saisie_portail_demande as Demande
        hote = SimpleNamespace(track=SimpleNamespace(IDaction=7, email_date=None))
        self.panne = r"DELETE\s+FROM\s+parametres"
        with mock.patch.object(Demande.wx, "MessageDialog"):
            self.assertFalse(Demande.Dialog.EnregistrerDemande(hote, "validation", u"Réponse", None))
        self.panne = None
        self.assertEqual(self.lignes("SELECT etat FROM portail_actions WHERE IDaction=7"), [("attente",)])
        self.assertTrue(self.suivi_brut())
        self.assertTrue(Demande.Dialog.EnregistrerDemande(hote, "validation", u"Réponse", None))
        self.assertEqual(self.lignes("SELECT etat FROM portail_actions WHERE IDaction=7"), [("validation",)])
        self.assertEqual(self.suivi_brut(), [])
        self.assertEqual(Suivis.Lire("portail_action_7_recu"), {A})
        self.assertEqual(self.lignes("SELECT parametre FROM parametres WHERE categorie='portail'"), [("x",)])

    def test_envoi_partiel_puis_complet_sur_mysql(self):
        from Utils import UTILS_Envoi_email
        import Dlg
        reprises._Transporteur.instances = []
        reprises._Transporteur.pendant_envoi = None
        faux = mock.Mock(Dialog=reprises._Transporteur)
        journal = reprises._Journal()

        def envoyer(acceptees, incertaines=()):
            reprises._Transporteur.scenario = staticmethod(lambda adresses, t: (set(acceptees), set(incertaines)))
            return UTILS_Envoi_email.EnvoiEmailFamille(parent=None, IDfamille=1, nomDoc=False, categorie="portail",
                                                       visible=False, log=journal,
                                                       CreationPDF=lambda nomDoc="", afficherDoc=True: {"{X}": "y"},
                                                       cle_suivi=CLE)
        with mock.patch.dict(sys.modules, {"Dlg.DLG_Mailer": faux}), \
                mock.patch.object(Dlg, "DLG_Mailer", faux, create=True), \
                mock.patch.object(UTILS_Envoi_email, "GetAdresseFamille", return_value=[A, B]):
            self.assertFalse(envoyer({A}))
            self.assertTrue(envoyer({B}))
            self.assertTrue(envoyer({A, B}))  # demande non encore enregistrée : aucun renvoi
        self.assertEqual([a for t in reprises._Transporteur.instances for a in t.adresses], [A, B, B])
        self.assertTrue(Suivis.LireSuivi(CLE).complet)

    def test_deux_traitements_simultanes_un_seul_envoi(self):
        from Utils import UTILS_Envoi_email
        import Dlg
        reprises._Transporteur.instances = []
        faux = mock.Mock(Dialog=reprises._Transporteur)
        resultats = []

        def envoyer():
            reprises._Transporteur.scenario = staticmethod(lambda adresses, t: ({A, B}, set()))
            return UTILS_Envoi_email.EnvoiEmailFamille(parent=None, IDfamille=1, nomDoc=False, categorie="portail",
                                                       visible=False, log=reprises._Journal(),
                                                       CreationPDF=lambda nomDoc="", afficherDoc=True: {"{X}": "y"},
                                                       cle_suivi=CLE)

        def seconde():
            fil = threading.Thread(target=lambda: resultats.append(envoyer()))
            fil.start()
            fil.join(30)
        reprises._Transporteur.pendant_envoi = staticmethod(
            lambda: (setattr(reprises._Transporteur, "pendant_envoi", None), seconde()))
        with mock.patch.dict(sys.modules, {"Dlg.DLG_Mailer": faux}), \
                mock.patch.object(Dlg, "DLG_Mailer", faux, create=True), \
                mock.patch.object(UTILS_Envoi_email, "GetAdresseFamille", return_value=[A, B]):
            self.assertTrue(envoyer())
        self.assertEqual(resultats, [False])
        self.assertEqual(len(reprises._Transporteur.instances), 1)


class SelectionParLeWorkflowTests(unittest.TestCase):
    def test_workflow_mysql_execute_ces_tests(self):
        texte = (Path(__file__).resolve().parents[1] / ".github" / "workflows" /
                 "noethys-sl-rc9-qualification.yml").read_text(encoding="utf-8")
        commande = next(l for l in texte.splitlines() if "python -m unittest" in l)
        self.assertIn("tests.test_connecthys_reprises_mysql", commande.split())


if __name__ == "__main__":
    unittest.main()
