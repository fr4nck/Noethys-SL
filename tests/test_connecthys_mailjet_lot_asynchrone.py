# -*- coding: utf-8 -*-
"""P0 Connecthys: un clic pour deux adresses Mailjet, sans réseau réel.

La logique du lot est testée par doubles sans initialiser de dialogue wx.
"""
from __future__ import annotations
import ast
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Dlg" / "DLG_Mailer.py"


class MailjetLotSourceContract(unittest.TestCase):
    def setUp(self):
        arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
        dlg = next(x for x in arbre.body if isinstance(x, ast.ClassDef) and x.name == "Dialog")
        self.methode = {x.name: x for x in dlg.body if isinstance(x, ast.FunctionDef)}
        self.source = SOURCE.read_text(encoding="utf-8")

    def test_un_clic_deux_adresses_emprunte_chemin_hors_ui(self):
        env = ast.get_source_segment(self.source, self.methode["Envoyer"])
        # Mailer caché (confirmations Connecthys) : envoi hors UI, message par message.
        self.assertIn("if not self.IsShownOnScreen():", env)
        self.assertIn('if dictExp["moteur"] == "mailjet":', env)
        self.assertIn("self._EnvoyerLotSmtpHorsUI", env)
        self.assertIn("self._EnvoyerLotMailjetHorsUI(dictExp, liste_messages, parent_progress)", env)

    def test_editeur_visible_mailjet_multiple_utilise_le_worker(self):
        env = ast.get_source_segment(self.source, self.methode["Envoyer"])
        self.assertIn('self.IsShownOnScreen() and dictExp["moteur"] == "mailjet"', env)
        self.assertIn("len(liste_messages) > 1", env)
        self.assertIn("options_lot=True", env)
        self.assertLess(env.index("options_lot=True"), env.index("messagerie.Envoyer_lot("))
        self.assertIn("callback_succes=MemoriserSucces", env)
        self.assertIn("self._envoi_en_cours = True", env)

    def test_envoi_complet_pour_tous_les_moteurs_hors_message_de_test(self):
        init = ast.get_source_segment(self.source, self.methode["__init__"])
        env = ast.get_source_segment(self.source, self.methode["Envoyer"])
        self.assertIn("self.envoi_complet = False", init)
        self.assertLess(env.index("self.envoi_complet = False"), env.index("dictExp = self.ctrl_exp.GetDonnees()"))
        # Trois routes de lot hors UI : masque, SMTP visible et Mailjet visible.
        # Ne pas lier le contrat au seul nombre de branches textuelles :
        # chaque route doit explicitement affecter envoi_complet.
        self.assertGreaterEqual(env.count("self.envoi_complet = adresseTest is None and complet"), 3)
        self.assertIn("self.envoi_complet = adresseTest is None and bool(self.listeSucces)", env)
        self.assertIn("len(self.listeSucces or []) == len(liste_messages)", env)

    def test_worker_deporte_connexion_et_envoi(self):
        meth = ast.get_source_segment(self.source, self.methode["_ExecuterEnvoiUniqueHorsUI"])
        self.assertIn("threading.Thread(target=_worker", meth)
        self.assertIn("messagerie.Connecter()", meth)
        self.assertIn("messagerie.Envoyer(message)", meth)
        self.assertIn("wx.CallAfter(dlg_attente.Terminer)", meth)

    def test_historique_separe_du_worker(self):
        worker = ast.get_source_segment(self.source, self.methode["_ExecuterEnvoiUniqueHorsUI"])
        lot = ast.get_source_segment(self.source, self.methode["_EnvoyerLotMailjetHorsUI"])
        self.assertNotIn("MemorisationHistorique", worker)
        self.assertIn("self.MemorisationHistorique(", lot)
        self.assertIn("self.listeSucces.append(message)", lot)
        self.assertIn("relancer_deconnexion=False", lot)
        self.assertIn("ne_pas_signaler_erreurs = False", lot)
        self.assertIn("self.envoi_complet = len(self.listeSucces) == total", lot)


try:
    import sys
    sys.path.insert(0, str(ROOT / "noethys"))
    import wx  # noqa: E402
    from Dlg import DLG_Mailer  # noqa: E402
    from Utils import UTILS_Envoi_email  # noqa: E402
except (ImportError, RuntimeError):
    wx = None


@unittest.skipIf(wx is None, "wxPython indisponible")
class MailjetLotComportement(unittest.TestCase):
    class Message:
        sujet = "Réservation"
        def __init__(self, adresse):
            self.adresse = adresse
        def GetLabelDestinataires(self):
            return self.adresse

    class Messagerie:
        LIBELLE_SERVICE = "Mailjet"
        def __init__(self, **kw):
            self.kw = kw

    class Dialogue:
        choix = []
        vues = []
        def __init__(self, *a, **kw):
            self.__class__.vues.append(kw)
        def ShowModal(self):
            return self.__class__.choix.pop(0)
        def Destroy(self):
            pass

    def setUp(self):
        self.messages = [self.Message("a@example.test"), self.Message("b@example.test")]
        self.config = dict(moteur="mailjet", smtp="", port=0, utilisateur="",
                           motdepasse="", adresse="from@example.test",
                           nom_adresse="Test", startTLS=False, parametres="")
        self.faux = mock.Mock()
        self.faux.listeSucces = []
        self.faux.listeAnomalies = []
        self.faux._ExecuterEnvoiUniqueHorsUI.side_effect = []
        self.__class__.Dialogue.vues = []
        self.__class__.Dialogue.choix = []

    def lancer(self, scenarios, options_lot=False):
        ui = threading.get_ident()
        appels = []
        def envoyer(messagerie, message, parent, index=1, total=1,
                    pause_avant=0, relancer_deconnexion=True):
            appels.append((message.adresse, index, total, pause_avant,
                           threading.get_ident(), relancer_deconnexion))
            return scenarios.pop(0)
        self.faux._ExecuterEnvoiUniqueHorsUI.side_effect = envoyer
        with mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie",
                               return_value=self.Messagerie()), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu") as bilan, \
             mock.patch.object(DLG_Mailer.DLG_Messagebox, "Dialog", self.Dialogue):
            resultat = DLG_Mailer.Dialog._EnvoyerLotMailjetHorsUI(
                self.faux, self.config, self.messages, None,
                options_lot=options_lot)
        return resultat, appels, bilan.call_args, ui

    def test_deux_acceptations_enregistrees_individuellement(self):
        ok = dict(succes=True, erreur=None, phase="envoi")
        resultat, appels, bilan, ui = self.lancer([ok.copy(), ok.copy()])
        self.assertTrue(resultat)
        self.assertEqual([a[0] for a in appels], ["a@example.test", "b@example.test"])
        self.assertEqual([a[1:4] for a in appels], [(1, 2, 0), (2, 2, 1)])
        self.assertEqual(self.faux.MemorisationHistorique.call_count, 2)
        self.assertEqual(len(bilan.args[2]), 2)
        self.assertTrue(all(a[-2] == ui for a in appels))
        self.assertTrue(all(a[-1] is False for a in appels))

    def test_deuxieme_timeout_pas_de_relance_automatique(self):
        ok = dict(succes=True, erreur=None, phase="envoi")
        timeout = dict(succes=False, erreur=TimeoutError("API timeout"), phase="envoi")
        self.Dialogue.choix = [0]  # seul bouton Terminer, PAS Réessayer
        resultat, appels, bilan, _ = self.lancer([ok, timeout])
        self.assertFalse(resultat)
        self.assertEqual(len(appels), 2)
        self.assertEqual(self.faux.MemorisationHistorique.call_count, 1)
        self.assertEqual(len(bilan.args[2]), 1)
        self.assertEqual(len(bilan.args[3]), 1)
        self.assertEqual(self.Dialogue.vues[0]["boutons"], ["Terminer"])

    def test_refus_explicite_second_message_retry_seul_second(self):
        ok = dict(succes=True, erreur=None, phase="envoi")
        refus = dict(succes=False,
                     erreur=UTILS_Envoi_email.ErreurMailjet("Mailjet a refusé le message (HTTP 400)"),
                     phase="envoi")
        self.Dialogue.choix = [0]  # Réessayer seulement le second
        resultat, appels, bilan, _ = self.lancer([ok.copy(), refus, ok.copy()])
        self.assertTrue(resultat)
        self.assertEqual([a[0] for a in appels],
                         ["a@example.test", "b@example.test", "b@example.test"])
        self.assertEqual(self.faux.MemorisationHistorique.call_count, 2)
        self.assertEqual(len(bilan.args[3]), 0)


    def test_lot_visible_option_silence_ne_relance_ni_ne_masque_le_bilan(self):
        self.messages.append(self.Message("c@example.test"))
        timeout = dict(succes=False, erreur=TimeoutError("HTTP incertain fictif"), phase="envoi")
        refus = dict(succes=False,
                     erreur=UTILS_Envoi_email.ErreurMailjet("Mailjet a refusé le message (HTTP 400)"),
                     phase="envoi")
        ok = dict(succes=True, erreur=None, phase="envoi")
        self.Dialogue.choix = [1]  # Continuer et ne plus signaler : 1er echec incertain.
        resultat, appels, bilan, _ = self.lancer([timeout, refus, ok],
                                                options_lot=True)
        self.assertFalse(resultat)
        self.assertEqual([a[0] for a in appels],
                         ["a@example.test", "b@example.test", "c@example.test"])
        self.assertEqual(len(self.Dialogue.vues), 1)
        self.assertIn("Continuer et ne plus signaler les erreurs",
                      self.Dialogue.vues[0]["boutons"])
        self.assertEqual(self.faux.listeIncertains, [self.messages[0]])
        self.assertEqual(len(bilan.args[2]), 1)
        self.assertEqual(len(bilan.args[3]), 2)
        self.assertEqual(bilan.args[4], [])
        self.assertEqual(self.faux.MemorisationHistorique.call_count, 1)

    def test_lot_cache_ne_propose_pas_choix_silence_nouveau(self):
        erreur = dict(succes=False, erreur=ConnectionError("avant connexion"),
                      phase="connexion")
        ok = dict(succes=True, erreur=None, phase="envoi")
        self.Dialogue.choix = [1]  # Continuer : choix masque historique.
        resultat, appels, bilan, _ = self.lancer([erreur, ok])
        self.assertFalse(resultat)
        self.assertEqual([x[0] for x in appels], ["a@example.test", "b@example.test"])
        self.assertEqual(self.Dialogue.vues[0]["boutons"],
                         ["Réessayer", "Continuer", "Arrêter"])

    def test_lot_visible_arreter_conserve_les_non_tentes(self):
        self.messages.append(self.Message("c@example.test"))
        erreur = dict(succes=False, erreur=RuntimeError("erreur API inconnue"),
                      phase="envoi")
        self.Dialogue.choix = [2]  # Arrêter si resultat incertain et mode visible.
        resultat, appels, bilan, _ = self.lancer([erreur], options_lot=True)
        self.assertFalse(resultat)
        self.assertEqual([x[0] for x in appels], ["a@example.test"])
        self.assertEqual(bilan.args[4], self.messages[1:])
        self.assertEqual(self.faux.listeIncertains, [self.messages[0]])
        self.assertNotIn("Réessayer", self.Dialogue.vues[0]["boutons"])

    def test_exception_de_worker_mailjet_reste_incertaine_sans_renvoi(self):
        self.faux._ExecuterEnvoiUniqueHorsUI.side_effect = RuntimeError(
            "interruption apres DATA fictive"
        )
        self.messages = self.messages[:1]
        self.Dialogue.choix = [0]  # Terminer, sans option reessayer.
        with mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie",
                               return_value=self.Messagerie()), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu"):
            with mock.patch.object(DLG_Mailer.DLG_Messagebox, "Dialog", self.Dialogue):
                resultat = DLG_Mailer.Dialog._EnvoyerLotMailjetHorsUI(
                    self.faux, self.config, self.messages, None, options_lot=True,
                )
        self.assertFalse(resultat)
        self.assertEqual(self.faux.listeIncertains, self.messages)
        self.assertEqual(self.Dialogue.vues[0]["boutons"], ["Terminer"])
        self.faux.MemorisationHistorique.assert_not_called()

    def test_lot_visible_refus_certain_reessaye_uniquement_la_meme_adresse(self):
        refus = dict(succes=False,
                     erreur=UTILS_Envoi_email.ErreurMailjet("Mailjet a refusé le message (HTTP 400)"),
                     phase="envoi")
        ok = dict(succes=True, erreur=None, phase="envoi")
        self.Dialogue.choix = [0]
        resultat, appels, bilan, _ = self.lancer([refus, ok.copy(), ok.copy()],
                                                options_lot=True)
        self.assertTrue(resultat)
        self.assertEqual([x[0] for x in appels],
                         ["a@example.test", "a@example.test", "b@example.test"])
        self.assertEqual(self.faux.MemorisationHistorique.call_count, 2)
        self.assertEqual(bilan.args[3], [])
        self.assertIn("Continuer et ne plus signaler les erreurs",
                      self.Dialogue.vues[0]["boutons"])

    def test_historique_inaccessible_ne_declenche_aucun_renvoi(self):
        ok = dict(succes=True, erreur=None, phase="envoi")
        self.faux.MemorisationHistorique.side_effect = OSError("base inaccessible")
        with mock.patch.object(DLG_Mailer.wx, "MessageDialog") as alerte:
            resultat, appels, _, _ = self.lancer([ok.copy(), ok.copy()])
        self.assertTrue(resultat)
        self.assertEqual(len(appels), 2)
        alerte.assert_called_once()


if __name__ == "__main__":
    unittest.main()
