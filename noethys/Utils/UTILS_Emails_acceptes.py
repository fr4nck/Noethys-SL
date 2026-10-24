# -*- coding: utf-8 -*-
"""Adresses déjà acceptées par le serveur d'envoi pour une confirmation
Connecthys partiellement envoyée.

Quand une confirmation (réponse à une demande, reçu, facture) n'est acceptée
que pour une partie des adresses de la famille, la demande reste « attente »
(aucun changement du protocole Connecthys). Les adresses déjà acceptées
sont mémorisées localement pour qu'un nouvel essai n'envoie qu'aux adresses
restantes, sans doublon. L'entrée est effacée dès que toutes les adresses
sont acceptées.

Stockage : table native `parametres`, catégorie dédiée, valeur JSON. Cette
catégorie n'est jamais lue par la synchronisation Connecthys (catégorie
`portail` uniquement) ; aucune migration de schéma.
"""
import json
import re

import GestionDB

CATEGORIE = "noethys_sl_emails_acceptes"
_CLE = re.compile(r"^[a-z0-9_]{1,80}$")


def CleDemande(IDaction, document):
    """Clé d'une confirmation Connecthys : demande + document envoyé."""
    cle = "portail_action_%d_%s" % (int(IDaction), document)
    if not _CLE.match(cle):
        raise ValueError("Clé de suivi invalide : %r" % cle)
    return cle


def _verifier(cle):
    if not isinstance(cle, str) or not _CLE.match(cle):
        raise ValueError("Clé de suivi invalide : %r" % (cle,))


def Normaliser(adresse):
    return (adresse or u"").strip().lower()


def Lire(cle):
    """Ensemble des adresses (normalisées) déjà acceptées pour cette clé."""
    _verifier(cle)
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq("SELECT parametre FROM parametres WHERE categorie='%s' AND nom='%s';" % (CATEGORIE, cle))
        lignes = DB.ResultatReq()
    finally:
        DB.Close()
    adresses = set()
    for (texte,) in lignes:
        try:
            valeurs = json.loads(texte or "[]")
        except ValueError:
            continue
        if isinstance(valeurs, list):
            adresses.update(Normaliser(v) for v in valeurs if isinstance(v, str) and v.strip())
    return adresses


def Effacer(cle):
    _verifier(cle)
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq("DELETE FROM parametres WHERE categorie='%s' AND nom='%s';" % (CATEGORIE, cle))
        DB.Commit()
    finally:
        DB.Close()


def Enregistrer(cle, adresses):
    """Remplace la liste mémorisée par `adresses` (une seule ligne par clé)."""
    _verifier(cle)
    valeur = json.dumps(sorted({Normaliser(a) for a in adresses if Normaliser(a)}))
    Effacer(cle)
    DB = GestionDB.DB()
    try:
        DB.ReqInsert("parametres", [("categorie", CATEGORIE), ("nom", cle), ("parametre", valeur)])
    finally:
        DB.Close()
