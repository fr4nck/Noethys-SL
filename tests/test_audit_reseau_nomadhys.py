# -*- coding: utf-8 -*-
"""Tests de caractérisation de l'audit réseau Nomadhys (lecture seule du code).

Ces tests DOCUMENTENT le comportement actuel (y compris défectueux) des
frontières réseau de la synchronisation Nomadhys. Ils ne modifient aucun
fichier de production : les fonctions sont extraites par AST et exécutées
avec des dépendances factices (pas de wx, pas de Twisted, pas d'Internet,
ftplib.FTP remplacé par un faux).

Un test qui « passe » ici signifie « l'anomalie décrite est reproduite ».
"""
from __future__ import annotations

import ast
import base64
import importlib.util
import json
import os
import pickle
import shutil
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
SRC_SYNCHRO = NOETHYS / "Dlg" / "DLG_Synchronisation.py"
SRC_SERVEUR = NOETHYS / "Ctrl" / "CTRL_Serveur_nomade.py"
SRC_EXPORT = NOETHYS / "Utils" / "UTILS_Export_nomade.py"
SRC_CRYPT = NOETHYS / "Utils" / "UTILS_Cryptage_fichier.py"
SRC_TRAITEMENT = NOETHYS / "Dlg" / "DLG_Synchronisation_donnees.py"

MDP_NOETHYS = "mdp-noethys"      # valeurs factices de test
MDP_TABLETTE = "mdp-tablette"


# ---------------------------------------------------------------------------
# Outils d'extraction
# ---------------------------------------------------------------------------

def _arbre(chemin):
    source = Path(chemin).read_text(encoding="utf-8")
    return source, ast.parse(source)


def _noeud(chemin, nom, conteneur=None):
    _, arbre = _arbre(chemin)
    corps = arbre.body
    if conteneur is not None:
        corps = next(n for n in corps if isinstance(n, ast.ClassDef) and n.name == conteneur).body
    return next(n for n in corps
                if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == nom)


def charger(chemin, noms, espace, conteneur=None):
    """Exécute les définitions demandées (module ou méthodes d'une classe)."""
    for nom in noms:
        n = _noeud(chemin, nom, conteneur)
        exec(compile(ast.Module(body=[n], type_ignores=[]), str(chemin), "exec"), espace)
    return espace


def charger_cryptage():
    spec = importlib.util.spec_from_file_location("audit_UTILS_Cryptage_fichier", str(SRC_CRYPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FauxWx(object):
    """wx minimal : enregistre les dialogues au lieu de les afficher."""
    OK = ICON_ERROR = ICON_INFORMATION = ICON_EXCLAMATION = 0

    def __init__(self):
        self.messages = []
        self.busy = 0

    def BusyInfo(self, *a, **k):
        self.busy += 1
        return object()

    def MessageDialog(self, parent, message, *a, **k):
        faux = self

        class _D(object):
            def ShowModal(self_inner):
                faux.messages.append(message)

            def Destroy(self_inner):
                pass
        return _D()


class FauxFTP(object):
    """Faux serveur FTP en mémoire (aucun réseau)."""
    instances = []
    fichiers = {}
    echec_retr = None      # nom de fichier dont le RETR est coupé à mi-parcours
    echec_delete = False

    def __init__(self, *args, **kwds):
        self.args, self.kwds = args, kwds
        self.supprimes = []
        FauxFTP.instances.append(self)

    def cwd(self, rep):
        pass

    def nlst(self):
        return list(FauxFTP.fichiers)

    def size(self, nom):
        return len(FauxFTP.fichiers[nom])

    def voidcmd(self, cmd):
        pass

    def retrbinary(self, cmd, callback):
        nom = cmd.split(" ", 1)[1]
        contenu = FauxFTP.fichiers[nom]
        if FauxFTP.echec_retr == nom:
            callback(contenu[: len(contenu) // 2])
            raise EOFError("connexion coupée pendant RETR")
        callback(contenu)

    def delete(self, nom):
        if FauxFTP.echec_delete:
            raise EOFError("connexion coupée pendant DELE")
        self.supprimes.append(nom)
        del FauxFTP.fichiers[nom]

    def quit(self):
        pass


def fabriquer_zip_actions(chemin_nsd):
    with zipfile.ZipFile(chemin_nsd, "w") as z:
        z.writestr("database.dat", b"SQLite format 3\x00" + b"x" * 64)


# ---------------------------------------------------------------------------
# Base commune : répertoire Sync temporaire
# ---------------------------------------------------------------------------

class BaseSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="audit_nomadhys_")
        self.sync = os.path.join(self.tmp, "Sync")
        os.makedirs(self.sync)
        self.crypt = charger_cryptage()
        self.config = {
            "synchro_cryptage_mdp": base64.b64encode(MDP_NOETHYS.encode()),
            "synchro_ftp_hote": "ftp.exemple.invalid",
            "synchro_ftp_identifiant": "user",
            "synchro_ftp_mdp": base64.b64encode(b"********"),
            "synchro_ftp_repertoire": "www/",
        }
        self.wx = FauxWx()
        FauxFTP.instances = []
        FauxFTP.fichiers = {}
        FauxFTP.echec_retr = None
        FauxFTP.echec_delete = False

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def espace_synchro(self, idfichier="IDF1"):
        sync = self.sync
        config = self.config
        return {
            "os": os, "six": __import__("six"), "base64": base64, "zipfile": zipfile,
            "shutil": shutil, "_": lambda t: t, "wx": self.wx,
            "ftplib": types.SimpleNamespace(FTP=FauxFTP),
            "UTILS_Fichiers": types.SimpleNamespace(GetRepSync=lambda f="": os.path.join(sync, f)),
            "UTILS_Config": types.SimpleNamespace(GetParametre=lambda nom, defaut=None: config.get(nom, defaut)),
            "UTILS_Export_nomade": types.SimpleNamespace(EXTENSION_CRYPTE=".nsc", EXTENSION_DECRYPTE=".nsd"),
            "UTILS_Cryptage_fichier": self.crypt,
            "FonctionsPerso": types.SimpleNamespace(GetIDfichier=lambda: idfichier),
        }

    def faux_dialog(self):
        return types.SimpleNamespace(ctrl_fichiers=types.SimpleNamespace(MAJ=lambda: None))

    def nsc_chiffre(self, nom, mdp):
        nsd = os.path.join(self.tmp, "src.nsd")
        fabriquer_zip_actions(nsd)
        nsc = os.path.join(self.tmp, nom)
        self.crypt.CrypterFichier(nsd, nsc, mdp)
        with open(nsc, "rb") as f:
            return f.read()


# ---------------------------------------------------------------------------
# 1. Cryptographie (UTILS_Cryptage_fichier)
# ---------------------------------------------------------------------------

class CryptageTests(BaseSync):
    def test_cle_aes_est_le_md5_hex_du_mot_de_passe_sans_sel(self):
        cle = self.crypt.hashPassword_MD5(MDP_NOETHYS)
        self.assertEqual(len(cle), 32)                      # 32 caractères hex -> AES-256
        self.assertTrue(all(c in "0123456789abcdef" for c in cle))  # entropie max 128 bits
        self.assertEqual(cle, self.crypt.hashPassword_MD5(MDP_NOETHYS))  # déterministe, sans sel

    def test_mauvais_mot_de_passe_ne_leve_aucune_erreur(self):
        src = os.path.join(self.tmp, "a.nsd")
        fabriquer_zip_actions(src)
        self.crypt.CrypterFichier(src, os.path.join(self.tmp, "a.nsc"), MDP_TABLETTE)
        self.crypt.DecrypterFichier(os.path.join(self.tmp, "a.nsc"), os.path.join(self.tmp, "b.nsd"), MDP_NOETHYS)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "b.nsd")))
        self.assertFalse(zipfile.is_zipfile(os.path.join(self.tmp, "b.nsd")))

    def test_absence_de_mac_alteration_non_detectee(self):
        src = os.path.join(self.tmp, "a.nsd")
        fabriquer_zip_actions(src)
        nsc = os.path.join(self.tmp, "a.nsc")
        self.crypt.CrypterFichier(src, nsc, MDP_NOETHYS)
        data = bytearray(open(nsc, "rb").read())
        data[40] ^= 0x01        # bit flip dans le chiffré (CFB)
        open(nsc, "wb").write(bytes(data))
        # Aucune exception : l'intégrité n'est pas vérifiée
        self.crypt.DecrypterFichier(nsc, os.path.join(self.tmp, "c.nsd"), MDP_NOETHYS)

    def test_ancien_format_deserialise_pickle_du_fichier_recu(self):
        """Un .nsc sans en-tête SV2 est passé à pickle.load : exécution de code."""
        marqueur = "AUDIT_NOMADHYS_PICKLE_%d" % os.getpid()
        os.environ.pop(marqueur, None)

        class Charge(object):
            def __reduce__(self):
                return (exec, ("import os; os.environ[%r] = '1'" % marqueur,))

        nsc = os.path.join(self.tmp, "actions_IDF1_x.nsc")
        with open(nsc, "wb") as f:
            pickle.dump(Charge(), f)
        try:
            with self.assertRaises(Exception):   # échoue APRÈS l'exécution du code
                self.crypt.DecrypterFichier(nsc, os.path.join(self.tmp, "x.nsd"), "")
            self.assertEqual(os.environ.get(marqueur), "1")
        finally:
            os.environ.pop(marqueur, None)


# ---------------------------------------------------------------------------
# 2. AnalyserFichier (DLG_Synchronisation)
# ---------------------------------------------------------------------------

class AnalyserFichierTests(BaseSync):
    def analyser(self):
        return charger(SRC_SYNCHRO, ["AnalyserFichier"], self.espace_synchro())["AnalyserFichier"]

    def test_mauvais_mdp_supprime_le_nsc_et_retourne_false(self):
        nom = "actions_IDF1_20261007120000.nsc"
        open(os.path.join(self.sync, nom), "wb").write(self.nsc_chiffre(nom, MDP_TABLETTE))
        self.assertFalse(self.analyser()(nom, typeTransfert="manuel"))
        self.assertFalse(os.path.exists(os.path.join(self.sync, nom)))          # original perdu
        self.assertTrue(os.path.exists(os.path.join(self.sync, nom[:-4] + ".nsd")))  # déchet
        self.assertFalse(os.path.exists(os.path.join(self.sync, nom[:-4] + ".dat")))

    def test_taille_incorrecte_supprime_le_fichier_local(self):
        nom = "actions_IDF1_20261007120000.nsd"
        fabriquer_zip_actions(os.path.join(self.sync, nom))
        self.assertFalse(self.analyser()(nom, tailleFichier=1, typeTransfert="ftp"))
        self.assertFalse(os.path.exists(os.path.join(self.sync, nom)))

    def test_nsd_en_clair_accepte_meme_si_cryptage_active(self):
        self.config["synchro_cryptage_activer"] = True
        nom = "actions_IDF1_20261007120000.nsd"
        fabriquer_zip_actions(os.path.join(self.sync, nom))
        self.assertTrue(self.analyser()(nom))
        self.assertTrue(os.path.exists(os.path.join(self.sync, nom[:-4] + ".dat")))


# ---------------------------------------------------------------------------
# 3. RecevoirFTP / purge FTP (DLG_Synchronisation.Dialog)
# ---------------------------------------------------------------------------

class RecevoirFTPTests(BaseSync):
    def recevoir(self, idfichier="IDF1"):
        espace = self.espace_synchro(idfichier)
        charger(SRC_SYNCHRO, ["AnalyserFichier"], espace)
        charger(SRC_SYNCHRO, ["RecevoirFTP", "On_outils_purger_ftp"], espace, conteneur="Dialog")
        return espace

    def test_aucun_timeout_ni_tls(self):
        espace = self.recevoir()
        espace["RecevoirFTP"](self.faux_dialog())
        self.assertTrue(FauxFTP.instances)
        for inst in FauxFTP.instances:
            self.assertNotIn("timeout", inst.kwds)
            self.assertEqual(len(inst.args), 3)   # (hote, identifiant, mdp) : ftplib.FTP, pas FTP_TLS

    def test_echec_dechiffrement_puis_suppression_distante_perte_totale(self):
        nom = "actions_IDF1_20261007120000.nsc"
        FauxFTP.fichiers[nom] = self.nsc_chiffre(nom, MDP_TABLETTE)
        espace = self.recevoir()
        espace["RecevoirFTP"](self.faux_dialog())
        self.assertNotIn(nom, FauxFTP.fichiers)                         # supprimé à distance
        self.assertFalse(os.path.exists(os.path.join(self.sync, nom)))  # supprimé localement
        self.assertFalse(os.path.exists(os.path.join(self.sync, nom[:-4] + ".dat")))
        self.assertEqual(self.wx.messages, [])                          # aucun avertissement

    def test_suppression_distante_avant_tout_import_local(self):
        nom = "actions_IDF1_20261007120000.nsd"
        chemin = os.path.join(self.tmp, nom)
        fabriquer_zip_actions(chemin)
        FauxFTP.fichiers[nom] = open(chemin, "rb").read()
        espace = self.recevoir()
        espace["RecevoirFTP"](self.faux_dialog())
        self.assertNotIn(nom, FauxFTP.fichiers)
        # Seule trace restante : un .dat local NON importé (import = étape manuelle ultérieure)
        self.assertTrue(os.path.exists(os.path.join(self.sync, nom[:-4] + ".dat")))

    def test_coupure_pendant_transfert_B(self):
        ok, coupe = "actions_IDF1_20261007110000.nsd", "actions_IDF1_20261007120000.nsd"
        for nom in (ok, coupe):
            chemin = os.path.join(self.tmp, nom)
            fabriquer_zip_actions(chemin)
            FauxFTP.fichiers[nom] = open(chemin, "rb").read()
        FauxFTP.echec_retr = coupe
        espace = self.recevoir()
        self.assertFalse(espace["RecevoirFTP"](self.faux_dialog()))
        self.assertIn(ok, FauxFTP.fichiers)
        self.assertIn(coupe, FauxFTP.fichiers)          # rien supprimé à distance
        self.assertIn(u"La connexion FTP n'a pas pu être établie", self.wx.messages[0])  # message trompeur
        # Fichiers locaux non analysés (orphelins .nsd, invisibles dans la liste qui ne montre que .dat)
        self.assertTrue(os.path.exists(os.path.join(self.sync, coupe)))

    def test_coupure_apres_analyse_avant_suppression_F_puis_reimport(self):
        nom = "actions_IDF1_20261007120000.nsd"
        chemin = os.path.join(self.tmp, nom)
        fabriquer_zip_actions(chemin)
        FauxFTP.fichiers[nom] = open(chemin, "rb").read()
        FauxFTP.echec_delete = True
        espace = self.recevoir()
        with self.assertRaises(EOFError):               # exception non interceptée dans le handler wx
            espace["RecevoirFTP"](self.faux_dialog())
        dat = os.path.join(self.sync, nom[:-4] + ".dat")
        self.assertTrue(os.path.exists(dat))
        # Simule l'import puis l'archivage local (renommage .dat -> .archive)
        os.rename(dat, dat[:-4] + ".archive")
        # Reprise : le fichier distant est toujours là -> nouveau .dat identique proposé à l'import
        FauxFTP.echec_delete = False
        espace["RecevoirFTP"](self.faux_dialog())
        self.assertTrue(os.path.exists(dat))
        self.assertTrue(os.path.exists(dat[:-4] + ".archive"))

    def test_purge_avec_idfichier_vide_supprime_tout(self):
        FauxFTP.fichiers = {"actions_AUTREBASE_1.nsc": b"x", "data_AUTREBASE.nsd": b"y", "index.html": b"z"}
        espace = self.recevoir(idfichier="")
        espace["On_outils_purger_ftp"](self.faux_dialog(), None)
        self.assertEqual(list(FauxFTP.fichiers), ["index.html"])


# ---------------------------------------------------------------------------
# 4. Serveur TCP direct (CTRL_Serveur_nomade.Echo)
# ---------------------------------------------------------------------------

class FauxTransport(object):
    def __init__(self, host="192.168.1.100"):
        self.ecrit = []
        self.ferme = False
        self.host = host

    def getPeer(self):
        return types.SimpleNamespace(host=self.host)

    def write(self, data):
        self.ecrit.append(data)

    def loseConnection(self):
        self.ferme = True


class FauxLog(object):
    def __init__(self):
        self.lignes = []

    def EcritLog(self, t):
        self.lignes.append(t)

    def SetImage(self, *a):
        pass

    def SetGauge(self, *a):
        pass

    def MAJ(self):
        pass


class ServeurTCPTests(BaseSync):
    def echo(self, ip_autorisees=None):
        self.appels_analyse = []
        sync = self.sync
        espace = {
            "Protocol": object, "json": json, "os": os, "re": __import__("re"),
            "six": __import__("six"), "_": lambda t: t,
            "wx": types.SimpleNamespace(CallLater=lambda *a, **k: None),
            "FonctionsPerso": types.SimpleNamespace(Formate_taille_octets=lambda n: str(n)),
            "UTILS_Fichiers": types.SimpleNamespace(GetRepSync=lambda f="": os.path.join(sync, f)),
            "AnalyserFichier": lambda *a, **k: self.appels_analyse.append((a, k)),
            "IP_AUTORISEES": ip_autorisees, "IP_INTERDITES": None,
        }
        charger(SRC_SERVEUR, ["Echo"], espace)
        proto = espace["Echo"]()
        proto.log = FauxLog()
        proto.transport = FauxTransport()
        proto.generations = []
        proto.GenerationFichierAEnvoyer = lambda: proto.generations.append(True)
        return proto

    def entete(self, nom, taille=10):
        return json.dumps({"action": "envoyer", "nom_appareil": "tab", "taille": taille, "nom": nom}).encode()

    def test_recevoir_sans_authentification_declenche_l_export(self):
        proto = self.echo()
        proto.connectionMade()
        proto.dataReceived(b"recevoir")
        self.assertEqual(proto.generations, [True])
        self.assertFalse(proto.transport.ferme)

    def test_nom_de_fichier_client_permet_l_ecriture_hors_sync(self):
        proto = self.echo()
        proto.dataReceived(self.entete("../hors_sync.txt"))
        proto.dataReceived(b"contenu")
        proto.dictFichierReception["fichier"].close()
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "hors_sync.txt")))

    def test_nom_absolu_ecrase_un_fichier_arbitraire(self):
        cible = os.path.join(self.tmp, "victime.cfg")
        open(cible, "w").write("contenu original")
        proto = self.echo()
        proto.dataReceived(self.entete(cible))       # tronqué dès l'en-tête
        proto.dictFichierReception["fichier"].close()
        self.assertEqual(open(cible).read(), "")

    def test_fin_de_connexion_analyse_sans_controle_de_taille(self):
        proto = self.echo()
        nom = "actions_IDF1_20261007120000.nsd"
        proto.dataReceived(self.entete(nom, taille=1000000))
        proto.dataReceived(b"PK-tronque")           # coupure B : 10 octets sur 1 000 000
        proto.connectionLost(None)
        self.assertEqual(self.appels_analyse, [((nom,), {})])   # pas de tailleFichier

    def test_taille_zero_division(self):
        proto = self.echo()
        proto.dataReceived(self.entete("actions_IDF1_1.nsd", taille=0))
        with self.assertRaises(ZeroDivisionError):
            proto.dataReceived(b"abc")
        proto.dictFichierReception["fichier"].close()

    def test_bloc_de_donnees_json_valide_mal_interprete(self):
        proto = self.echo()
        proto.dataReceived(self.entete("actions_IDF1_1.nsd", taille=100))
        with self.assertRaises(TypeError):
            proto.dataReceived(b"123")              # morceau de fichier = JSON valide
        proto.dictFichierReception["fichier"].close()

    def test_filtre_ip_par_prefixe(self):
        proto = self.echo()
        self.assertTrue(proto.IsIPinListe("192.168.1.1", "192.168.1.100"))
        self.assertTrue(proto.IsIPinListe("10.0.0.1", "10.0.0.123"))

    def test_envoyer_infos_avec_export_echoue(self):
        proto = self.echo()
        with self.assertRaises(TypeError):
            proto.EnvoyerInfosSurFichierAEnvoyer(None)   # Export.Run() renvoie None en cas d'erreur


class ServeurSourceTests(unittest.TestCase):
    def test_ecoute_toutes_interfaces_sans_interface_explicite(self):
        src = SRC_SERVEUR.read_text(encoding="utf-8")
        self.assertIn("reactor.listenTCP(port, factory)", src)
        self.assertNotIn("interface=", src)

    def test_stopserver_jamais_appele(self):
        appelants = []
        for chemin in NOETHYS.rglob("*.py"):
            if chemin == SRC_SERVEUR:
                continue
            try:
                if "StopServer" in chemin.read_text(encoding="utf-8", errors="ignore"):
                    appelants.append(chemin)
            except OSError:
                pass
        self.assertEqual(appelants, [])

    def test_generation_export_dans_un_thread_avec_dialogue_wx(self):
        run = ast.get_source_segment(SRC_SERVEUR.read_text(encoding="utf-8"),
                                     _noeud(SRC_SERVEUR, "run", "GenerationFichier"))
        self.assertIn("export.Run()", run)
        self.assertIn("EnvoyerInfosSurFichierAEnvoyer", run)     # transport.write hors reactor
        run_export = ast.get_source_segment(SRC_EXPORT.read_text(encoding="utf-8"),
                                            _noeud(SRC_EXPORT, "Run", "Export"))
        self.assertIn("wx.MessageDialog(None", run_export)

    def test_export_contient_tables_sensibles(self):
        src = SRC_EXPORT.read_text(encoding="utf-8")
        for table in ('"familles"', '"utilisateurs"'):
            self.assertIn(table, src)


# ---------------------------------------------------------------------------
# 5. Thread d'import (Traitement) — compléments à #377/#378
# ---------------------------------------------------------------------------

class TraitementTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            import test_noethys_sl_nomadhys_wx_thread as base
        finally:
            sys.path.pop(0)
        self.base = base
        self.ui = base.FauxThreadUI()
        self.bilans = []

        def AfficherBilan(nbre, anomalies):
            self.bilans.append((nbre, list(anomalies)))

        self.espace = base.charger({"Abort", "AppelSynchroneUI", "Traitement"}, self.ui,
                                   {"AfficherBilan": AfficherBilan})
        self.erreurs = []
        self._hook = threading.excepthook
        threading.excepthook = lambda args: self.erreurs.append(args.exc_type)

    def tearDown(self):
        threading.excepthook = self._hook
        self.ui.arreter()

    def lancer(self, tracks):
        parent = self.base.FauxDialogTraitement(self.ui, tracks)
        parent.Abort = self.espace["Abort"]
        t = self.espace["Traitement"](parent)
        parent.traitement = t
        t.start()
        t.join(10)
        self.assertFalse(t.is_alive())
        return t, parent

    def test_action_inconnue_reutilise_le_resultat_precedent(self):
        tracks = [self.base.FauxTrack("A"), self.base.FauxTrack("B", action="dupliquer")]
        t, parent = self.lancer(tracks)
        self.assertTrue(t.succes)
        self.assertIn(("statut", "B", "ok"), parent.journal)     # faux succès
        self.assertEqual(parent.journal.count(("grille", "Sauvegarde")), 2)

    def test_etat_inconnu_tue_le_thread_sans_bilan(self):
        track = self.base.FauxTrack("A")
        track.etat = "demande"
        t, parent = self.lancer([track])
        self.assertFalse(t.succes)
        self.assertEqual(self.bilans, [])
        self.assertNotIn(("fermer", True), parent.journal)
        self.assertTrue(self.erreurs)           # UnboundLocalError remontée au threading.excepthook


if __name__ == "__main__":
    unittest.main()
