#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Site internet :  www.noethys.com
# Licence:         Licence GNU GPL
#------------------------------------------------------------------------
""" Dates d'ouverture d'un périmètre (IDactivite, IDgroupe) dans la table
`ouvertures`.

`ouvertures` contient une ligne par (IDactivite, IDunite, IDgroupe, date) :
plusieurs unités ouvertes le même jour pour le même périmètre produisent
plusieurs lignes ce jour-là. Le nombre de jours ouverts d'un périmètre
n'est donc jamais un COUNT(*) sur cette table -- c'est le nombre de dates
DISTINCTES, sans jamais filtrer ni distinguer par IDunite. """

import GestionDB
from Utils import UTILS_Dates


def GetDatesOuverture(IDactivite, IDgroupe, date_debut, date_fin):
    """ Retourne la liste triée des dates distinctes où le périmètre
    (IDactivite, IDgroupe) a été ouvert (au moins une unité ouverte ce
    jour-là), sur la période [date_debut, date_fin] incluse.

    Ne filtre jamais par IDunite : une seule unité ouverte suffit à
    considérer le jour comme ouvert pour ce périmètre. """
    req = """SELECT DISTINCT date
    FROM ouvertures
    WHERE IDactivite=%d AND IDgroupe=%d AND date>='%s' AND date<='%s'
    ORDER BY date;""" % (IDactivite, IDgroupe, str(date_debut), str(date_fin))
    DB = GestionDB.DB()
    DB.ExecuterReq(req)
    listeDonnees = DB.ResultatReq()
    DB.Close()
    return [UTILS_Dates.DateEngEnDateDD(date) for date, in listeDonnees]


def GetNombreJoursOuverture(IDactivite, IDgroupe, date_debut, date_fin):
    """ Nombre de jours ouverts distincts pour ce périmètre. Ne recompte
    jamais les lignes brutes de `ouvertures` (plusieurs unités par jour) :
    s'appuie uniquement sur GetDatesOuverture(). """
    return len(GetDatesOuverture(IDactivite, IDgroupe, date_debut, date_fin))
