#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------
""" Plus petit adaptateur reliant UTILS_AFAS_Perimetre.GetDonneesPerimetre
(heures + jours ouverts déjà qualifiés pour un périmètre (IDactivite,
IDgroupe) sur une période) à UTILS_AFAS.EstimerPeriode/ConstruireComparaison
(qui attendent un historique multi-années ordonné du plus récent au plus
ancien, cf. docstring de EstimerPeriode : "[... N-1, N-2 ...]").

N'invente aucune règle métier : les bornes de chaque année historique
viennent de UTILS_AFAS.GetCycleAFAS(annee), jamais recalculées ici ; le
nombre d'années à construire n'est fixé par aucune constante de ce module
(aucune méthode d'estimation n'impose un nombre d'années minimal ou
maximal : N-1 ajustée n'utilise que historique[0], les moyennes utilisent
historique[:2]/historique[:3] avec autant d'années que disponibles) --
c'est donc à l'appelant de le préciser explicitement via `nombre_annees`. """

from Utils import UTILS_AFAS
from Utils import UTILS_AFAS_Perimetre


def ConstruireHistoriquePerimetre(IDactivite, IDgroupe, annee_reference, nombre_annees, dictUnites, dict_options,
                                   phase=UTILS_AFAS.PHASE_REEL, dictInfosIndividus=None, dictInfosFamilles=None):
    """ Construit, pour un même périmètre (IDactivite, IDgroupe), la liste
    d'historique attendue par UTILS_AFAS.EstimerPeriode/ConstruireComparaison :

    [
        {"heures": ..., "jours_ouverts": ...},   # annee_reference - 1
        {"heures": ..., "jours_ouverts": ...},   # annee_reference - 2
        ...
    ]

    ordonnée du plus récent (annee_reference - 1) au plus ancien
    (annee_reference - nombre_annees), une entrée par année.

    Chaque entrée provient de GetDonneesPerimetre(...) appelé sur les
    bornes [date_debut, date_fin] de la phase demandée (par défaut
    PHASE_REEL -- année civile complète déjà close, cf. docstring module
    UTILS_AFAS : "réel : année civile complète") telles que retournées par
    GetCycleAFAS(annee) : ce module ne recalcule ni ne redéfinit ces bornes.

    Ne contient aucune logique d'estimation (ratio heures/jour, moyennes,
    etc.) : celle-ci reste entièrement dans UTILS_AFAS.EstimerPeriode, à
    qui la liste retournée ici peut être transmise telle quelle. """
    if nombre_annees < 1:
        raise ValueError("nombre_annees doit être >= 1")

    historique = []
    for delta in range(1, nombre_annees + 1):
        annee = annee_reference - delta
        cycle_annee = UTILS_AFAS.GetCycleAFAS(annee)[phase]
        donnees = UTILS_AFAS_Perimetre.GetDonneesPerimetre(
            IDactivite=IDactivite,
            IDgroupe=IDgroupe,
            date_debut=cycle_annee["date_debut"],
            date_fin=cycle_annee["date_fin"],
            dictUnites=dictUnites,
            dict_options=dict_options,
            dictInfosIndividus=dictInfosIndividus,
            dictInfosFamilles=dictInfosFamilles,
        )
        historique.append(donnees)
    return historique
