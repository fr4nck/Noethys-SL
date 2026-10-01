#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------
""" Plus petit orchestrateur reliant les heures réalisées (État global) et
les jours ouverts (table `ouvertures`) pour un même périmètre
(IDactivite, IDgroupe), sur une période donnée.

N'invente aucune règle métier CAF/AFAS, ne calcule aucune nouvelle donnée :
assemble uniquement deux résultats déjà qualifiés séparément --
CalculateurEtatGlobal.CalculerEtatGlobal() (LOT 1/3A) et
UTILS_Ouvertures.GetNombreJoursOuverture() (LOT 2). Produit le contrat
stable attendu par un futur historique UTILS_AFAS, sans toucher à
UTILS_AFAS.py lui-même. """

import datetime

from Dlg import DLG_Etat_global
from Utils import UTILS_Ouvertures


def GetDonneesPerimetre(IDactivite, IDgroupe, date_debut, date_fin, dictUnites, dict_options,
                         dictInfosIndividus=None, dictInfosFamilles=None):
    """ Pour le périmètre (IDactivite, IDgroupe) sur [date_debut, date_fin] :

    {
        "heures": float,        # total des heures de dict_resultats, toutes
                                 # clés de regroupement confondues
        "jours_ouverts": int,   # GetNombreJoursOuverture(IDactivite, IDgroupe, ...)
    }

    Les deux valeurs portent strictement sur le même (IDactivite, IDgroupe) :
    `heures` est obtenu via listeActivites=[IDactivite],
    listeGroupes=[IDgroupe] (filtre ajouté en LOT 3A) ; `jours_ouverts` via
    le même couple, sans jamais filtrer par IDunite. """
    calculateur = DLG_Etat_global.CalculateurEtatGlobal()
    resultat = calculateur.CalculerEtatGlobal(
        date_debut=date_debut,
        date_fin=date_fin,
        listeActivites=[IDactivite],
        listeGroupes=[IDgroupe],
        dictUnites=dictUnites,
        dict_options=dict_options,
        dictInfosIndividus=dictInfosIndividus or {},
        dictInfosFamilles=dictInfosFamilles or {},
    )

    total = datetime.timedelta(0)
    for dict_tranches in resultat["dict_resultats"].values():
        for dict_periodes in dict_tranches.values():
            for dict_regimes in dict_periodes.values():
                for valeur in dict_regimes.values():
                    total += valeur
    heures = total.total_seconds() / 3600.0

    jours_ouverts = UTILS_Ouvertures.GetNombreJoursOuverture(IDactivite, IDgroupe, date_debut, date_fin)

    return {"heures": heures, "jours_ouverts": jours_ouverts}
