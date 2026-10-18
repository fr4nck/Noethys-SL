# -*- coding: utf-8 -*-
"""Suggestions de repas de direction (#430), independantes de toute base.

Une organisation mono-site peut commander un repas de directeur par site.
Une organisation multisite identifiee peut mutualiser ce poste de direction,
et eventuellement commander un repas de renfort (adjoint ou stagiaire).
Les deux repas doivent etre explicitement declares comme non deja comptes.
Ce module ne presume jamais de l'encadrement reglementaire.
"""


def _cle_direction(parametres, date):
    if not isinstance(parametres, dict):
        return None
    site = str(parametres.get("site_directeur") or "").strip().casefold()
    service = str(parametres.get("service_directeur") or "").strip().casefold()
    if not site or not service:
        return None
    if parametres.get("direction_multisite"):
        groupe = str(parametres.get("groupe_direction") or "").strip().casefold()
        if not groupe:
            return None
        return (date, service, "multisite", groupe)
    return (date, service, "site", site)


def _supplements(parametres, date, comptes, inclure_renfort):
    cle = _cle_direction(parametres, date)
    if cle is None:
        return 0
    total = 0
    if parametres.get("repas_directeur_detache"):
        cle_directeur = cle + ("directeur",)
        if cle_directeur not in comptes:
            comptes.add(cle_directeur)
            total += 1
    if inclure_renfort and parametres.get("repas_renfort_direction"):
        if parametres.get("direction_renfort") in ("adjoint", "stagiaire"):
            # Un poste de renfort au plus, meme si deux colonnes le
            # qualifient differemment. Ne compte pas automatiquement
            # le renfort comme animateur de terrain.
            cle_renfort = cle + ("renfort",)
            if cle_renfort not in comptes:
                comptes.add(cle_renfort)
                total += 1
    return total


def SupplementDirecteur(parametres, date, sites_deja_comptes):
    """Compatibilite avec le premier lot : un directeur, jamais deux."""
    return _supplements(parametres, date, sites_deja_comptes, False)


def SupplementRepasDirection(parametres, date, personnels_deja_comptes):
    """Nombre de repas de direction optionnels (0, 1 ou 2).

    Le decompte se limite aux colonnes d'une meme commande. Pour
    plusieurs commandes independantes, un controle inter-commandes
    et une affectation de repas restent a developper.
    """
    return _supplements(parametres, date, personnels_deja_comptes, True)
