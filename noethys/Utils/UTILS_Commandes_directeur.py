# -*- coding: utf-8 -*-
"""Supplement de commande de repas : directeur detache d'animation (RC8 / #430).

Ce module ne consulte aucune base et ne deduit jamais la presence du directeur.
L'option explicite du modele signifie que son repas n'est pas deja compte
par la colonne des adultes. Le resultat reste une suggestion a confirmer
via « Convertir les suggestions » dans la commande.
"""


def SupplementDirecteur(parametres, date, sites_deja_comptes):
    """Retourne 1 au plus une fois par site/date/service (sinon 0).

    « Site » est l'identifiant renseigne dans le modele de commande ; le
    meme site peut avoir plusieurs groupes et colonnes sans doublon.
    """
    if not isinstance(parametres, dict) or not parametres.get("repas_directeur_detache"):
        return 0
    site = str(parametres.get("site_directeur") or "").strip().casefold()
    service = str(parametres.get("service_directeur") or "").strip().casefold()
    if not site or not service:
        return 0
    cle = (date, site, service)
    if cle in sites_deja_comptes:
        return 0
    sites_deja_comptes.add(cle)
    return 1
