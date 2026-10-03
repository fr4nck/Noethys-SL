#!/usr/bin/env python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Licence :        GNU GPL
#------------------------------------------------------------------------
"""Calendrier scolaire métropolitain utile au dashboard.

Source 2026-2027 : Ministère de l'Éducation nationale, calendrier scolaire
publié sur education.gouv.fr. Le départ a lieu après la classe le jour indiqué
et la reprise le matin du jour indiqué.

Ce module reste volontairement sans accès réseau : l'accueil doit pouvoir
afficher ses prochaines périodes même hors connexion.
"""

import datetime


DEPARTEMENTS_PAR_ZONE = {
    "A": {
        "01", "03", "07", "15", "16", "17", "19", "21", "23", "24",
        "25", "26", "33", "38", "39", "40", "42", "43", "47", "58",
        "63", "64", "69", "70", "71", "73", "74", "79", "86", "87",
        "89", "90",
    },
    "B": {
        "02", "04", "05", "06", "08", "10", "13", "14", "18", "22",
        "27", "28", "29", "35", "36", "37", "41", "44", "45", "49",
        "50", "51", "52", "53", "54", "55", "56", "57", "59", "60",
        "61", "62", "67", "68", "72", "76", "80", "83", "84", "85",
        "88",
    },
    "C": {
        "09", "11", "12", "30", "31", "32", "34", "46", "48", "65",
        "66", "75", "77", "78", "81", "82", "91", "92", "93", "94",
        "95",
    },
}


CALENDRIER_2026_2027 = {
    "A": [
        (u"Toussaint", "2026-10-17", "2026-11-02"),
        (u"Noël", "2026-12-19", "2027-01-04"),
        (u"Hiver", "2027-02-13", "2027-03-01"),
        (u"Printemps", "2027-04-10", "2027-04-26"),
        (u"Été", "2027-07-03", None),
    ],
    "B": [
        (u"Toussaint", "2026-10-17", "2026-11-02"),
        (u"Noël", "2026-12-19", "2027-01-04"),
        (u"Hiver", "2027-02-20", "2027-03-08"),
        (u"Printemps", "2027-04-17", "2027-05-03"),
        (u"Été", "2027-07-03", None),
    ],
    "C": [
        (u"Toussaint", "2026-10-17", "2026-11-02"),
        (u"Noël", "2026-12-19", "2027-01-04"),
        (u"Hiver", "2027-02-06", "2027-02-22"),
        (u"Printemps", "2027-04-03", "2027-04-19"),
        (u"Été", "2027-07-03", None),
    ],
}


def GetZoneDepuisCodePostal(cp):
    """Déduit A/B/C d'un code postal métropolitain, sinon None."""
    if cp is None:
        return None
    cp = str(cp).strip()
    if len(cp) != 5 or not cp.isdigit():
        return None

    # Corse : calendrier spécifique, ne pas lui attribuer une fausse zone.
    if cp.startswith("20"):
        return None

    departement = cp[:2]
    for zone, departements in DEPARTEMENTS_PAR_ZONE.items():
        if departement in departements:
            return zone
    return None


def _Date(texte):
    if texte is None:
        return None
    return datetime.datetime.strptime(texte, "%Y-%m-%d").date()


def GetPeriodes(zone):
    if zone not in CALENDRIER_2026_2027:
        return []
    return [
        {"nom": nom, "debut": _Date(debut), "reprise": _Date(reprise)}
        for nom, debut, reprise in CALENDRIER_2026_2027[zone]
    ]


def GetProchainePeriode(zone, date_reference=None):
    if date_reference is None:
        date_reference = datetime.date.today()
    for periode in GetPeriodes(zone):
        # Tant que la reprise n'est pas passée, la période reste pertinente.
        limite = periode["reprise"] or periode["debut"]
        if limite > date_reference or periode["debut"] == date_reference:
            return periode
    return None
