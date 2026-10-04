#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Convention de vacances utilisée par la génération des plannings.

Les dates officielles stockées en base ne sont pas modifiées. Pour la
génération des ouvertures, une période de vacances commence au premier
dimanche à partir de sa date officielle de début. Le samedi de départ
reste donc traité comme un jour scolaire.
"""

import datetime


def _ConvertirDate(valeur):
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    if isinstance(valeur, str):
        return datetime.datetime.strptime(valeur[:10], "%Y-%m-%d").date()
    raise ValueError("Date de vacances invalide : %r" % (valeur,))


def GetDebutVacancesGeneration(date_debut):
    """Retourne le premier dimanche à partir du début officiel."""
    date_debut = _ConvertirDate(date_debut)
    jours_jusqua_dimanche = (6 - date_debut.weekday()) % 7
    return date_debut + datetime.timedelta(days=jours_jusqua_dimanche)


def EstEnVacancesGeneration(dateDD, listeVacances):
    """Indique si une date est en vacances pour la génération du planning."""
    dateDD = _ConvertirDate(dateDD)
    for valeurs in listeVacances:
        date_debut = GetDebutVacancesGeneration(valeurs[0])
        date_fin = _ConvertirDate(valeurs[1])
        if date_debut <= dateDD <= date_fin:
            return True
    return False
