# -*- coding: utf-8 -*-
"""Lots d'emails (SMTP et Mailjet) : arrêt après erreur (MAIL-FAM-02),
historique (MAIL-HIST-01), erreurs Mailjet (MAILJET-ERR-01).

Aucun email réel : la connexion Mailjet est une doublure, les dialogues wx
sont remplacés. Les défauts caractérisés au commit 96b6ea7 (arrêt sans
bilan, succès après 'Réessayer' listé en échec, erreurs Mailjet opaques,
historique écrit en fin de lot, libellé « envoyé avec succès ») sont ici
vérifiés comme corrigés.
"""
from __future__ import annotations

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
    """MAIL-FAM-02 : 'Arrêter' après une erreur -> bilan en trois catégories."""

    def _messages(self):
        return [message("a@example.org"), message("b@example.org"), message("c@example.org")]

    def _verifier_bilan(self, m, d, msgs):
        self.assertEqual(m.dernier_bilan["acceptes"], [msgs[0]])
        self.assertEqual([x for x, e in m.dernier_bilan["echecs"]], [msgs[1]])
        self.assertEqual(m.dernier_bilan["non_tentes"], [msgs[2]])
        cr = d.comptes_rendus()
        self.assertEqual(len(cr), 1)
        self.assertIn(u"1 en échec, 1 non tenté(s)", cr[0]["introduction"])
        self.assertIn(u"En échec :\n- b@example.org : ", cr[0]["detail"])
        self.assertIn(u"Non tentés (envoi arrêté) :\n- c@example.org", cr[0]["detail"])
        self.assertIn(u"- a@example.org", cr[0]["detail"])

    def test_mailjet_arreter_produit_un_bilan(self):
        msgs = self._messages()
        m = self.mailjet([succes_mailjet("a@example.org"), RuntimeError("panne")])
        succes, d = self.lancer(m, msgs, [3])
        self.assertEqual(succes, [msgs[0]])
        self.assertEqual(m.connection.send.create.call_count, 2)   # c@ jamais tenté
        self._verifier_bilan(m, d, msgs)
        self.assertIn(u"accepté(s) par Mailjet", d.comptes_rendus()[0]["introduction"])

    def test_smtp_arreter_produit_un_bilan(self):
        msgs = self._messages()
        m = self.smtp([1, RuntimeError("panne")])
        succes, d = self.lancer(m, msgs, [3])
        self.assertEqual(succes, [msgs[0]])
        self._verifier_bilan(m, d, msgs)

    def test_reessayer_puis_succes_n_est_plus_compte_en_echec(self):
        msgs = self._messages()[:2]
        m = self.mailjet([RuntimeError("panne"), succes_mailjet("a@example.org"), succes_mailjet("b@example.org")])
        succes, d = self.lancer(m, msgs, [0])
        self.assertEqual(succes, msgs)
        self.assertEqual(m.dernier_bilan["echecs"], [])
        self.assertNotIn(u"panne", d.texte_comptes_rendus())

    def test_continuer_liste_les_echecs_sans_non_tentes(self):
        msgs = self._messages()
        m = self.mailjet([succes_mailjet("a@example.org"), RuntimeError("panne"), succes_mailjet("c@example.org")])
        succes, d = self.lancer(m, msgs, [1])
        self.assertEqual(succes, [msgs[0], msgs[2]])
        self.assertEqual(m.dernier_bilan["non_tentes"], [])
        self.assertIn(u"2 Email(s) accepté(s) par Mailjet, 1 en échec, 0 non tenté(s).", d.texte_comptes_rendus())


class HistoriqueAuFilDeLEauTests(_Base):
    """MAIL-HIST-01 : rappel par message accepté, avant la suite du lot."""

    def test_rappel_appele_des_l_acceptation_meme_si_le_lot_est_arrete(self):
        msgs = [message("a@example.org"), message("b@example.org"), message("c@example.org")]
        m = self.mailjet([succes_mailjet("a@example.org"), RuntimeError("panne")])
        vus = []
        d = Dialogues([3])
        with mock.patch.object(UTILS_Envoi_email.DLG_Messagebox, "Dialog", d.Messagebox), \
                mock.patch.object(UTILS_Envoi_email.wx, "MessageDialog", d.MessageDialog), \
                mock.patch("builtins.print"):
            m.Envoyer_lot(messages=msgs, callback_succes=vus.append)
        self.assertEqual(vus, [msgs[0]])

    def test_rappel_smtp_et_erreur_du_rappel_n_interrompt_pas_le_lot(self):
        msgs = [message("a@example.org"), message("b@example.org")]
        m = self.smtp([1, 1])

        def rappel(msg):
            raise RuntimeError("base indisponible")
        d = Dialogues([])
        with mock.patch.object(UTILS_Envoi_email.DLG_Messagebox, "Dialog", d.Messagebox), \
                mock.patch.object(UTILS_Envoi_email.wx, "MessageDialog", d.MessageDialog), \
                mock.patch("builtins.print"):
            succes = m.Envoyer_lot(messages=msgs, afficher_confirmation_envoi=False, callback_succes=rappel)
        self.assertEqual(succes, msgs)

    def test_dlg_mailer_branche_le_rappel_et_ne_reecrit_plus_en_fin_de_lot(self):
        source = (NOETHYS_DIR / "Dlg" / "DLG_Mailer.py").read_text(encoding="utf-8")
        self.assertIn("callback_succes=MemoriserSucces", source)
        self.assertNotIn("        if self.listeSucces != False:\n            for message in self.listeSucces :", source)

    def test_historique_apostrophe_et_identifiant_mailjet(self):
        from Dlg import DLG_Mailer
        requetes, actions = [], []

        class FausseDB(object):
            def ExecuterReq(self, req):
                requetes.append(req)

            def ResultatReq(self):
                return [(5, 50)]

            def Close(self):
                pass
        msg = message("o'brien@example.org")
        msg.mailjet_ids = [("o'brien@example.org", "uuid-1", 1001)]
        with mock.patch.object(DLG_Mailer.GestionDB, "DB", FausseDB), \
                mock.patch.object(DLG_Mailer.UTILS_Historique, "InsertActions", side_effect=actions.extend):
            DLG_Mailer.Dialog.MemorisationHistorique(object(), "o'brien@example.org", u"Facture", message=msg)
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE individus (IDindividu INTEGER, mail TEXT, travail_mail TEXT)")
        conn.execute("CREATE TABLE rattachements (IDindividu INTEGER, IDfamille INTEGER)")
        conn.execute(requetes[0])   # plus d'erreur SQL
        self.assertEqual(actions[0]["action"], u"Envoi de l'Email 'Facture' (accepté par Mailjet, MessageID 1001)")


class ErreursMailjetTests(_Base):
    """MAILJET-ERR-01 : motif utile, sans secret."""

    def _erreur_affichee(self, reponse):
        m = self.mailjet([reponse])
        succes, d = self.lancer(m, [message("a@example.org")], [1])
        self.assertEqual(succes, [])
        detail = d.erreurs()[0]["detail"]
        for secret in (CLE_FACTICE, SECRET_FACTICE, "Authorization", "Basic "):
            self.assertNotIn(secret, detail)
        return detail

    def test_status_error_affiche_le_motif_mailjet(self):
        detail = self._erreur_affichee(reponse_mailjet({"Messages": [{"Status": "error", "Errors": [
            {"ErrorCode": "mj-0013", "StatusCode": 400, "ErrorMessage": "\"x\" is an invalid email address.",
             "ErrorRelatedTo": ["To[0].Email"]}]}]}, status=400))
        self.assertEqual(detail, u"Mailjet a refusé le message (HTTP 400) : \"x\" is an invalid email address. [mj-0013] (To[0].Email)")

    def test_erreur_globale_401(self):
        detail = self._erreur_affichee(reponse_mailjet({"ErrorIdentifier": "x", "StatusCode": 401,
                                                         "ErrorMessage": "API key authentication/authorization failure."},
                                                        status=401))
        self.assertEqual(detail, u"Mailjet a refusé le message (HTTP 401) : API key authentication/authorization failure.")

    def test_reponse_non_json_5xx(self):
        detail = self._erreur_affichee(reponse_mailjet(status=502, json_erreur=ValueError("Expecting value")))
        self.assertEqual(detail, u"Mailjet a refusé le message (HTTP 502) : <html>Bad Gateway</html>")

    def test_reponse_200_inattendue(self):
        detail = self._erreur_affichee(reponse_mailjet({"Foo": 1}, status=200))
        self.assertEqual(detail, u"Mailjet n'a pas accepté le message : réponse inattendue de Mailjet")

    def test_exception_de_la_bibliotheque_reste_lisible(self):
        """mailjet-rest >= 1.9 lève lui-même ValidationError('Payload validation
        failed: ...') sur un 4xx : le texte est affiché tel quel."""
        detail = self._erreur_affichee(RuntimeError("Payload validation failed: \"x\" is an invalid email address."))
        self.assertIn(u"invalid email address", detail)

    def test_journal_ne_contient_ni_secret_ni_payload(self):
        m = self.mailjet([reponse_mailjet({"Messages": [{"Status": "error", "Errors": [{"ErrorMessage": "refus"}]}]}, status=400)])
        imprime = []
        with mock.patch("builtins.print", side_effect=lambda *a, **k: imprime.append(u" ".join(str(x) for x in a))):
            with self.assertRaises(UTILS_Envoi_email.ErreurMailjet):
                m.Envoyer(message("a@example.org"))
        journal = u"\n".join(imprime)
        self.assertIn(u"refus", journal)
        for interdit in (CLE_FACTICE, SECRET_FACTICE, u"Bonjour", u"Base64Content"):
            self.assertNotIn(interdit, journal)

    def test_identifiants_mailjet_conserves_sur_le_message(self):
        m = self.mailjet([succes_mailjet("a@example.org", uuid="uuid-9", mid=9009)])
        msg = message("a@example.org")
        self.assertEqual(m.Envoyer(msg), u"success")
        self.assertEqual(msg.mailjet_ids, [("a@example.org", "uuid-9", 9009)])


class LibellesTests(_Base):
    """Accepté par le service d'envoi != remis au destinataire."""

    def test_confirmation_mailjet_dit_accepte_et_pas_remis(self):
        m = self.mailjet([succes_mailjet("a@example.org")])
        succes, d = self.lancer(m, [message("a@example.org")], [])
        texte = d.texte_comptes_rendus()
        self.assertIn(u"L'Email a été accepté par Mailjet pour envoi.", texte)
        self.assertIn(u"ne vérifie pas leur remise effective", texte)
        self.assertNotIn(u"envoyé avec succès", texte)

    def test_confirmation_smtp(self):
        m = self.smtp([1, 1])
        succes, d = self.lancer(m, [message("a@example.org"), message("b@example.org")], [])
        self.assertIn(u"Les 2 Emails ont été acceptés par le serveur de messagerie pour envoi.", d.texte_comptes_rendus())

    def test_plus_de_libelle_envoye_avec_succes_dans_les_parcours_email(self):
        for chemin in ("Dlg/DLG_Mailer.py", "Utils/UTILS_Envoi_email.py", "Dlg/DLG_Saisie_portail_demande.py"):
            source = (NOETHYS_DIR / chemin).read_text(encoding="utf-8")
            lignes = [l for l in source.splitlines() if u"envoyé avec succès" in l or u"envoyés avec succès" in l]
            lignes = [l for l in lignes if not l.lstrip().startswith("#")]
            self.assertEqual(lignes, [], chemin)


if __name__ == "__main__":
    unittest.main()
