# -*- coding: utf-8 -*-
"""Contrat de prevalidation des commandes avant PDF ou email (#430)."""

from datetime import date
from Utils.UTILS_Repas_totaux import TotauxRepas

ROLES = ("moins_6", "six_plus", "animateurs", "direction", "autres_adultes", "sans_porc")
CHAMPS = ("enfants_moins_6", "enfants_6_et_plus", "animateurs_repas",
          "direction_repas", "autres_adultes_repas", "sans_porc")
CLE_CHAMP = dict(zip(ROLES, CHAMPS))


def ConstruireControle(donnees):
    """Construit une representation non nominative des cellules existantes.

    Refuse les roles redondants dans une meme plage ainsi que les erreurs de
    source. N'ecrit aucune donnee et n'infere pas les noms des colonnes.
    """
    colonnes = donnees.get("liste_colonnes", [])
    dates = [d for d in donnees.get("liste_dates", []) if isinstance(d, date)]
    cases = donnees.get("cases", {})
    if donnees.get("erreurs_sans_porc"):
        raise ValueError("Parametrage sans porc incomplet : %s" %
                         "; ".join(str(x) for x in donnees["erreurs_sans_porc"].values()))
    config = []
    non_classes = []
    for index, col in enumerate(colonnes):
        params = col.get("parametres") or {}
        role = params.get("role_repas", "aucun")
        if role not in ROLES:
            if "numerique" in col.get("categorie", "") and "total" not in col.get("categorie", ""):
                non_classes.append(col.get("nom_colonne", "Colonne non classee"))
            continue
        site = str(params.get("site_directeur") or "").strip()
        service = str(params.get("service_directeur") or "").strip()
        if not site or not service:
            raise ValueError("Site et service manquants pour la colonne %s" % col.get("nom_colonne"))
        config.append((index, role, site, service))
    if not config:
        raise ValueError("Aucune colonne de repas classee : configurez les roles dans le modele")
    resultat = {}
    for row, jour in enumerate(dates):
        for col, role, site, service in config:
            cle = (jour, site, service)
            entree = resultat.setdefault(cle, {"date": jour, "site": site, "service": service,
                                                 "valeurs": {champ: 0 for champ in CHAMPS},
                                                 "cases": {}})
            if role in entree["cases"]:
                raise ValueError("Deux colonnes %s sur le meme site et service" % role)
            case = cases.get((row, col))
            if case is None:
                raise ValueError("Case de repas manquante dans la grille")
            valeur = case.GetValeur()
            if valeur is None:
                valeur = 0
            entree["valeurs"][CLE_CHAMP[role]] = valeur
            entree["cases"][role] = case
    lignes = []
    for key, entree in sorted(resultat.items()):
        entree["totaux"] = TotauxRepas(**entree["valeurs"])
        entree["colonnes_non_classees"] = tuple(non_classes)
        lignes.append(entree)
    return lignes


def AppliquerControle(lignes):
    """Applique uniquement les valeurs explicites du dialogue accepte."""
    for item in lignes:
        TotauxRepas(**item["valeurs"])
    for item in lignes:
        for role, case in item["cases"].items():
            case.SetValeur(item["valeurs"][CLE_CHAMP[role]])
