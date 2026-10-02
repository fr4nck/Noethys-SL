#!/usr/bin/env python
# -*- coding: utf-8 -*-
#-----------------------------------------------------------
# Identité publique du produit (affichage uniquement).
#
# Noethys SL est la marque et la version publiques de ce fork. La version
# de compatibilité interne (VERSION_APPLICATION dans Noethys.py, dérivée de
# Versions.txt via FonctionsPerso.GetVersionLogiciel()) reste inchangée et
# ne doit JAMAIS être remplacée par PRODUCT_VERSION : elle alimente
# MainFrame.ConvertVersionTuple()/ValidationVersionFichier() (Noethys.py),
# les 134 paliers de UpgradeDB.DB.Upgrade(), FonctionsPerso.CompareVersions()
# et le protocole Connecthys (UTILS_Portail_synchro.Update_application(),
# qui envoie un entier au serveur) -- tous exigent une chaîne "x.x.x.x"
# strictement numérique et échouent immédiatement sur un suffixe comme
# "-rc.1" (voir l'audit ayant motivé ce fichier séparé).
#-----------------------------------------------------------

PRODUCT_NAME = u"Noethys SL"

# Forme canonique (tag Git, noms d'artefacts) : noethys-sl-0.1.0-rc.2,
# Noethys-SL-0.1.0-rc.2-Windows-portable.zip, Noethys-SL-0.1.0-rc.2-Setup.exe
PRODUCT_VERSION = "0.1.0-rc.2"

# Forme affichée à l'utilisateur (titre de fenêtre, à propos, écran d'accueil)
PRODUCT_VERSION_DISPLAY = u"0.1.0 RC2"
