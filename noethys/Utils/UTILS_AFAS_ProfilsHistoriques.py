# -*- coding: utf-8 -*-
"""Sécurisation des profils CAF historiques de l'état global.

Les anciens profils d'état global restent utilisables pour un contrôle
interne. Ils ne sont ni des presets AFAS V2, ni une déclaration CAF.
Aucune écriture dans les paramètres persistés n'est réalisée ici.
"""
import unicodedata


_PROFILS_CAF_HISTORIQUES = ("caf - periscolaire", "caf - extrascolaire")


def EstProfilCAFHistorique(nom):
    """Reconnaît seulement les deux profils constatés dans l'audit ALSH.

    Ne s'applique pas aux autres profils de l'état global ni à AFAS V2.
    """
    if not isinstance(nom, str):
        return False
    texte = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode("ascii")
    texte = " ".join(texte.lower().replace("\u2013", "-").replace("\u2014", "-").split())
    return texte in _PROFILS_CAF_HISTORIQUES


def PreparerProfilCAFHistorique(nom, parametres):
    """Sélectionne 'présent' seul en mémoire au chargement du profil.

    Renvoie (paramètres, modifiés). La source originale n'est jamais mutée
    ni réenregistrée sans clic explicite sur Enregistrer.
    """
    if not isinstance(parametres, dict) or not EstProfilCAFHistorique(nom):
        return parametres, False
    if parametres.get("etat_consommations") == ["present"]:
        return parametres, False
    corrige = dict(parametres)
    corrige["etat_consommations"] = ["present"]
    return corrige, True


def ErreurEtatsProfilCAFHistorique(nom, etats):
    """Avant aperçu, interdit que réservation ou absence redevienne du réalisé."""
    if not EstProfilCAFHistorique(nom):
        return None
    if isinstance(etats, (list, tuple)) and list(etats) == ["present"]:
        return None
    return (
        "Le profil CAF historique ne peut pas compter les réservations ou les "
        "absences comme heures réalisées. Dans 'Etat des consommations', "
        "sélectionnez uniquement 'Présent'. Pour préparer une déclaration "
        "CAF, utilisez 'Consommations > Déclarations AFAS' (V2)."
    )
