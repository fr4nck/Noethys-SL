# -*- coding: utf-8 -*-
"""Tests de caractérisation -- audit réseau des emails sortants (lecture seule).

Ces tests NE CORRIGENT RIEN : ils figent le comportement actuel du code de
production (noethys/Utils/UTILS_Envoi_email.py, noethys/Outils/mail/smtp.py,
noethys/Dlg/DLG_Mailer.py) face à des pannes réseau reproduites avec un
mini-serveur SMTP local (socket + threading, 127.0.0.1 uniquement).

Aucun accès Internet, aucun email réel, aucun secret réel (valeurs factices
"FAUX-..." uniquement). wx est importé (import seul, sans wx.App ni display) ;
les dialogues wx sont remplacés par des doubles.

Un test nommé "test_anomalie_..." réussit lorsque l'anomalie décrite est
PRÉSENTE (caractérisation de l'existant) : il devra être inversé le jour où
l'anomalie sera corrigée.
"""
from __future__ import annotations

import ast
import smtplib
import socket
import sqlite3
import ssl
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

try:
    import wx  # noqa: F401,E402
    from Utils import UTILS_Envoi_email  # noqa: E402
    from Outils.mail import smtp as mail_smtp  # noqa: E402
    from Outils.mail.utils import DNS_NAME  # noqa: E402
    IMPORT_ERREUR = None
except Exception as err:  # pragma: no cover - environnement sans wx
    IMPORT_ERREUR = err

MOT_DE_PASSE_FACTICE = "FAUX-MDP-AUDIT-123"


def setUpModule():
    if IMPORT_ERREUR is not None:
        raise unittest.SkipTest("Import Noethys impossible : %r" % (IMPORT_ERREUR,))
    # Évite un socket.getfqdn() potentiellement lent dans le bac à sable.
    DNS_NAME._fqdn = "localhost"


# ---------------------------------------------------------------------------
# Mini-serveur SMTP local, scriptable
# ---------------------------------------------------------------------------
class MiniSMTP(object):
    """Serveur SMTP minimal (une connexion à la fois).

    comportements_data : liste consommée à chaque fin de DATA ("." reçu) :
      - "ok"      : répond 250 (message accepté) ;
      - "coupe"   : le message est intégralement reçu/compté, puis la
                    connexion est fermée SANS envoyer le 250 ;
      - "silence" : le message est compté, aucune réponse, la connexion
                    reste ouverte jusqu'à ce que le client abandonne.
    Au-delà de la liste : "ok".
    """

    def __init__(self, comportements_data=None, starttls=False, auth=False,
                 refuses=()):
        self.comportements_data = list(comportements_data or [])
        self.starttls = starttls
        self.auth = auth
        self.refuses = set(refuses)
        self.messages = []          # messages dont le DATA est complet
        self.rcpt_refuses = []
        self.commandes = []
        self.connexions = 0
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self._sock.settimeout(0.2)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._boucle, daemon=True)
        self._thread.start()

    def fermer_ecoute(self):
        """Refuse les nouvelles connexions sans couper la session en cours."""
        self._sock.close()

    def arreter(self):
        self._stop.set()
        self._thread.join(5)
        self._sock.close()

    def _boucle(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.connexions += 1
            try:
                self._session(conn)
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def _session(self, conn):
        conn.settimeout(5)
        fichier = conn.makefile("rb")

        def envoyer(ligne):
            conn.sendall(ligne.encode("ascii") + b"\r\n")

        envoyer("220 localhost ESMTP audit")
        while not self._stop.is_set():
            ligne = fichier.readline()
            if not ligne:
                return
            commande = ligne.decode("utf-8", "replace").strip()
            self.commandes.append(commande)
            verbe = commande.split(" ")[0].upper()
            if verbe in ("EHLO", "HELO"):
                lignes = ["250-localhost"]
                if self.starttls:
                    lignes.append("250-STARTTLS")
                if self.auth:
                    lignes.append("250-AUTH PLAIN LOGIN")
                lignes.append("250 8BITMIME")
                for l in lignes:
                    envoyer(l)
            elif verbe == "AUTH":
                envoyer("535 5.7.8 Authentication credentials invalid")
            elif verbe == "MAIL":
                envoyer("250 OK")
            elif verbe == "RCPT":
                adresse = commande.split(":", 1)[1].strip().strip("<>")
                if adresse in self.refuses:
                    self.rcpt_refuses.append(adresse)
                    envoyer("550 5.1.1 Mailbox unavailable")
                else:
                    envoyer("250 OK")
            elif verbe == "DATA":
                envoyer("354 End data with <CR><LF>.<CR><LF>")
                contenu = []
                while True:
                    l = fichier.readline()
                    if not l:
                        return
                    if l in (b".\r\n", b".\n"):
                        break
                    contenu.append(l)
                self.messages.append(b"".join(contenu))
                comportement = self.comportements_data.pop(0) if self.comportements_data else "ok"
                if comportement == "coupe":
                    conn.shutdown(socket.SHUT_RDWR)
                    return
                if comportement == "silence":
                    # On attend que le client abandonne (timeout côté client).
                    while not self._stop.is_set():
                        try:
                            if not conn.recv(1):
                                return
                        except socket.timeout:
                            continue
                        except OSError:
                            return
                    return
                envoyer("250 2.0.0 Ok: queued")
            elif verbe == "RSET" or verbe == "NOOP":
                envoyer("250 OK")
            elif verbe == "QUIT":
                envoyer("221 Bye")
                return
            else:
                envoyer("502 Command not implemented")


def _port_ferme():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class FausseProgressDialog(object):
    def __init__(self, *args, **kwargs):
        self.detruite = False

    def SetSize(self, *a):
        pass

    def CenterOnScreen(self, *a):
        pass

    def SetRange(self, *a):
        pass

    def Update(self, *a, **k):
        return True, False

    def Destroy(self):
        self.detruite = True


class _BaseSMTP(unittest.TestCase):
    timeout_parametre = None

    def setUp(self):
        p = mock.patch.object(UTILS_Envoi_email.UTILS_Parametres, "Parametres",
                              return_value=self.timeout_parametre)
        p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch.object(UTILS_Envoi_email.wx, "ProgressDialog", FausseProgressDialog)
        p2.start()
        self.addCleanup(p2.stop)

    def serveur(self, **kwargs):
        srv = MiniSMTP(**kwargs)
        self.addCleanup(srv.arreter)
        return srv

    def messagerie(self, srv_port, **kwargs):
        params = dict(backend="smtp", hote="127.0.0.1", port=srv_port,
                      utilisateur=None, motdepasse=None,
                      email_exp="expediteur@example.org", nom_exp=u"Accueil Élé",
                      timeout=5, use_tls=0, parametres="notification==0")
        params.update(kwargs)
        return UTILS_Envoi_email.Messagerie(**params)

    @staticmethod
    def message(destinataires=("famille@example.org",), sujet=u"Facture été 2026 – n°12"):
        return UTILS_Envoi_email.Message(
            destinataires=list(destinataires), sujet=sujet,
            texte_html=u"<p>Bonjour, voici votre <b>facture</b> : 12,50 €</p>",
            fichiers=[], images=[])


# ---------------------------------------------------------------------------
# 1. STARTTLS / TLS
# ---------------------------------------------------------------------------
class StartTLSTests(_BaseSMTP):

    @unittest.skipIf(sys.version_info < (3, 12), "keyfile/certfile retirés de smtplib en 3.12")
    def test_anomalie_backend_smtp_starttls_leve_typeerror_python312(self):
        """EMAIL-01 : Outils/mail/smtp.py:68 passe keyfile=/certfile= à
        SMTP.starttls(), paramètres supprimés en Python 3.12."""
        srv = self.serveur(starttls=True)
        backend = mail_smtp.EmailBackend(host="127.0.0.1", port=srv.port, use_tls=True, timeout=5)
        with self.assertRaises(TypeError) as ctx:
            backend.open()
        self.assertIn("keyfile", str(ctx.exception))
        # TypeError n'est pas une SMTPException : pas de filet fail_silently.
        self.assertNotIsInstance(ctx.exception, smtplib.SMTPException)
        # La connexion SMTP (socket TCP) reste ouverte et référencée : aucun
        # close() n'est fait par open() sur ce chemin d'erreur.
        self.assertIsNotNone(backend.connection)
        self.assertIsNotNone(backend.connection.sock)
        backend.connection.close()

    @unittest.skipIf(sys.version_info < (3, 12), "keyfile/certfile retirés de smtplib en 3.12")
    def test_anomalie_moteur_smtp_par_defaut_inutilisable_avec_starttls(self):
        """Parcours réel : Messagerie(backend='smtp', use_tls=1).Connecter()."""
        srv = self.serveur(starttls=True)
        m = self.messagerie(srv.port, use_tls=1, utilisateur="u", motdepasse=MOT_DE_PASSE_FACTICE)
        with self.assertRaises(TypeError):
            m.Connecter()
        self.assertEqual(srv.messages, [])
        # Aucune commande STARTTLS ni AUTH n'a atteint le serveur.
        self.assertFalse(any(c.upper().startswith(("STARTTLS", "AUTH")) for c in srv.commandes))

    def test_anomalie_starttls_sans_verification_de_certificat(self):
        """EMAIL-02 : starttls() sans context => ssl._create_stdlib_context()
        (CERT_NONE, pas de contrôle de nom d'hôte). Ni SmtpV1 ni le backend
        Outils.mail ne fournissent de contexte."""
        ctx = ssl._create_stdlib_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)
        self.assertFalse(ctx.check_hostname)

        source_smtp = (NOETHYS_DIR / "Outils" / "mail" / "smtp.py").read_text(encoding="utf-8")
        self.assertNotIn("create_default_context", source_smtp)
        self.assertNotIn("context=", source_smtp)

        # SmtpV1 : starttls() appelé sans argument.
        faux_smtp = mock.MagicMock()
        with mock.patch.object(UTILS_Envoi_email.smtplib, "SMTP", return_value=faux_smtp):
            m = UTILS_Envoi_email.Messagerie(backend="smtp_obsolete", hote="smtp.example.org", port=587,
                                             utilisateur="u", motdepasse=MOT_DE_PASSE_FACTICE,
                                             email_exp="e@example.org", use_tls=True)
            m.Connecter()
        faux_smtp.starttls.assert_called_once_with()


# ---------------------------------------------------------------------------
# 2. CAS CRITIQUE : DATA reçu par le serveur, confirmation perdue
# ---------------------------------------------------------------------------
class ResultatIncertainTests(_BaseSMTP):

    def test_anomalie_coupure_apres_data_renvoi_automatique_doublon_lot(self):
        """EMAIL-03 : SmtpV2.Envoyer_lot() (UTILS_Envoi_email.py:666-678)
        traite SMTPServerDisconnected par reconnexion + renvoi automatique,
        sans distinguer une coupure APRÈS la fin du DATA."""
        srv = self.serveur(comportements_data=["coupe", "ok"])
        m = self.messagerie(srv.port)
        m.Connecter()
        with mock.patch.object(UTILS_Envoi_email.time, "sleep"):
            succes = m.Envoyer_lot(messages=[self.message()], dlg_progress=None,
                                   afficher_confirmation_envoi=False)
        m.Fermer()
        self.assertEqual(len(succes), 1)
        # Le serveur a reçu DEUX fois le message complet : doublon chez le destinataire.
        self.assertEqual(len(srv.messages), 2)
        self.assertEqual(srv.connexions, 2)
        # Chaque tentative régénère un Message-ID (Outils/mail/message.py:327) :
        # aucune déduplication possible côté serveur/destinataire.
        import re
        ids = [re.search(rb"Message-ID: (<[^>]+>)", m).group(1) for m in srv.messages]
        self.assertNotEqual(ids[0], ids[1])

    def test_anomalie_coupure_apres_data_renvoi_automatique_doublon_unitaire(self):
        """EMAIL-03 : même logique dans le worker unitaire de DLG_Mailer
        (DLG_Mailer.py:467-473)."""
        from Dlg import DLG_Mailer

        class FausseAttente(object):
            def __init__(self, parent, message):
                self.fin = threading.Event()

            def SetEtape(self, message):
                pass

            def Terminer(self):
                self.fin.set()

            def ShowModal(self):
                self.fin.wait(20)

            def Destroy(self):
                pass

        srv = self.serveur(comportements_data=["coupe", "ok"])
        m = self.messagerie(srv.port)
        with mock.patch.object(DLG_Mailer, "_DialogAttenteEnvoi", FausseAttente), \
                mock.patch.object(DLG_Mailer.wx, "CallAfter", lambda f, *a, **k: f(*a, **k)):
            etat = DLG_Mailer.Dialog._ExecuterEnvoiUniqueHorsUI(object(), m, self.message(), None)
        self.assertTrue(etat["succes"])
        self.assertIsNone(etat["erreur"])
        self.assertEqual(len(srv.messages), 2)

    def test_echec_reconnexion_apres_coupure_reste_declare_en_erreur(self):
        """Coupure après DATA puis serveur indisponible : le message (pourtant
        reçu par le serveur) est déclaré en échec, sans mention d'incertitude."""
        srv = self.serveur(comportements_data=["coupe"])
        m = self.messagerie(srv.port)
        m.Connecter()
        srv.fermer_ecoute()  # la reconnexion sera refusée

        class FauxMessagebox(object):
            vus = []

            def __init__(self, *a, **k):
                FauxMessagebox.vus.append(k)

            def ShowModal(self):
                return 1  # "Arrêter" (seul message => boutons Réessayer/Arrêter)

            def Destroy(self):
                pass

        with mock.patch.object(UTILS_Envoi_email.DLG_Messagebox, "Dialog", FauxMessagebox), \
                mock.patch.object(UTILS_Envoi_email.time, "sleep"):
            succes = m.Envoyer_lot(messages=[self.message()], afficher_confirmation_envoi=False)
        self.assertEqual(succes, [])
        self.assertEqual(len(srv.messages), 1)  # reçu malgré tout
        detail = FauxMessagebox.vus[0]["detail"]
        self.assertNotIn(u"incertain", detail.lower())


class TimeoutApresDataTests(_BaseSMTP):
    timeout_parametre = "1"  # paramètre email/timeout = 1 s (prime sur timeout=5)

    def test_anomalie_timeout_attente_250_renvoi_automatique_doublon(self):
        """Un timeout pendant l'attente du 250 devient SMTPServerDisconnected
        dans smtplib.getreply() => renvoi automatique => doublon."""
        srv = self.serveur(comportements_data=["silence", "ok"])
        m = self.messagerie(srv.port)
        self.assertEqual(m.timeout, 1)
        m.Connecter()
        debut = time.time()
        with mock.patch.object(UTILS_Envoi_email.time, "sleep"):
            succes = m.Envoyer_lot(messages=[self.message()], afficher_confirmation_envoi=False)
        m.Fermer()
        self.assertLess(time.time() - debut, 15)
        self.assertEqual(len(succes), 1)
        self.assertEqual(len(srv.messages), 2)


# ---------------------------------------------------------------------------
# 3. Refus de destinataires / erreurs de connexion / authentification
# ---------------------------------------------------------------------------
class DestinatairesEtErreursTests(_BaseSMTP):

    def test_anomalie_acceptation_partielle_multi_destinataires_ignoree(self):
        """EMAIL-05 : Outils/mail/smtp.py:126 ignore le dict des refus renvoyé
        par sendmail() ; SmtpV2.Envoyer() renvoie 1 (succès)."""
        srv = self.serveur(refuses={"refuse@example.org"})
        m = self.messagerie(srv.port)
        m.Connecter()
        resultat = m.Envoyer(self.message(destinataires=["ok@example.org", "refuse@example.org"]))
        m.Fermer()
        self.assertEqual(resultat, 1)
        self.assertEqual(srv.rcpt_refuses, ["refuse@example.org"])
        self.assertEqual(len(srv.messages), 1)

    def test_destinataire_unique_refuse_leve_une_erreur(self):
        srv = self.serveur(refuses={"refuse@example.org"})
        m = self.messagerie(srv.port)
        m.Connecter()
        with self.assertRaises(smtplib.SMTPRecipientsRefused):
            m.Envoyer(self.message(destinataires=["refuse@example.org"]))
        m.Fermer()
        self.assertEqual(srv.messages, [])

    def test_connexion_refusee_leve_oserror_sans_secret(self):
        m = self.messagerie(_port_ferme(), utilisateur="u", motdepasse=MOT_DE_PASSE_FACTICE)
        with self.assertRaises(OSError) as ctx:
            m.Connecter()
        self.assertNotIsInstance(ctx.exception, smtplib.SMTPException)
        self.assertNotIn(MOT_DE_PASSE_FACTICE, str(ctx.exception))

    def test_dns_impossible_leve_gaierror(self):
        m = self.messagerie(25, hote="hote-inexistant.invalid")
        with mock.patch("socket.getaddrinfo", side_effect=socket.gaierror(-2, "Name or service not known")):
            with self.assertRaises(socket.gaierror):
                m.Connecter()

    def test_auth_incorrecte_message_sans_mot_de_passe(self):
        from Dlg import DLG_Mailer
        srv = self.serveur(auth=True)
        m = self.messagerie(srv.port, utilisateur="compte@example.org", motdepasse=MOT_DE_PASSE_FACTICE)
        with self.assertRaises(smtplib.SMTPAuthenticationError) as ctx:
            m.Connecter()
        self.assertNotIn(MOT_DE_PASSE_FACTICE, str(ctx.exception))
        self.assertNotIn(MOT_DE_PASSE_FACTICE, DLG_Mailer._FormateErreurMessagerie(ctx.exception))
        # Le mot de passe a transité en clair-base64 (pas de STARTTLS demandé).
        self.assertTrue(any(c.upper().startswith("AUTH") for c in srv.commandes))

    def test_unicode_sujet_nom_expediteur_et_corps(self):
        srv = self.serveur()
        m = self.messagerie(srv.port)
        m.Connecter()
        self.assertEqual(m.Envoyer(self.message()), 1)
        m.Fermer()
        brut = srv.messages[0]
        self.assertIn(b"Subject: =?utf-8?", brut)
        self.assertIn(b"From: =?utf-8?", brut)

    def test_piece_jointe_absente_echoue_avant_tout_envoi(self):
        srv = self.serveur()
        m = self.messagerie(srv.port)
        m.Connecter()
        msg = self.message()
        msg.fichiers = ["/chemin/inexistant/facture.pdf"]
        with self.assertRaises(FileNotFoundError):
            m.Envoyer(msg)
        m.Fermer()
        self.assertEqual(srv.messages, [])


class PieceJointeTexteTests(unittest.TestCase):
    def test_anomalie_pj_texte_ouverte_sans_encodage_explicite(self):
        """EMAIL-12 : AttacheFichiersJoints() (UTILS_Envoi_email.py:430)
        ouvre les PJ text/* avec open(fichier) sans encoding => encodage
        de la locale (cp1252 sous Windows) pour le sms.txt écrit en UTF-8
        par DLG_Envoi_sms."""
        appels = []
        vrai_open = open

        def open_espion(fichier, *args, **kwargs):
            appels.append((fichier, args, kwargs))
            return vrai_open(fichier, *args, **kwargs)

        import tempfile, os
        rep = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(rep, ignore_errors=True))
        chemin = os.path.join(rep, "sms.txt")
        with vrai_open(chemin, "w", encoding="utf-8") as f:
            f.write(u"T-Réunion à 18h\n#-0600000000")
        msg = UTILS_Envoi_email.Message.__new__(UTILS_Envoi_email.Message)
        msg.fichiers = [chemin]
        conteneur = mock.MagicMock()
        UTILS_Envoi_email.open = open_espion
        try:
            msg.AttacheFichiersJoints(conteneur)
        finally:
            del UTILS_Envoi_email.open
        self.assertEqual(len(appels), 1)
        self.assertEqual(appels[0][1], ())
        self.assertNotIn("encoding", appels[0][2])


# ---------------------------------------------------------------------------
# 4. Mailjet
# ---------------------------------------------------------------------------
class MailjetTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(UTILS_Envoi_email.UTILS_Parametres, "Parametres", return_value="7")
        p.start()
        self.addCleanup(p.stop)
        p2 = mock.patch.object(UTILS_Envoi_email.wx, "ProgressDialog", FausseProgressDialog)
        p2.start()
        self.addCleanup(p2.stop)

    def _mailjet(self):
        return UTILS_Envoi_email.Messagerie(backend="mailjet", email_exp="e@example.org", nom_exp="T",
                                            parametres="api_key==FAUX-CLE##api_secret==FAUX-SECRET")

    def test_timeout_noethys_non_transmis_au_client_mailjet(self):
        m = self._mailjet()
        self.assertEqual(m.timeout, 7)
        with mock.patch("mailjet_rest.Client") as client:
            m.Connecter()
        args, kwargs = client.call_args
        self.assertNotIn("timeout", kwargs)
        self.assertEqual(kwargs.get("version"), "v3.1")

    def test_anomalie_reessayer_apres_timeout_renvoie_le_meme_message(self):
        """EMAIL-04 : après un timeout HTTP (résultat incertain), le bouton
        'Réessayer' re-POST le même message sans avertissement."""
        m = self._mailjet()
        reponse_ok = mock.MagicMock()
        reponse_ok.json.return_value = {"Messages": [{"Status": "success"}]}
        connexion = mock.MagicMock()
        connexion.send.create.side_effect = [TimeoutError("Request to Mailjet API timed out"), reponse_ok]
        m.connection = connexion

        class FauxMessagebox(object):
            def __init__(self, *a, **k):
                self.k = k

            def ShowModal(self):
                return 0  # "Réessayer"

            def Destroy(self):
                pass

        msg = _BaseSMTP.message()
        with mock.patch.object(UTILS_Envoi_email.DLG_Messagebox, "Dialog", FauxMessagebox), \
                mock.patch.object(UTILS_Envoi_email.time, "sleep"), \
                mock.patch("traceback.print_exc"):
            succes = m.Envoyer_lot(messages=[msg], afficher_confirmation_envoi=False)
        self.assertEqual(len(succes), 1)
        self.assertEqual(connexion.send.create.call_count, 2)
        p1 = connexion.send.create.call_args_list[0].kwargs["data"]
        p2 = connexion.send.create.call_args_list[1].kwargs["data"]
        self.assertEqual(p1, p2)

    def test_reponse_inattendue_message_derreur_opaque(self):
        """Réponse HTTP 200 sans clé 'Messages' : l'erreur affichée est
        "'Messages'" (KeyError), la réponse brute est imprimée sur stdout."""
        m = self._mailjet()
        rep = mock.MagicMock()
        rep.status_code = 200
        rep.json.return_value = {"ErrorMessage": "x"}
        m.connection = mock.MagicMock()
        m.connection.send.create.return_value = rep
        with mock.patch("builtins.print"):
            with self.assertRaises(Exception) as ctx:
                m.Envoyer(_BaseSMTP.message())
        self.assertEqual(str(ctx.exception), "'Messages'")

    def test_anomalie_parametres_contenant_egal_egal_font_planter(self):
        with self.assertRaises(ValueError):
            UTILS_Envoi_email.Messagerie(backend="mailjet", email_exp="e@example.org",
                                         parametres="api_key==a##api_secret==b==c")


# ---------------------------------------------------------------------------
# 5. SMS via API HTTP : secret dans le message d'exception
# ---------------------------------------------------------------------------
class SecretDansExceptionHttpTests(unittest.TestCase):
    def test_anomalie_mot_de_passe_ovh_present_dans_le_message_dexception(self):
        """EMAIL-06 : DLG_Envoi_sms.py:1129-1133 met login/mot de passe OVH
        dans la query string d'un requests.get() non protégé. En cas d'échec
        réseau, l'URL complète (donc le mot de passe) figure dans le texte de
        l'exception, non capturée : traceback sur stderr/console (le hook
        UTILS_Rapport_bugs.Activer_rapport_erreurs est commenté dans
        Noethys.py:4603, donc pas de vanilla_crash.log sur ce chemin)."""
        try:
            import requests
        except ImportError:
            self.skipTest("requests absent")
        session = requests.Session()
        session.trust_env = False  # pas de proxy : reproduit l'échec de connexion local
        with self.assertRaises(requests.exceptions.ConnectionError) as ctx:
            session.get("http://127.0.0.1:%d/cgi-bin/sms/http2sms.cgi" % _port_ferme(),
                        params={"account": "sms-faux", "login": "faux",
                                "password": MOT_DE_PASSE_FACTICE, "to": "+33600000000"},
                        timeout=5)
        self.assertIn(MOT_DE_PASSE_FACTICE, str(ctx.exception))

        source = (NOETHYS_DIR / "Dlg" / "DLG_Envoi_sms.py").read_text(encoding="utf-8")
        self.assertIn('"password": self.dictDonnees["ovh_mot_passe"]', source)
        self.assertIn('requests.get(\n                    "https://www.ovh.com/cgi-bin/sms/http2sms.cgi", params=params)', source)


# ---------------------------------------------------------------------------
# 6. État local après envoi
# ---------------------------------------------------------------------------
class EtatLocalTests(unittest.TestCase):
    def test_anomalie_dlg_mailer_listeanomalies_jamais_alimentee(self):
        """EMAIL-07 : DLG_Saisie_reglement.py:1229 juge le succès sur
        dlg2.listeAnomalies, que DLG_Mailer n'alimente jamais."""
        source = (NOETHYS_DIR / "Dlg" / "DLG_Mailer.py").read_text(encoding="utf-8")
        arbre = ast.parse(source)
        affectations = []
        for noeud in ast.walk(arbre):
            cibles = []
            if isinstance(noeud, ast.Assign):
                cibles = noeud.targets
            elif isinstance(noeud, (ast.AugAssign, ast.AnnAssign)):
                cibles = [noeud.target]
            for c in cibles:
                if isinstance(c, ast.Attribute) and c.attr == "listeAnomalies":
                    affectations.append(noeud.lineno)
        self.assertEqual(affectations, [107])
        self.assertNotIn("listeAnomalies.append", source)
        self.assertNotIn("listeAnomalies.extend", source)
        appelant = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_reglement.py").read_text(encoding="utf-8")
        self.assertIn("if len(dlg2.listeAnomalies) == 0 :", appelant)

    def test_anomalie_historique_sql_casse_sur_apostrophe(self):
        """EMAIL-08 : MemorisationHistorique() (DLG_Mailer.py:745-749)
        formate l'adresse dans le SQL : une adresse valide contenant une
        apostrophe casse la requête APRÈS un envoi réussi."""
        from Dlg import DLG_Mailer
        requetes = []

        class FausseDB(object):
            def ExecuterReq(self, req):
                requetes.append(req)

            def ResultatReq(self):
                return []

            def Close(self):
                pass

        with mock.patch.object(DLG_Mailer.GestionDB, "DB", FausseDB):
            DLG_Mailer.Dialog.MemorisationHistorique(object(), adresse="o'brien@example.org", sujet="x")
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE individus (IDindividu INTEGER, mail TEXT, travail_mail TEXT)")
        conn.execute("CREATE TABLE rattachements (IDindividu INTEGER, IDfamille INTEGER)")
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute(requetes[0])

    def test_anomalie_pieces_communes_ajoutees_a_la_liste_du_destinataire(self):
        """EMAIL-09 : DLG_Mailer.Envoyer() (lignes 612-613) fait
        listePieces = track.pieces ; listePieces.extend(communes) : la liste
        du track est mutée, un 2e clic (après échec, ou après Envoyer test)
        duplique les pièces communes."""
        source = (NOETHYS_DIR / "Dlg" / "DLG_Mailer.py").read_text(encoding="utf-8")
        self.assertIn("listePieces = listePiecesPersonnelles\n", source)
        self.assertIn("listePieces.extend(listePiecesCommunes)", source)
        # Démonstration du mécanisme Python sous-jacent :
        track_pieces = ["perso.pdf"]
        for _ in range(2):  # deux clics "Envoyer"
            listePieces = track_pieces
            listePieces.extend(["commune.pdf"])
        self.assertEqual(track_pieces, ["perso.pdf", "commune.pdf", "commune.pdf"])

    def test_anomalie_portail_recu_declare_envoye_sans_tester_le_resultat(self):
        """EMAIL-10 : DLG_Saisie_portail_demande.py:1221-1223 : la réponse
        Connecthys 'Reçu de règlement envoyé par Email.' est fixée quel que
        soit le résultat d'EnvoiEmailFamille()."""
        source = (NOETHYS_DIR / "Dlg" / "DLG_Saisie_portail_demande.py").read_text(encoding="utf-8")
        bloc = ('resultat = UTILS_Envoi_email.EnvoiEmailFamille(parent=dlg_impression, IDfamille=self.track.IDfamille, '
                'nomDoc=nomDoc, categorie=categorie, visible=False, log=self.track)\n'
                '                reponse = _(u"Reçu de règlement envoyé par Email.")')
        self.assertIn(bloc, source)


if __name__ == "__main__":
    unittest.main()
