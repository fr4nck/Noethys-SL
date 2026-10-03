#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gestion ciblée des modèles Noedoc de catégorie ``convention``.

Ce module ne crée aucun moteur documentaire parallèle : il pilote les tables
historiques ``documents_modeles`` / ``documents_objets`` et réutilise les
fonctions génériques d'import de ``UTILS_Export_documents``.
"""

from __future__ import annotations

import GestionDB
from Utils.UTILS_Traduction import _
from Utils import UTILS_Export_documents


CATEGORIE = "convention"


def _VerifierNom(nom):
    nom = (nom or u"").strip()
    if not nom:
        raise ValueError(_(u"Le nom du modèle ne peut pas être vide."))
    return nom


def GetModele(IDmodele):
    """Retourne les propriétés utiles d'un modèle Convention, ou ``None``."""
    if IDmodele is None:
        return None
    DB = GestionDB.DB()
    req = """SELECT IDmodele, nom, categorie, largeur, hauteur, IDfond,
                    defaut, supprimable, observations
             FROM documents_modeles WHERE IDmodele=%d;""" % int(IDmodele)
    DB.ExecuterReq(req)
    lignes = DB.ResultatReq()
    DB.Close()
    if not lignes:
        return None
    (IDmodele, nom, categorie, largeur, hauteur, IDfond,
     defaut, supprimable, observations) = lignes[0]
    if categorie != CATEGORIE:
        return None
    return {
        "IDmodele": IDmodele,
        "nom": nom or u"",
        "categorie": categorie,
        "largeur": largeur,
        "hauteur": hauteur,
        "IDfond": IDfond,
        "defaut": int(defaut or 0),
        "supprimable": int(supprimable or 0),
        "observations": observations or u"",
    }


def GetModeles():
    """Liste les modèles Convention sans charger leurs objets."""
    DB = GestionDB.DB()
    DB.ExecuterReq("""SELECT IDmodele, nom, defaut, supprimable
                      FROM documents_modeles
                      WHERE categorie='convention'
                      ORDER BY nom, IDmodele;""")
    lignes = DB.ResultatReq()
    DB.Close()
    return [
        {
            "IDmodele": IDmodele,
            "nom": nom or u"",
            "defaut": int(defaut or 0),
            "supprimable": int(supprimable or 0),
        }
        for IDmodele, nom, defaut, supprimable in lignes
    ]


def InstallerModelesExemples():
    """Installe idempotemment tous les exemples Convention embarqués.

    Un modèle déjà installé n'est jamais écrasé. Le modèle scolaire est donc
    disponible au même titre que les modèles associatifs, sans traitement
    métier spécifique.
    """
    IDs = []
    for exemple in UTILS_Export_documents.GetModelesExemplesConvention():
        if exemple.get("categorie") != CATEGORIE:
            continue
        IDs.append(UTILS_Export_documents.ImporterModeleExempleIdempotent(
            fichier=exemple["fichier"]
        ))
    return IDs


def AssurerModelesDisponibles():
    """Installe les exemples uniquement si aucun modèle Convention n'existe."""
    modeles = GetModeles()
    if modeles:
        return [modele["IDmodele"] for modele in modeles]
    return InstallerModelesExemples()


def DupliquerModele(IDmodele, nom):
    """Duplique un modèle et tous ses objets ; la copie n'est jamais défaut."""
    source = GetModele(IDmodele)
    if source is None:
        raise ValueError(_(u"Le modèle de convention sélectionné n'existe plus."))
    nom = _VerifierNom(nom)

    DB = GestionDB.DB()
    conditions = "IDmodele=%d" % int(IDmodele)
    newIDmodele = DB.Dupliquer(
        "documents_modeles", "IDmodele", conditions,
        {"nom": nom, "categorie": CATEGORIE, "defaut": 0, "supprimable": 1},
    )
    DB.Dupliquer(
        "documents_objets", "IDobjet", conditions,
        {"IDmodele": newIDmodele},
    )
    DB.Close()
    return newIDmodele


def RenommerModele(IDmodele, nom):
    """Renomme un modèle Convention existant."""
    if GetModele(IDmodele) is None:
        raise ValueError(_(u"Le modèle de convention sélectionné n'existe plus."))
    nom = _VerifierNom(nom)
    DB = GestionDB.DB()
    resultat = DB.ReqMAJ(
        "documents_modeles", [("nom", nom)], "IDmodele", int(IDmodele)
    )
    DB.Close()
    return resultat


def DefinirModeleDefaut(IDmodele):
    """Définit un unique modèle par défaut pour la catégorie Convention."""
    if GetModele(IDmodele) is None:
        raise ValueError(_(u"Le modèle de convention sélectionné n'existe plus."))
    DB = GestionDB.DB()
    DB.ExecuterReq("""SELECT IDmodele FROM documents_modeles
                      WHERE categorie='convention';""")
    IDs = [ligne[0] for ligne in DB.ResultatReq()]
    for IDcourant in IDs:
        DB.ReqMAJ(
            "documents_modeles",
            [("defaut", 1 if IDcourant == int(IDmodele) else 0)],
            "IDmodele", IDcourant,
        )
    DB.Close()
    return True


def SupprimerModele(IDmodele):
    """Supprime un modèle supprimable et ses objets.

    Si le modèle supprimé était le défaut, le premier modèle restant devient
    le nouveau défaut afin de conserver une sélection stable au prochain
    démarrage.
    """
    modele = GetModele(IDmodele)
    if modele is None:
        raise ValueError(_(u"Le modèle de convention sélectionné n'existe plus."))
    if not modele["supprimable"]:
        raise ValueError(_(u"Ce modèle est protégé et ne peut pas être supprimé."))

    DB = GestionDB.DB()
    DB.ReqDEL("documents_objets", "IDmodele", int(IDmodele))
    DB.ReqDEL("documents_modeles", "IDmodele", int(IDmodele))
    DB.Close()

    if modele["defaut"]:
        restants = GetModeles()
        if restants:
            DefinirModeleDefaut(restants[0]["IDmodele"])
    return True
