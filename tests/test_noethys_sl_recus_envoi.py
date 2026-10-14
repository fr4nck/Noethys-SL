# -*- coding: utf-8 -*-
"""RC6 lot B : un reçu n'est jamais considéré comme envoyé si l'envoi a échoué.

Serveur SMTP de capture local (MiniSMTP, 127.0.0.1) : aucun email réel,
adresses example.org uniquement. Dialogues wx remplacés par des doublures.
- Envoyer_lot : un retour 0/None du moteur (aucun destinataire accepté) n'est
  plus compté comme accepté ni mémorisé dans l'historique ;
- EnvoiEmailFamille : PDF non généré (False ou None) -> aucun envoi ;
- portail, mode manuel : la demande « par Email » n'est validée que si le
  dialogue d'édition a réellement fait accepter le reçu par le serveur.
"""
from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
NOETHYS_DIR = TESTS_DIR.parent / "noethys"
for chemin in (str(NOETHYS_DIR), str(TESTS_DIR)):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

try:
    import _garde_reseau  # noqa: F401  (profil temporaire, aucune base réseau)
    import wx  # noqa: F401
    from Utils import UTILS_Envoi_email
    from Outils.mail.utils import DNS_NAME
    from Dlg import DLG_Saisie_portail_demande, DLG_Impression_recu
    from test_audit_reseau_emails import MiniSMTP, FausseProgressDialog
    IMPORT_ERREUR = None
except Exception as err:  # pragma: no cover - environnement sans wx
    IMPORT_ERREUR = err


def setUpModule():
    if IMPORT_ERREUR is not None:
        raise unittest.SkipTest("Import Noethys impossible : %r" % (IMPORT_ERREUR,))
    DNS_NAME._fqdn = "localhost"


class _Dialogues(object):
    """ Messagebox d'erreur : « Arrêter » ; compte-rendu final mémorisé. """

    def __init__(self):
        self.erreurs = []
        self.messages = []

    def Messagebox(self, *args, **kwargs):
        self.erreurs.append(kwargs.get("detail"))
        boutons = kwargs.get("boutons") or []
        dialogue = mock.MagicMock()
        dialogue.ShowModal.return_value = len(boutons) - 1
        return dialogue

    def MessageDialog(self, parent, message, *args, **kwargs):
        self.messages.append(message)
        return mock.MagicMock()


class EnvoiLotCaptureTests(unittest.TestCase):
    def setUp(self):
        for cible, nom, valeur in (
                (UTILS_Envoi_email.UTILS_Parametres, "Parametres", None),
                (UTILS_Envoi_email.wx, "ProgressDialog", FausseProgressDialog)):
            p = mock.patch.object(cible, nom, return_value=valeur) if nom == "Parametres" else mock.patch.object(cible, nom, valeur)
            p.start()
            self.addCleanup(p.stop)
        self.srv = MiniSMTP()
        self.addCleanup(self.srv.arreter)
        self.pdf = tempfile.NamedTemporaryFile(prefix="RECU_", suffix=".pdf", delete=False)
        self.pdf.write(b"%PDF-1.4\n% recu fictif\n%%EOF\n")
        self.pdf.close()
        self.addCleanup(os.remove, self.pdf.name)

    def envoyer_lot(self, destinataires):
        messagerie = UTILS_Envoi_email.Messagerie(
            backend="smtp", hote="127.0.0.1", port=self.srv.port, utilisateur=None, motdepasse=None,
            email_exp="accueil@example.org", nom_exp=u"Accueil", timeout=5, use_tls=0,
            parametres="notification==0")
        message = UTILS_Envoi_email.Message(
            destinataires=list(destinataires), sujet=u"Reçu de règlement n°42",
            texte_html=u"<p>Votre reçu de 12,50 €</p>", fichiers=[self.pdf.name], images=[])
        acceptes, d = [], _Dialogues()
        with mock.patch.object(UTILS_Envoi_email.DLG_Messagebox, "Dialog", d.Messagebox), \
                mock.patch.object(UTILS_Envoi_email.wx, "MessageDialog", d.MessageDialog), \
                mock.patch("builtins.print"), mock.patch("traceback.print_exc"):
            messagerie.Connecter()
            succes = messagerie.Envoyer_lot(messages=[message], dlg_progress=None,
                                            afficher_confirmation_envoi=False,
                                            callback_succes=acceptes.append)
            messagerie.Fermer()
        return succes, acceptes, d

    def test_recu_accepte_par_le_serveur_avec_son_pdf(self):
        succes, acceptes, d = self.envoyer_lot(["famille@example.org"])
        self.assertEqual(len(succes), 1)
        self.assertEqual(len(acceptes), 1)
        self.assertEqual(len(self.srv.messages), 1)
        self.assertIn(os.path.basename(self.pdf.name).encode("ascii"), self.srv.messages[0])
        self.assertEqual(d.erreurs, [])

    def test_aucun_destinataire_accepte_n_est_pas_un_succes(self):
        # Adresse vide : SmtpV2.Envoyer renvoie 0 sans rien transmettre.
        succes, acceptes, d = self.envoyer_lot([""])
        self.assertEqual(self.srv.messages, [])
        self.assertEqual(succes, [])
        self.assertEqual(acceptes, [], "historique écrit pour un reçu jamais envoyé")
        self.assertEqual(len(d.erreurs), 1)

    def test_destinataire_refuse_n_est_pas_un_succes(self):
        self.srv.refuses = {"famille@example.org"}
        succes, acceptes, d = self.envoyer_lot(["famille@example.org"])
        self.assertEqual(self.srv.messages, [])
        self.assertEqual((succes, acceptes), ([], []))


class EnvoiEmailFamilleTests(unittest.TestCase):
    def test_pdf_non_genere_aucun_envoi(self):
        from Dlg import DLG_Mailer
        for retour in (False, None):
            with mock.patch.object(DLG_Mailer, "Dialog", side_effect=AssertionError("Mailer ouvert")):
                self.assertIs(UTILS_Envoi_email.EnvoiEmailFamille(
                    IDfamille=1, nomDoc="RECU.pdf", categorie="recu_reglement",
                    listeAdresses=["famille@example.org"], visible=False,
                    CreationPDF=lambda nomDoc, afficherDoc: retour), False)


class PortailManuelTests(unittest.TestCase):
    def executer(self, methode, email_envoye):
        impression = mock.MagicMock()
        impression.email_envoye = email_envoye
        logs = []
        traitement = types.SimpleNamespace(
            mode="manuel", parent=None,
            dict_parametres={"IDreglement": "12", "methode_envoi": methode},
            track=types.SimpleNamespace(IDfamille=3),
            EcritLog=lambda message="", log_jumeau=None: logs.append(message))
        with mock.patch.object(DLG_Impression_recu, "Dialog", return_value=impression):
            resultat = DLG_Saisie_portail_demande.Traitement.Traitement_recus(traitement)
        impression.ShowModal.assert_called_once_with()
        return resultat, logs

    def test_email_non_envoye_demande_reste_en_attente(self):
        resultat, logs = self.executer("email", False)
        self.assertIs(resultat, False)
        self.assertIn(u"Le reçu de règlement n'a pas été envoyé par Email.", logs)

    def test_email_accepte_demande_validee(self):
        resultat, logs = self.executer("email", True)
        self.assertEqual(resultat, {"etat": True, "reponse": u"Reçu de règlement envoyé par Email."})

    def test_courrier_inchange(self):
        resultat, logs = self.executer("courrier", False)
        self.assertEqual(resultat, {"etat": True, "reponse": u"Reçu de règlement envoyé par courrier."})


class ContratsSourceTests(unittest.TestCase):
    """ Parcours wx non instanciables sans base : contrats vérifiés sur le source. """

    def test_saisie_reglement_n_envoie_pas_sans_pdf(self):
        source = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_reglement.py").read_text(encoding="utf-8")
        self.assertNotIn("#return False\n\n                        succes = False", source)
        debut = source.index("dictChamps = dlg1.CreationPDF(nomDoc=nomDoc, afficherDoc=False)")
        bloc = source[debut:debut + 2500]
        self.assertLess(bloc.index("if dictChamps in (False, None) :"), bloc.index("DLG_Mailer.Dialog("))
        self.assertIn(u"Le reçu n'a pas été envoyé : %s", bloc)
        self.assertEqual(bloc.count("dlg1.Destroy()"), 1)

    def test_creation_pdf_echouee_ne_laisse_rien_a_memoriser(self):
        source = (NOETHYS_DIR / "Dlg" / "DLG_Impression_recu.py").read_text(encoding="utf-8")
        self.assertIn("if impression.erreur is not None or not os.path.isfile(nomDoc) :\n"
                      "            self.dictSave = {}\n            return False", source)
        impression = (NOETHYS_DIR / "Utils" / "UTILS_Impression_recu.py").read_text(encoding="utf-8")
        self.assertIn('"Permission denied" in str(err)', impression)
        self.assertIn("self.erreur = err", impression)


if __name__ == "__main__":
    unittest.main()
