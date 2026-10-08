# -*- coding: utf-8 -*-
"""Garde des tests : aucune connexion à une base réseau (MySQL).

Sur un poste de travail, la configuration de Noethys (dossier Portable ou
%APPDATA%/noethys/Config.json) peut désigner la base réseau de production.
Tout GestionDB.DB() non redirigé vers une base de test s'y connecterait :
lectures, et écritures comme l'insertion d'un paramètre absent par
UTILS_Parametres.Parametres(mode="get").

Installée, la garde fait échouer toute ouverture réseau : GestionDB passe en
echec=1 et Noethys retombe sur ses valeurs par défaut, comme sans fichier
ouvert. Les bases SQLite de test ne sont pas concernées.
"""

import sys
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import GestionDB  # noqa: E402

TENTATIVES = []


class ConnexionReseauInterdite(RuntimeError):
    pass


def _interdire(*args, **kwargs):
    TENTATIVES.append(args[0] if args else None)
    raise ConnexionReseauInterdite(u"Tests : connexion à une base réseau interdite.")


def Installer():
    if getattr(GestionDB.GetConnexionReseau, "_garde_tests", False):
        return
    _interdire._garde_tests = True
    GestionDB.GetConnexionReseau = _interdire


Installer()
