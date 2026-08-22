#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:          Ivan LUCAS
# Copyright:       (c) 2010-16 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------

import Chemins
import os
import sys
import shutil
import platform
import subprocess
from Utils import UTILS_Customize
import appdirs
import six


def GetRepData(fichier=""):
    # Vérifie si un répertoire 'Portable' existe
    chemin = Chemins.GetMainPath("Portable")
    if os.path.isdir(chemin):
        chemin = os.path.join(chemin, "Data")
        if not os.path.isdir(chemin):
            os.mkdir(chemin)
        return os.path.join(chemin, fichier)

    # Recherche s'il existe un chemin personnalisé dans le Customize.ini
    chemin = UTILS_Customize.GetValeur("repertoire_donnees", "chemin", "")
    #chemin = chemin.decode("utf8")
    if chemin != "" and os.path.isdir(chemin):
        return os.path.join(chemin, fichier)

    # Recherche le chemin du répertoire des données. appdirs peut retourner une
    # arborescence dont les parents n'existent pas encore (notamment ~/.local/share
    # sur une session Linux neuve), donc il faut créer la chaîne complète.
    if sys.platform == "win32" and platform.release() != "Vista" :

        chemin = appdirs.site_data_dir(appname=None, appauthor=False)
        #chemin = chemin.decode("utf8")

        chemin = os.path.join(chemin, "noethys")
        if not os.path.isdir(chemin):
            os.makedirs(chemin)
    else :

        chemin = appdirs.user_data_dir(appname=None, appauthor=False)
        chemin = os.path.join(chemin, "noethys", "Data")
        if not os.path.isdir(chemin):
            os.makedirs(chemin)

    # Ajoute le dirname si besoin
    return os.path.join(chemin, fichier)


def GetRepTemp(fichier=""):
    chemin = GetRepUtilisateur(os.path.join("Temp", str(os.getpid())))
    if not os.path.isdir(chemin):
        os.makedirs(chemin)
    return os.path.join(chemin, fichier)
def GetRepUpdates(fichier=""):
    chemin = GetRepUtilisateur("Updates")
    return os.path.join(chemin, fichier)
def GetRepLang(fichier=""):
    chemin = GetRepUtilisateur("Lang")
    return os.path.join(chemin, fichier)
def GetRepSync(fichier=""):
    chemin = GetRepUtilisateur("Sync")
    return os.path.join(chemin, fichier)
def GetRepExtensions(fichier=""):
    chemin = GetRepUtilisateur("Extensions")
    return os.path.join(chemin, fichier)
def GetRepUtilisateur(fichier=""):
    """ Recherche le répertoire Utilisateur pour stockage des fichiers de config et provisoires """
    chemin = None

    # Vérifie si un répertoire 'Portable' existe
    chemin = Chemins.GetMainPath("Portable")
    if os.path.isdir(chemin):
        return os.path.join(chemin, fichier)

    # Recherche le chemin du répertoire de l'utilisateur
    chemin = appdirs.user_config_dir(appname=None, appauthor=False, roaming=True)
    #chemin = chemin.decode("utf8")

    # Ajoute 'noethys' dans le chemin et création du répertoire
    chemin = os.path.join(chemin, "noethys")
    if not os.path.isdir(chemin):
        os.mkdir(chemin)

    # Ajoute le dirname si besoin
    return os.path.join(chemin, fichier)


def _MigreFichierLocal(source, destination):
    """Migre un fichier historique sans jamais écraser le fichier utilisateur actif."""
    if not os.path.isfile(source):
        return False

    source_absolue = os.path.abspath(source)
    destination_absolue = os.path.abspath(destination)
    if source_absolue == destination_absolue:
        return False

    if os.path.exists(destination):
        print(["migration ignoree, destination deja presente :", source, " > ", destination])
        return False

    print(["deplacement fichier config :", source, " > ", destination])
    shutil.move(source, destination)
    return True


def DeplaceFichiers():
    """ Vérifie si des fichiers du répertoire Data ou du répertoire Utilisateur sont à déplacer vers le répertoire Utilisateur>AppData>Roaming """

    # Les sources historiques doivent être ancrées sur Noethys. L'ancien rep=""
    # dépendait du répertoire courant du processus et pouvait déplacer un fichier
    # sans rapport avec Noethys lorsqu'un raccourci ou un installateur changeait le CWD.
    repertoires_historiques = (
        Chemins.GetMainPath(""),
        Chemins.GetMainPath("Data"),
        os.path.join(os.path.expanduser("~"), "noethys"),
    )

    # Journal et personnalisation peuvent être migrés indépendamment.
    for nom in ("journal.log", "Customize.ini"):
        destination = GetRepUtilisateur(nom)
        for rep in repertoires_historiques:
            source = os.path.join(rep, nom)
            if _MigreFichierLocal(source, destination):
                break

    # Config.json est autoritaire dès qu'il existe dans le profil utilisateur.
    # Son .bak n'est migré que si la configuration correspondante vient elle-même
    # d'être migrée, afin de ne jamais associer un vieux backup à une config active.
    destination_config = GetRepUtilisateur("Config.json")
    destination_backup = GetRepUtilisateur("Config.json.bak")
    if not os.path.exists(destination_config):
        for rep in repertoires_historiques:
            source_config = os.path.join(rep, "Config.json")
            if _MigreFichierLocal(source_config, destination_config):
                source_backup = os.path.join(rep, "Config.json.bak")
                _MigreFichierLocal(source_backup, destination_backup)
                break

    # Déplace les fichiers xlang
    if os.path.isdir(Chemins.GetMainPath("Lang")) :
        for nomFichier in os.listdir(Chemins.GetMainPath("Lang")) :
            if nomFichier.endswith(".xlang") :
                source = Chemins.GetMainPath(u"Lang/%s" % nomFichier)
                print(["deplacement fichier xlang :", source, " > ", GetRepLang(nomFichier)])
                shutil.move(source, GetRepLang(nomFichier))

    # Déplace les fichiers du répertoire Sync
    if os.path.isdir(Chemins.GetMainPath("Sync")) :
        for nomFichier in os.listdir(Chemins.GetMainPath("Sync")) :
            shutil.move(Chemins.GetMainPath("Sync/%s" % nomFichier), GetRepSync(nomFichier))

    # Déplace les fichiers de données du répertoire Data
    if GetRepData() != "Data/" and os.path.isdir(Chemins.GetMainPath("Data")) :
        for nomFichier in os.listdir(Chemins.GetMainPath("Data")) :
            if six.PY2:
                nomFichier = nomFichier.decode("utf8")
            if nomFichier.endswith(".dat") and "_" in nomFichier and "EXEMPLE_" not in nomFichier and "_archive.dat" not in nomFichier :
                source = Chemins.GetMainPath(u"Data/%s" % nomFichier)
                destination = GetRepData(nomFichier)
                archive = Chemins.GetMainPath(u"Data/%s" % nomFichier.replace(".dat", "_archive.dat"))
                print(["copie base de donnees :", nomFichier, " > ", destination])
                shutil.copy(source, destination)
                # L'archive marque la migration comme terminée. Un échec ne doit
                # pas être masqué, sinon la source sera recopiée au démarrage suivant.
                os.replace(source, archive)

def DeplaceExemples():
    """ Déplace les fichiers exemples vers le répertoire des fichiers de données """
    if GetRepData() != "Data/" :
        chemin = Chemins.GetStaticPath("Exemples")
        for nomFichier in os.listdir(chemin) :
            if nomFichier.endswith(".dat") and "EXEMPLE_" in nomFichier :
                # Déplace le fichier vers le répertoire des fichiers de données
                shutil.copy(os.path.join(chemin, nomFichier), GetRepData(nomFichier))

def OuvrirRepertoire(rep):
    if platform.system() == "Windows":
        subprocess.Popen(["explorer", rep])
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", rep])
    else:
        subprocess.Popen(["xdg-open", rep])



if __name__ == "__main__":
    # Teste les déplacements de fichiers
    # DeplaceFichiers()

    # Répertoire utilisateur
    print(GetRepUtilisateur())

    # Répertoire des données
    chemin = GetRepData()
    print(1, os.path.join(chemin, u"Testé.pdf"))
    print(2, os.path.join(chemin, "Test.pdf"))