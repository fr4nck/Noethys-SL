# -*- coding: utf-8 -*-
"""Export fournisseur Océane : copie du bordereau officiel, mercredi par site.

Les données proviennent d'un contrôle explicite des commandes Noethys.
L'export ne transmet aucun mail et ne modifie ni la base ni le modèle.
"""
from datetime import timedelta
from pathlib import Path

from Utils import UTILS_Repas_oceane as O
from Utils import UTILS_Oceane_xlsx as X
from Utils.UTILS_Repas_oceane_annexe import _grammage

LIGNES_LIBELLES = {
    8: "Entrée", 9: "Plat", 10: "Garniture", 11: "Laitage", 12: "Dessert",
    17: "Dont sans porc", 18: "Dt sans viande", 19: "Dont végétarien",
    20: "Dont sans allergène",
}
ONGLETS = {"LGB": 7011, "MOUT": 7012, "Bais": 7077}


def AffecterBlocs(lignes):
    """Deux semaines (au plus) pour le bordereau, le même bloc sur les sites.

    Aucune date hors mercredi, aucun doublon site/date, aucune disparition
    silencieuse du troisième mercredi d'une période.
    """
    lignes = list(lignes)
    if not lignes:
        raise ValueError("Aucun mercredi de repas à exporter")
    jours = [O._mercredi(ligne["date"]) for ligne in lignes]
    semaines = sorted({jour - timedelta(days=2) for jour in jours})
    if len(semaines) > 2:
        raise ValueError("Le bordereau Océane contient deux semaines maximum : découpez la période")
    vus = set()
    resultat = []
    for ligne, jour in zip(lignes, jours):
        feuille, _ = O._site(ligne["site"])
        cle = (feuille, jour)
        if cle in vus:
            raise ValueError("Commande Océane en double pour le site et la date")
        vus.add(cle)
        nouvelle = dict(ligne)
        nouvelle["date"] = jour
        nouvelle["bloc"] = semaines.index(jour - timedelta(days=2)) + 1
        resultat.append(nouvelle)
    return resultat


def _valider_modele(chemin, sites):
    donnees, _is1904 = X.LireClasseur(chemin, noms=sites)
    for site in sites:
        cellules = donnees[site]
        try:
            code = int(cellules.get("B2"))
            code2 = int(cellules.get("B27"))
        except (TypeError, ValueError):
            raise ValueError("Le bordereau ne contient pas les codes client Océane")
        if code != ONGLETS[site] or code2 != code:
            raise ValueError("Code client incorrect pour %s" % site)
        for shift in (0, 25):
            if str(cellules.get("I%d" % (6 + shift), "")).strip().upper() != "MERCREDI":
                raise ValueError("Mise en page Océane non reconnue : mercredi absent")
            for col, lib in (("I", "M"), ("J", "P"), ("K", "A")):
                if str(cellules.get("%s%d" % (col, 7 + shift), "")).strip() != lib:
                    raise ValueError("Colonnes M/P/A Océane non reconnues")
            for ligne, prefixe in LIGNES_LIBELLES.items():
                titre = str(cellules.get("A%d" % (ligne + shift), "")).strip()
                if not titre.startswith(prefixe):
                    raise ValueError("Ligne fournisseur %d non reconnue (%s)" %
                                     (ligne + shift, prefixe))
    return donnees


def ExporterBordereau(modele_xlsx, destination_xlsx, lignes):
    """Génère le bordereau par site et mercredi sur deux semaines max.

    Chaque ligne attend 'date', 'site', 'service', 'totaux' et quatre
    variantes alimentaires ventilées M/P. Les quantités des composantes
    peuvent être précisées explicitement (sinon M/P). Le document est
    toujours sauvegardé comme copie distincte.
    """
    attribuees = AffecterBlocs(lignes)
    propositions = O.PreparerLotsMercredis(attribuees)
    sites = {p["site"] for p in propositions}
    modele = _valider_modele(modele_xlsx, sites)
    ecritures = {}
    blocs = {}
    for ligne, p in zip(attribuees, propositions):
        if p["repartition_alimentaire_a_completer"]:
            raise ValueError(
                "%s %s : précisez M/P pour sans porc, sans viande, végétarien "
                "et sans allergène avant l'export" %
                (p["site"], p["date"].strftime("%d/%m/%Y")))
        feuille = p["site"]
        bloc = p["bloc"]
        jour = p["date"]
        # Prévol de tous les emplacements : refuser un bordereau déjà saisi.
        cells = modele[feuille]
        for coord in list(p["cellules"]) + list(p["colonne_adulte_a_vider"]):
            val = cells.get(coord)
            if val is not None and str(val).strip():
                raise ValueError("%s : %s contient déjà une valeur" % (feuille, coord))
        decalage = (bloc - 1) * 25
        debut, fin = jour - timedelta(days=2), jour + timedelta(days=2)
        ecritures.setdefault(feuille, {}).update(p["cellules"])
        # La fiche du fournisseur n'a pas de colonne grammage.
        # Une demande explicite pour le PLAT peut figurer dans Commentaires,
        # le détail interne est conservé dans l'annexe CSV.
        grammes_plat = (ligne.get("grammages") or {}).get("plat") or {}
        grammes_M = _grammage(grammes_plat.get("M"))
        grammes_P = _grammage(grammes_plat.get("P"))
        if grammes_M or grammes_P:
            texte = "Plat : grammage demandé M %s g / P %s g (à confirmer)" % (
                grammes_M if grammes_M else "-",
                grammes_P if grammes_P else "-")
            ecritures[feuille]["J%d" % (21 + decalage)] = texte
        ecritures[feuille].update({
            "C%d" % (4 + decalage): jour.isocalendar().week,
            "E%d" % (4 + decalage): debut.strftime("%d/%m/%Y"),
            "J%d" % (4 + decalage): fin.strftime("%d/%m/%Y"),
        })
        blocs[(feuille, bloc)] = jour
    # Prévol des cellules de semaine contre toute écriture antérieure.
    for feuille, edit in ecritures.items():
        for coord in edit:
            val = modele[feuille].get(coord)
            if val is not None and str(val).strip():
                raise ValueError("%s : cellule %s déjà renseignée" % (feuille, coord))
    X.EcrireCopie(modele_xlsx, destination_xlsx, ecritures)
    return {
        "chemin": str(Path(destination_xlsx)),
        "sites": tuple(sorted(sites)), "mercredis": len(propositions),
        "blocs": len(set(j for _s,j in blocs)),
        "adultes_inclus_P": sum(p["adultes_dans_P"] for p in propositions),
        "total_M": sum(p["repas_M"] for p in propositions),
        "total_P": sum(p["repas_P"] for p in propositions),
    }
