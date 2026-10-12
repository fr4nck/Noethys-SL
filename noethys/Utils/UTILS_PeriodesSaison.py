#!/usr/bin/env python
# -*- coding: utf-8 -*-
#-----------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Licence:         Licence GNU GPL
#-----------------------------------------------------------

"""Moteur commun des périodes de saison Noethys SL.

Les raccourcis historiques (saison, trimestres, semestres) restent
compatibles. Les périodes périscolaires sont calculées à partir des
vacances enregistrées dans Noethys, sans accès réseau ni dépendance wx.

Convention PMSL pour les vacances utilisées par les plannings :
- le samedi de départ reste scolaire ;
- les vacances commencent au premier dimanche à partir du début enregistré ;
- elles se terminent au premier dimanche à partir de la fin enregistrée ;
- la période périscolaire reprend donc le lundi suivant.
"""

import calendar
import datetime
import unicodedata


PERIODES_PERISCOLAIRES = (
    "periode_1",
    "periode_2",
    "periode_3",
    "periode_4",
    "periode_5",
)


def _ConvertirDate(valeur):
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    if isinstance(valeur, str):
        return datetime.datetime.strptime(valeur[:10], "%Y-%m-%d").date()
    raise ValueError("Date invalide : %r" % (valeur,))


def _PremierDimanche(dateDD):
    dateDD = _ConvertirDate(dateDD)
    return dateDD + datetime.timedelta(days=(6 - dateDD.weekday()) % 7)


def _NormaliserNom(nom):
    texte = "" if nom is None else str(nom)
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(car for car in texte if unicodedata.category(car) != "Mn")
    return " ".join(texte.lower().replace("-", " ").split())


def _TypeVacances(nom):
    nom = _NormaliserNom(nom)
    if "toussaint" in nom:
        return "toussaint"
    if "noel" in nom:
        return "noel"
    if "fevrier" in nom or "hiver" in nom:
        return "hiver"
    if "paques" in nom or "printemps" in nom:
        return "printemps"
    if "ete" in nom:
        return "ete"
    return None


def _LireVacance(valeur):
    """Normalise une ligne de la table vacances.

    Formats acceptés :
    - tuple/list : (nom, date_debut, date_fin)
    - dict : nom + date_debut/date_fin

    Les lignes incohérentes sont ignorées par le calcul appelant.
    """
    if isinstance(valeur, dict):
        nom = valeur.get("nom")
        date_debut = valeur.get("date_debut")
        date_fin = valeur.get("date_fin")
    else:
        nom, date_debut, date_fin = valeur[:3]
    return nom, _ConvertirDate(date_debut), _ConvertirDate(date_fin)


def GetAnneeDebutSaison(date_reference=None):
    """Retourne l'année de début de la saison septembre -> août."""
    if date_reference is None:
        date_reference = datetime.date.today()
    if date_reference.month >= 9:
        return date_reference.year
    return date_reference.year - 1


def GetBornesPeriodesPeriscolaires(annee_debut, liste_vacances):
    """Calcule les cinq périodes périscolaires de la saison.

    Les vacances fournies sont celles enregistrées dans la base Noethys.
    Une ligne manifestement invalide (fin antérieure au début) est ignorée.

    P1 : début de saison -> Toussaint
    P2 : Toussaint -> Noël
    P3 : Noël -> vacances d'hiver
    P4 : vacances d'hiver -> vacances de printemps/Pâques
    P5 : vacances de printemps/Pâques -> vacances d'été

    Les bornes sont inclusives et excluent les vacances selon la convention
    PMSL dimanche -> dimanche : le samedi de départ appartient encore à la
    période périscolaire, et la reprise est le lundi.
    """
    annee_debut = int(annee_debut)
    debut_saison = datetime.date(annee_debut, 9, 1)
    fin_saison = datetime.date(annee_debut + 1, 8, 31)

    vacances = {}
    lignes = []
    for valeur in liste_vacances or []:
        try:
            nom, date_debut, date_fin = _LireVacance(valeur)
        except (TypeError, ValueError, IndexError):
            continue
        if date_fin < date_debut:
            continue
        type_vacances = _TypeVacances(nom)
        if type_vacances is None:
            continue

        debut = _PremierDimanche(date_debut)
        fin = _PremierDimanche(date_fin)
        if debut_saison <= debut <= fin_saison:
            lignes.append((debut, fin, type_vacances))

    # En cas de doublon, la première période chronologique valide de chaque
    # type dans la saison est retenue. Cela évite qu'une ancienne ligne
    # dupliquée ou mal datée écrase une période cohérente.
    for debut, fin, type_vacances in sorted(lignes):
        if type_vacances not in vacances:
            vacances[type_vacances] = (debut, fin)

    def _Entre(code, debut, vacances_suivantes):
        if debut is None or vacances_suivantes is None:
            return
        fin = vacances_suivantes[0] - datetime.timedelta(days=1)
        if debut <= fin:
            periodes[code] = (debut, fin)

    periodes = {}
    toussaint = vacances.get("toussaint")
    noel = vacances.get("noel")
    hiver = vacances.get("hiver")
    printemps = vacances.get("printemps")
    ete = vacances.get("ete")

    _Entre("periode_1", debut_saison, toussaint)
    _Entre("periode_2", toussaint[1] + datetime.timedelta(days=1) if toussaint else None, noel)
    _Entre("periode_3", noel[1] + datetime.timedelta(days=1) if noel else None, hiver)
    _Entre("periode_4", hiver[1] + datetime.timedelta(days=1) if hiver else None, printemps)
    _Entre("periode_5", printemps[1] + datetime.timedelta(days=1) if printemps else None, ete)

    return periodes


def GetBornesPeriodesSaison(annee_debut, liste_vacances=None):
    """Retourne les bornes des périodes d'une saison.

    Les codes trimestre_* restent disponibles pour compatibilité avec les
    préférences et appels historiques, mais l'interface commune privilégie
    désormais les cinq périodes périscolaires.
    """
    annee_debut = int(annee_debut)
    annee_fin = annee_debut + 1
    dernier_jour_fevrier = calendar.monthrange(annee_fin, 2)[1]

    periodes = {
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
    if liste_vacances is not None:
        periodes.update(GetBornesPeriodesPeriscolaires(annee_debut, liste_vacances))
    return periodes


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


def GetCodePeriodePeriscolaireEnCours(date_reference, liste_vacances):
    """Retourne periode_1..periode_5, ou None pendant les vacances."""
    if date_reference is None:
        date_reference = datetime.date.today()
    date_reference = _ConvertirDate(date_reference)
    annee_debut = GetAnneeDebutSaison(date_reference)
    for code, bornes in GetBornesPeriodesPeriscolaires(annee_debut, liste_vacances).items():
        if bornes[0] <= date_reference <= bornes[1]:
            return code
    return None


def GetPeriodeSaison(code, annee_debut=None, date_reference=None, liste_vacances=None):
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

    periodes = GetBornesPeriodesSaison(annee_debut, liste_vacances=liste_vacances)
    if code not in periodes:
        if code in PERIODES_PERISCOLAIRES:
            raise ValueError(
                "Période périscolaire indisponible : calendrier de vacances incomplet pour %s-%s"
                % (annee_debut, int(annee_debut) + 1)
            )
        raise ValueError("Code de période de saison inconnu : %s" % code)
    return periodes[code]
