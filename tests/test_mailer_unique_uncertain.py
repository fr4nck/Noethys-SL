# -*- coding: utf-8 -*-
"""UI-2D : un email accepte de facon incertaine ne doit pas etre renvoye.

Le code reel du Mailer est teste avec des transporteurs et des messages
synthetiques ; aucun SMTP, HTTP ou acces a une base n'est effectue.
"""
from __future__ import annotations

import ast
import smtplib
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Dlg" / "DLG_Mailer.py"


class ContratsSource(unittest.TestCase):
    def test_single_refuse_la_reconnexion_implicite_et_garde_le_double_clic(self):
        source = SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        dialogue = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "Dialog")
        methods = {x.name: ast.get_source_segment(source, x)
                   for x in dialogue.body if isinstance(x, ast.FunctionDef)}
        self.assertIn("relancer_deconnexion=False", methods["_EnvoyerMessageUnique"])
        self.assertIn("self.listeIncertains", methods["_EnvoyerMessageUnique"])
        self.assertIn("refus_explicit", methods["_EnvoyerMessageUnique"])
        self.assertIn('self._envoi_en_cours = True', methods["Envoyer"])
        self.assertIn('self._envoi_en_cours = False', methods["Envoyer"])


try:
    sys.path.insert(0, str(ROOT / "noethys"))
    import wx
    from Dlg import DLG_Mailer
    from Utils import UTILS_Envoi_email
except (ImportError, RuntimeError):
    wx = None


@unittest.skipIf(wx is None, "wxPython requis pour charger le code du Mailer")
class RefusEtIncertitudeUnitaire(unittest.TestCase):
    class MessageFictif:
        sujet = "Test synthetique"

        def GetLabelDestinataires(self):
            return "contact@example.test"

    class BoiteFictive:
        vues = []
        choix = []

        def __init__(self, *args, **kwargs):
            self.__class__.vues.append(kwargs)

        def ShowModal(self):
            return self.__class__.choix.pop(0)

        def Destroy(self):
            pass

    def setUp(self):
        self.faux = mock.Mock()
        self.faux.listeSucces = []
        self.faux.afficher_confirmation_envoi = False
        self.BoiteFictive.vues = []
        self.BoiteFictive.choix = []
        self.message = self.MessageFictif()

    def envoyer(self, states, messenger=None, choices=(0,)):
        self.BoiteFictive.choix = list(choices)
        self.faux._ExecuterEnvoiUniqueHorsUI.side_effect = list(states)
        with mock.patch.object(DLG_Mailer.DLG_Messagebox, "Dialog", self.BoiteFictive), \
             mock.patch.object(UTILS_Envoi_email, "_AfficherCompteRendu"):
            resultat = DLG_Mailer.Dialog._EnvoyerMessageUnique(
                self.faux, messenger if messenger is not None else object(),
                self.message, None,
            )
        return resultat, self.faux._ExecuterEnvoiUniqueHorsUI.call_args_list

    def test_timeout_smtp_apres_data_interdit_meme_retry_manuel_implicite(self):
        erreur = {"succes": False, "erreur": TimeoutError("DATA sans reponse fictive"),
                  "phase": "envoi"}
        succes = {"succes": True, "erreur": None, "phase": "envoi"}
        resultat, appels = self.envoyer([erreur, succes], choices=[0])
        self.assertFalse(resultat)
        self.assertEqual(len(appels), 1)
        self.assertFalse(appels[0].kwargs["relancer_deconnexion"])
        self.assertEqual(self.faux.listeIncertains, [self.message])
        self.assertEqual(self.BoiteFictive.vues[0]["boutons"], ["Terminer"])
        self.assertEqual(self.faux.listeSucces, [])

    def test_timeout_mailjet_apres_transmission_reste_incertain(self):
        erreur = {"succes": False, "erreur": TimeoutError("Mailjet faux timeout"),
                  "phase": "envoi"}
        resultat, appels = self.envoyer([erreur], choices=[0])
        self.assertFalse(resultat)
        self.assertEqual(len(appels), 1)
        self.assertEqual(self.faux.listeIncertains, [self.message])
        self.assertNotIn("Réessayer", self.BoiteFictive.vues[0]["boutons"])

    def test_refus_smtp_explicit_est_reessayable_une_fois(self):
        erreur = {"succes": False,
                  "erreur": smtplib.SMTPRecipientsRefused({
                      "contact@example.test": (550, "Refus fictif")
                  }), "phase": "envoi"}
        succes = {"succes": True, "erreur": None, "phase": "envoi"}
        resultat, appels = self.envoyer([erreur, succes], choices=[0])
        self.assertTrue(resultat)
        self.assertEqual(len(appels), 2)
        self.assertFalse(appels[0].kwargs["relancer_deconnexion"])
        self.assertFalse(appels[1].kwargs["relancer_deconnexion"])
        self.assertEqual(self.faux.listeIncertains, [])
        self.assertEqual(self.faux.listeSucces, [self.message])
        self.assertEqual(self.BoiteFictive.vues[0]["boutons"],
                         ["Réessayer", "Arrêter"])

    def test_refus_mailjet_400_est_reessayable_une_fois(self):
        erreur = {"succes": False,
                  "erreur": UTILS_Envoi_email.ErreurMailjet(
                      "Mailjet a refusé le message (HTTP 400)"),
                  "phase": "envoi"}
        succes = {"succes": True, "erreur": None, "phase": "envoi"}

        class FakeMailjet:
            LIBELLE_SERVICE = "Mailjet"

        resultat, appels = self.envoyer([erreur, succes],
                                        messenger=FakeMailjet(), choices=[0])
        self.assertTrue(resultat)
        self.assertEqual(len(appels), 2)
        self.assertEqual(self.faux.listeSucces, [self.message])

    def test_interruption_en_dehors_du_worker_est_traitee_comme_incertaine(self):
        self.faux._ExecuterEnvoiUniqueHorsUI.side_effect = RuntimeError(
            "dialogue modal interrompu apres acceptation factice"
        )
        self.BoiteFictive.choix = [0]
        with mock.patch.object(DLG_Mailer.DLG_Messagebox, "Dialog",
                               self.BoiteFictive):
            resultat = DLG_Mailer.Dialog._EnvoyerMessageUnique(
                self.faux, object(), self.message, None,
            )
        self.assertFalse(resultat)
        self.assertEqual(self.faux.listeIncertains, [self.message])
        self.assertEqual(self.BoiteFictive.vues[0]["boutons"], ["Terminer"])

    def test_erreur_connexion_ne_marque_pas_destinataire_incertain(self):
        erreur = {"succes": False, "erreur": ConnectionError("connex fail fictif"),
                  "phase": "connexion"}
        resultat, appels = self.envoyer([erreur], choices=[0])
        self.assertFalse(resultat)
        self.assertEqual(len(appels), 1)
        self.assertEqual(self.faux.listeIncertains, [])
        self.assertEqual(self.BoiteFictive.vues[0]["boutons"], ["Ok"])


if __name__ == "__main__":
    unittest.main()
