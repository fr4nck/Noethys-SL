# -*- coding: utf-8 -*-
"""Suivi agrégé des restes Océane et suggestions prudentes.

Fichier CSV local, sans nom d'enfant ni donnée de santé. La recommandation
est indicative et ne modifie jamais une commande fournisseur.
"""
import csv
from datetime import date
import math
import os
from pathlib import Path
import tempfile
import unicodedata

from Utils.UTILS_Repas_totaux import EntierNaturel
from Utils.UTILS_Repas_oceane import COMPOSANTES, _site, _mercredi

CHAMPS = ("date", "site", "composante", "plat", "tranche",
          "commandes", "livrees", "servies", "restes_assiettes_g",
          "grammes_par_portion")
TRANCHES = ("M", "P")


def _positive_decimal(value, name):
    if isinstance(value, bool) or value is None:
        raise ValueError("%s invalide" % name)
    try:
        nombre = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("%s invalide" % name)
    if not math.isfinite(nombre) or nombre < 0:
        raise ValueError("%s doit être positif ou nul" % name)
    return nombre


def ValiderObservation(donnees):
    """Les portions non servies sont livrées - servies.

    Les restes d'assiette sont pesés et ne sont pas déduits en portions
    tant que le grammage réel de la composante n'est pas fourni.
    """
    if not isinstance(donnees, dict):
        raise ValueError("Observation invalide")
    jour = _mercredi(donnees.get("date"))
    site, _client = _site(donnees.get("site"))
    comp = donnees.get("composante")
    if comp not in COMPOSANTES:
        raise ValueError("Composante du menu inconnue")
    tranche = donnees.get("tranche")
    if tranche not in TRANCHES:
        raise ValueError("Tranche M ou P requise")
    plat = " ".join(str(donnees.get("plat", "")).split())
    if not plat or len(plat) > 250:
        raise ValueError("Intitulé du plat obligatoire")
    nombres = {k: EntierNaturel(donnees.get(k), k)
               for k in ("commandes", "livrees", "servies")}
    if nombres["servies"] > nombres["livrees"]:
        raise ValueError("Portions servies supérieures aux portions livrées")
    if nombres["livrees"] > nombres["commandes"]:
        # Une livraison supérieure est permise en pratique : elle doit
        # toutefois être constatée explicitement par l'opérateur.
        pass
    restes = _positive_decimal(
        donnees.get("restes_assiettes_g", 0), "Restes d'assiettes")
    grammes = _positive_decimal(
        donnees.get("grammes_par_portion", 0), "Grammage par portion")
    if restes and not grammes:
        raise ValueError("Précisez le grammage de référence pour les restes d'assiettes")
    if grammes and restes > nombres["servies"] * grammes:
        raise ValueError("Les restes pesés dépassent le poids des portions servies")
    return dict(date=jour.isoformat(), site=site, composante=comp,
                plat=plat, tranche=tranche,
                restes_assiettes_g="%.2f" % restes,
                grammes_par_portion="%.2f" % grammes,
                **nombres)


def LireHistorique(path):
    if not Path(path).is_file():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as fichier:
        reader = csv.DictReader(fichier, delimiter=";")
        if reader.fieldnames != list(CHAMPS):
            raise ValueError("Format d'historique Océane inconnu")
        resultat = []
        for index, ligne in enumerate(reader, start=2):
            try:
                resultat.append(ValiderObservation(ligne))
            except ValueError as exc:
                raise ValueError("Historique des restes ligne %d : %s" % (index, exc))
        return resultat


def EnregistrerObservations(path, observations):
    """Enregistrement atomique, refuse les doublons, pas d'effacement discret."""
    if Path(path).suffix.lower() != ".csv":
        raise ValueError("Fichier de suivi attendu en CSV")
    if not isinstance(observations, (list, tuple)) or not observations:
        raise ValueError("Aucune observation à enregistrer")
    nouvelles = [ValiderObservation(e) for e in observations]
    precedentes = LireHistorique(path)
    cles = set()
    for ligne in precedentes + nouvelles:
        cle = tuple(ligne[f] for f in ("date", "site", "composante",
                                      "plat", "tranche"))
        if cle in cles:
            raise ValueError("Observation déjà enregistrée : %s" % (cle,))
        cles.add(cle)
    cible = Path(path)
    cible.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8-sig", newline="",
                dir=str(cible.parent), prefix=".restes-", suffix=".csv",
                delete=False) as fichier:
            temp = Path(fichier.name)
            writer = csv.DictWriter(
                fichier, fieldnames=CHAMPS, delimiter=";", lineterminator="\n")
            writer.writeheader()
            writer.writerows(precedentes + nouvelles)
        os.replace(temp, cible)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return len(nouvelles)


def _normaliser_nom(plat):
    txt = unicodedata.normalize("NFKD", plat.casefold())
    return " ".join("".join(c for c in txt if not unicodedata.combining(c)).split())


def SuggereQuantite(historique, site, composante, plat, tranche,
                    quantite_prevue, minimum_observations=3):
    """Propose -0 à -15% à partir d'au moins 3 services COMPARABLES.

    Calcule le surplus non servi et les retours d'assiette en équivalents
    portions quand des grammages sont disponibles. La commande source
    n'est jamais modifiée. Les intitulés doivent correspondre exactement
    après normalisation : aucune extrapolation entre plats différents.
    """
    site, _ = _site(site)
    if composante not in COMPOSANTES or tranche not in TRANCHES:
        raise ValueError("Composante ou tranche invalide")
    attente = EntierNaturel(quantite_prevue, "quantite_prevue")
    candidatures = [
        ValiderObservation(item) for item in historique
        if _site(item["site"])[0] == site
        and item["composante"] == composante
        and item["tranche"] == tranche
        and _normaliser_nom(item["plat"]) == _normaliser_nom(plat)
    ]
    dates = {x["date"] for x in candidatures}
    if len(dates) < minimum_observations:
        return None
    livrees = sum(int(x["livrees"]) for x in candidatures)
    if livrees <= 0:
        return None
    non_servies = sum(int(x["livrees"]) - int(x["servies"])
                      for x in candidatures)
    retours_equivalents = sum(
        float(x["restes_assiettes_g"]) / float(x["grammes_par_portion"])
        for x in candidatures if float(x["grammes_par_portion"]) > 0)
    taux = min(0.15, max(0.0, (non_servies + retours_equivalents) / livrees))
    propose = max(0, math.ceil(attente * (1 - taux)))
    return {"nombre_observations": len(dates), "taux_observe":
            round((non_servies + retours_equivalents) / livrees, 4),
            "taux_reduction_plafonne": round(taux, 4),
            "quantite_prevue": attente, "quantite_proposee": propose,
            "validation_humaine_obligatoire": True}
