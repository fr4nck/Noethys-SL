# -*- coding: utf-8 -*-
"""UI-2A: SMTP Connecthys non bloquant, sans reseau ni destinataires reels."""
from __future__ import annotations

import ast
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Dlg" / "DLG_Mailer.py"


class SmtpSourceContract(unittest.TestCase):
    def setUp(self):
        source = SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        dialog = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == "Dialog")
        self.methods = {m.name: ast.get_source_segment(source, m) for m in dialog.body
                        if isinstance(m, ast.FunctionDef)}

    def test_smtp_cache_ne_touche_pas_envoyer_lot_synchrone(self):
        env = self.methods["Envoyer"]
        self.assertIn("if not self.IsShownOnScreen():", env)
        self.assertIn("self._EnvoyerLotSmtpHorsUI(dictExp, liste_messages, parent_progress)", env)
        self.assertLess(env.index("_EnvoyerLotSmtpHorsUI"), env.index("messagerie.Connecter()"))

    def test_worker_smtp_nautorise_pas_renvoi_automatique_ambigu(self):
        src = self.methods["_EnvoyerLotSmtpHorsUI"]
        self.assertIn("relancer_deconnexion=False", src)
        self.assertIn("self.listeIncertains.append(message)", src)
        self.assertIn("self.MemorisationHistorique(", src)
        self.assertIn("parent=parent_progress", src)
        worker = self.methods["_ExecuterEnvoiUniqueHorsUI"]
        self.assertIn("if not relancer_deconnexion:", worker)
        self.assertIn("wx.CallAfter(dlg_attente.Terminer)", worker)
        self.assertIn("threading.Thread(target=_worker", worker)

    def test_lhistorique_est_seulement_sur_le_fil_ui(self):
        worker = self.methods["_ExecuterEnvoiUniqueHorsUI"]
        self.assertNotIn("MemorisationHistorique", worker)


try:
    sys.path.insert(0, str(ROOT / "noethys"))
    import wx
    from Dlg import DLG_Mailer
except (ImportError, RuntimeError):
    wx = None


@unittest.skipIf(wx is None, "wxPython requis")
class SmtpSimulationTests(unittest.TestCase):
    class Message:
        sujet = "Confirmation fictive"
        def __init__(self, adresse):
            self.adresse = adresse

        def GetLabelDestinataires(self):
            return self.adresse

    class Transport:
        LIBELLE_SERVICE = "SMTP"
        def __init__(self, **options):
            self.dict_parametres = {"nbre_mails": "2", "duree_pause": "4"}

    class Dialogue:
        choix = []
        instances = []
        def __init__(self, *a, **kw):
            self.__class__.instances.append((a, kw))
        def ShowModal(self):
            return self.__class__.choix.pop(0)
        def Destroy(self):
            pass

    def setUp(self):
        self.messages = [self.Message("contact-001@example.test"),
                         self.Message("contact-002@example.test")]
        self.config = dict(moteur="smtp", smtp="smtp.example.test", port=2525,
                           utilisateur="", motdepasse="", adresse="from@example.test",
                           nom_adresse="Simulation", startTLS=False, parametres="")
        self.fake = mock.Mock()
        self.fake.listeSucces = []
        self.fake.listeAnomalies = []
        self.fake.listeIncertains = []
        self.fake.afficher_confirmation_envoi = False
        self.Dialogue.choix = []
        self.Dialogue.instances = []

    def executer(self, etats, messages=None):
        messages = messages or self.messages
        appels = []
        ui_thread = threading.get_ident()
        def worker(transport, message, owner, index=1, total=1,
                   pause_avant=0, relancer_deconnexion=True):
            appels.append((message.adresse, index, total, pause_avant,
                           relancer_deconnexion, threading.get_ident()))
            return etats.pop(0)
        self.fake._ExecuterEnvoiUniqueHorsUI.side_effect = worker
        with mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", self.Transport), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu") as bilan, \
             mock.patch.object(DLG_Mailer.DLG_Messagebox, "Dialog", self.Dialogue):
            result = DLG_Mailer.Dialog._EnvoyerLotSmtpHorsUI(
                self.fake, self.config, messages, None,
            )
        return result, appels, bilan, ui_thread

    def test_deux_acceptes_historises_avant_prochain_envoi(self):
        ok = dict(succes=True, erreur=None, phase="envoi")
        result, appels, bilan, ui = self.executer([ok.copy(), ok.copy()])
        self.assertTrue(result)
        self.assertEqual([x[0] for x in appels],
                         ["contact-001@example.test", "contact-002@example.test"])
        self.assertEqual([x[3] for x in appels], [0, 1])
        self.assertTrue(all(x[4] is False and x[5] == ui for x in appels))
        self.assertEqual(self.fake.MemorisationHistorique.call_count, 2)
        self.assertEqual(len(self.fake.listeIncertains), 0)
        self.assertEqual(bilan.call_args.kwargs["parent"], None)

    def test_timeout_apres_emission_ne_relance_pas_et_marque_incertain(self):
        ok = dict(succes=True, erreur=None, phase="envoi")
        doute = dict(succes=False, erreur=TimeoutError("SMTP timeout factice"), phase="envoi")
        self.Dialogue.choix = [0]  # uniquement Terminer, sans bouton Reessayer
        result, appels, bilan, _ = self.executer([ok, doute])
        self.assertFalse(result)
        self.assertEqual(len(appels), 2)
        self.assertEqual(self.fake.MemorisationHistorique.call_count, 1)
        self.assertEqual(self.fake.listeIncertains, [self.messages[1]])
        self.assertEqual(self.Dialogue.instances[0][1]["boutons"], ["Terminer"])
        self.assertEqual(len(bilan.call_args.args[2]), 1)
        self.assertEqual(len(bilan.call_args.args[3]), 1)

    def test_erreur_connexion_est_reessayable_uniquement_sur_la_meme_adresse(self):
        ok = dict(succes=True, erreur=None, phase="envoi")
        erreur = dict(succes=False, erreur=ConnectionError("refus fictif"),
                      phase="connexion")
        self.Dialogue.choix = [0]
        result, appels, _, _ = self.executer([ok.copy(), erreur, ok.copy()])
        self.assertTrue(result)
        self.assertEqual([x[0] for x in appels],
                         ["contact-001@example.test", "contact-002@example.test",
                          "contact-002@example.test"])
        self.assertEqual(self.fake.MemorisationHistorique.call_count, 2)
        self.assertEqual(len(self.fake.listeIncertains), 0)
        self.assertFalse(appels[-1][4])

    def test_erreur_apres_emission_pour_un_seul_destinataire(self):
        err = dict(succes=False, erreur=OSError("envoi non confirme"), phase="envoi")
        self.Dialogue.choix = [0]
        result, appels, _, _ = self.executer([err], messages=[self.messages[0]])
        self.assertFalse(result)
        self.assertEqual(len(appels), 1)
        self.assertEqual(self.fake.listeIncertains, [self.messages[0]])
        self.fake.MemorisationHistorique.assert_not_called()

    def test_historique_indisponible_ne_renvoie_jamais(self):
        ok = dict(succes=True, erreur=None, phase="envoi")
        self.fake.MemorisationHistorique.side_effect = OSError("SQLite fictif")
        with mock.patch.object(DLG_Mailer.wx, "MessageDialog") as warning:
            result, appels, _, _ = self.executer([ok.copy(), ok.copy()])
        self.assertTrue(result)
        self.assertEqual(len(appels), 2)
        warning.assert_called_once()

    def test_exception_externe_au_worker_reste_incertaine(self):
        """Une exception de ShowModal/worker n'est PAS une preuve de non-envoi."""
        self.fake._ExecuterEnvoiUniqueHorsUI.side_effect = RuntimeError(
            "worker interrompu apres DATA"
        )
        self.Dialogue.choix = [0]  # Terminer, sans renvoyer
        with mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie", self.Transport), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu") as bilan, \
             mock.patch.object(DLG_Mailer.DLG_Messagebox, "Dialog", self.Dialogue):
            resultat = DLG_Mailer.Dialog._EnvoyerLotSmtpHorsUI(
                self.fake, self.config, [self.messages[0]], None,
            )
        self.assertFalse(resultat)
        self.assertEqual(self.fake.listeIncertains, [self.messages[0]])
        self.fake.MemorisationHistorique.assert_not_called()
        self.assertEqual(self.Dialogue.instances[0][1]["boutons"], ["Terminer"])

    def test_arret_apres_erreur_ne_tente_pas_la_suivante(self):
        self.messages.append(self.Message("contact-003@example.test"))
        erreur = dict(succes=False, erreur=ConnectionError("indisponible"),
                      phase="connexion")
        self.Dialogue.choix = [3]  # Arreter, avant les deux destinataires suivants
        result, appels, bilan, _ = self.executer([erreur])
        self.assertFalse(result)
        self.assertEqual(len(appels), 1)
        self.assertEqual(bilan.call_args.args[4], self.messages[1:])


if __name__ == "__main__":
    unittest.main()
