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
        self.assertIn('if dictExp["moteur"] == "mailjet":', env)
        self.assertIn("self._EnvoyerLotMailjetHorsUI(dictExp, liste_messages, parent_progress)", env)

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

    def lancer(self, scenarios):
        ui = threading.get_ident()
        appels = []
        def envoyer(messagerie, message, parent, index=1, total=1, pause_avant=0):
            appels.append((message.adresse, index, total, pause_avant, threading.get_ident()))
            return scenarios.pop(0)
        self.faux._ExecuterEnvoiUniqueHorsUI.side_effect = envoyer
        with mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "Messagerie",
                               return_value=self.Messagerie()), \
             mock.patch.object(DLG_Mailer.UTILS_Envoi_email, "_AfficherCompteRendu") as bilan, \
             mock.patch.object(DLG_Mailer.DLG_Messagebox, "Dialog", self.Dialogue):
            resultat = DLG_Mailer.Dialog._EnvoyerLotMailjetHorsUI(
                self.faux, self.config, self.messages, None)
        return resultat, appels, bilan.call_args, ui

    def test_deux_acceptations_enregistrees_individuellement(self):
        ok = dict(succes=True, erreur=None, phase="envoi")
        resultat, appels, bilan, ui = self.lancer([ok.copy(), ok.copy()])
        self.assertTrue(resultat)
        self.assertEqual([a[0] for a in appels], ["a@example.test", "b@example.test"])
        self.assertEqual([a[1:4] for a in appels], [(1, 2, 0), (2, 2, 1)])
        self.assertEqual(self.faux.MemorisationHistorique.call_count, 2)
        self.assertEqual(len(bilan.args[2]), 2)
        self.assertTrue(all(a[-1] == ui for a in appels))

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
