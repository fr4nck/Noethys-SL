# -*- coding: utf-8 -*-
"""Suggestions d'encadrement par site et creneau (Noethys-SL #429).

Calcul purement indicatif : aucun acces aux fiches, aucun rapprochement des
repas adultes, et aucune attestation de conformite reglementaire.
"""

from datetime import date, datetime


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def AgeAuJour(naissance, jour):
    """Age en annees revolues, ou None si la date manque/est incoherente."""
    naissance, jour = _date(naissance), _date(jour)
    if naissance is None or jour is None or naissance > jour:
        return None
    return jour.year - naissance.year - ((jour.month, jour.day) < (naissance.month, naissance.day))


def TauxEncadrement(cadre, duree_heures=None, pedt=False):
    """Renvoie les ratios (<6, >=6). PEDT jamais suppose par defaut.

    Le seuil periscolaire est de 5 heures *consecutives incluses* ; le midi
    distinct est un creneau autonome, pas une duree ajoutee au matin.
    """
    if not isinstance(pedt, bool):
        raise ValueError("pedt doit etre un booleen explicite")
    if cadre == "extrascolaire":
        if pedt:
            raise ValueError("PEDT non applicable a l'extrascolaire")
        return (8, 12)
    if cadre != "periscolaire":
        raise ValueError("cadre d'accueil inconnu")
    if isinstance(duree_heures, bool) or not isinstance(duree_heures, (int, float)) or not 0 < duree_heures <= 24:
        raise ValueError("duree consecutive periscolaire obligatoire (en heures)")
    court = duree_heures <= 5
    if pedt:
        return (14, 18) if court else (10, 14)
    return (10, 14) if court else (8, 12)


def _plafond(nombre, ratio):
    return (nombre + ratio - 1) // ratio


def CalculerEncadrement(consommations, individus, unites_config, mode="previsionnel"):
    """Regroupe les mineurs uniques par (date, site, creneau) et suggere un besoin.

    consommations : dicts avec date, IDindividu, IDgroupe, IDunite et etat.
    individus : dict IDindividu -> {'date_naiss': date/ISO, 'est_adulte': bool?}.
    unites_config : dict (IDgroupe, IDunite) -> {'site', 'creneau',
        'cadre', 'duree_heures' si periscolaire, 'pedt' (bool optionnel)}.
    "previsionnel" prend reservations + presents, "reel" les presents seuls.
    L'affectation du site et du creneau est explicite, jamais devinee des repas.
    """
    if mode not in ("previsionnel", "reel"):
        raise ValueError("mode de comptage inconnu")
    etats = ("reservation", "present") if mode == "previsionnel" else ("present",)
    blocs = {}
    par_enfant = {}
    for conso in consommations:
        if conso.get("etat") not in etats:
            continue
        ident = conso.get("IDindividu")
        jour = _date(conso.get("date"))
        if ident is None or jour is None:
            raise ValueError("consommation sans identifiant ou date valide")
        cle_unite = (conso.get("IDgroupe"), conso.get("IDunite"))
        if cle_unite not in unites_config:
            raise ValueError("unite/groupe sans rattachement site et creneau : %r" % (cle_unite,))
        param = unites_config[cle_unite]
        site = str(param.get("site") or "").strip()
        creneau = str(param.get("creneau") or "").strip()
        if not site or not creneau:
            raise ValueError("site et creneau doivent etre explicites")
        cadre = param.get("cadre")
        duree = param.get("duree_heures")
        pedt = param.get("pedt", False)
        TauxEncadrement(cadre, duree, pedt)
        cle = (jour, site, creneau)
        configuration = (cadre, duree if cadre == "periscolaire" else None, pedt)
        if cle not in blocs:
            blocs[cle] = {"config": configuration, "individus": set()}
        if blocs[cle]["config"] != configuration:
            raise ValueError("taux contradictoires au meme site/date/creneau")
        blocs[cle]["individus"].add(ident)
        par_enfant.setdefault((jour, creneau, ident), set()).add(site)

    resultats = []
    for (jour, site, creneau), bloc in sorted(blocs.items()):
        cadre, duree, pedt = bloc["config"]
        taux_moins_6, taux_plus_6 = TauxEncadrement(cadre, duree, pedt)
        moins_6 = plus_6 = age_inconnu = adultes_ignores = 0
        conflits_sites = 0
        for ident in bloc["individus"]:
            infos = individus.get(ident, {}) or {}
            if infos.get("est_adulte") is True:
                adultes_ignores += 1
                continue
            age = AgeAuJour(infos.get("date_naiss"), jour)
            if age is None:
                age_inconnu += 1
            elif age >= 18:
                adultes_ignores += 1
            elif age < 6:
                moins_6 += 1
            else:
                plus_6 += 1
            if len(par_enfant[(jour, creneau, ident)]) > 1:
                conflits_sites += 1
        n_moins = _plafond(moins_6, taux_moins_6)
        n_plus = _plafond(plus_6, taux_plus_6)
        resultats.append({
            "date": jour.isoformat(), "site": site, "creneau": creneau,
            "mode": mode, "cadre": cadre, "duree_heures": duree,
            "pedt": pedt, "moins_6": moins_6, "six_et_plus": plus_6,
            "age_inconnu": age_inconnu, "adultes_ignores": adultes_ignores,
            "enfants_connus": moins_6 + plus_6,
            "taux_moins_6": taux_moins_6, "taux_six_et_plus": taux_plus_6,
            "animateurs_moins_6": n_moins, "animateurs_six_et_plus": n_plus,
            "animateurs_suggeres": n_moins + n_plus,
            "calcul_complet": age_inconnu == 0 and conflits_sites == 0,
            "conflits_sites": conflits_sites,
        })
    return resultats
