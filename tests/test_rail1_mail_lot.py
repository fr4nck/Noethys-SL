# -*- coding: utf-8 -*-
"""Lots d'emails (SMTP et Mailjet) : arrêt après erreur (MAIL-FAM-02),
historique (MAIL-HIST-01), erreurs Mailjet (MAILJET-ERR-01).

Aucun email réel : la connexion Mailjet est une doublure, les dialogues wx
sont remplacés. Les tests 'test_caracterisation_*' figent le comportement
AVANT correction.
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

try:
    import wx  # noqa: F401
    from Utils import UTILS_Envoi_email
    IMPORT_ERREUR = None
except Exception as err:  # pragma: no cover
    IMPORT_ERREUR = err

CLE_FACTICE = "FAUX-CLE-RAIL1"
SECRET_FACTICE = "FAUX-SECRET-RAIL1"


def setUpModule():
    if IMPORT_ERREUR is not None:
        raise unittest.SkipTest("Import Noethys impossible : %r" % (IMPORT_ERREUR,))


class FausseProgress(object):
    def __init__(self, *a, **k):
        pass

    def SetSize(self, *a):
        pass

    def CenterOnScreen(self, *a):
        pass

    def SetRange(self, *a):
        pass

    def Update(self, *a, **k):
        return True, False

    def Destroy(self):
        pass


class Dialogues(object):
    """Doublures de DLG_Messagebox.Dialog et wx.MessageDialog.
    reponses : réponses successives aux boîtes d'erreur (0 Réessayer,
    1 Continuer, 2 Continuer sans signaler, 3 Arrêter)."""

    def __init__(self, reponses=()):
        self.reponses = list(reponses)
        self.vus = []
        dialogues = self

        class Messagebox(object):
            def __init__(self, *a, **k):
                self.k = k
                dialogues.vus.append(k)

            def ShowModal(self):
                if self.k.get("titre") == u"Erreur" and dialogues.reponses:
                    return dialogues.reponses.pop(0)
                return 0

            def Destroy(self):
                pass

        class MessageDialog(object):
            def __init__(self, parent, message, titre=u"", *a, **k):
                dialogues.vus.append({"titre": titre, "introduction": message, "detail": u""})

            def ShowModal(self):
                return wx.ID_OK

            def Destroy(self):
                pass

        self.Messagebox = Messagebox
        self.MessageDialog = MessageDialog

    def erreurs(self):
        return [k for k in self.vus if k.get("titre") == u"Erreur"]

    def comptes_rendus(self):
        return [k for k in self.vus if k.get("titre") != u"Erreur"]

    def texte_comptes_rendus(self):
        return u"\n".join(u"%s\n%s" % (k.get("introduction", u""), k.get("detail", u"") or u"")
                          for k in self.comptes_rendus())


def message(adresse):
    return UTILS_Envoi_email.Message(destinataires=[adresse], sujet=u"Facture n°1",
                                     texte_html=u"<p>Bonjour</p>", fichiers=[], images=[])


def reponse_mailjet(json_data=None, status=200, json_erreur=None):
    rep = mock.MagicMock()
    rep.status_code = status
    if json_erreur is not None:
        rep.json.side_effect = json_erreur
    else:
        rep.json.return_value = json_data
    rep.text = u"<html>Bad Gateway</html>"
    return rep


def succes_mailjet(adresse, uuid="uuid-1", mid=1001):
    return reponse_mailjet({"Messages": [{"Status": "success", "To": [
        {"Email": adresse, "MessageUUID": uuid, "MessageID": mid,
         "MessageHref": "https://api.mailjet.com/v3/REST/message/%d" % mid}]}]})


class _Base(unittest.TestCase):
    def setUp(self):
        for cible, valeur in ((UTILS_Envoi_email.UTILS_Parametres, ("Parametres", "20")),
                              (UTILS_Envoi_email.wx, ("ProgressDialog", FausseProgress)),
                              (UTILS_Envoi_email.time, ("sleep", lambda *a: None))):
            nom, v = valeur
            p = mock.patch.object(cible, nom, return_value=v) if nom == "Parametres" else mock.patch.object(cible, nom, v)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch("traceback.print_exc")
        p.start()
        self.addCleanup(p.stop)

    def mailjet(self, reponses):
        m = UTILS_Envoi_email.Messagerie(backend="mailjet", email_exp="e@example.org", nom_exp="T",
                                         parametres="api_key==%s##api_secret==%s" % (CLE_FACTICE, SECRET_FACTICE))
        m.connection = mock.MagicMock()
        m.connection.send.create.side_effect = reponses
        return m

    def smtp(self, effets):
        m = UTILS_Envoi_email.Messagerie(backend="smtp", hote="127.0.0.1", port=25, email_exp="e@example.org",
                                         nom_exp="T", parametres="notification==0")
        m.Envoyer = mock.MagicMock(side_effect=effets)
        m.Connecter = mock.MagicMock()
        return m

    def lancer(self, m, messages, reponses_dialogues, confirmation=True):
        d = Dialogues(reponses_dialogues)
        with mock.patch.object(UTILS_Envoi_email.DLG_Messagebox, "Dialog", d.Messagebox), \
                mock.patch.object(UTILS_Envoi_email.wx, "MessageDialog", d.MessageDialog), \
                mock.patch("builtins.print"):
            succes = m.Envoyer_lot(messages=messages, afficher_confirmation_envoi=confirmation)
        return succes, d


class ArretApresErreurTests(_Base):
    """MAIL-FAM-02 : 'Arrêter' après une erreur."""

    def _messages(self):
        return [message("a@example.org"), message("b@example.org"), message("c@example.org")]

    def test_caracterisation_mailjet_arreter_sans_compte_rendu(self):
        msgs = self._messages()
        m = self.mailjet([succes_mailjet("a@example.org"), RuntimeError("panne")])
        succes, d = self.lancer(m, msgs, [3])
        self.assertEqual(succes, [msgs[0]])
        self.assertEqual(d.comptes_rendus(), [])   # aucun bilan : c@ jamais tenté, non signalé

    def test_caracterisation_smtp_arreter_sans_compte_rendu(self):
        msgs = self._messages()
        m = self.smtp([1, RuntimeError("panne")])
        succes, d = self.lancer(m, msgs, [3])
        self.assertEqual(succes, [msgs[0]])
        self.assertEqual(d.comptes_rendus(), [])

    def test_caracterisation_reessayer_puis_succes_reste_compte_en_echec(self):
        msgs = self._messages()[:2]
        m = self.mailjet([RuntimeError("panne"), succes_mailjet("a@example.org"), succes_mailjet("b@example.org")])
        succes, d = self.lancer(m, msgs, [0])
        self.assertEqual(succes, msgs)
        texte = d.texte_comptes_rendus()
        self.assertIn(u"a@example.org : panne", texte)   # signalé en échec alors qu'il a été accepté


class ErreursMailjetTests(_Base):
    """MAILJET-ERR-01 : ce que l'utilisateur voit."""

    def _erreur_affichee(self, reponse):
        m = self.mailjet([reponse])
        succes, d = self.lancer(m, [message("a@example.org")], [1])
        self.assertEqual(succes, [])
        return d.erreurs()[0]["detail"]

    def test_caracterisation_status_error(self):
        detail = self._erreur_affichee(reponse_mailjet({"Messages": [{"Status": "error", "Errors": [
            {"ErrorCode": "mj-0013", "StatusCode": 400, "ErrorMessage": "\"x\" is an invalid email address.",
             "ErrorRelatedTo": ["To[0].Email"]}]}]}, status=400))
        self.assertEqual(detail, u"error")

    def test_caracterisation_messages_absent(self):
        detail = self._erreur_affichee(reponse_mailjet({"ErrorIdentifier": "x", "StatusCode": 401,
                                                         "ErrorMessage": "API key authentication/authorization failure."},
                                                        status=401))
        self.assertEqual(detail, u"'Messages'")

    def test_caracterisation_reponse_non_json(self):
        detail = self._erreur_affichee(reponse_mailjet(status=502, json_erreur=ValueError("Expecting value: line 1 column 1 (char 0)")))
        self.assertIn(u"Expecting value", detail)


class HistoriqueTests(unittest.TestCase):
    """MAIL-HIST-01 : l'historique est écrit après le lot entier."""

    def test_caracterisation_pas_de_rappel_par_message(self):
        for classe in (UTILS_Envoi_email.SmtpV2, UTILS_Envoi_email.Mailjet):
            params = inspect.signature(classe.Envoyer_lot).parameters
            self.assertNotIn("callback_succes", params)
        source = (NOETHYS_DIR / "Dlg" / "DLG_Mailer.py").read_text(encoding="utf-8")
        self.assertIn("        if self.listeSucces != False:\n            for message in self.listeSucces :\n"
                      "                self.MemorisationHistorique(message.GetLabelDestinataires(), message.sujet)", source)


class LibellesTests(_Base):
    def test_caracterisation_confirmation_affirme_envoye(self):
        m = self.mailjet([succes_mailjet("a@example.org")])
        succes, d = self.lancer(m, [message("a@example.org")], [])
        self.assertIn(u"L'Email a été envoyé avec succès !", d.texte_comptes_rendus())


if __name__ == "__main__":
    unittest.main()
