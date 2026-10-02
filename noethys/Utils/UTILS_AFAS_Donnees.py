#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------
""" Plus petit orchestrateur combinant, pour un même périmètre (IDactivite,
IDgroupe) et une phase AFAS donnée, les heures RÉELLES (État global,
typeCalcul 0/1/3 selon le profil fourni) et les heures FACTURÉES (État
global, typeCalcul=2 -- prestations.temps_facture, déduplication par
IDprestation déjà gérée par le moteur), chacune avec son sous-total "dont
AEEH" déterminé par `aeeh_periodes` à la date de situation de la phase.

N'invente aucune règle métier :
- le réel et le facturé sont chacun calculés par
  DLG_Etat_global.CalculateurEtatGlobal.CalculerEtatGlobal(), sans aucune
  transformation supplémentaire (pas d'arrondi AFAS, pas de redéfinition du
  temps facturé) ;
- le forfait de présence méridienne (dict_options["forfait_presence_midi"])
  n'est JAMAIS appliqué au run facturé -- vérifié sur données réelles
  PMSL (IDactivite=1) : prestations.temps_facture y est systématiquement
  la durée réellement bookée (heure_fin - heure_debut) de la consommation
  facturée, pas un forfait fixe comme le coeff réel -- quand cette durée
  couvre déjà le midi (ex. Journée 08:30-17:30 -> temps_facture="09:00",
  demi-journée 08:30-13:30 -> "05:00"), le midi y est donc déjà compté ;
  ajouter le forfait par-dessus doublerait cette heure. Le run facturé
  reçoit donc une COPIE de dict_options avec forfait_presence_midi forcé
  à 0, jamais le dict_options fourni par l'appelant (qui n'est jamais
  muté) -- le run réel, lui, conserve intégralement le dict_options du
  profil, forfait midi compris ;
- les bornes de la phase viennent de UTILS_AFAS.GetCycleAFAS(annee)[phase],
  jamais recalculées ici ;
- les individus AEEH applicables à la phase viennent de
  UTILS_AEEH_Periodes.GetIndividusActifsADate(date_situation), jamais de
  individus.aeeh ;
- le sous-total AEEH n'est jamais ajouté au total : c'est le même jeu de
  consommations, simplement reventilé par individu (regroupement déjà
  existant du moteur, "individu") pour isoler la part des individus AEEH
  -- aucune consommation n'est recalculée ni dupliquée, aucun découpage
  jour par jour selon des changements administratifs (une seule
  appartenance AEEH par individu, pour toute la période de la phase). """

import datetime

from Dlg import DLG_Etat_global
from Utils import UTILS_AEEH_Periodes
from Utils import UTILS_AFAS
from Utils import UTILS_Ouvertures


_LABEL_AEEH = "AEEH"


def _sommer_par_regroupement(IDactivite, IDgroupe, date_debut, date_fin, dictUnites, dict_options,
                              dictInfosIndividus_aeeh):
    """ Calcule le total d'heures du périmètre et son sous-total "dont
    AEEH", en UNE SEULE exécution du moteur : le regroupement "individu"
    (déjà existant, cf. DLG_Etat_global.CalculerEtatGlobal) bascule chaque
    consommation dans le compartiment _LABEL_AEEH si son IDindividu est
    une clé de dictInfosIndividus_aeeh, ou dans le compartiment générique
    (None) sinon -- sans changer quelles consommations sont incluses ni
    comment chacune est calculée (même dictUnites, mêmes filtres). """
    options_individu = dict(dict_options)
    options_individu["regroupement_principal"] = "individu"

    calculateur = DLG_Etat_global.CalculateurEtatGlobal()
    resultat = calculateur.CalculerEtatGlobal(
        date_debut=date_debut,
        date_fin=date_fin,
        listeActivites=[IDactivite],
        listeGroupes=[IDgroupe],
        dictUnites=dictUnites,
        dict_options=options_individu,
        dictInfosIndividus=dictInfosIndividus_aeeh,
        dictInfosFamilles={},
    )

    total = datetime.timedelta(0)
    total_aeeh = datetime.timedelta(0)
    for regroupement, dict_tranches in resultat["dict_resultats"].items():
        sous_total = datetime.timedelta(0)
        for dict_periodes in dict_tranches.values():
            for dict_regimes in dict_periodes.values():
                for valeur in dict_regimes.values():
                    sous_total += valeur
        total += sous_total
        if regroupement == _LABEL_AEEH:
            total_aeeh += sous_total

    return total.total_seconds() / 3600.0, total_aeeh.total_seconds() / 3600.0


def GetDonneesAFAS(IDactivite, IDgroupe, annee, phase, dictUnites_reel, dictUnites_facture, dict_options):
    """ Pour le périmètre (IDactivite, IDgroupe), sur la phase AFAS
    `phase` de l'année `annee` (bornes = UTILS_AFAS.GetCycleAFAS(annee)[phase]) :

    {
        "heures_reelles": float,
        "heures_reelles_aeeh": float,       # sous-total, jamais ajouté au total
        "heures_facturees": float,
        "heures_facturees_aeeh": float,     # sous-total, jamais ajouté au total
        "jours_ouverts": int,
    }

    `dictUnites_reel` : configuration des unités pour le calcul réel
    (typeCalcul 0/coeff, 1/temps réel ou 3/formule selon le profil --
    inchangé, transmis tel quel au moteur).

    `dictUnites_facture` : configuration des unités pour le calcul facturé
    (typeCalcul=2, prestations.temps_facture) -- même moteur, même
    déduplication par IDprestation déjà en place, aucune redéfinition.

    Les deux calculs portent sur le MÊME périmètre, les mêmes bornes de
    dates et les mêmes filtres de `dict_options` (état/période/jours
    ouvrés-vacances/plafond), donc les mêmes consommations éligibles --
    seule la configuration des unités diffère entre réel et facturé,
    exactement comme le moteur le permet déjà. Seule exception
    volontaire : le forfait de présence méridienne n'est jamais appliqué
    côté facturé (cf. docstring du module) -- le run facturé reçoit une
    copie de `dict_options` avec `forfait_presence_midi` forcé à 0,
    jamais `dict_options` lui-même (jamais muté).

    Le sous-total AEEH est déterminé une seule fois par phase (pas par
    jour) : un individu dont le droit AEEH est actif à `date_situation`
    (bornes inclusives, cf. UTILS_AEEH_Periodes.GetIndividusActifsADate)
    voit la totalité de ses heures de la phase comptées aussi dans le
    sous-total "dont AEEH", quelle que soit la date exacte de chaque
    consommation à l'intérieur de la phase. """
    cycle = UTILS_AFAS.GetCycleAFAS(annee)[phase]
    date_debut = cycle["date_debut"]
    date_fin = cycle["date_fin"]
    date_situation = cycle["date_situation"]

    liste_individus_aeeh = UTILS_AEEH_Periodes.GetIndividusActifsADate(date_situation)
    dictInfosIndividus_aeeh = {IDindividu: {"INDIVIDU_NOM_COMPLET": _LABEL_AEEH} for IDindividu in liste_individus_aeeh}

    heures_reelles, heures_reelles_aeeh = _sommer_par_regroupement(
        IDactivite, IDgroupe, date_debut, date_fin, dictUnites_reel, dict_options, dictInfosIndividus_aeeh,
    )

    # Verdict vérifié sur données réelles PMSL (cf. docstring module) :
    # prestations.temps_facture inclut déjà le midi quand la durée
    # facturée le couvre -- jamais de copie non modifiée de dict_options
    # ici, jamais de mutation du dict_options fourni par l'appelant.
    dict_options_facture = dict(dict_options)
    dict_options_facture["forfait_presence_midi"] = 0
    heures_facturees, heures_facturees_aeeh = _sommer_par_regroupement(
        IDactivite, IDgroupe, date_debut, date_fin, dictUnites_facture, dict_options_facture, dictInfosIndividus_aeeh,
    )

    jours_ouverts = UTILS_Ouvertures.GetNombreJoursOuverture(IDactivite, IDgroupe, date_debut, date_fin)

    return {
        "heures_reelles": heures_reelles,
        "heures_reelles_aeeh": heures_reelles_aeeh,
        "heures_facturees": heures_facturees,
        "heures_facturees_aeeh": heures_facturees_aeeh,
        "jours_ouverts": jours_ouverts,
    }
