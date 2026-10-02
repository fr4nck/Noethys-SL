#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------
""" Statut Bénéficiaire AEEH d'un individu : tri-état NULL/0/1. """

from Utils.UTILS_Traduction import _

# (valeur stockée en base, libellé affiché) - l'ordre définit l'index des contrôles wx.Choice
CHOIX_AEEH = [
    (None, _(u"Non renseigné")),
    (0, _(u"Non")),
    (1, _(u"Oui")),
]


def GetLabels():
    return [label for valeur, label in CHOIX_AEEH]


def IndexVersValeur(index):
    """ Convertit un index de contrôle (wx.Choice) en valeur stockée (None/0/1) """
    if index is None or index < 0 or index >= len(CHOIX_AEEH):
        return None
    return CHOIX_AEEH[index][0]


def ValeurVersIndex(valeur):
    """ Convertit une valeur stockée (None/0/1) en index de contrôle (wx.Choice) """
    for index, (val, label) in enumerate(CHOIX_AEEH):
        if val == valeur:
            return index
    return 0


def ValeurVersTexte(valeur):
    """ Formate la valeur stockée pour affichage (Etat Nominatif, etc.) """
    if valeur == 1:
        return _(u"Oui")
    if valeur == 0:
        return _(u"Non")
    return u""
