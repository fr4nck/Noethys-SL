#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Auteur:          Ivan LUCAS
# Copyright:       (c) 2010-16 Ivan LUCAS
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------

import os, sys

frozen = getattr(sys, 'frozen', '')
if not frozen:
    REP_COURANT = os.path.dirname(os.path.abspath(__file__))
else :
    REP_COURANT = os.path.dirname(sys.executable)

if REP_COURANT not in sys.path :
    sys.path.insert(1, REP_COURANT)

for rep in os.listdir(REP_COURANT) :
    chemin = os.path.join(REP_COURANT, rep)
    if os.path.isdir(chemin) and chemin not in sys.path :
        sys.path.insert(2, chemin)

# Certains écrans historiques construisent le nom de l'icône à partir du
# libellé du type de structure. Des bases existantes peuvent donc demander ces
# trois noms alors que le paquet historique ne contient qu'une icône générique.
# Le repli reste volontairement limité à ces ressources connues.
STATIC_IMAGE_ALIASES = {
    os.path.normpath("Images/16x16/Collectivite.png"): os.path.normpath("Images/16x16/Organisme.png"),
    os.path.normpath("Images/16x16/Association.png"): os.path.normpath("Images/16x16/Organisme.png"),
    os.path.normpath("Images/16x16/Entreprise.png"): os.path.normpath("Images/16x16/Organisme.png"),
}


def GetStaticPath(fichier=""):
    """ Retourne le chemin du répertoire Static """
    chemin = os.path.join(REP_COURANT, "Static")
    relatif = os.path.normpath(fichier)
    resultat = os.path.join(chemin, relatif)
    if not os.path.isfile(resultat) and relatif in STATIC_IMAGE_ALIASES:
        resultat = os.path.join(chemin, STATIC_IMAGE_ALIASES[relatif])
    return resultat

def GetMainPath(fichier=""):
    """ Retourne le chemin du répertoire principal """
    return os.path.join(REP_COURANT, fichier)