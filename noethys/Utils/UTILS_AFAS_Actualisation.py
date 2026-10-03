# -*- coding: utf-8 -*-
"""Préparation de l'activité AFAS actualisée, sans transmission à la CAF."""
import csv
import datetime
import math

from Utils import UTILS_AFAS
from Utils import UTILS_AFAS_Donnees
from Utils import UTILS_Ouvertures

PHASES = (
    (UTILS_AFAS.PHASE_PREVISIONNEL, "Prévisionnel annuel"),
    (UTILS_AFAS.PHASE_ACTUALISATION_JUIN, "Actualisée (Juin)"),
    (UTILS_AFAS.PHASE_ACTUALISATION_SEPTEMBRE, "Actualisée (Septembre)"),
    (UTILS_AFAS.PHASE_REEL, "Réel annuel"),
)


def Periodes(annee, phase):
    cycle = UTILS_AFAS.GetCycleAFAS(annee)[phase]
    situation = cycle["date_situation"]
    debut, fin = cycle["date_debut"], cycle["date_fin"]
    if phase == UTILS_AFAS.PHASE_PREVISIONNEL:
        return None, None, debut, fin, fin
    if phase == UTILS_AFAS.PHASE_REEL:
        return debut, fin, None, None, fin
    return debut, situation, situation + datetime.timedelta(days=1), fin, situation


def LabelPeriode(debut, fin):
    if debut is None:
        return "Sans période"
    return "%s–%s" % (debut.strftime("%d/%m"), fin.strftime("%d/%m"))


METRIQUES = (
    ("heures_reelles", "Heures réalisées"),
    ("heures_reelles_aeeh", "Dont heures réalisées AEEH"),
    ("heures_facturees", "Heures facturées"),
    ("heures_facturees_aeeh", "Dont heures facturées AEEH"),
)


def NombrePositif(valeur):
    nombre = float(str(valeur).replace(",", "."))
    if not math.isfinite(nombre) or nombre < 0:
        raise ValueError("Saisir un nombre positif ou nul et fini")
    return nombre


def PreparerActualisation(annee, perimetres, dictUnites, dict_options,
                         methode=UTILS_AFAS.METHODE_N1_AJUSTE, valeurs_manuelles=None,
                         phase=UTILS_AFAS.PHASE_ACTUALISATION_SEPTEMBRE):
    annee = int(annee)
    debut, fin_reel, restant, fin, situation = Periodes(annee, phase)
    if not perimetres:
        raise ValueError("Sélectionner les activités et groupes de l'équipement CAF")
    activites = {a for a, g in perimetres}
    unites = {cle: dict(valeur) for cle, valeur in dictUnites.items()
              if valeur["IDactivite"] in activites}
    if not unites or any(a not in {u["IDactivite"] for u in unites.values()} for a in activites):
        raise ValueError("Configurer les unités de chaque activité sélectionnée dans l'état global")
    if any(u["typeCalcul"] in (2, 3) for u in unites.values()):
        raise ValueError("Le profil du réalisé doit utiliser les coefficients ou les temps réels. "
                         "Les formules uniteN ne sont pas encore qualifiées pour AFAS.")
    facture = {cle: dict(valeur, typeCalcul=2, coeff=None, arrondi=None,
                        duree_plafond=None, duree_seuil=None, heure_plafond=None,
                        heure_seuil=None, formule=None) for cle, valeur in unites.items()}
    def charger(d1, d2, date_situation):
        return UTILS_AFAS_Donnees.GetDonneesPeriodeAFAS(
            perimetres, d1, d2, date_situation, unites, facture, dict_options)
    reel = charger(debut, fin_reel, situation) if debut else dict(
        {cle: 0.0 for cle, label in METRIQUES}, jours_ouverts=0)
    jours = len(set(date for a, g in perimetres for date in
                    UTILS_Ouvertures.GetDatesOuverture(a, g, restant, fin))) if restant else 0
    historique = None
    if restant and methode == UTILS_AFAS.METHODE_N1_AJUSTE:
        if jours == 0:
            raise ValueError("Aucun jour d'ouverture programmé sur la période à prévoir : "
                             "vérifier le calendrier ou saisir le prévisionnel manuellement")
        historique = charger(restant.replace(year=annee-1), fin.replace(year=annee-1),
                             datetime.date(annee-1, 12, 31))
        if historique["jours_ouverts"] == 0:
            raise ValueError("Aucun calendrier exploitable sur la même période de N-1. "
                             "Saisir le prévisionnel manuellement")
    elif restant and methode != UTILS_AFAS.METHODE_MANUEL:
        raise ValueError("Méthode inconnue")
    lignes = {}
    for cle, label in METRIQUES:
        if not restant:
            estimation = 0.0
        elif methode == UTILS_AFAS.METHODE_MANUEL:
            if valeurs_manuelles is None or cle not in valeurs_manuelles:
                raise ValueError("Prévision manuelle manquante : " + label)
            estimation = NombrePositif(valeurs_manuelles[cle])
        else:
            estimation = UTILS_AFAS.EstimerPeriode(methode,
                [{"heures": historique[cle], "jours_ouverts": historique["jours_ouverts"]}], jours)
        lignes[cle] = UTILS_AFAS.CalculerActualisation(reel[cle], estimation)
    for total, part in (("heures_reelles", "heures_reelles_aeeh"),
                        ("heures_facturees", "heures_facturees_aeeh")):
        if lignes[part]["prevision_restant"] > lignes[total]["prevision_restant"]:
            raise ValueError("Le sous-total AEEH prévisionnel dépasse le total")
    return dict(annee=annee, phase=phase, perimetres=list(perimetres), methode=methode,
                date_situation=situation, lignes=lignes, historique=historique,
                jours_realises=reel["jours_ouverts"], jours_previsionnels=jours,
                options=dict(dict_options), unites=unites)


def ExporterCSV(chemin, rapport, equipement):
    """UTF-8 avec BOM et décimales françaises, lisible dans Excel."""
    with open(chemin, "w", encoding="utf-8-sig", newline="") as fichier:
        writer = csv.writer(fichier, delimiter=";")
        writer.writerow(["Équipement", equipement])
        writer.writerow(["Déclaration", dict(PHASES)[rapport["phase"]], rapport["annee"]])
        debut, fin_reel, restant, fin, situation = Periodes(rapport["annee"], rapport["phase"])
        writer.writerow(["Périmètres (activité, groupe)", repr(rapport["perimetres"])])
        writer.writerow(["Méthode", rapport["methode"]])
        writer.writerow(["États retenus", ", ".join(rapport["options"].get("etat_consommations", []))])
        writer.writerow(["Options de calcul", repr(rapport["options"])])
        writer.writerow(["Unités du réalisé", repr(rapport["unites"])])
        writer.writerow(["AEEH", "Droits actifs à la date de situation", str(situation), "Historique : au 31/12 N-1"])
        writer.writerow(["Données financières", "À compléter depuis la comptabilité ; hors de cet export d'activité"])
        writer.writerow(["Indicateur (heures)", "Réalisé " + LabelPeriode(debut, fin_reel), "Prévision " + LabelPeriode(restant, fin), "Total annuel"])
        for cle, label in METRIQUES:
            ligne = rapport["lignes"][cle]
            writer.writerow([label] + [format(ligne[col], ".2f").replace(".", ",")
                                      for col in ("realise", "prevision_restant", "total_actualise")])
        writer.writerow(["Jours ouverts distincts", rapport["jours_realises"], rapport["jours_previsionnels"]])
        if rapport["historique"] is not None:
            writer.writerow(["Historique " + LabelPeriode(restant, fin), rapport["annee"]-1,
                             "Jours ouverts", rapport["historique"]["jours_ouverts"]])
            for cle, label in METRIQUES:
                writer.writerow([label, rapport["historique"][cle]])
