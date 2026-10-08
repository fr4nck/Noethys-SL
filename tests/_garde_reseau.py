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
"""

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


class ConnexionReseauInterdite(RuntimeError):
    pass


def _interdire(*args, **kwargs):
    TENTATIVES.append(args[0] if args else None)
    raise ConnexionReseauInterdite(u"Tests : connexion à une base réseau interdite.")


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
