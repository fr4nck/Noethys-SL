# -*- coding: utf-8 -*-
"""Tests de caractérisation : audit réseau (bases distantes MySQL) et secrets.

Lecture seule du code de production : aucun fichier sous noethys/ n'est
modifié. Pas d'Internet : MySQLdb / mysql.connector / smtplib sont remplacés
par des faux. Les mots de passe utilisés sont FACTICES.

Convention : un test qui passe signifie « le comportement décrit (souvent une
anomalie) est reproduit sur ce commit ». Si une correction est livrée, le test
correspondant doit être inversé.
"""
from __future__ import annotations

import ast
import base64
import contextlib
import inspect
import io
import os
import sqlite3
import ssl
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"

MDP_FACTICE = "Factice-Mdp-42"

# Isole le répertoire utilisateur Noethys (GetRepUtilisateur crée un dossier).
_XDG = tempfile.mkdtemp(prefix="noethys-audit-secrets-")
os.environ.setdefault("XDG_CONFIG_HOME", _XDG)
if str(NOETHYS) not in sys.path:
    sys.path.insert(0, str(NOETHYS))

try:
    import wx  # noqa: F401
    WX_OK = True
except Exception:  # pragma: no cover - dépend de l'environnement
    WX_OK = False

if WX_OK:
    import GestionDB
else:  # pragma: no cover
    GestionDB = None


def _src(rel):
    return (NOETHYS / rel).read_text(encoding="utf-8")


def _methode(rel, classe, nom):
    """Retourne le noeud AST d'une méthode (ou fonction si classe=None)."""
    arbre = ast.parse(_src(rel))
    corps = arbre.body
    if classe is not None:
        corps = next(n for n in corps if isinstance(n, ast.ClassDef) and n.name == classe).body
    return next(n for n in corps if isinstance(n, ast.FunctionDef) and n.name == nom)


def _compiler_fonction(rel, classe, nom, espace):
    noeud = _methode(rel, classe, nom)
    module = ast.Module(body=[noeud], type_ignores=[])
    exec(compile(module, rel, "exec"), espace)
    return espace[nom]


# ---------------------------------------------------------------------------
# Faux pilotes MySQL
# ---------------------------------------------------------------------------

class _FauxCurseur(object):
    def __init__(self):
        self.requetes = []

    def execute(self, req, *args):
        self.requetes.append(req)

    def fetchall(self):
        return []


class _FausseConnexion(object):
    def __init__(self):
        self.curseur = _FauxCurseur()

    def set_character_set(self, nom):
        self.charset = nom

    def cursor(self):
        return self.curseur

    def close(self):
        pass

    def commit(self):
        pass


@unittest.skipUnless(WX_OK, "wxPython absent : GestionDB non importable")
class FrontiereMySQLTests(unittest.TestCase):
    """DB-01..DB-04 : paramètres réellement passés au pilote MySQL."""

    def setUp(self):
        self.appels = []
        self._sauve = {k: getattr(GestionDB, k, None) for k in
                       ("MySQLdb", "conversions", "FIELD_TYPE", "INTERFACE_MYSQL", "CERTIFICATS_SSL", "mysql", "POOL_MYSQL")}
        appels = self.appels

        def connect(**kwargs):
            appels.append(kwargs)
            return _FausseConnexion()

        GestionDB.MySQLdb = types.SimpleNamespace(connect=connect)
        GestionDB.conversions = {}
        GestionDB.FIELD_TYPE = types.SimpleNamespace(LONG=3)
        GestionDB.INTERFACE_MYSQL = "mysqldb"
        GestionDB.CERTIFICATS_SSL = {}

    def tearDown(self):
        for k, v in self._sauve.items():
            if v is None and hasattr(GestionDB, k) and k in ("MySQLdb", "conversions", "FIELD_TYPE", "mysql"):
                try:
                    delattr(GestionDB, k)
                except AttributeError:
                    pass
            else:
                setattr(GestionDB, k, v)

    def _nom(self, mdp):
        return u"3306;db.exemple.invalid;agent;%s[RESEAU]centre_data" % mdp

    def test_db01_mysqldb_sans_connect_timeout_ni_read_timeout(self):
        GestionDB.GetConnexionReseau(self._nom(GestionDB.EncodeMdpReseau(MDP_FACTICE)))
        kwargs = self.appels[-1]
        for cle in ("connect_timeout", "read_timeout", "write_timeout"):
            self.assertNotIn(cle, kwargs)
        self.assertEqual(kwargs["passwd"], MDP_FACTICE)  # base64 décodé avant envoi

    def test_db02_ssl_vide_sans_certificats_et_jamais_ssl_mode(self):
        GestionDB.GetConnexionReseau(self._nom(GestionDB.EncodeMdpReseau(MDP_FACTICE)))
        kwargs = self.appels[-1]
        self.assertEqual(kwargs["ssl"], {})          # aucun TLS imposé côté client
        self.assertNotIn("ssl_mode", kwargs)          # ni REQUIRED ni VERIFY_IDENTITY

    def test_db02b_mysql_connector_ca_sans_verification(self):
        captures = []

        def connect(**params):
            captures.append(params)
            return _FausseConnexion()

        GestionDB.mysql = types.SimpleNamespace(connector=types.SimpleNamespace(connect=connect))
        GestionDB.INTERFACE_MYSQL = "mysql.connector"
        GestionDB.CERTIFICATS_SSL = {"ca": "/chemin/ca-cert.pem"}
        GestionDB.POOL_MYSQL = 5
        GestionDB.GetConnexionReseau(self._nom(GestionDB.EncodeMdpReseau(MDP_FACTICE)))
        params = captures[-1]
        self.assertEqual(params["ssl_ca"], "/chemin/ca-cert.pem")
        self.assertNotIn("ssl_verify_cert", params)
        self.assertNotIn("ssl_verify_identity", params)
        self.assertNotIn("connection_timeout", params)

    def test_db03_mot_de_passe_clair_avec_point_virgule_rend_la_connexion_impossible(self):
        # Chemin DLG_Saisie_param_reseau.TestConnexion / UTILS_Sauvegarde : mdp en clair.
        db = GestionDB.DB(nomFichier=self._nom("abc;def"), suffixe=None)
        self.assertEqual(db.echec, 1)
        self.assertIsInstance(db.erreur, ValueError)
        self.assertEqual(self.appels, [])  # le serveur n'est même pas contacté

    def test_db03b_encodage_nom_fichier_leve_valueerror_si_point_virgule(self):
        with self.assertRaises(ValueError):
            GestionDB.EncodeNomFichierReseau(self._nom("abc;def"))

    def test_db04_mdp_clair_commencant_par_64_est_decode_a_tort(self):
        clair = "#64#" + base64.b64encode(b"autre").decode()
        self.assertEqual(GestionDB.DecodeMdpReseau(clair), "autre")


@unittest.skipUnless(WX_OK, "wxPython absent : GestionDB non importable")
class AtomiciteEcrituresTests(unittest.TestCase):
    """DB-05/DB-06 : écritures multi-requêtes sans transaction ni rollback."""

    def setUp(self):
        self.rep = tempfile.mkdtemp(prefix="audit-db-")
        self.chemin = os.path.join(self.rep, "base.dat")
        db = GestionDB.DB(nomFichier=self.chemin, suffixe=None, modeCreation=True)
        db.ExecuterReq("CREATE TABLE reglements (IDreglement INTEGER PRIMARY KEY AUTOINCREMENT, montant FLOAT)")
        db.ExecuterReq("CREATE TABLE ventilation (IDventilation INTEGER PRIMARY KEY AUTOINCREMENT, IDreglement INTEGER, montant FLOAT)")
        db.Commit()
        db.Close()

    def _compter(self, table):
        cx = sqlite3.connect(self.chemin)
        try:
            return cx.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        finally:
            cx.close()

    def test_db05_coupure_apres_insert_reglement_laisse_un_reglement_sans_ventilation(self):
        db = GestionDB.DB(nomFichier=self.chemin, suffixe=None)
        IDreglement = db.ReqInsert("reglements", [("montant", 10.0)])
        self.assertIsNotNone(IDreglement)

        class CurseurCoupe(object):
            def execute(self, *a, **k):
                raise sqlite3.OperationalError("Lost connection to MySQL server during query (simulé)")

        db.cursor = CurseurCoupe()
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            IDventilation = db.ReqInsert("ventilation", [("IDreglement", IDreglement), ("montant", 10.0)])
            db.ReqMAJ("ventilation", [("montant", 5.0)], "IDventilation", 1)
        db.Close()
        # Aucune exception remontée à l'appelant : l'erreur est seulement imprimée.
        self.assertIsNone(IDventilation)
        self.assertIn("Requete sql d'INSERT incorrecte", sortie.getvalue())
        # Le règlement est déjà validé (commit par appel), la ventilation manque.
        self.assertEqual(self._compter("reglements"), 1)
        self.assertEqual(self._compter("ventilation"), 0)

    def test_db06_commit_false_puis_erreur_avalee_puis_commit_valide_un_lot_partiel(self):
        db = GestionDB.DB(nomFichier=self.chemin, suffixe=None)
        db.ReqInsert("reglements", [("montant", 1.0)], commit=False)
        with contextlib.redirect_stdout(io.StringIO()):
            db.ReqInsert("table_inexistante", [("x", 1)], commit=False)  # échec avalé
        db.Commit()  # l'appelant ne sait pas qu'une étape a échoué
        db.Close()
        self.assertEqual(self._compter("reglements"), 1)

    def test_db07_reglement_et_facturation_sans_transaction_explicite(self):
        reglement = ast.get_source_segment(_src("Dlg/DLG_Saisie_reglement.py"),
                                           _methode("Dlg/DLG_Saisie_reglement.py", "Dialog", "Sauvegarde"))
        self.assertIn('DB.ReqInsert("reglements", listeDonnees)', reglement)
        self.assertNotIn("rollback", reglement)
        self.assertNotIn("commit=False", reglement)
        facture = _src("Dlg/DLG_Factures_generation_selection.py")
        self.assertIn('IDfacture = DB.ReqInsert("factures", listeDonnees)', facture)
        self.assertNotIn("rollback", facture)
        self.assertNotIn("FOR UPDATE", facture)  # numéro = MAX(numero)+1 sans verrou


@unittest.skipUnless(WX_OK, "wxPython absent : GestionDB non importable")
class FuitesSecretsReseauTests(unittest.TestCase):

    def test_sec01_executerreq_imprime_le_mdp_mysql_en_cas_d_echec(self):
        rep = tempfile.mkdtemp(prefix="audit-db-")
        db = GestionDB.DB(nomFichier=os.path.join(rep, "b.dat"), suffixe=None, modeCreation=True)
        # Requête construite comme DLG_Saisie_utilisateur_reseau.Sauvegarde (l. 307)
        req = u"CREATE USER '%s'@'%s' IDENTIFIED BY '%s';" % ("agent", "%", MDP_FACTICE)
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            resultat = db.ExecuterReq(req)
        db.Close()
        self.assertEqual(resultat, 0)
        self.assertIn(MDP_FACTICE, sortie.getvalue())  # stdout -> journal.log en version packagée

    def test_sec02_obfuscation_base64_reversible(self):
        encode = GestionDB.EncodeMdpReseau(MDP_FACTICE)
        self.assertTrue(encode.startswith("#64#"))
        self.assertEqual(base64.b64decode(encode[4:]).decode(), MDP_FACTICE)

    def test_sec03_titre_fenetre_ne_contient_pas_le_mdp(self):
        titres = []
        espace = {"_": lambda s: s,
                  "Identite": types.SimpleNamespace(PRODUCT_NAME="Noethys-SL", PRODUCT_VERSION_DISPLAY="0.1")}
        fonction = _compiler_fonction("Noethys.py", "MainFrame", "SetTitleFrame", espace)
        encode = GestionDB.EncodeMdpReseau(MDP_FACTICE)
        fonction(types.SimpleNamespace(SetTitle=titres.append),
                 nomFichier=u"3306;hote;agent;%s[RESEAU]centre" % encode)
        self.assertNotIn(MDP_FACTICE, titres[-1])
        self.assertNotIn(encode, titres[-1])
        self.assertIn("hote", titres[-1])
        self.assertIn("agent", titres[-1])


@unittest.skipUnless(WX_OK, "wxPython absent")
class SauvegardeTests(unittest.TestCase):

    @unittest.skipIf(os.name != "posix", "droits POSIX")
    def test_sec04_fichier_login_mysqldump_en_clair_droits_selon_umask(self):
        from Utils import UTILS_Sauvegarde
        chemin = os.path.join(tempfile.mkdtemp(prefix="audit-cnf-"), "logintemp.cnf")
        ancien = os.umask(0o022)
        try:
            UTILS_Sauvegarde.CreationFichierLoginTemp(host="h", user="u", port="3306",
                                                      password=GestionDB.EncodeMdpReseau(MDP_FACTICE),
                                                      nomFichier=chemin)
        finally:
            os.umask(ancien)
        contenu = Path(chemin).read_text()
        self.assertIn("password=%s" % MDP_FACTICE, contenu)    # mdp décodé, en clair, non quoté
        self.assertTrue(os.stat(chemin).st_mode & stat.S_IROTH)  # pas de chmod 0600 explicite


class CryptageTests(unittest.TestCase):

    def setUp(self):
        from Utils import UTILS_Cryptage_fichier
        self.C = UTILS_Cryptage_fichier
        self.rep = tempfile.mkdtemp(prefix="audit-crypt-")

    def test_sec05_dechiffrement_avec_mauvais_mdp_ne_detecte_rien(self):
        clair = os.path.join(self.rep, "a.zip")
        Path(clair).write_bytes(b"PK\x03\x04" + b"donnees" * 50)
        chiffre = os.path.join(self.rep, "a.noc")
        self.C.CrypterFichier(clair, chiffre, "bon-mdp-factice")
        sortie = os.path.join(self.rep, "b.zip")
        self.C.DecrypterFichier(chiffre, sortie, "mauvais-mdp-factice")  # aucune exception
        self.assertNotEqual(Path(sortie).read_bytes(), Path(clair).read_bytes())

    def test_sec06_mode_par_defaut_restauration_locale_conserve_le_pickle(self):
        """RISQUE RÉSIDUEL ACCEPTÉ au rail 1 (SEC-06 / X-01) : le mode par
        défaut de DecrypterFichier (restauration locale volontaire) désérialise
        encore l'ancien format. Les entrées réseau (pièces Connecthys, fichiers
        Nomadhys) utilisent le mode strict : voir tests/test_rail1_format_chiffrement.py."""
        drapeau = "NOETHYS_AUDIT_PICKLE_%d" % os.getpid()

        class Charge(object):
            def __reduce__(self):
                return (exec, ("import os; os.environ[%r] = '1'" % drapeau,))

        import pickle
        piege = os.path.join(self.rep, "piege.noc")
        with open(piege, "wb") as f:
            pickle.dump(Charge(), f)
        try:
            with self.assertRaises(Exception):
                self.C.DecrypterFichier(piege, os.path.join(self.rep, "x"), "peu-importe")
            self.assertEqual(os.environ.get(drapeau), "1")  # code exécuté AVANT tout contrôle
        finally:
            os.environ.pop(drapeau, None)

    def test_sec07_cle_derivee_md5_hex_sans_sel(self):
        source = _src("Utils/UTILS_Cryptage_fichier.py")
        self.assertIn("fonction(fichierDecrypte, fichierCrypte, hashPassword_MD5(motdepasse))", source)
        self.assertNotIn("pbkdf2", source.lower())
        self.assertNotIn("scrypt", source.lower())


@unittest.skipUnless(WX_OK, "wxPython absent")
class ConnecthysTests(unittest.TestCase):

    def setUp(self):
        from Utils import UTILS_Portail_synchro
        self.P = UTILS_Portail_synchro
        self._ctx = ssl._create_default_https_context

    def tearDown(self):
        ssl._create_default_https_context = self._ctx

    def test_sec08_jeton_syncdown_derive_de_secret_key_et_imprime(self):
        s = self.P.Synchro.__new__(self.P.Synchro)
        s.dict_parametres = {"secret_key": "ab1cd2ef3gh4ij5kl6mn7op8qr9st1uv2wx3yz4A"}
        jeton = s.GetSecretInteger()
        self.assertTrue(jeton.endswith("1234567891234"))  # chiffres de secret_key
        source = inspect.getsource(self.P.Synchro.Download_data)
        self.assertIn('print("URL syncdown =", url)', source)
        self.assertIn('"syncdown/%d/%d" % (int(secret), last)', source)

    def test_sec09_accept_all_cert_ne_touche_plus_le_contexte_tls_global(self):
        """CORRIGÉ (X-03, rail 1)."""
        avant = ssl._create_default_https_context
        self.P.Synchro(dict_parametres={"accept_all_cert": True})
        self.assertIs(ssl._create_default_https_context, avant)
        self.assertIsNot(ssl._create_default_https_context, ssl._create_unverified_context)

    def test_sec10_config_py_avec_secrets_reste_dans_temp(self):
        source = inspect.getsource(self.P.Synchro.Upload_config)
        self.assertIn('Ecrit_ligne("SECRET_KEY"', source)
        self.assertIn("UTILS_Fichiers.GetRepTemp(fichier=nomFichier)", source)
        self.assertNotIn("os.remove", source)

    def test_sec11_ssh_sans_verification_de_cle_hote(self):
        source = inspect.getsource(self.P.Synchro.Connexion)
        self.assertIn("paramiko.AutoAddPolicy()", source)


class SmtpTests(unittest.TestCase):

    def _backend(self, classe_smtp):
        from Outils.mail import smtp

        class Backend(smtp.EmailBackend):
            @property
            def connection_class(self):
                return classe_smtp

        return Backend(host="smtp.exemple.invalid", port=587, username="u", password=MDP_FACTICE,
                       use_tls=True, fail_silently=False)

    def test_sec12_starttls_sans_contexte_donc_certificat_non_verifie(self):
        appels = {}

        class FauxSMTP(object):
            def __init__(self, *a, **k):
                pass

            def starttls(self, **kwargs):
                appels["starttls"] = kwargs

            def login(self, u, p):
                appels["login"] = (u, p)

        self._backend(FauxSMTP).open()
        self.assertNotIn("context", appels["starttls"])
        self.assertEqual(appels["login"][1], MDP_FACTICE)
        # Sans contexte, smtplib utilise ssl._create_stdlib_context() : CERT_NONE.
        self.assertEqual(ssl._create_stdlib_context().verify_mode, ssl.CERT_NONE)

    @unittest.skipIf(sys.version_info < (3, 12), "keyfile/certfile retirés en 3.12")
    def test_sec13_starttls_keyfile_certfile_typeerror_python_312(self):
        import smtplib

        class SMTPReel(smtplib.SMTP):
            def __init__(self, *a, **k):
                pass

        with self.assertRaises(TypeError):
            self._backend(SMTPReel).open()


class SecretsStatiquesTests(unittest.TestCase):

    def test_sec14_mdp_utilisateur_ecrit_en_clair_en_base(self):
        segment = ast.get_source_segment(_src("Dlg/DLG_Saisie_utilisateur.py"),
                                         _methode("Dlg/DLG_Saisie_utilisateur.py", "Dialog", "Sauvegarde"))
        self.assertIn('("mdp", self.mdp)', segment)
        self.assertIn('("mdp", dictAdministrateur["mdp"])', _src("Noethys.py"))

    def test_sec15_mot_de_passe_du_jour_administrateur(self):
        import datetime
        espace = {"datetime": datetime}
        fonction = _compiler_fonction("Ctrl/CTRL_Identification.py", "CTRL", "GetPasse", espace)
        attendu = str(int(datetime.datetime.today().strftime("%d%m%Y")) // 3)
        self.assertEqual(fonction(None, "x"), attendu)  # calculable par quiconque

    def test_sec16_export_nnc_contient_le_mdp_mysql_en_clair(self):
        segment = ast.get_source_segment(_src("Dlg/DLG_Ouvrir_fichier.py"),
                                         _methode("Dlg/DLG_Ouvrir_fichier.py", "MyDialog", "OnBoutonExporterCodes"))
        self.assertIn('"pwd": self.ctrl_motdepasse.GetValue()', segment)
        self.assertNotIn("Encode", segment)

    def test_sec17_cle_secrete_mailjet_affichee_en_clair(self):
        source = _src("Dlg/DLG_Saisie_email_exp.py")
        self.assertIn('self.ctrl_api_secret = wx.TextCtrl(self, -1, "")', source)
        self.assertIn('parametres = "api_key==%s##api_secret==%s" % (api_key, api_secret)', source)

    def test_sec18_pr355_absente_de_rc2(self):
        self.assertFalse((NOETHYS / "Utils" / "UTILS_Interdomain_Secrets.py").exists())
        self.assertFalse((NOETHYS / "Utils" / "UTILS_Interdomain_Mailbox_Client.py").exists())


if __name__ == "__main__":
    unittest.main()
