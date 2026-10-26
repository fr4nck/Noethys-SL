# -*- coding: utf-8 -*-
"""CE-4/CE-5 : vrai parcours metier, SQLite jetable et grille Quantite fictive."""
import datetime
import concurrent.futures
import subprocess
import sys
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from tests import test_connecthys_ui3c_sauvegarde as precedent

Module = precedent.Module
if Module is not None:
    try:
        from Utils import UTILS_Portail_reconciliation as Marqueurs
    except ImportError:
        Marqueurs = None  # les quatre contre-epreuves tournent aussi sur le HEAD anterieur
DAY = datetime.date(2026, 11, 4)


class GrilleQuantite:
    def __init__(self, fixture):
        self.fixture = fixture
        self.quantites = {101: 0, 102: 0}
        self.saves = 0
        self.saisies = 0
        self.partielle = False
        self.panne_save = None
        self.usage = "portail"
        self.ctrl_titre = NS(GetNom=lambda: "Individu fictif")
        self.grille = NS(dictUnites={ID: dict(nom=str(ID), type="Quantite",
                                            heure_debut=None, heure_fin=None)
                                   for ID in self.quantites})

    def InitGrille(self, **kwargs):
        # Recharge l'etat durable, comme une reouverture du vrai ecran.
        self.fixture.base.db.ExecuterReq("SELECT IDunite, quantite FROM consommations")
        self.quantites = {101: 0, 102: 0}
        self.quantites.update(dict(self.fixture.base.db.ResultatReq()))

    def GetCase(self, IDunite, date):
        def clic(**kwargs):
            self.quantites[IDunite] = kwargs["saisieQuantite"]
        return NS(GetListeConso=lambda: [], ouvert=True,
                  quantite=self.quantites[IDunite], HasPlaceDisponible=lambda *a: True,
                  VerifieCompatibilitesUnites=lambda: None,
                  IsCaseDisponible=lambda *a: not self.quantites[IDunite],
                  OnClick=clic, ModifieEtat=lambda *a: None)

    def IsOuvert(self, **kwargs):
        return True

    def HasPlacesDisponibles(self, **kwargs):
        return True

    def SaisieConso(self, IDunite, **kwargs):
        self.saisies += 1
        if self.partielle and IDunite == 102:
            return "Refus fictif de la deuxieme unite"
        # Le calcul Quantite initiale/existante est celui de production.
        return Module.DLG_Badgeage_grille.CTRL.SaisieConso(self, IDunite=IDunite, **kwargs)

    def Sauvegarde(self):
        self.saves += 1
        # Une ecriture reelle sur la base fictive precede la panne injectee.
        db = self.fixture.base.db
        db.ExecuterReq("DELETE FROM consommations")
        for ID, quantite in self.quantites.items():
            if quantite:
                db.ExecuterReq("INSERT INTO consommations (IDunite, quantite) VALUES (%d,%d)"
                               % (ID, quantite))
        db.Commit()
        if self.panne_save == "exception":
            raise RuntimeError("Save_grille apres ecriture fictive")
        if self.panne_save == "false":
            return False


@unittest.skipIf(Module is None, "wxPython requis")
class ReconciliationTests(unittest.TestCase):
    setUp = precedent.SauvegardeEchecTests.setUp
    etat_sql = precedent.SauvegardeEchecTests.etat_sql

    def preparer(self):
        for table in ("portail_reservations", "portail_unites"):
            self.base.db.CreationTable(table, dicoDB=precedent.Tables.DB_DATA)
        self.base.inserer("portail_unites", ["IDunite", "nom"], [(1, "Choix A"), (2, "Choix B")])
        self.base.inserer("portail_reservations",
                          ["IDreservation", "IDaction", "date", "IDinscription", "IDunite", "etat"],
                          [(1, 7, DAY, 77, 1, 1), (2, 7, DAY, 77, 2, 1)])
        self.configurer_ui(self.ui)
        # Toute tentative de transport reel echoue explicitement.
        for cible in ("socket.socket.connect", "socket.create_connection",
                      "Dlg.DLG_Saisie_portail_demande.UTILS_Envoi_email.EnvoiEmailFamille"):
            patch = mock.patch(cible, side_effect=AssertionError("Reseau/email interdit"))
            patch.start()
            self.addCleanup(patch.stop)
        from Dlg import DLG_Messagebox
        patch = mock.patch.object(DLG_Messagebox, "Dialog")
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(Module.Traitement, "Verifier_ventilation")
        self.ventilation = patch.start()
        self.addCleanup(patch.stop)

    def configurer_ui(self, ui):
        ui.track.action = "saisie"
        ui.track.IDindividu = 42
        ui.track.parametres = "IDactivite=1#date_debut_periode=%s#date_fin_periode=%s" % (DAY, DAY)
        ui.track.horodatage = datetime.datetime(2026, 10, 26)
        ui.track.EcritLog = mock.Mock()
        ui.dictUnites = {ID: dict(nom="Choix %d" % ID, IDactivite=1,
                                 unites_principales=[100 + ID], unites_secondaires=[])
                         for ID in (1, 2)}
        ui.dictActivites = {1: dict(portail_reservations_absenti=None)}
        ui.ctrl_grille = GrilleQuantite(self)

    def quantites_sql(self):
        self.base.db.ExecuterReq("SELECT IDunite, quantite FROM consommations ORDER BY IDunite")
        return self.base.db.ResultatReq()

    def relancer_sans_exception(self, mode="automatique"):
        try:
            return self.ui.Traitement(mode=mode)
        except RuntimeError:
            # Le code anterieur propage la panne ; la contre-epreuve doit
            # atteindre l'assertion metier de non-rejeu, pas s'arreter la.
            return False

    def test_ce4_application_partielle_ne_rejoue_pas_quantite(self):
        self.preparer()
        self.ui.ctrl_grille.partielle = True
        self.relancer_sans_exception()
        self.assertEqual(self.quantites_sql(), [(101, 1)])
        self.assertEqual(self.etat_sql()[0], "attente")
        self.relancer_sans_exception()
        self.assertEqual(self.quantites_sql(), [(101, 1)], "CE-4 : quantite doublee apres application partielle")
        self.assertEqual(self.ui.ctrl_grille.saves, 1)

    def test_ce5_exception_post_save_ne_rejoue_pas_quantite(self):
        self.preparer()
        self.ventilation.side_effect = RuntimeError("Exception post-sauvegarde fictive")
        self.relancer_sans_exception()
        self.assertEqual(self.quantites_sql(), [(101, 1), (102, 1)])
        self.relancer_sans_exception()
        self.assertEqual(self.quantites_sql(), [(101, 1), (102, 1)], "CE-5 : quantites doublees apres Save_grille")
        self.assertEqual(self.ui.ctrl_grille.saves, 1)

    def test_save_grille_false_ne_valide_pas_la_demande(self):
        self.preparer()
        self.ui.ctrl_grille.panne_save = "false"
        self.relancer_sans_exception()
        self.assertEqual(self.etat_sql()[0], "attente", "Un refus Save_grille ne doit pas valider")
        self.relancer_sans_exception()
        self.assertEqual(self.ui.ctrl_grille.saves, 1)

    def test_save_grille_exception_ne_rejoue_pas(self):
        self.preparer()
        self.ui.ctrl_grille.panne_save = "exception"
        self.relancer_sans_exception()
        self.relancer_sans_exception()
        self.assertEqual(self.ui.ctrl_grille.saves, 1)
        self.assertEqual(self.quantites_sql(), [(101, 1), (102, 1)])

    def test_reouverture_bloque_modes_validation_et_emails_apres_ce4_et_ce5(self):
        self.preparer()
        self.ui.ctrl_grille.partielle = True
        self.relancer_sans_exception()
        self.assertTrue(Marqueurs.EnAttente(7))
        ui = precedent.DialogueFictif()
        self.configurer_ui(ui)
        for mode in ("automatique", "manuel"):
            self.assertFalse(ui.Traitement(mode=mode))
        ui.radio_validation.SetValue(True)
        ui.ctrl_reponse.ChangeValue("Ne pas envoyer cette confirmation fictive")
        self.assertFalse(ui.Sauvegarde())
        self.assertFalse(Module.Dialog.Envoyer(ui, visible=False))
        self.assertFalse(Module.Dialog.Envoyer(ui, visible=True))
        self.assertEqual(ui.ctrl_grille.saisies, 0)
        self.assertEqual(ui.ctrl_grille.saves, 0)
        self.assertEqual(self.quantites_sql(), [(101, 1)])
        self.assertEqual(self.etat_sql()[0], "attente")
        self.assertIn("Réconciliation", self.dlg.call_args.args[2])

    def test_marqueur_visible_depuis_un_processus_neuf(self):
        self.preparer()
        self.ui.ctrl_grille.panne_save = "exception"
        self.relancer_sans_exception()
        # Aucun etat Python du dialogue n'est transmis a cet interpreteur.
        script = ("import sys; import _garde_reseau; "
                  "from _fixtures_noethys_db import RedirectionGestionDB; "
                  "from Utils import UTILS_Portail_reconciliation as m; "
                  "ctx=RedirectionGestionDB(sys.argv[1]); ctx.__enter__(); "
                  "assert m.EnAttente(7); "
                  "m.Commencer(7)")
        resultat = subprocess.run([sys.executable, "-c", script, self.base.chemin],
                                  capture_output=True, text=True, timeout=20)
        self.assertNotEqual(resultat.returncode, 0)
        self.assertIn("ReconciliationRequise: Tentative precedente", resultat.stderr)
        self.assertEqual(self.quantites_sql(), [(101, 1), (102, 1)])

    def test_succes_complet_retire_marqueur_apres_commit_et_interdit_track_perime(self):
        self.preparer()
        self.ui.Traitement()
        self.assertEqual(self.etat_sql()[0], "validation")
        self.assertFalse(Marqueurs.EnAttente(7))
        self.assertFalse(self.ui.Traitement())
        perime = precedent.DialogueFictif()
        self.configurer_ui(perime)
        self.assertFalse(perime.Traitement())
        self.assertEqual(perime.ctrl_grille.saves, 0)
        self.assertEqual(self.quantites_sql(), [(101, 1), (102, 1)])

    def test_echec_portail_actions_retente_sql_seul_et_preserve_rc9(self):
        self.preparer()
        complet, partiel = "portail_action_7_reponse", "portail_action_7_recu"
        precedent.Suivis.Enregistrer(complet, precedent.Suivis.Suivi(["a@example.test"], [], None, True))
        precedent.Suivis.Enregistrer(partiel, precedent.Suivis.Suivi(["b@example.test"], ["c@example.test"]))
        self.echec_sql = True
        self.assertFalse(self.ui.Traitement())
        self.assertTrue(Marqueurs.EnAttente(7))
        self.assertTrue(precedent.Suivis.LireSuivi(complet).complet)
        self.assertEqual(precedent.Suivis.LireSuivi(partiel).incertaines, {"c@example.test"})
        self.assertFalse(Module.Dialog.Envoyer(self.ui, visible=False))
        # Une autre fenetre n'a pas le resultat complet fige en memoire :
        # elle exige une reconciliation, jamais un nouvel appel au metier.
        autre = precedent.DialogueFictif()
        self.configurer_ui(autre)
        self.assertFalse(autre.Traitement())
        self.echec_sql = False
        self.assertTrue(self.ui.Traitement(mode="manuel"))
        self.assertEqual(self.ui.ctrl_grille.saves, 1)
        self.assertFalse(Marqueurs.EnAttente(7))
        self.assertEqual(self.etat_sql()[0], "validation")
        self.assertEqual(precedent.Suivis.Lire(complet), set())
        self.assertEqual(precedent.Suivis.Lire(partiel), {"b@example.test"})
        self.assertEqual(precedent.Suivis.LireSuivi(partiel).incertaines, {"c@example.test"})

    def test_nettoyage_marqueur_refuse_apres_commit_ne_rejoue_pas(self):
        self.preparer()
        with mock.patch.object(Marqueurs, "Terminer", side_effect=RuntimeError("Panne nettoyage")):
            self.assertFalse(self.ui.Traitement())
        self.assertEqual(self.etat_sql()[0], "validation")
        self.assertTrue(Marqueurs.EnAttente(7))
        self.assertIsNotNone(self.ui._finalisation_en_attente)
        self.assertTrue(self.ui.Traitement())
        self.assertEqual(self.ui.ctrl_grille.saves, 1)
        self.assertFalse(Marqueurs.EnAttente(7))

    def test_exception_refresh_post_commit_garde_marqueur_et_finalisation(self):
        self.preparer()
        self.ui.track.Refresh.side_effect = RuntimeError("Refresh apres commit")
        self.assertFalse(self.ui.Traitement())
        self.assertTrue(Marqueurs.EnAttente(7))
        self.assertEqual(self.etat_sql()[0], "validation")
        self.ui.track.Refresh.side_effect = None
        self.assertTrue(self.ui.Traitement())
        self.assertEqual(self.ui.ctrl_grille.saves, 1)

    def test_marqueur_illisible_doublon_et_mauvais_jeton_ne_sont_jamais_effaces(self):
        self.preparer()
        self.base.inserer("parametres", ["categorie", "nom", "parametre"],
                          [(Marqueurs.CATEGORIE, "action_7", "corrompu"),
                           (Marqueurs.CATEGORIE, "action_7", "autre")])
        self.assertTrue(Marqueurs.EnAttente(7))
        with self.assertRaises(Marqueurs.ReconciliationRequise):
            Marqueurs.Terminer(7, "corrompu")
        self.assertFalse(self.ui.Traitement())
        self.assertEqual(self.ui.ctrl_grille.saisies, 0)
        self.assertTrue(Marqueurs.EnAttente(7))

    def test_marqueur_commite_avant_premiere_saisie_et_separe_des_emails(self):
        self.preparer()
        original = self.ui.ctrl_grille.SaisieConso
        def saisir(**kwargs):
            self.assertTrue(Marqueurs.EnAttente(7))
            self.assertNotEqual(Marqueurs.CATEGORIE, precedent.Suivis.CATEGORIE)
            return original(**kwargs)
        self.ui.ctrl_grille.SaisieConso = saisir
        self.ui.Traitement()
        self.assertEqual(self.etat_sql()[0], "validation")

    def test_lecture_ou_ecriture_marqueur_impossible_interdit_tout_effet(self):
        self.preparer()
        with mock.patch.object(Marqueurs, "Commencer", side_effect=RuntimeError("SQL indisponible")), \
                mock.patch.object(Marqueurs, "EnAttente", side_effect=RuntimeError("Lecture impossible")):
            self.assertFalse(self.ui.Traitement())
            self.assertFalse(self.ui.Sauvegarde())
            self.assertFalse(Module.Dialog.Envoyer(self.ui))
        self.assertEqual(self.ui.ctrl_grille.saisies, 0)
        self.assertEqual(self.ui.ctrl_grille.saves, 0)

    def test_deux_connexions_sqlite_une_seule_tentative(self):
        self.preparer()
        def commencer():
            try:
                return Marqueurs.Commencer(7)
            except Marqueurs.ReconciliationRequise:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            resultats = list(pool.map(lambda _: commencer(), range(2)))
        self.assertEqual(sum(v is not None for v in resultats), 1)
        self.assertTrue(Marqueurs.EnAttente(7))

    def test_mode_manuel_annulation_et_refus_save(self):
        self.preparer()
        from Dlg import DLG_Portail_reservations
        dlg = mock.Mock(ctrl_grille=self.ui.ctrl_grille)
        dlg.ShowModal.return_value = Module.wx.ID_CANCEL
        dlg.GetReponse.return_value = ""
        with mock.patch.object(DLG_Portail_reservations, "Dialog", return_value=dlg):
            self.assertFalse(self.ui.Traitement(mode="manuel"))
            self.assertFalse(Marqueurs.EnAttente(7))
            dlg.ShowModal.return_value = Module.wx.ID_OK
            dlg.GetReponse.return_value = "Reponse fictive"
            self.ui.ctrl_grille.panne_save = "false"
            self.assertFalse(self.ui.Traitement(mode="manuel"))
        self.assertTrue(Marqueurs.EnAttente(7))
        self.assertEqual(self.etat_sql()[0], "attente")
        self.assertEqual(self.ui.ctrl_grille.saves, 1)
        self.assertEqual(dlg.Destroy.call_count, 2)

    def test_commit_marqueur_accepte_mais_reponse_perdue_ne_lance_pas_le_metier(self):
        self.preparer()
        vraie_db = precedent.GestionDB.DB
        class Connexion:
            def __init__(self, originale):
                self.originale = originale
            def commit(self):
                self.originale.commit()
                raise RuntimeError("Reponse commit perdue apres acceptation fictive")
            def __getattr__(self, nom):
                return getattr(self.originale, nom)
        def ouvrir(*args, **kwargs):
            db = vraie_db(*args, **kwargs)
            db.connexion = Connexion(db.connexion)
            return db
        with mock.patch.object(precedent.GestionDB, "DB", side_effect=ouvrir):
            self.assertFalse(self.ui.Traitement())
        self.assertTrue(Marqueurs.EnAttente(7))
        self.assertFalse(self.ui.Traitement())
        self.assertEqual(self.ui.ctrl_grille.saisies, 0)
        self.assertEqual(self.quantites_sql(), [])

    def test_echec_insert_marqueur_ne_lance_pas_le_metier(self):
        self.preparer()
        executer = Marqueurs._executer
        def refuser_insert(db, sql, valeurs=()):
            if sql.startswith("INSERT INTO parametres"):
                raise RuntimeError("INSERT marqueur refuse")
            return executer(db, sql, valeurs)
        with mock.patch.object(Marqueurs, "_executer", side_effect=refuser_insert):
            self.assertFalse(self.ui.Traitement())
        self.assertFalse(Marqueurs.EnAttente(7))
        self.assertEqual(self.ui.ctrl_grille.saisies, 0)
        self.assertEqual(self.quantites_sql(), [])

    def test_fermeture_apres_incertain_conserve_barriere_et_suivis(self):
        self.preparer()
        precedent.Suivis.Enregistrer("portail_action_7_reponse", ["a@example.test"])
        self.ui.ctrl_grille.partielle = True
        self.relancer_sans_exception()
        event = mock.Mock()
        self.ui.OnClose(event)
        event.Skip.assert_called_once()
        self.assertTrue(Marqueurs.EnAttente(7))
        self.assertEqual(precedent.Suivis.Lire("portail_action_7_reponse"), {"a@example.test"})
        self.assertEqual(self.ui.ctrl_grille.saves, 1)

    def test_contrat_mysql_sans_reseau_verrou_jeton_et_liberation(self):
        self.preparer()
        # Le vrai helper parle a un curseur fictif : aucun serveur n'est lance.
        db = mock.Mock(isNetwork=True, echec=0)
        db.cursor.fetchall.side_effect = [((1,),), (), (("attente",),), ((1,),)]
        with mock.patch.object(precedent.GestionDB, "DB", return_value=db):
            jeton = Marqueurs.Commencer(7)
        self.assertEqual(len(jeton), 32)
        requetes = [call.args[0] for call in db.cursor.execute.call_args_list]
        self.assertIn("GET_LOCK", requetes[0])
        self.assertIn("RELEASE_LOCK", requetes[-1])
        self.assertIn("%s", requetes[1])
        self.assertEqual(db.connexion.commit.call_count, 2)
        db.Close.assert_called_once()
        db = mock.Mock(isNetwork=True, echec=0)
        db.cursor.fetchall.side_effect = [((0,),)]
        with mock.patch.object(precedent.GestionDB, "DB", return_value=db):
            with self.assertRaises(Marqueurs.ReconciliationRequise):
                Marqueurs.Commencer(7)
        self.assertEqual(db.cursor.execute.call_count, 1)
        db.Close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
