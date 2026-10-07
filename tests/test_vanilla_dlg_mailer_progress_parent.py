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

from Dlg import DLG_Mailer  # noqa: E402
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


class DlgMailerProgressParentTests(unittest.TestCase):
    def setUp(self):
        FausseProgressDialog.instances = []
        FausseMessagerie.dernier_dlg_progress = None
        FausseMessagerie.thread_connecter = None
        FausseMessagerie.thread_envoyer = None

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

    def _envoyer_legacy(self, dlg, listeDestinataires):
        with mock.patch.object(DLG_Mailer.wx, "ProgressDialog", FausseProgressDialog), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", FausseMessagerie):
            resultat = dlg.Envoyer(listeDestinataires=listeDestinataires)
        self.assertNotEqual(resultat, False)
        self.assertEqual(len(FausseProgressDialog.instances), 1)
        return FausseProgressDialog.instances[0]

    def test_chemin_cache_progressdialog_parentee_sur_le_parent_visible(self):
        """visible=False : DLG_Mailer caché, son parent est visible.

        La ProgressDialog doit être parentée directement sur ce parent
        visible -- jamais sur le DLG_Mailer caché, jamais sur None.
        """
        parent_frame, dlg, destinataires = self._construire_dlg(montrer_dlg=False)

        self.assertFalse(dlg.IsShownOnScreen())
        self.assertTrue(parent_frame.IsShownOnScreen())

        progress = self._envoyer_legacy(dlg, destinataires)

        self.assertIsNotNone(progress.parent)
        self.assertIs(progress.parent, parent_frame)
        self.assertIsNot(progress.parent, dlg)
        self.assertTrue(progress.detruite)

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


if __name__ == "__main__":
    unittest.main()
