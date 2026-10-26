# -*- coding: utf-8 -*-
"""Non-régression : clignotement vidéo Windows lors de l'envoi d'un mail.

Symptôme observé en recette (Windows) : lors de l'envoi d'une réponse mail
depuis une demande Connecthys, la fenêtre Noethys disparaît une fraction de
seconde (bureau ou autre application brièvement visible) juste après la fin
de l'envoi, avant que Noethys ne reprenne le dessus.

Cause initiale : DLG_Mailer.Dialog.Envoyer() construisait sa
wx.ProgressDialog ("Envoi des mails") avec parent=None -- une fenêtre
top-level sans owner Win32, dont la destruction laisse le gestionnaire de
fenêtres choisir seul la prochaine fenêtre active.

Premier correctif (parent=self) insuffisant : vérifié mécaniquement
(GetParent()/IsShownOnScreen()/GW_OWNER natif), dans le chemin
EnvoiEmailFamille(visible=False) le DLG_Mailer.Dialog lui-même n'est
JAMAIS affiché -- seul son parent (la demande Connecthys) est visible à
l'écran. parent=self donnerait alors à la ProgressDialog un owner Win32
immédiat caché, ce qui ne règle pas le problème.

Correctif générique de parentage retenu pour le chemin caché : la
ProgressDialog est parentée à la première fenêtre réellement visible à
l'écran.

Depuis la recette RC2 des commandes de repas, le chemin interactif visible
avec un seul destinataire a en plus un contrat différent : connexion et
envoi réseau s'exécutent hors du thread wx, derrière une petite boîte modale
animée. Le chemin caché Connecthys conserve provisoirement la ProgressDialog
historique.

Ce test construit un DLG_Mailer.Dialog *réel* et vérifie les deux contrats,
sans aucun réseau ni email réel.
"""
from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402

_APP = wx.GetApp() or wx.App(False)

from _fixtures_noethys_db import BaseTest, RedirectionGestionDB  # noqa: E402
from Data import DATA_Tables as Tables  # noqa: E402

from Dlg import DLG_Mailer, DLG_Messagebox  # noqa: E402
from Ol import OL_Destinataires_emails  # noqa: E402


class FausseProgressDialog:
    """Double minimal de wx.ProgressDialog qui mémorise juste son parent."""

    instances = []

    def __init__(self, titre="", message="", maximum=1, parent=None):
        self.parent = parent
        self.detruite = False
        FausseProgressDialog.instances.append(self)

    def SetSize(self, taille):
        pass

    def CenterOnScreen(self):
        pass

    def Update(self, valeur, message=""):
        return True, True

    def Pulse(self, message=""):
        return True, True

    def Destroy(self):
        if self.detruite:
            raise RuntimeError("wrapped C/C++ object has been deleted")
        self.detruite = True


class FausseMessagerie:
    """Double de UTILS_Envoi_email.Messagerie : aucun réseau, aucun email réel."""

    dernier_dlg_progress = None
    thread_connecter = None
    thread_envoyer = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def Connecter(self):
        FausseMessagerie.thread_connecter = threading.get_ident()

    def Envoyer(self, message=None):
        FausseMessagerie.thread_envoyer = threading.get_ident()
        return True

    def Envoyer_lot(self, messages=None, dlg_progress=None, afficher_confirmation_envoi=True):
        # Comportement réel des backends : la dlg_progress est détruite
        # avant de rendre la main, en fin d'envoi réussi.
        FausseMessagerie.dernier_dlg_progress = dlg_progress
        if dlg_progress is not None:
            dlg_progress.Destroy()
        return list(messages or [])

    def Fermer(self):
        pass


class FausseMessagerieMailjet(FausseMessagerie):
    """Double Mailjet : acceptation par l'API puis echec de fermeture."""

    LIBELLE_SERVICE = u"Mailjet"
    nb_envois = 0

    def Envoyer(self, message=None):
        FausseMessagerieMailjet.nb_envois += 1
        FausseMessagerie.thread_envoyer = threading.get_ident()
        return u"success"

    def Fermer(self):
        raise RuntimeError("fermeture impossible apres acceptation")


class DlgMailerProgressParentTests(unittest.TestCase):
    def setUp(self):
        FausseProgressDialog.instances = []
        FausseMessagerie.dernier_dlg_progress = None
        FausseMessagerie.thread_connecter = None
        FausseMessagerie.thread_envoyer = None
        FausseMessagerieMailjet.nb_envois = 0

        self.base = BaseTest()
        self.base.db.CreationTable("adresses_mail", dicoDB=Tables.DB_DATA)
        self.base.inserer(
            "adresses_mail",
            ["IDadresse", "adresse", "nom_adresse", "motdepasse", "smtp", "port",
             "defaut", "connexionAuthentifiee", "startTLS", "utilisateur", "moteur", "parametres"],
            [(1, "expediteur@example.org", "Expéditeur Test", "", "smtp.example.org", 587,
              1, 1, 1, "expediteur@example.org", "smtp", "")],
        )
        self.base.db.Commit()
        self.addCleanup(self.base.fermer)

        self._redirection = RedirectionGestionDB(self.base.chemin)
        self._redirection.__enter__()
        self.addCleanup(self._redirection.__exit__)

    def _construire_dlg(self, montrer_dlg):
        """Construit un DLG_Mailer.Dialog réel, prêt à envoyer.

        montrer_dlg=False reproduit EnvoiEmailFamille(visible=False) :
        le parent (simulant la demande Connecthys) est affiché, le
        DLG_Mailer.Dialog lui ne l'est jamais.
        montrer_dlg=True reproduit EnvoiEmailFamille(visible=True) : le
        DLG_Mailer.Dialog lui-même est affiché (éditeur ouvert).
        """
        parent_frame = wx.Frame(None)
        parent_frame.Show()
        self.addCleanup(parent_frame.Destroy)

        dlg = DLG_Mailer.Dialog(parent_frame, afficher_confirmation_envoi=False)
        self.addCleanup(dlg.Destroy)
        if montrer_dlg:
            dlg.Show()

        track = OL_Destinataires_emails.Track(
            dlg.ctrl_destinataires,
            {"adresse": "destinataire@example.org"},
        )

        dlg.ctrl_objet.SetValue("Objet du test")
        dlg.ctrl_editeur.EcritTexte("Corps du message de test.")

        return parent_frame, dlg, [track]

    def test_chemin_cache_smtp_est_asynchrone_et_parent_visible(self):
        """Le dialogue cache envoie en worker; aucune ProgressDialog sans parent."""
        parent_frame, dlg, destinataires = self._construire_dlg(montrer_dlg=False)
        thread_ui = threading.get_ident()
        with mock.patch.object(DLG_Mailer.wx, "ProgressDialog", FausseProgressDialog), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", FausseMessagerie), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu") as bilan:
            resultat = dlg.Envoyer(listeDestinataires=destinataires)
        self.assertTrue(resultat)
        self.assertFalse(dlg.IsShownOnScreen())
        self.assertTrue(parent_frame.IsShownOnScreen())
        self.assertEqual(FausseProgressDialog.instances, [])
        self.assertIsNotNone(FausseMessagerie.thread_connecter)
        self.assertIsNotNone(FausseMessagerie.thread_envoyer)
        self.assertNotEqual(FausseMessagerie.thread_connecter, thread_ui)
        self.assertNotEqual(FausseMessagerie.thread_envoyer, thread_ui)
        self.assertIs(bilan.call_args.kwargs["parent"], parent_frame)

    def test_chemin_visible_unitaire_execute_le_reseau_hors_thread_wx(self):
        """visible=True + un destinataire : SMTP/API ne bloque plus le thread wx."""
        parent_frame, dlg, destinataires = self._construire_dlg(montrer_dlg=True)

        self.assertTrue(dlg.IsShownOnScreen())
        thread_ui = threading.get_ident()

        with mock.patch.object(DLG_Mailer.wx, "ProgressDialog", FausseProgressDialog), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", FausseMessagerie):
            resultat = dlg.Envoyer(listeDestinataires=destinataires)

        self.assertTrue(resultat)
        self.assertEqual(FausseProgressDialog.instances, [])
        self.assertIsNotNone(FausseMessagerie.thread_connecter)
        self.assertIsNotNone(FausseMessagerie.thread_envoyer)
        self.assertNotEqual(FausseMessagerie.thread_connecter, thread_ui)
        self.assertNotEqual(FausseMessagerie.thread_envoyer, thread_ui)


    def test_editeur_visible_lot_smtp_emet_hors_ui_sans_progression_orpheline(self):
        """SMTP multi interactif: l'UI et l'historique restent sur le thread wx."""
        frame, dlg, tracks = self._construire_dlg(montrer_dlg=True)
        autre = OL_Destinataires_emails.Track(
            dlg.ctrl_destinataires, {"adresse": "deux@example.test"},
        )
        tracks.append(autre)
        ui_thread = threading.get_ident()
        with mock.patch.object(DLG_Mailer.wx, "ProgressDialog", FausseProgressDialog), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", FausseMessagerie), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu") as bilan, \
             mock.patch.object(dlg, "MemorisationHistorique") as historique:
            resultat = dlg.Envoyer(listeDestinataires=tracks)
        self.assertTrue(resultat)
        self.assertTrue(dlg.envoi_complet)
        self.assertEqual(FausseProgressDialog.instances, [])
        self.assertEqual(historique.call_count, 2)
        self.assertNotEqual(FausseMessagerie.thread_connecter, ui_thread)
        self.assertNotEqual(FausseMessagerie.thread_envoyer, ui_thread)
        self.assertIs(bilan.call_args.kwargs["parent"], dlg)
        self.assertFalse(dlg._envoi_en_cours)
        self.assertTrue(dlg.IsShownOnScreen())
        self.assertTrue(frame.IsShownOnScreen())

    def test_editeur_visible_refuse_second_clic_envoi_smtp_pendant_le_lot(self):
        frame, dlg, tracks = self._construire_dlg(montrer_dlg=True)
        autre = OL_Destinataires_emails.Track(
            dlg.ctrl_destinataires, {"adresse": "deux@example.test"},
        )
        tracks.append(autre)
        envoi_initial = dlg._ExecuterEnvoiUniqueHorsUI
        deuxiemes_clics = []

        def tentative_concurrente(*args, **kwargs):
            deuxiemes_clics.append(dlg.Envoyer(listeDestinataires=tracks))
            return envoi_initial(*args, **kwargs)

        with mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", FausseMessagerie), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu"), \
             mock.patch.object(dlg, "MemorisationHistorique") as historique, \
             mock.patch.object(dlg, "_ExecuterEnvoiUniqueHorsUI",
                               side_effect=tentative_concurrente):
            self.assertTrue(dlg.Envoyer(listeDestinataires=tracks))
        self.assertEqual(deuxiemes_clics, [False, False])
        self.assertEqual(historique.call_count, 2)
        self.assertFalse(dlg._envoi_en_cours)

    def test_editeur_visible_lot_mailjet_travaille_hors_ui(self):
        """Mailjet multi interactif : boucle wx reactive, historique par adresse."""
        frame, dlg, tracks = self._construire_dlg(montrer_dlg=True)
        tracks.append(OL_Destinataires_emails.Track(
            dlg.ctrl_destinataires, {"adresse": "deux@example.test"},
        ))
        config = dict(dlg.ctrl_exp.GetDonnees())
        config["moteur"] = "mailjet"
        ui_thread = threading.get_ident()
        with mock.patch.object(dlg.ctrl_exp, "GetDonnees", return_value=config), \
             mock.patch.object(DLG_Mailer.wx, "ProgressDialog", FausseProgressDialog), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", FausseMessagerieMailjet), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu") as bilan, \
             mock.patch.object(dlg, "MemorisationHistorique") as historique:
            resultat = dlg.Envoyer(listeDestinataires=tracks)
        self.assertTrue(resultat)
        self.assertTrue(dlg.envoi_complet)
        self.assertEqual(FausseProgressDialog.instances, [])
        self.assertEqual(FausseMessagerieMailjet.nb_envois, 2)
        self.assertEqual(historique.call_count, 2)
        self.assertNotEqual(FausseMessagerie.thread_connecter, ui_thread)
        self.assertNotEqual(FausseMessagerie.thread_envoyer, ui_thread)
        self.assertIs(bilan.call_args.kwargs["parent"], dlg)
        self.assertFalse(dlg._envoi_en_cours)
        self.assertTrue(dlg.IsShownOnScreen())
        self.assertTrue(frame.IsShownOnScreen())

    def test_editeur_visible_lot_mailjet_refuse_double_clic(self):
        frame, dlg, tracks = self._construire_dlg(montrer_dlg=True)
        tracks.append(OL_Destinataires_emails.Track(
            dlg.ctrl_destinataires, {"adresse": "deux@example.test"},
        ))
        config = dict(dlg.ctrl_exp.GetDonnees())
        config["moteur"] = "mailjet"
        original = dlg._ExecuterEnvoiUniqueHorsUI
        secondes_tentatives = []

        def controle(*args, **kwargs):
            secondes_tentatives.append(dlg.Envoyer(listeDestinataires=tracks))
            return original(*args, **kwargs)

        with mock.patch.object(dlg.ctrl_exp, "GetDonnees", return_value=config), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", FausseMessagerieMailjet), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu"), \
             mock.patch.object(dlg, "MemorisationHistorique") as historique, \
             mock.patch.object(dlg, "_ExecuterEnvoiUniqueHorsUI", side_effect=controle):
            self.assertTrue(dlg.Envoyer(listeDestinataires=tracks))
        self.assertEqual(secondes_tentatives, [False, False])
        self.assertEqual(FausseMessagerieMailjet.nb_envois, 2)
        self.assertEqual(historique.call_count, 2)
        self.assertFalse(dlg._envoi_en_cours)

    def test_messagebox_win32_herite_de_son_owner_sans_remaximiser(self):
        """L'alerte doit appartenir a sa frame et ne pas etre topmost globale."""
        import sys
        if sys.platform != "win32":
            self.skipTest("GW_OWNER seulement sur Windows")
        import ctypes
        from Dlg import DLG_Messagebox

        frame = wx.Frame(None)
        frame.Show()
        frame.Maximize(True)
        self.addCleanup(frame.Destroy)
        est_maximise = frame.IsMaximized()
        dialogue = DLG_Messagebox.Dialog(
            frame, titre="Controle technique", introduction="Message de test",
            icone=wx.ICON_INFORMATION, boutons=["OK"],
        )
        try:
            self.assertFalse(dialogue.GetWindowStyleFlag() & wx.DIALOG_NO_PARENT)
            self.assertFalse(dialogue.GetWindowStyleFlag() & wx.STAY_ON_TOP)
            u32 = ctypes.windll.user32
            u32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            u32.GetWindow.restype = ctypes.c_void_p
            owner = u32.GetWindow(ctypes.c_void_p(dialogue.GetHandle()), 4)
            self.assertEqual(owner, frame.GetHandle())
        finally:
            dialogue.Destroy()
        self.assertEqual(frame.IsMaximized(), est_maximise)

    def test_messagebox_remonte_d_un_parent_masque_vers_la_frame_visible(self):
        frame = wx.Frame(None)
        frame.Show()
        self.addCleanup(frame.Destroy)
        enfant_cache = wx.Dialog(frame)
        self.addCleanup(enfant_cache.Destroy)
        self.assertFalse(enfant_cache.IsShownOnScreen())
        dialogue = DLG_Messagebox.Dialog(
            enfant_cache, titre="Test", introduction="Alerte fictive",
            boutons=["OK"],
        )
        try:
            self.assertIs(dialogue.GetParent(), frame)
            self.assertIs(dialogue.parent, frame)
        finally:
            dialogue.Destroy()

    def test_latences_smtp_fictives_3_8_15_secondes_wx_reste_reactif(self):
        """Un timer wx est servi PENDANT l'attente d'un transport factice."""
        frame, dlg, destinataires = self._construire_dlg(montrer_dlg=False)
        self.assertTrue(frame.IsShownOnScreen())
        ui = threading.get_ident()

        class SmtpFactice:
            def __init__(self, delai):
                self.delai = delai
                self.worker_threads = []

            def Connecter(self):
                self.worker_threads.append(threading.get_ident())

            def Envoyer(self, message):
                self.worker_threads.append(threading.get_ident())
                time.sleep(self.delai)
                return True

            def Fermer(self):
                pass

        class MessageFictif:
            def GetLabelDestinataires(self):
                return "contact@example.test"

        for delai in (3, 8, 15):
            with self.subTest(delai=delai):
                transport = SmtpFactice(delai)
                t0 = time.monotonic()
                signaux_wx = []
                timer = wx.CallLater(120, lambda: signaux_wx.append(
                    (time.monotonic(), threading.get_ident())))
                resultat = dlg._ExecuterEnvoiUniqueHorsUI(
                    transport, MessageFictif(), frame, relancer_deconnexion=False,
                )
                timer.Stop()
                self.assertTrue(resultat["succes"])
                self.assertEqual(len(signaux_wx), 1)
                self.assertEqual(signaux_wx[0][1], ui)
                self.assertLess(signaux_wx[0][0] - t0, 2)
                self.assertTrue(all(t != ui for t in transport.worker_threads))

    def test_chemin_unitaire_mailjet_compte_rendu_accepte_sans_renvoi(self):
        """Mailjet : bilan « accepte pour envoi » de main, jamais de renvoi apres acceptation."""
        parent_frame, dlg, destinataires = self._construire_dlg(montrer_dlg=True)
        FausseMessagerieMailjet.nb_envois = 0
        bilans = []

        def compte_rendu(messagerie, messages, succes, anomalies, non_tentes, confirmation, parent=None):
            self.assertIs(parent, dlg)
            bilans.append((len(messages), len(succes), len(anomalies), len(non_tentes)))

        with mock.patch.object(DLG_Mailer.wx, "ProgressDialog", FausseProgressDialog),              mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", FausseMessagerieMailjet),              mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu", compte_rendu):
            resultat = dlg.Envoyer(listeDestinataires=destinataires)

        self.assertTrue(resultat)
        self.assertEqual(FausseMessagerieMailjet.nb_envois, 1)
        self.assertEqual(bilans, [(1, 1, 0, 0)])


if __name__ == "__main__":
    unittest.main()
