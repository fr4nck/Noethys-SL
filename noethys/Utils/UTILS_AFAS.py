#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Moteur de prévision CAF / AFAS pour les ALSH.

Les dates de situation suivent le cycle déclaratif CAF 35 :
- prévisionnel : année civile complète ;
- actualisation juin : situation au 30 juin ;
- actualisation septembre : situation au 30 septembre ;
- réel : année civile complète.

La méthode d'estimation historique ci-dessous est une règle applicative
Noethys/PMSL, pas une règle imposée par la Caf.
"""

import datetime


METHODE_N1_AJUSTE = "n1_ajuste"
METHODE_MOYENNE_2_ANS = "moyenne_2_ans"
METHODE_MOYENNE_3_ANS = "moyenne_3_ans"
METHODE_MANUEL = "manuel"

PHASE_PREVISIONNEL = "previsionnel"
PHASE_ACTUALISATION_JUIN = "actualisation_juin"
PHASE_ACTUALISATION_SEPTEMBRE = "actualisation_septembre"
PHASE_REEL = "reel"


def GetCycleAFAS(annee):
    """Retourne les bornes utiles du cycle CAF / AFAS pour une année civile."""
    annee = int(annee)
    return {
        PHASE_PREVISIONNEL: {
            "date_debut": datetime.date(annee, 1, 1),
            "date_fin": datetime.date(annee, 12, 31),
            "date_situation": None,
        },
        PHASE_ACTUALISATION_JUIN: {
            "date_debut": datetime.date(annee, 1, 1),
            "date_fin": datetime.date(annee, 12, 31),
            "date_situation": datetime.date(annee, 6, 30),
        },
        PHASE_ACTUALISATION_SEPTEMBRE: {
            "date_debut": datetime.date(annee, 1, 1),
            "date_fin": datetime.date(annee, 12, 31),
            "date_situation": datetime.date(annee, 9, 30),
        },
        PHASE_REEL: {
            "date_debut": datetime.date(annee, 1, 1),
            "date_fin": datetime.date(annee, 12, 31),
            "date_situation": datetime.date(annee, 12, 31),
        },
    }


def _VerifierHistorique(historique):
    """Normalise une liste de dicts {'heures': x, 'jours_ouverts': y}."""
    resultat = []
    for item in historique:
        heures = float(item.get("heures", 0.0))
        jours = float(item.get("jours_ouverts", 0.0))
        if jours <= 0:
            continue
        resultat.append({
            "heures": heures,
            "jours_ouverts": jours,
            "heures_par_jour": heures / jours,
        })
    return resultat


def EstimerPeriode(
    methode,
    historique,
    jours_ouverts_cible,
    valeur_manuelle=None,
):
    """Calcule une estimation d'heures-enfants pour une période homogène.

    historique :
        liste ordonnée du plus récent au plus ancien, par exemple :
        [
            {"heures": 12600, "jours_ouverts": 20},  # N-1
            {"heures": 11800, "jours_ouverts": 19},  # N-2
        ]

    La méthode N-1 ajustée extrapole le ratio heures/jour de N-1 vers le
    nombre de jours ouverts de N.

    Les moyennes 2/3 ans font la moyenne des ratios heures/jour disponibles,
    puis l'appliquent au nombre de jours ouverts de N.
    """
    jours_ouverts_cible = float(jours_ouverts_cible)

    if methode == METHODE_MANUEL:
        if valeur_manuelle is None:
            raise ValueError("Une valeur manuelle est requise")
        return float(valeur_manuelle)

    historique = _VerifierHistorique(historique)
    if not historique:
        raise ValueError("Aucun historique exploitable")

    if methode == METHODE_N1_AJUSTE:
        taux = historique[0]["heures_par_jour"]
        return taux * jours_ouverts_cible

    if methode == METHODE_MOYENNE_2_ANS:
        echantillon = historique[:2]
    elif methode == METHODE_MOYENNE_3_ANS:
        echantillon = historique[:3]
    else:
        raise ValueError("Méthode d'estimation inconnue : %s" % methode)

    taux_moyen = sum(item["heures_par_jour"] for item in echantillon) / len(echantillon)
    return taux_moyen * jours_ouverts_cible


def ConstruireComparaison(historique, jours_ouverts_cible):
    """Retourne les principales estimations à comparer pour l'utilisateur."""
    resultat = {}
    for methode in (
        METHODE_N1_AJUSTE,
        METHODE_MOYENNE_2_ANS,
        METHODE_MOYENNE_3_ANS,
    ):
        try:
            resultat[methode] = EstimerPeriode(
                methode=methode,
                historique=historique,
                jours_ouverts_cible=jours_ouverts_cible,
            )
        except ValueError:
            resultat[methode] = None
    return resultat


def CalculerActualisation(realise, prevision_restant):
    """Une actualisation AFAS = réalisé connu + prévisionnel restant."""
    realise = float(realise)
    prevision_restant = float(prevision_restant)
    return {
        "realise": realise,
        "prevision_restant": prevision_restant,
        "total_actualise": realise + prevision_restant,
    }
