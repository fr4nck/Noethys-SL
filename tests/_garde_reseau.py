# -*- coding: utf-8 -*-
"""Garde des tests : configuration de test explicite et aucune connexion à
une base réseau (MySQL).

Sur un poste de travail, la configuration de Noethys (dossier Portable ou
%APPDATA%/noethys/Config.json) peut désigner la base réseau de production.
Tout GestionDB.DB() non redirigé vers une base de test s'y connecterait :
lectures, et écritures comme l'insertion d'un paramètre absent par
UTILS_Parametres.Parametres(mode="get").

Installée, la garde :
1. redirige le profil utilisateur (Config.json, Customize.ini, Data, Temp...)
   vers un dossier temporaire vide propre au processus : aucune configuration
   réelle n'est lue ni écrite, et aucun fichier par défaut n'est désigné ;
2. fait échouer toute ouverture réseau : GestionDB passe en echec=1 et
   Noethys retombe sur ses valeurs par défaut, comme sans fichier ouvert.
Les bases SQLite de test, ouvertes par chemin explicite, ne sont pas concernées.

Exception explicite : ServeurMySQLDeTest() autorise, le temps d'un bloc
« with », le seul serveur MySQL local de test déclaré par les variables
NOETHYS_TEST_MYSQL_HOST / _PORT / _USER / _PASSWORD (hôte 127.0.0.1 ou
localhost uniquement). Toute autre destination reste interdite. Les
identifiants ne sont jamais écrits dans le dépôt.
"""

import contextlib

import os
import tempfile

import sys
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import GestionDB  # noqa: E402
from Utils import UTILS_Fichiers  # noqa: E402

TENTATIVES = []
PROFIL_TEST = None
_CONNEXION_REELLE = GestionDB.GetConnexionReseau
_AUTORISE = {"hote": None, "port": None}
HOTES_LOCAUX = ("127.0.0.1", "localhost")


class ConnexionReseauInterdite(RuntimeError):
    pass


def _destination(nomFichier):
    port, hote = str(nomFichier).split("[RESEAU]")[0].split(";")[:2]
    return hote.strip().lower(), int(port)


def _interdire(*args, **kwargs):
    nomFichier = args[0] if args else kwargs.get("nomFichier", "")
    try:
        destination = _destination(nomFichier)
    except Exception:
        destination = None
    if destination is not None and _AUTORISE["hote"] is not None and destination == (_AUTORISE["hote"], _AUTORISE["port"]):
        return _CONNEXION_REELLE(*args, **kwargs)
    TENTATIVES.append(destination)
    raise ConnexionReseauInterdite(u"Tests : connexion à une base réseau interdite.")


def ParametresMySQLDeTest():
    """ Paramètres du serveur MySQL local de test, ou None s'il n'est pas déclaré. """
    hote = os.environ.get("NOETHYS_TEST_MYSQL_HOST", "").strip().lower()
    if not hote:
        return None
    if hote not in HOTES_LOCAUX:
        raise ConnexionReseauInterdite(u"Serveur MySQL de test non local refusé : %s" % hote)
    return {"hote": hote, "port": int(os.environ.get("NOETHYS_TEST_MYSQL_PORT", "3306")),
            "utilisateur": os.environ.get("NOETHYS_TEST_MYSQL_USER", "root"),
            "motdepasse": os.environ.get("NOETHYS_TEST_MYSQL_PASSWORD", "")}


@contextlib.contextmanager
def ServeurMySQLDeTest():
    """ Autorise le seul serveur MySQL local de test pendant le bloc. """
    parametres = ParametresMySQLDeTest()
    if parametres is None:
        raise ConnexionReseauInterdite(u"Aucun serveur MySQL de test déclaré.")
    _AUTORISE.update(hote=parametres["hote"], port=parametres["port"])
    try:
        yield parametres
    finally:
        _AUTORISE.update(hote=None, port=None)


def _installer_profil():
    global PROFIL_TEST
    if getattr(UTILS_Fichiers.GetRepUtilisateur, "_garde_tests", False):
        return
    PROFIL_TEST = tempfile.mkdtemp(prefix="noethys-profil-test-")
    for sous_dossier in ("Data", "Temp", "Updates", "Sync", "Lang", "Extensions"):
        os.makedirs(os.path.join(PROFIL_TEST, sous_dossier), exist_ok=True)

    def rep_utilisateur(fichier=""):
        return os.path.join(PROFIL_TEST, fichier)

    def rep_data(fichier=""):
        return os.path.join(PROFIL_TEST, "Data", fichier)

    def rep_temp(fichier=""):
        return os.path.join(PROFIL_TEST, "Temp", fichier)

    for fonction in (rep_utilisateur, rep_data, rep_temp):
        fonction._garde_tests = True
    UTILS_Fichiers.GetRepUtilisateur = rep_utilisateur
    UTILS_Fichiers.GetRepData = rep_data
    UTILS_Fichiers.GetRepTemp = rep_temp

    # Configuration de test explicite : aucun fichier ouvert (comme Noethys
    # après son initialisation), jamais celle du poste.
    from Utils import UTILS_Config
    UTILS_Config.FichierConfig().SetItemConfig("nomFichier", "")


def Installer():
    _installer_profil()
    if getattr(GestionDB.GetConnexionReseau, "_garde_tests", False):
        return
    _interdire._garde_tests = True
    GestionDB.GetConnexionReseau = _interdire


Installer()
