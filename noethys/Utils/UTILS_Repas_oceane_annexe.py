# -*- coding: utf-8 -*-
"""Annexe interne de commande, avec menus et grammages par composante.

CSV séparé du modèle fournisseur : aucune donnée nominative, pas de
modification des inscriptions Noethys ou de la commande validée.
"""
import csv
from pathlib import Path
import os
import tempfile
from datetime import date
from Utils import UTILS_Repas_oceane as O
from Utils.UTILS_Repas_totaux import EntierNaturel

CHAMPS = ("date", "site", "composante", "plat", "tranche",
          "commandes", "grammes_par_portion")


def _grammage(valeur):
    if valeur in ("", None):
        return 0
    nombre = EntierNaturel(valeur, "grammage")
    if nombre > 2000:
        raise ValueError("Grammage par portion excessif")
    return nombre


def ConstruireAnnexe(lignes):
    resultat = []
    for ligne in lignes:
        jour = O._mercredi(ligne["date"])
        site, _ = O._site(ligne["site"])
        composants = ligne.get("composantes")
        if not isinstance(composants, dict) or set(composants) != set(O.COMPOSANTES):
            raise ValueError("Composantes manquantes dans l'annexe Océane")
        noms = ligne.get("intitules") or {}
        grammes = ligne.get("grammages") or {}
        for comp in O.COMPOSANTES:
            quantites = O._colonnes_tranches(composants[comp])
            texte = " ".join(str(noms.get(comp) or "A PRECISER").split())
            if len(texte) > 250:
                raise ValueError("Intitulé menu excessif")
            for tranche in ("M", "P"):
                resultat.append({
                    "date": jour.isoformat(), "site": site,
                    "composante": comp, "plat": texte, "tranche": tranche,
                    "commandes": quantites[tranche],
                    "grammes_par_portion": _grammage(
                        (grammes.get(comp) or {}).get(tranche)),
                })
    if not resultat:
        raise ValueError("Annexe vide")
    return resultat


def EnregistrerAnnexe(chemin, lignes):
    if Path(chemin).suffix.lower() != ".csv":
        raise ValueError("L'annexe est attendue en CSV")
    donnees = ConstruireAnnexe(lignes)
    dest = Path(chemin)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8-sig", newline="",
                dir=str(dest.parent), prefix=".oc-annexe-",
                suffix=".csv", delete=False) as f:
            temp = Path(f.name)
            writer = csv.DictWriter(f, fieldnames=CHAMPS,
                                    delimiter=";", lineterminator="\n")
            writer.writeheader()
            writer.writerows(donnees)
        os.replace(temp, dest)
    finally:
        if temp and temp.exists():
            temp.unlink()
    return len(donnees)


def LireAnnexe(chemin):
    with open(chemin, "r", newline="", encoding="utf-8-sig") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        if lecteur.fieldnames != list(CHAMPS):
            raise ValueError("Ce CSV ne correspond pas à une annexe Océane")
        donnees = []
        for row in lecteur:
            jour = O._mercredi(row["date"])
            site, _ = O._site(row["site"])
            comp = row["composante"]
            tranche = row["tranche"]
            if comp not in O.COMPOSANTES or tranche not in ("M", "P"):
                raise ValueError("Composante ou catégorie erronée dans l'annexe")
            donnees.append(dict(
                date=jour.isoformat(), site=site,
                composante=comp, plat=row["plat"], tranche=tranche,
                commandes=EntierNaturel(row["commandes"], "commandes"),
                grammes_par_portion=_grammage(row["grammes_par_portion"])))
    if not donnees:
        raise ValueError("Annexe sans quantité")
    return donnees
