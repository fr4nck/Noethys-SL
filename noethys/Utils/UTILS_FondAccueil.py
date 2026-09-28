#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Calculs purs pour l'affichage adaptatif du fond d'accueil Noethys SL."""

MODES_FOND = ("remplir", "adapter", "etirer", "original")
MODE_FOND_DEFAUT = "remplir"


def NormaliserMode(mode):
    if mode in MODES_FOND:
        return mode
    return MODE_FOND_DEFAUT


def CalculerPlacementFond(largeur_image, hauteur_image, largeur_zone, hauteur_zone, mode=MODE_FOND_DEFAUT):
    """Renvoie (x, y, largeur, hauteur) pour dessiner le fond.

    - remplir : conserve le ratio et couvre toute la zone (recadrage possible) ;
    - adapter : conserve le ratio et montre toute l'image (marges possibles) ;
    - etirer : remplit exactement la zone sans conserver le ratio ;
    - original : conserve la taille native, ancrée en haut à gauche.
    """
    valeurs = (largeur_image, hauteur_image, largeur_zone, hauteur_zone)
    if any(int(valeur) <= 0 for valeur in valeurs):
        return (0, 0, 0, 0)

    largeur_image = int(largeur_image)
    hauteur_image = int(hauteur_image)
    largeur_zone = int(largeur_zone)
    hauteur_zone = int(hauteur_zone)
    mode = NormaliserMode(mode)

    if mode == "original":
        return (0, 0, largeur_image, hauteur_image)

    if mode == "etirer":
        return (0, 0, largeur_zone, hauteur_zone)

    ratio_x = float(largeur_zone) / float(largeur_image)
    ratio_y = float(hauteur_zone) / float(hauteur_image)
    facteur = max(ratio_x, ratio_y) if mode == "remplir" else min(ratio_x, ratio_y)

    largeur = max(1, int(round(largeur_image * facteur)))
    hauteur = max(1, int(round(hauteur_image * facteur)))
    x = int((largeur_zone - largeur) / 2)
    y = int((hauteur_zone - hauteur) / 2)
    return (x, y, largeur, hauteur)
