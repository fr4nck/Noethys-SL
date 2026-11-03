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
- le réalisé des actualisations s'arrête à la date de situation ;
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

# AFAS : selection propre a chaque indicateur, independante de l'etat global.
# Ancien profil sans ces cles : les presences seules sont retenues.
_ETATS_AFAS = ("present", "reservation", "absentj", "absenti")


def SelectionEtatsAFAS(options, cle):
    """Renvoie les états explicitement autorisés pour une métrique AFAS.

    Les heures réelles n'acceptent pas les réservations non pointées.
    Les absences facturées restent une option distincte et explicite.
    """
    if cle not in ("afas_etats_reels", "afas_etats_factures"):
        raise ValueError("Métrique AFAS inconnue : %s" % cle)
    valeurs = options.get(cle, ["present"])
    if (not isinstance(valeurs, (list, tuple)) or not valeurs
            or any(type(v) is not str or v not in _ETATS_AFAS for v in valeurs)
            or len(valeurs) != len(set(valeurs))):
        raise ValueError("États AFAS invalides pour %s : sélectionner des états distincts et connus." % cle)
    if cle == "afas_etats_reels" and "reservation" in valeurs:
        raise ValueError("Les réservations non pointées ne sont pas des heures réalisées AFAS.")
    return list(valeurs)


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
        listeActivites=IDactivite if isinstance(IDactivite, list) else [IDactivite],
        listeGroupes=IDgroupe if isinstance(IDgroupe, list) else [IDgroupe],
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

    Les deux calculs portent sur le MÊME périmètre et les mêmes bornes de
    dates. Leurs états sont sélectionnés séparément par
    `afas_etats_reels` et `afas_etats_factures` (par défaut :
    "present" seulement, sans hériter des filtres de l'état global).
    Les autres filtres du profil (période, jours ouverts/vacances,
    plafonds) restent identiques. Le forfait méridien ne s'applique
    jamais au calcul facturé, qui reçoit sa propre copie des options.
    Le dictionnaire d'options de l'appelant n'est jamais modifié.

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

    if phase in (UTILS_AFAS.PHASE_ACTUALISATION_JUIN, UTILS_AFAS.PHASE_ACTUALISATION_SEPTEMBRE):
        date_fin = date_situation
    return GetDonneesPeriodeAFAS([(IDactivite, IDgroupe)], date_debut, date_fin,
                                date_situation, dictUnites_reel, dictUnites_facture, dict_options)


def GetDonneesPeriodeAFAS(perimetres, date_debut, date_fin, date_situation,
                         dictUnites_reel, dictUnites_facture, dict_options):
    """Un équipement peut réunir plusieurs activités/groupes.

    Une seule exécution par métrique conserve la déduplication des prestations
    et les plafonds individuels entre groupes. Les jours ouverts sont une union.
    Les IDs de groupe sont uniques dans la base.
    """
    if not perimetres or date_fin < date_debut:
        raise ValueError("Périmètre ou période invalide")
    IDactivite = sorted(set(activite for activite, groupe in perimetres))
    IDgroupe = sorted(set(groupe for activite, groupe in perimetres))
    liste_individus_aeeh = UTILS_AEEH_Periodes.GetIndividusActifsADate(date_situation)
    dictInfosIndividus_aeeh = {IDindividu: {"INDIVIDU_NOM_COMPLET": _LABEL_AEEH} for IDindividu in liste_individus_aeeh}

    options_reel = dict(dict_options)
    options_reel["etat_consommations"] = SelectionEtatsAFAS(dict_options, "afas_etats_reels")
    options_facture = dict(dict_options)
    options_facture["etat_consommations"] = SelectionEtatsAFAS(dict_options, "afas_etats_factures")
    options_facture["forfait_presence_midi"] = 0

    heures_reelles, heures_reelles_aeeh = _sommer_par_regroupement(
        IDactivite, IDgroupe, date_debut, date_fin, dictUnites_reel, options_reel, dictInfosIndividus_aeeh,
    )

    # Le temps facture inclut deja le midi lorsqu'il est facture dans
    # prestations.temps_facture : ne jamais ajouter de forfait midi ici.
    heures_facturees, heures_facturees_aeeh = _sommer_par_regroupement(
        IDactivite, IDgroupe, date_debut, date_fin, dictUnites_facture, options_facture, dictInfosIndividus_aeeh,
    )

    jours_ouverts = len(set(date for activite, groupe in perimetres
                           for date in UTILS_Ouvertures.GetDatesOuverture(
                               activite, groupe, date_debut, date_fin)))

    return {
        "heures_reelles": heures_reelles,
        "heures_reelles_aeeh": heures_reelles_aeeh,
        "heures_facturees": heures_facturees,
        "heures_facturees_aeeh": heures_facturees_aeeh,
        "jours_ouverts": jours_ouverts,
    }
