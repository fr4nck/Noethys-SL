#!/usr/bin/env python
# -*- coding: utf-8 -*-
#-----------------------------------------------------------
# Application :    Noethys, gestion multi-activités
# Licence:         Licence GNU GPL
#-----------------------------------------------------------
"""Règles pures de sélection ville / code postal.

Ce module reste volontairement indépendant de wxPython afin que les règles
anti-ambiguïté puissent être testées sur toutes les plateformes de CI.
"""


def _normaliser_nom(valeur):
    return (valeur or "").strip().casefold()


def _normaliser_cp(valeur):
    return str(valeur or "").strip()


def CoupleExiste(liste_villes, ville, cp):
    """Retourne True si le couple ville + code postal existe tel quel."""
    nom_attendu = _normaliser_nom(ville)
    cp_attendu = _normaliser_cp(cp)
    if not nom_attendu or not cp_attendu:
        return False
    return any(
        _normaliser_nom(nom) == nom_attendu and _normaliser_cp(code) == cp_attendu
        for nom, code in liste_villes
    )


def CodesPourVille(liste_villes, ville):
    """Retourne les codes distincts connus pour une ville, dans l'ordre source."""
    nom_attendu = _normaliser_nom(ville)
    if not nom_attendu:
        return []

    codes = []
    vus = set()
    for nom, code in liste_villes:
        if _normaliser_nom(nom) != nom_attendu:
            continue
        code_normalise = _normaliser_cp(code)
        if code_normalise and code_normalise not in vus:
            vus.add(code_normalise)
            codes.append(code_normalise)
    return codes


def AutocompletionUnique(liste_villes, texte):
    """Retourne (ville, cp) uniquement si le préfixe désigne un couple unique.

    Un même nom associé à plusieurs codes postaux reste volontairement ambigu :
    aucune première ligne arbitraire ne doit pouvoir réécrire le code postal.
    Les doublons strictement identiques dans le référentiel sont dédupliqués.
    """
    prefixe = _normaliser_nom(texte)
    if not prefixe:
        return None

    candidats = []
    vus = set()
    for ville, cp in liste_villes:
        if not _normaliser_nom(ville).startswith(prefixe):
            continue
        cle = (_normaliser_nom(ville), _normaliser_cp(cp))
        if cle in vus:
            continue
        vus.add(cle)
        candidats.append((ville, _normaliser_cp(cp)))

    if len(candidats) == 1:
        return candidats[0]
    return None
