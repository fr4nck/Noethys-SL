#!/usr/bin/env python
# -*- coding: utf-8 -*-
#-----------------------------------------------------------
# Identité publique du produit (affichage uniquement).
#
# Noethys SL est la marque et la version publiques de ce fork.
# "Noethys SL" sans suffixe désigne le produit, le moteur fonctionnel et la
# logique métier commune. Les suffixes "wx" et "Qt" ne sont employés que
# lorsqu'un changement concerne spécifiquement l'interface graphique :
# "Noethys SL wx" pour wxPython, "Noethys SL Qt" pour Qt.
# "Vanilla" reste un terme historique de travail, pas un nom de produit ni
# un identifiant de toolkit.
#
# La numérotation publique est volontairement indépendante de la nomenclature
# historique de Noethys afin de ne pas créer de collision ni de fausse
# continuité avec les numéros de version de Noethys d'origine, créé par
# Ivan LUCAS, et avec ses évolutions ultérieures.
#
# La version de compatibilité interne (VERSION_APPLICATION dans Noethys.py,
# dérivée de Versions.txt via FonctionsPerso.GetVersionLogiciel()) reste
# inchangée et
# ne doit JAMAIS être remplacée par PRODUCT_VERSION : elle alimente
# MainFrame.ConvertVersionTuple()/ValidationVersionFichier() (Noethys.py),
# les 134 paliers de UpgradeDB.DB.Upgrade(), FonctionsPerso.CompareVersions()
# et le protocole Connecthys (UTILS_Portail_synchro.Update_application(),
# qui envoie un entier au serveur) -- tous exigent une chaîne "x.x.x.x"
# strictement numérique et échouent immédiatement sur un suffixe comme
# "-rc.1" (voir l'audit ayant motivé ce fichier séparé).
#-----------------------------------------------------------

PRODUCT_NAME = u"Noethys SL"

# Forme canonique (tag Git, noms d'artefacts) : noethys-sl-0.1.0-rc.1,
# Noethys-SL-0.1.0-rc.1-Windows-portable.zip, Noethys-SL-0.1.0-rc.1-Setup.exe
PRODUCT_VERSION = "0.1.0-rc.1"

# Forme affichée à l'utilisateur (titre de fenêtre, à propos, écran d'accueil)
PRODUCT_VERSION_DISPLAY = u"0.1.0 RC1"
