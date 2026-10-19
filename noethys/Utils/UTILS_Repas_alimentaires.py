# -*- coding: utf-8 -*-
"""Comptage non nominatif de repas sans porc depuis une reponse explicite.

Source : question de questionnaire individuel de type choix ou case a cocher.
Aucune interpretation de notes libres, de donnees medicales ou d'identite.
Les anciens modeles demeurent inchanges si aucune question n'est choisie.
"""

from datetime import date, datetime


CONTROLES_CHOIX = ("liste_deroulante", "liste_coches", "case_coche")


def ConfigurationSansPorc(question, choix, controle):
    """Valide un contrat de questionnaire deterministe, sans inference."""
    try:
        question_id = int(question)
        choix_id = int(choix)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("La question et la reponse sans porc doivent etre identifiees")
    if question_id <= 0 or choix_id <= 0:
        raise ValueError("Identifiants de question/reponse invalides")
    if controle not in CONTROLES_CHOIX:
        raise ValueError("Seules les questions a choix ou la case a cocher sont admises")
    if controle == "case_coche" and choix_id != 1:
        raise ValueError("Une case sans porc est positive seulement si cochee (1)")
    return (question_id, choix_id, controle)


def EstSansPorc(reponse, choix_id, controle):
    """Comparaison exacte des codes bruts de questionnaire, jamais de texte libre."""
    if controle not in CONTROLES_CHOIX:
        raise ValueError("Type de controle questionnaire non autorise")
    if reponse is None:
        return False
    attendu = str(int(choix_id))
    if controle == "case_coche":
        return attendu == "1" and str(reponse).strip() == "1"
    # En Noethys, la liste a cocher est stockee « ID1;ID2;... ».
    return attendu in [element.strip() for element in str(reponse).split(";")]


def CompterSansPorc(consommations, reponses, unites, choix_id, controle):
    """Compte les enfants uniques par date pour les unites de ce service.

    Les consommations ont les champs date, IDindividu, IDgroupe, IDunite, etat.
    Les reponses sont {IDindividu: chaine brute de questionnaire}. Toute
    reponse absente est non renseignee, pas assimilee a une reponse negative.
    Une question ne doit etre associee qu'a un service de repas explicite.
    """
    unites = set(tuple(p) for p in unites)
    resultats = {}
    for ligne in consommations:
        if ligne.get("etat") not in ("reservation", "present"):
            continue
        if (ligne.get("IDgroupe"), ligne.get("IDunite")) not in unites:
            continue
        individu = ligne.get("IDindividu")
        jour = ligne.get("date")
        if isinstance(jour, datetime):
            jour = jour.date()
        if not isinstance(jour, date) or individu is None:
            raise ValueError("Consommation sans date ou individu valide")
        resultats.setdefault(jour, set()).add(individu)
    sortie = {}
    for jour, ids in resultats.items():
        sans_porc = sum(bool(EstSansPorc(reponses.get(ident), choix_id, controle)) for ident in ids)
        non_renseignes = sum(ident not in reponses or reponses[ident] in (None, "") for ident in ids)
        sortie[jour] = {"sans_porc": sans_porc, "repas": len(ids), "non_renseignes": non_renseignes}
    return sortie
