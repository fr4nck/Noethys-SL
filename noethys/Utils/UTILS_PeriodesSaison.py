#!/usr/bin/env python
# -*- coding: utf-8 -*-
#-----------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Licence:         Licence GNU GPL
#-----------------------------------------------------------

import calendar
import datetime


def GetAnneeDebutSaison(date_reference=None):
    """Retourne l'année de début de la saison septembre -> août."""
    if date_reference is None:
        date_reference = datetime.date.today()
    if date_reference.month >= 9:
        return date_reference.year
    return date_reference.year - 1


def GetBornesPeriodesSaison(annee_debut):
    """Retourne les bornes des périodes fixes d'une saison."""
    annee_debut = int(annee_debut)
    annee_fin = annee_debut + 1
    dernier_jour_fevrier = calendar.monthrange(annee_fin, 2)[1]

    return {
        "saison": (
            datetime.date(annee_debut, 9, 1),
            datetime.date(annee_fin, 8, 31),
        ),
        "trimestre_1": (
            datetime.date(annee_debut, 9, 1),
            datetime.date(annee_debut, 12, 31),
        ),
        "trimestre_2": (
            datetime.date(annee_fin, 1, 1),
            datetime.date(annee_fin, 3, 31),
        ),
        "trimestre_3": (
            datetime.date(annee_fin, 4, 1),
            datetime.date(annee_fin, 8, 31),
        ),
        "semestre_1": (
            datetime.date(annee_debut, 9, 1),
            datetime.date(annee_fin, 2, dernier_jour_fevrier),
        ),
        "semestre_2": (
            datetime.date(annee_fin, 3, 1),
            datetime.date(annee_fin, 8, 31),
        ),
    }


def GetCodeTrimestreEnCours(date_reference=None):
    if date_reference is None:
        date_reference = datetime.date.today()
    if date_reference.month >= 9:
        return "trimestre_1"
    if date_reference.month <= 3:
        return "trimestre_2"
    return "trimestre_3"


def GetCodeSemestreEnCours(date_reference=None):
    if date_reference is None:
        date_reference = datetime.date.today()
    if date_reference.month >= 9 or date_reference.month <= 2:
        return "semestre_1"
    return "semestre_2"


def GetPeriodeSaison(code, annee_debut=None, date_reference=None):
    """Résout un code de période en un tuple (date_debut, date_fin).

    Les alias *_courant sont toujours calculés par rapport à la date réelle
    de référence et donc à la saison courante.
    """
    if date_reference is None:
        date_reference = datetime.date.today()

    if code == "trimestre_courant":
        annee_debut = GetAnneeDebutSaison(date_reference)
        code = GetCodeTrimestreEnCours(date_reference)
    elif code == "semestre_courant":
        annee_debut = GetAnneeDebutSaison(date_reference)
        code = GetCodeSemestreEnCours(date_reference)
    elif annee_debut is None:
        annee_debut = GetAnneeDebutSaison(date_reference)

    periodes = GetBornesPeriodesSaison(annee_debut)
    if code not in periodes:
        raise ValueError("Code de période de saison inconnu : %s" % code)
    return periodes[code]
