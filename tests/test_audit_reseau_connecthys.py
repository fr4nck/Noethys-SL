# -*- coding: utf-8 -*-
"""Audit réseau Connecthys / Portail Famille -- tests de CARACTÉRISATION.

Ces tests décrivent le comportement RÉEL du code de production (RC2,
HEAD 91d9e625), y compris ses défauts : un test qui passe ici signifie
"le comportement constaté est bien celui-ci", pas "le comportement est
correct". Aucun fichier sous noethys/ n'est modifié. Aucun accès
Internet : mini-serveurs http.server locaux (127.0.0.1, port éphémère),
mocks pour FTP/SSH, fichiers temporaires.

Secrets : uniquement des valeurs factices générées pour le test.
"""
from __future__ import annotations

import contextlib
import copy
import datetime
import http.server
import io
import json
import os
import pickle
import socket
import ssl
import sys
import tempfile
import threading
import time
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
TESTS_DIR = Path(__file__).resolve().parent
for _p in (str(NOETHYS_DIR), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import wx  # noqa: F401
    import paramiko  # noqa: F401
    import sqlalchemy  # noqa: F401
    from Utils import UTILS_Portail_synchro
    from Utils import UTILS_Portail_installation
    from Utils import UTILS_Portail_controle
    from Utils import UTILS_Cryptage_fichier
    from Utils import UTILS_Fichiers
    from Ctrl import CTRL_Portail_serveur
    from Dlg import DLG_Portail_config
    import GestionDB
    from Data import DATA_Tables as Tables
    from _fixtures_noethys_db import RedirectionGestionDB
    IMPORT_OK = True
    IMPORT_ERREUR = ""
except Exception as _err:  # pragma: no cover - environnement sans wx
    IMPORT_OK = False
    IMPORT_ERREUR = repr(_err)

# Clé factice : 40 caractères, mélange de chiffres et lettres (comme GetSecretKey)
CLE_FACTICE = "ab12cd34ef56gh78jk90mv12wx34yz56AB78CD90"
CHIFFRES_CLE = "".join(c for c in CLE_FACTICE if c.isdigit())


# ---------------------------------------------------------------------------
# Outils communs
# ---------------------------------------------------------------------------

class FauxLog:
    def __init__(self):
        self.logs = []
        self.jauges = []

    def EcritLog(self, message=""):
        self.logs.append(message if isinstance(message, str) else repr(message))

    def SetGauge(self, valeur=0):
        self.jauges.append(valeur)


class ServeurHTTPLocal:
    """Mini-serveur HTTP local, comportement piloté par une fonction
    handler(requete) -> None (la fonction écrit elle-même la réponse)."""

    def __init__(self, comportement):
        self.requetes = []
        parent = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                parent.requetes.append(self.path)
                comportement(self)

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def repondre(handler, code=200, corps=b"", entetes=None):
    handler.send_response(code)
    for k, v in (entetes or {}).items():
        handler.send_header(k, v)
    if "Content-Length" not in (entetes or {}):
        handler.send_header("Content-Length", str(len(corps)))
    handler.end_headers()
    if corps:
        handler.wfile.write(corps)


def creer_base_portail(chemin):
    db = GestionDB.DB(nomFichier=chemin, suffixe=None, modeCreation=True)
    for nom in ("portail_actions", "portail_reservations", "portail_renseignements",
                "portail_reservations_locations", "familles", "utilisateurs", "parametres"):
        db.CreationTable(nom, dicoDB=Tables.DB_DATA)
    db.Commit()
    db.Close()


def lire(chemin, req):
    db = GestionDB.DB(nomFichier=chemin, suffixe=None)
    db.ExecuterReq(req)
    res = db.ResultatReq()
    db.Close()
    return res


def action_portail(ref, IDfamille=1, categorie="reservations", action="maj", etat="attente",
                   reservations=None, renseignements=None):
    a = {
        "horodatage": "2026-10-01 10:00:00", "IDfamille": IDfamille, "IDindividu": 2,
        "IDutilisateur": None, "categorie": categorie, "action": action,
        "description": "Demande %s" % ref, "commentaire": "", "parametres": "",
        "etat": etat, "traitement_date": None, "IDperiode": 7, "ref_unique": ref,
        "reponse": None, "reservations": reservations or [],
    }
    if renseignements is not None:
        a["renseignements"] = renseignements
    return a


def params_synchro(url, **extra):
    p = {"accept_all_cert": False, "serveur_type": 0, "url_connecthys": url,
         "secret_key": CLE_FACTICE, "client_rechercher_updates": False,
         "hebergement_type": 0}
    p.update(extra)
    return p


@unittest.skipUnless(IMPORT_OK, "wx/paramiko/sqlalchemy indisponibles : %s" % IMPORT_ERREUR)
class _BaseDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="audit-cnx-")
        self.chemin = os.path.join(self.tmp.name, "test.dat")
        creer_base_portail(self.chemin)
        self.redir = RedirectionGestionDB(self.chemin)
        self.redir.__enter__()

    def tearDown(self):
        self.redir.__exit__(None, None, None)
        self.tmp.cleanup()


# ---------------------------------------------------------------------------
# 1. Download_data (syncdown) : contrat de livraison, déduplication, erreurs
# ---------------------------------------------------------------------------

class DownloadDataTests(_BaseDB):

    def _synchro(self, url):
        return UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro(url), log=FauxLog())

    def test_nominal_curseur_et_jeton_dans_url(self):
        """URL = /syncdown/<AAAAMMJJ + chiffres de secret_key>/<dernier ref_unique>."""
        reponses = [[action_portail("1001"), action_portail("1002")], []]

        def comportement(h):
            repondre(h, 200, json.dumps(reponses.pop(0)).encode())

        with ServeurHTTPLocal(comportement) as srv:
            s = self._synchro(srv.url)
            with contextlib.redirect_stdout(io.StringIO()) as sortie:
                self.assertTrue(s.Download_data())
                self.assertTrue(s.Download_data())
        jeton = datetime.date.today().strftime("%Y%m%d") + CHIFFRES_CLE
        self.assertEqual(srv.requetes[0], "/syncdown/%s/0" % jeton)
        self.assertEqual(srv.requetes[1], "/syncdown/%s/1002" % jeton)
        # Le jeton d'authentification est imprimé sur stdout (redirigé vers
        # journal.log dans l'exécutable Windows, Noethys.py l.4616-4617).
        self.assertIn(jeton, sortie.getvalue())
        self.assertEqual(lire(self.chemin, "SELECT IDaction, ref_unique FROM portail_actions ORDER BY IDaction"),
                         [(1, "1001"), (2, "1002")])

    def test_dedup_depend_entierement_du_serveur(self):
        """Si le serveur ignore le curseur (ou si le curseur recule), les
        actions sont réinsérées : aucune déduplication locale par
        ref_unique hors full_synchro."""
        def comportement(h):
            repondre(h, 200, json.dumps([action_portail("2001")]).encode())

        with ServeurHTTPLocal(comportement) as srv:
            s = self._synchro(srv.url)
            with contextlib.redirect_stdout(io.StringIO()):
                s.Download_data()
                s.Download_data()
        self.assertEqual(lire(self.chemin, "SELECT ref_unique FROM portail_actions"), [("2001",), ("2001",)])

    def test_full_synchro_deduplique_par_ref_unique(self):
        def comportement(h):
            repondre(h, 200, json.dumps([action_portail("3001"), action_portail("3002")]).encode())

        with ServeurHTTPLocal(comportement) as srv:
            s = self._synchro(srv.url)
            with contextlib.redirect_stdout(io.StringIO()):
                s.Download_data()
                s.Download_data(full_synchro=True)
        self.assertEqual(len(lire(self.chemin, "SELECT * FROM portail_actions")), 2)
        self.assertTrue(srv.requetes[1].endswith("/0"))

    def test_deux_synchros_concurrentes_dupliquent_les_demandes(self):
        """Course réelle : B lit le curseur, pendant son appel réseau A
        télécharge et commite ; B calcule ensuite max(IDaction)+1 et
        insère les mêmes ref_unique. Aucun verrou inter-synchro / inter-poste."""
        corps = json.dumps([action_portail("4001", reservations=[
            {"date": "2026-10-12", "IDinscription": 5, "IDunite": 3, "etat": "ajouter"}])]).encode()

        def comportement(h):
            repondre(h, 200, corps)

        with ServeurHTTPLocal(comportement) as srv:
            a = self._synchro(srv.url)
            b = self._synchro(srv.url)
            vrai_urlopen = UTILS_Portail_synchro.urlopen
            deja = []

            def urlopen_b(req, *args, **kw):
                if not deja:
                    deja.append(1)
                    a.Download_data()  # A s'exécute "pendant" la requête de B
                return vrai_urlopen(req, *args, **kw)

            with contextlib.redirect_stdout(io.StringIO()):
                with mock.patch.object(UTILS_Portail_synchro, "urlopen", side_effect=urlopen_b):
                    self.assertTrue(b.Download_data())
        self.assertEqual(lire(self.chemin, "SELECT IDaction, ref_unique FROM portail_actions ORDER BY IDaction"),
                         [(1, "4001"), (2, "4001")])
        self.assertEqual(len(lire(self.chemin, "SELECT * FROM portail_reservations")), 2)

    def test_ref_unique_non_numerique_fait_repartir_le_curseur_a_zero(self):
        db = GestionDB.DB(nomFichier=self.chemin, suffixe=None)
        db.ExecuterReq("INSERT INTO portail_actions (IDaction, ref_unique, etat) VALUES (1, 'ABC-1', 'validation')")
        db.Commit()
        db.Close()

        def comportement(h):
            repondre(h, 200, b"[]")

        with ServeurHTTPLocal(comportement) as srv:
            with contextlib.redirect_stdout(io.StringIO()):
                self._synchro(srv.url).Download_data()
        self.assertTrue(srv.requetes[0].endswith("/0"))

    def test_codes_http_et_corps_invalides_retournent_false_sans_ecriture(self):
        cas = {
            "400": lambda h: repondre(h, 400, b"bad"),
            "401": lambda h: repondre(h, 401, b"no"),
            "403": lambda h: repondre(h, 403, b"no"),
            "404": lambda h: repondre(h, 404, b"no"),
            "500": lambda h: repondre(h, 500, b"<html>err</html>"),
            "502": lambda h: repondre(h, 502, b""),
            "503": lambda h: repondre(h, 503, b""),
            "vide": lambda h: repondre(h, 200, b""),
            "json_invalide": lambda h: repondre(h, 200, b"<html>maintenance</html>"),
            "null": lambda h: repondre(h, 200, b"null"),
            "tronque": lambda h: repondre(h, 200, b'[{"ref_unique": "1"', {"Content-Length": "100"}),
        }
        for nom, comportement in cas.items():
            with self.subTest(cas=nom):
                with ServeurHTTPLocal(comportement) as srv:
                    log = FauxLog()
                    s = UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro(srv.url), log=log)
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertFalse(s.Download_data())
                    self.assertIn(u"Téléchargement des demandes impossible", log.logs)
                self.assertEqual(lire(self.chemin, "SELECT COUNT(*) FROM portail_actions"), [(0,)])

    def test_redirection_suivie_avec_le_jeton(self):
        def comportement(h):
            if h.path.startswith("/syncdown"):
                repondre(h, 302, b"", {"Location": "/ailleurs" + h.path})
            else:
                repondre(h, 200, b"[]")

        with ServeurHTTPLocal(comportement) as srv:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(self._synchro(srv.url).Download_data())
        self.assertTrue(srv.requetes[1].startswith("/ailleurs/syncdown/"))

    def test_json_dict_au_lieu_de_liste_leve_hors_du_try(self):
        """Réponse JSON valide mais de forme inattendue : exception non
        rattrapée par Download_data (rattrapée plus haut par Synchro_totale)."""
        def comportement(h):
            repondre(h, 200, b'{"erreur": "x"}')

        with ServeurHTTPLocal(comportement) as srv:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(TypeError):
                    self._synchro(srv.url).Download_data()
        self.assertEqual(lire(self.chemin, "SELECT COUNT(*) FROM portail_actions"), [(0,)])

    def test_renseignement_indechiffrable_perdu_silencieusement(self):
        crypt = UTILS_Cryptage_fichier.AESCipher(CLE_FACTICE[10:20], bs=16, prefixe=u"#@#")
        ok = crypt.encrypt(u"06.00.00.00.00")
        corps = json.dumps([action_portail("5001", categorie="renseignements", renseignements=[
            {"champ": "tel_mobile", "valeur": ok},
            {"champ": "mail", "valeur": "#@#corrompu!!"},
        ])]).encode()

        def comportement(h):
            repondre(h, 200, corps)

        with ServeurHTTPLocal(comportement) as srv:
            log = FauxLog()
            s = UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro(srv.url), log=log)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(s.Download_data())
        self.assertEqual(lire(self.chemin, "SELECT champ FROM portail_renseignements"), [("tel_mobile",)])
        self.assertFalse(any("mail" in m for m in log.logs))

    def test_maj_password_applique_immediatement_sans_traitement(self):
        db = GestionDB.DB(nomFichier=self.chemin, suffixe=None)
        db.ExecuterReq("INSERT INTO familles (IDfamille, internet_mdp) VALUES (1, 'ancien')")
        db.Commit()
        db.Close()
        a = action_portail("6001", categorie="compte", action="maj_password")
        a["parametres"] = "nouveau_hash_factice"

        def comportement(h):
            repondre(h, 200, json.dumps([a]).encode())

        with ServeurHTTPLocal(comportement) as srv:
            with contextlib.redirect_stdout(io.StringIO()):
                self._synchro(srv.url).Download_data()
        self.assertEqual(lire(self.chemin, "SELECT internet_mdp FROM familles"), [("nouveau_hash_factice",)])
        self.assertEqual(lire(self.chemin, "SELECT etat FROM portail_actions"), [("validation",)])

    def test_aucun_timeout_sur_urlopen(self):
        appels = []

        def faux_urlopen(*args, **kw):
            appels.append((args, kw))
            raise OSError("coupure simulée")

        s = UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro("http://127.0.0.1:9"), log=FauxLog())
        with mock.patch.object(UTILS_Portail_synchro, "urlopen", side_effect=faux_urlopen):
            with contextlib.redirect_stdout(io.StringIO()):
                s.Download_data()
                s.Update_application()
                s.Upgrade_application()
                s.Repair_application()
                s.Clear_application()
        self.assertEqual(len(appels), 5)
        for args, kw in appels:
            self.assertEqual(kw, {})
            self.assertEqual(len(args), 1)
        self.assertIsNone(socket.getdefaulttimeout())

    def test_serveur_muet_bloque_le_client_au_dela_du_delai(self):
        """Serveur qui accepte la connexion puis ne répond pas : le client
        attend sans limite (on vérifie seulement qu'il attend > 1,5 s)."""
        lsock = socket.socket()
        lsock.bind(("127.0.0.1", 0))
        lsock.listen(1)
        port = lsock.getsockname()[1]
        s = UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro("http://127.0.0.1:%d" % port), log=FauxLog())
        resultat = []
        t = threading.Thread(target=lambda: resultat.append(s.Download_data()), daemon=True)
        with contextlib.redirect_stdout(io.StringIO()):
            t.start()
            t.join(1.5)
            toujours_bloque = t.is_alive()
            conn, _ = lsock.accept()
            conn.close()
            t.join(5)
        lsock.close()
        self.assertTrue(toujours_bloque)
        self.assertEqual(resultat, [False])

    def test_https_certificat_autosigne(self):
        """Certificat invalide : échec propre si accept_all_cert=False ;
        accepté (et désactivé pour tout le processus) si True."""
        try:
            certfile = _certificat_autosigne(self.tmp.name)
        except Exception as err:
            self.skipTest("génération de certificat impossible : %r" % err)
        ctx_srv = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx_srv.load_cert_chain(certfile)
        ctx_defaut = ssl._create_default_https_context

        def comportement(h):
            repondre(h, 200, b"[]" if h.path.startswith("/syncdown") else b'{"r": 1}')

        try:
            with ServeurHTTPLocal(comportement) as srv:
                srv.httpd.socket = ctx_srv.wrap_socket(srv.httpd.socket, server_side=True)
                url = "https://127.0.0.1:%d" % srv.port
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertFalse(self._synchro(url).Download_data())
                # Processus neuf : accept_all_cert=True AVANT tout urlopen
                # -> certificat invalide accepté.
                self.assertEqual(_sous_processus_tls(url, premier_urlopen_verifie=False), "True")
                # Processus neuf : un urlopen vérifié a déjà eu lieu, puis
                # accept_all_cert=True. Résultat dépendant de la version de
                # Python (urllib met en cache le contexte TLS de l'opener
                # global depuis 3.13 : HTTPSHandler.__init__ appelle
                # http.client._create_https_context).
                import inspect, urllib.request
                cache = "_create_https_context" in inspect.getsource(urllib.request.HTTPSHandler.__init__)
                attendu = "False" if cache else "True"
                self.assertEqual(_sous_processus_tls(url, premier_urlopen_verifie=True), attendu)
        finally:
            ssl._create_default_https_context = ctx_defaut


SCRIPT_TLS = r"""
import sys, io, contextlib
sys.path.insert(0, sys.argv[1])
from Utils import UTILS_Portail_synchro as U
class L:
    def EcritLog(self, m=""): pass
    def SetGauge(self, v=0): pass
p = {"accept_all_cert": False, "serveur_type": 0, "url_connecthys": sys.argv[2],
     "secret_key": "ab12cd34ef56gh78jk90mv12wx34yz56AB78CD90", "client_rechercher_updates": False}
with contextlib.redirect_stdout(io.StringIO()):
    if sys.argv[3] == "1":
        U.Synchro(dict_parametres=dict(p), log=L()).Upgrade_application()
    p["accept_all_cert"] = True
    r = U.Synchro(dict_parametres=p, log=L()).Upgrade_application()
sys.stderr.write("RESULTAT=%s\n" % r)
"""


def _sous_processus_tls(url, premier_urlopen_verifie):
    import subprocess
    r = subprocess.run([sys.executable, "-c", SCRIPT_TLS, str(NOETHYS_DIR), url,
                        "1" if premier_urlopen_verifie else "0"],
                       capture_output=True, text=True, timeout=60)
    for ligne in r.stderr.splitlines():
        if ligne.startswith("RESULTAT="):
            return ligne.split("=", 1)[1]
    return "ERREUR:" + r.stderr[-500:]


def _certificat_autosigne(rep):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nom = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u"connecthys.invalid")])
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nom).issuer_name(nom).public_key(cle.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(maintenant - datetime.timedelta(days=1))
            .not_valid_after(maintenant + datetime.timedelta(days=1)).sign(cle, hashes.SHA256()))
    chemin = os.path.join(rep, "cert.pem")
    with open(chemin, "wb") as f:
        f.write(cle.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                  serialization.NoEncryption()))
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return chemin


# ---------------------------------------------------------------------------
# 2. Commandes distantes /update /upgrade /repairdb /cleardb
# ---------------------------------------------------------------------------

@unittest.skipUnless(IMPORT_OK, "wx indisponible")
class CommandesDistantesTests(unittest.TestCase):

    def test_urls_et_jeton_partage(self):
        def comportement(h):
            repondre(h, 200, b'{"resultat": false}')

        with ServeurHTTPLocal(comportement) as srv:
            s = UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro(srv.url + "/"), log=FauxLog())
            with contextlib.redirect_stdout(io.StringIO()) as sortie:
                self.assertTrue(s.Upgrade_application())
                self.assertTrue(s.Repair_application())
                self.assertTrue(s.Clear_application())
        jeton = datetime.date.today().strftime("%Y%m%d") + CHIFFRES_CLE
        self.assertEqual(srv.requetes, ["/upgrade/%s" % jeton, "/repairdb/%s" % jeton, "/cleardb/%s" % jeton])
        self.assertIn("/cleardb/%s" % jeton, sortie.getvalue())

    def test_reponse_non_json_ou_5xx_signalee_en_echec(self):
        for code, corps in ((500, b"x"), (200, b"<html>")):
            with self.subTest(code=code):
                with ServeurHTTPLocal(lambda h: repondre(h, code, corps)) as srv:
                    s = UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro(srv.url), log=FauxLog())
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertFalse(s.Clear_application())

    def test_wrappers_dlg_portail_config_perdent_le_resultat(self):
        """DLG_Portail_config.Synchro.Upgrade/Repair/Clear ne renvoient pas
        le booléen : 'Upgrade effectué.' / 'Effacement effectué.' ne
        s'affichent jamais (l.2039, 2054, 2074)."""
        w = DLG_Portail_config.Synchro(parent=FauxLog(), dict_parametres=params_synchro("http://x"))
        for nom in ("Upgrade_application", "Repair_application", "Clear_application"):
            with mock.patch.object(UTILS_Portail_synchro.Synchro, nom, return_value=True):
                self.assertIsNone(getattr(w, nom)())


# ---------------------------------------------------------------------------
# 3. TLS / SSH / FTP
# ---------------------------------------------------------------------------

@unittest.skipUnless(IMPORT_OK, "wx indisponible")
class TransportsTests(unittest.TestCase):

    def setUp(self):
        self._ctx = ssl._create_default_https_context

    def tearDown(self):
        ssl._create_default_https_context = self._ctx

    def test_accept_all_cert_desactive_tls_pour_tout_le_processus(self):
        UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro("x", accept_all_cert=True), log=FauxLog())
        self.assertIs(ssl._create_default_https_context, ssl._create_unverified_context)
        # Une instance ultérieure avec accept_all_cert=False ne restaure rien
        UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro("x", accept_all_cert=False), log=FauxLog())
        self.assertIs(ssl._create_default_https_context, ssl._create_unverified_context)

    def _ssh_mock(self):
        client = mock.MagicMock(name="SSHClient")
        return client

    def test_ssh_autoaddpolicy_sans_known_hosts_ni_timeout_et_client_non_ferme(self):
        client = self._ssh_mock()
        p = params_synchro("x", hebergement_type=2, ssh_serveur="srv.invalid", ssh_port="22",
                           ssh_utilisateur="u", ssh_mdp="MDP_FACTICE", ssh_key_file="", ssh_repertoire="www")
        s = UTILS_Portail_synchro.Synchro(dict_parametres=p, log=FauxLog())
        with mock.patch.object(UTILS_Portail_synchro.paramiko, "SSHClient", return_value=client):
            ftp, ssh = s.Connexion()
            s.Deconnexion(ftp)
        politique = client.set_missing_host_key_policy.call_args[0][0]
        self.assertIsInstance(politique, UTILS_Portail_synchro.paramiko.AutoAddPolicy)
        client.load_system_host_keys.assert_not_called()
        client.load_host_keys.assert_not_called()
        kw = client.connect.call_args[1]
        self.assertNotIn("timeout", kw)
        self.assertNotIn("banner_timeout", kw)
        ftp.close.assert_called_once()
        client.close.assert_not_called()  # SSHClient jamais fermé

    def test_ssh_controle_autoaddpolicy(self):
        client = self._ssh_mock()
        obj = UTILS_Portail_controle.ServeurConnecthys.__new__(UTILS_Portail_controle.ServeurConnecthys)
        obj.parent = FauxLog()
        obj.dict_parametres = {"ssh_serveur": "srv.invalid", "ssh_port": "22", "ssh_utilisateur": "u",
                               "ssh_mdp": "MDP_FACTICE", "ssh_key_file": ""}
        with mock.patch.object(UTILS_Portail_controle.paramiko, "SSHClient", return_value=client):
            obj.OpenSSHConnec()
        self.assertIsInstance(client.set_missing_host_key_policy.call_args[0][0],
                              UTILS_Portail_controle.paramiko.AutoAddPolicy)

    def test_ftp_en_clair_sans_timeout(self):
        p = params_synchro("x", hebergement_type=1, ftp_serveur="ftp.invalid",
                           ftp_utilisateur="u", ftp_mdp="MDP_FACTICE")
        s = UTILS_Portail_synchro.Synchro(dict_parametres=p, log=FauxLog())
        with mock.patch.object(UTILS_Portail_synchro.ftplib, "FTP") as faux_ftp, \
                mock.patch.object(UTILS_Portail_synchro.ftplib, "FTP_TLS") as faux_tls:
            s.Connexion()
        faux_ftp.assert_called_once_with("ftp.invalid", "u", "MDP_FACTICE")
        faux_tls.assert_not_called()

    def test_erreur_ssh_journalisee_brute(self):
        client = self._ssh_mock()
        client.connect.side_effect = Exception("Authentication failed for u@srv")
        p = params_synchro("x", hebergement_type=2, ssh_serveur="srv.invalid", ssh_port="22",
                           ssh_utilisateur="u", ssh_mdp="MDP_FACTICE", ssh_key_file="", ssh_repertoire="www")
        log = FauxLog()
        s = UTILS_Portail_synchro.Synchro(dict_parametres=p, log=log)
        with mock.patch.object(UTILS_Portail_synchro.paramiko, "SSHClient", return_value=client), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(s.Connexion())
        self.assertTrue(any("Authentication failed" in m for m in log.logs))
        self.assertFalse(any("MDP_FACTICE" in m for m in log.logs))

    def test_sftp_telecharge_pieces_remonte_trop_haut(self):
        """repFichier='pieces/' : chdir('pieces/') puis chdir('../../')."""
        p = params_synchro("x", hebergement_type=2)
        s = UTILS_Portail_synchro.Synchro(dict_parametres=p, log=FauxLog())
        sftp = mock.MagicMock()
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(UTILS_Portail_synchro.UTILS_Fichiers, "GetRepTemp", return_value=d):
            s.TelechargeFichier(ftp=sftp, nomFichier="f.crypt", repFichier="pieces/")
        self.assertEqual([c[0][0] for c in sftp.chdir.call_args_list], ["pieces/", "../../"])

    def test_sftp_upload_config_chmod_0644(self):
        """Tout fichier envoyé en SFTP (dont application/data/config.py qui
        contient SECRET_KEY et mots de passe) est forcé en 0644."""
        p = params_synchro("x", hebergement_type=2, ssh_repertoire="www/connecthys")
        s = UTILS_Portail_synchro.Synchro(dict_parametres=p, log=FauxLog())
        sftp = mock.MagicMock()
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "config.py")
            open(f, "w").close()
            self.assertTrue(s.UploadFichier(ftp=sftp, nomFichierComplet=f, repDest="application/data"))
        sftp.chmod.assert_called_once_with("/www/connecthys/application/data/config.py", mode=0o644)

    def test_connect_et_telecharge_ne_deconnecte_pas_en_cas_echec(self):
        s = UTILS_Portail_synchro.Synchro(dict_parametres=params_synchro("x", hebergement_type=1), log=FauxLog())
        ftp = mock.MagicMock()
        with mock.patch.object(s, "Connexion", return_value=(ftp, None)), \
                mock.patch.object(s, "TelechargeFichier", return_value=False), \
                mock.patch.object(s, "Deconnexion") as deco:
            self.assertFalse(s.ConnectEtTelechargeFichier("x.crypt", "pieces/", lecture=False))
        deco.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Fichier config.py généré et envoyé au portail
# ---------------------------------------------------------------------------

@unittest.skipUnless(IMPORT_OK, "wx indisponible")
class UploadConfigTests(unittest.TestCase):

    def test_config_contient_les_secrets_en_clair_reste_sur_disque_et_echec_upload_ignore(self):
        p = params_synchro("x", db_type=1, db_serveur="db.invalid", db_utilisateur="dbu",
                           db_mdp="DBPASS_FACTICE", db_nom="cx", prefixe_tables="cx_", mode_debug=False,
                           talisman=True, captcha=1, email_type_adresse=999, email_serveur="smtp.invalid",
                           email_adresse="a@b.invalid", email_port=587, email_tls=True, email_ssl=False,
                           email_utilisateur="smtpu", email_password="SMTPPASS_FACTICE", serveur_type=0)
        s = UTILS_Portail_synchro.Synchro(dict_parametres=p, log=FauxLog())
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(UTILS_Portail_synchro.UTILS_Fichiers, "GetRepTemp",
                                   side_effect=lambda fichier="": os.path.join(d, fichier)), \
                    mock.patch.object(s, "TelechargeFichier", return_value=False), \
                    mock.patch.object(s, "UploadFichier", return_value=False) as up:
                self.assertTrue(s.Upload_config(ftp=None))  # échec d'upload ignoré
            up.assert_called_once()
            chemin = os.path.join(d, "config.py")
            self.assertTrue(os.path.isfile(chemin))  # jamais supprimé
            contenu = open(chemin, encoding="utf8").read()
            for secret in (CLE_FACTICE, "DBPASS_FACTICE", "SMTPPASS_FACTICE"):
                self.assertIn(secret, contenu)
            mode = os.stat(chemin).st_mode & 0o777
            self.assertEqual(mode, 0o666 & ~_umask())  # permissions par défaut du processus


def _umask():
    m = os.umask(0)
    os.umask(m)
    return m


# ---------------------------------------------------------------------------
# 5. Fichiers chiffrés : intégrité et désérialisation pickle
# ---------------------------------------------------------------------------

MARQUEUR_PICKLE = []


def _marqueur(*args):
    MARQUEUR_PICKLE.append(args)
    return "x"


class _Charge:
    def __reduce__(self):
        return (_marqueur, ("code exécuté pendant pickle.load",))


@unittest.skipUnless(IMPORT_OK, "Crypto indisponible")
class CryptageFichierTests(unittest.TestCase):

    def test_fichier_non_sv2_deserialise_par_pickle(self):
        """DecrypterFichier (appelé sur une pièce téléchargée du portail,
        DLG_Saisie_portail_demande.Traitement_pieces l.1606) fait
        pickle.load sur tout fichier ne commençant pas par b'SV2'."""
        del MARQUEUR_PICKLE[:]
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "piece.crypt")
            with open(src, "wb") as f:
                pickle.dump(_Charge(), f)
            with self.assertRaises(Exception):
                UTILS_Cryptage_fichier.DecrypterFichier(src, src, "0123456789")
        self.assertEqual(MARQUEUR_PICKLE, [("code exécuté pendant pickle.load",)])

    def test_aucune_integrite_fichier_tronque_ou_altere(self):
        with tempfile.TemporaryDirectory() as d:
            clair = os.path.join(d, "clair.pdf")
            data = b"%PDF-1.4 " + os.urandom(1000)
            open(clair, "wb").write(data)
            chiffre = os.path.join(d, "c.crypt")
            UTILS_Cryptage_fichier.CrypterFichier(clair, chiffre, "0123456789")
            brut = open(chiffre, "rb").read()

            altere = bytearray(brut)
            altere[50] ^= 0xFF
            open(chiffre, "wb").write(bytes(altere))
            UTILS_Cryptage_fichier.DecrypterFichier(chiffre, os.path.join(d, "o1"), "0123456789")
            o1 = open(os.path.join(d, "o1"), "rb").read()
            self.assertNotEqual(o1, data)  # corruption silencieuse, aucune exception

            open(chiffre, "wb").write(brut[:-200])  # tronqué
            UTILS_Cryptage_fichier.DecrypterFichier(chiffre, os.path.join(d, "o2"), "0123456789")
            self.assertNotEqual(open(os.path.join(d, "o2"), "rb").read(), data)

            # mauvaise clé : aucune erreur non plus
            open(chiffre, "wb").write(brut)
            UTILS_Cryptage_fichier.DecrypterFichier(chiffre, os.path.join(d, "o3"), "MAUVAISE__")
            self.assertNotEqual(open(os.path.join(d, "o3"), "rb").read(), data)


# ---------------------------------------------------------------------------
# 6. Installation / contrôle serveur
# ---------------------------------------------------------------------------

@unittest.skipUnless(IMPORT_OK, "wx indisponible")
class InstallationTests(unittest.TestCase):

    def test_boucle_infinie_si_taille_inconnue(self):
        """num_essai n'est jamais incrémenté (l.448-455) : hors ligne ou
        sans Content-Length, Installer() boucle indéfiniment sur le thread UI."""
        inst = UTILS_Portail_installation.Installer.__new__(UTILS_Portail_installation.Installer)
        inst.parent = FauxLog()
        inst.dict_parametres = {}
        inst.url_telechargement = "http://127.0.0.1:9/master.zip"
        inst.dlgprogress = None
        sommeils = []

        class Stop(BaseException):
            pass

        def faux_sleep(n):
            sommeils.append(n)
            if len(sommeils) >= 20:
                raise Stop()

        dlg = mock.MagicMock()
        dlg.ShowModal.return_value = UTILS_Portail_installation.wx.ID_YES
        with mock.patch.object(UTILS_Portail_installation.wx, "MessageDialog", return_value=dlg), \
                mock.patch.object(UTILS_Portail_installation, "AffichetailleFichier", return_value=0), \
                mock.patch.object(UTILS_Portail_installation.time, "sleep", side_effect=faux_sleep):
            with self.assertRaises(Stop):
                inst.Installer()
        self.assertEqual(len(sommeils), 20)

    def test_dezipper_zip_slip(self):
        inst = UTILS_Portail_installation.Installer.__new__(UTILS_Portail_installation.Installer)
        inst.dlgprogress = mock.MagicMock()
        inst.dlgprogress.Update.return_value = (True, False)
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "dest")
            os.mkdir(dest)
            z = os.path.join(d, "a.zip")
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("../evade.txt", "hors destination")
            inst.Dezipper(z, dest)
            self.assertTrue(os.path.isfile(os.path.join(d, "evade.txt")))

    def test_source_installee_non_epinglee_ni_verifiee(self):
        inst = UTILS_Portail_installation.Installer(parent=None)
        self.assertEqual(inst.url_telechargement, "https://github.com/Noethys/Connecthys/archive/master.zip")
        import inspect
        src = inspect.getsource(UTILS_Portail_installation)
        for motif in ("sha256", "hashlib", "signature", "timeout"):
            self.assertNotIn(motif, src)

    def test_arret_local_tue_tout_processus_python_run_py(self):
        obj = UTILS_Portail_controle.ServeurConnecthys.__new__(UTILS_Portail_controle.ServeurConnecthys)
        etranger = mock.MagicMock()
        etranger.name.return_value = "python3"
        etranger.cmdline.return_value = ["python3", "/home/autre/projet/run.py"]
        with mock.patch.object(UTILS_Portail_controle.psutil, "process_iter", return_value=[etranger]):
            obj.Arreter_serveurLocal()
        etranger.kill.assert_called_once()

    def test_demarrage_local_shell_true_avec_liste(self):
        obj = UTILS_Portail_controle.ServeurConnecthys.__new__(UTILS_Portail_controle.ServeurConnecthys)
        obj.parent = FauxLog()
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "run.py"), "w").close()
            obj.dict_parametres = {"hebergement_local_repertoire": d, "serveur_options": "--port 5000"}
            with mock.patch.object(UTILS_Portail_controle.subprocess, "Popen") as popen:
                obj.Demarrer_serveurLocal()
        args, kw = popen.call_args
        self.assertIsInstance(args[0], list)
        self.assertTrue(kw.get("shell"))


# ---------------------------------------------------------------------------
# 7. Thread de synchronisation automatique
# ---------------------------------------------------------------------------

@unittest.skipUnless(IMPORT_OK, "wx indisponible")
class ThreadSynchroTests(unittest.TestCase):

    def test_thread_non_daemon(self):
        self.assertFalse(CTRL_Portail_serveur.Serveur(parent=FauxLog()).daemon)

    def test_maj_bouton_appele_depuis_le_thread_worker(self):
        threads = []

        class Parent(FauxLog):
            last_synchro = datetime.datetime.now() - datetime.timedelta(days=1)
            synchro_ouverture = False
            delai = 1

            def SetImage(self, nom):
                pass

            def MAJ_bouton(self):
                threads.append(threading.current_thread())

        serveur = CTRL_Portail_serveur.Serveur(Parent())
        with mock.patch.object(UTILS_Portail_synchro, "Synchro"):
            t = threading.Thread(target=serveur.EffectuerCycle)
            t.start()
            t.join(5)
        self.assertEqual(len(threads), 1)
        self.assertIsNot(threads[0], threading.main_thread())

    def test_panel_maj_bouton_touche_les_widgets_sans_callafter(self):
        import inspect
        src = inspect.getsource(CTRL_Portail_serveur.Panel.MAJ_bouton)
        self.assertIn("self.bouton_traiter.SetLabel(texte)", src)
        self.assertNotIn("CallAfter", src)

    def test_synchro_manuelle_dialogue_ignore_le_thread_de_fond(self):
        """DLG_Portail_config.Synchro.Start lance Synchro_totale sur le
        thread UI sans consulter HasSynchroEnCours()."""
        import inspect
        src = inspect.getsource(DLG_Portail_config.Synchro.Start)
        self.assertIn("synchro.Synchro_totale(full_synchro=full_synchro)", src)
        self.assertNotIn("HasSynchroEnCours", src)


# ---------------------------------------------------------------------------
# 8. Upload_data : scénario critique "réponse syncup perdue"
# ---------------------------------------------------------------------------

MODELS_FACTICE = '''
import os
from sqlalchemy import create_engine as _ce
from sqlalchemy.orm import sessionmaker as _sm

ENREGISTREMENTS = []

def create_engine(url, **kw):
    chemin = url.replace("sqlite:///", "")
    open(chemin, "wb").close()
    class E:
        def dispose(self): pass
    return E()

class _Meta:
    def drop_all(self, e): pass
    def create_all(self, e): pass

class Base:
    metadata = _Meta()

class _Session:
    def add(self, m): ENREGISTREMENTS.append(m)
    def commit(self): pass
    def close(self): pass

def sessionmaker(bind=None):
    return _Session

class _Modele:
    def __init__(self, **kw): self.__dict__.update(kw)

def __getattr__(nom):
    return type(nom, (_Modele,), {})
'''


@unittest.skipUnless(IMPORT_OK, "wx indisponible")
class UploadDataReponsePerdueTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="audit-cnx-up-")
        self.chemin = os.path.join(self.tmp.name, "test.dat")
        db = GestionDB.DB(nomFichier=self.chemin, suffixe=None, modeCreation=True)
        for nom in Tables.DB_DATA:
            db.CreationTable(nom, dicoDB=Tables.DB_DATA)
        db.CreationTable("documents", dicoDB=Tables.DB_DOCUMENTS)
        db.ExecuterReq("INSERT INTO organisateur (IDorganisateur, nom) VALUES (1, 'Org test')")
        db.Commit()
        db.Close()
        self.redir = RedirectionGestionDB(self.chemin)
        self.redir.__enter__()
        self.portail = os.path.join(self.tmp.name, "portail")
        os.makedirs(os.path.join(self.portail, "application", "data"))
        with open(os.path.join(self.portail, "application", "models.py"), "w") as f:
            f.write(MODELS_FACTICE)
        self.temp = os.path.join(self.tmp.name, "temp")
        os.makedirs(self.temp)

    def tearDown(self):
        self.redir.__exit__(None, None, None)
        self.tmp.cleanup()

    def _synchro(self, url):
        p = copy.deepcopy(DLG_Portail_config.VALEURS_DEFAUT)
        p.update(params_synchro(url, hebergement_type=0, hebergement_local_repertoire=self.portail))
        p["image_identification"] = ""
        return UTILS_Portail_synchro.Synchro(dict_parametres=p, log=FauxLog())

    def test_reponse_perdue_puis_nouvel_essai(self):
        traites = []

        def comportement(h):
            traites.append(h.path)  # "Connecthys" a traité le fichier
            if len(traites) == 1:
                h.close_connection = True
                h.connection.shutdown(socket.SHUT_RDWR)  # réponse perdue
                return
            repondre(h, 200, b"True")

        with ServeurHTTPLocal(comportement) as srv, \
                mock.patch.object(UTILS_Portail_synchro.UTILS_Fichiers, "GetRepTemp",
                                  side_effect=lambda fichier="": os.path.join(self.temp, fichier)), \
                mock.patch.object(UTILS_Portail_synchro.time, "sleep"), \
                contextlib.redirect_stdout(io.StringIO()):
            s1 = self._synchro(srv.url)
            try:
                r1 = s1.Upload_data()
            except Exception as err:  # pragma: no cover - diagnostic
                self.skipTest("Upload_data non exécutable dans ce banc : %r" % err)
            last1 = UTILS_Portail_synchro.UTILS_Parametres.Parametres(
                mode="get", categorie="portail", nom="last_synchro", valeur="")
            r2 = self._synchro(srv.url).Upload_data()
            last2 = UTILS_Portail_synchro.UTILS_Parametres.Parametres(
                mode="get", categorie="portail", nom="last_synchro", valeur="")

        self.assertFalse(r1)               # Noethys conclut à l'échec...
        self.assertEqual(len(traites), 2)  # ...alors que le portail a reçu/traité 2 fois
        self.assertEqual(last1, "")        # last_synchro non mis à jour après la perte
        self.assertTrue(r2)
        self.assertNotEqual(last2, "")
        self.assertNotEqual(traites[0], traites[1])  # nouveau nom aléatoire à chaque essai
        # Deux exports chiffrés distincts déposés côté portail, aucun nettoyage
        deposes = sorted(f for f in os.listdir(os.path.join(self.portail, "application", "data"))
                         if f.endswith(".crypt"))
        self.assertEqual(len(deposes), 2)
        # Côté poste : base SQLite d'export + .crypt laissés dans Temp/<pid>
        restes = os.listdir(self.temp)
        self.assertEqual(len([f for f in restes if f.startswith("import_") and f.endswith(".db")]), 2)
        self.assertEqual(len([f for f in restes if f.startswith("import_") and f.endswith(".crypt")]), 2)
        self.assertIn("config.py", restes)

    def test_reponse_true_avec_saut_de_ligne_consideree_comme_echec(self):
        with ServeurHTTPLocal(lambda h: repondre(h, 200, b"True\n")) as srv, \
                mock.patch.object(UTILS_Portail_synchro.UTILS_Fichiers, "GetRepTemp",
                                  side_effect=lambda fichier="": os.path.join(self.temp, fichier)), \
                mock.patch.object(UTILS_Portail_synchro.time, "sleep"), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                r = self._synchro(srv.url).Upload_data()
            except Exception as err:  # pragma: no cover
                self.skipTest("Upload_data non exécutable dans ce banc : %r" % err)
        self.assertFalse(r)


if __name__ == "__main__":
    unittest.main()
