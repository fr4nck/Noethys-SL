# -*- coding: utf-8 -*-
"""Lecture seule des consommations ALSH pour les situations communales.

Ce module n'utilise aucune facture et n'ecrit jamais dans GestionDB. Les choix
activite/unite/accueil sont effectues explicitement par l'utilisateur.
Les adresses lues sont les adresses *actuelles*, pas un historique certifie.
"""

from datetime import date

from Utils.UTILS_Frequentation_collectivites import (
    ErreurFrequentation, _code_commune, _date,
    consolider_export_consommations,
)


def _annee(annee):
    if isinstance(annee, bool) or not isinstance(annee, int) or not (2000 <= annee <= 2100):
        raise ErreurFrequentation("Annee civile invalide")
    return annee


def _executer(db, sql):
    if not db.ExecuterReq(sql):
        raise ErreurFrequentation("Echec de lecture de la base Noethys (SQL)")
    return db.ResultatReq()


def _connecter(db):
    if db is not None:
        return db, False
    import GestionDB
    connexion = GestionDB.DB()
    if getattr(connexion, "echec", False):
        connexion.Close()
        raise ErreurFrequentation("Fichier Noethys indisponible")
    return connexion, True


def lister_unites(annee, db=None, inclure_absenti=False):
    """Unites utilisees sur l'annee, sans noms ni identifiants d'enfants."""
    a = _annee(annee)
    if not isinstance(inclure_absenti, bool):
        raise ErreurFrequentation("Choix des absences non booleen")
    connexion, proprietaire = _connecter(db)
    try:
        sql = """SELECT c.IDactivite, c.IDunite, a.nom, u.nom, COUNT(c.IDconso)
          FROM consommations AS c
          JOIN activites AS a ON a.IDactivite=c.IDactivite
          JOIN unites AS u ON u.IDunite=c.IDunite AND u.IDactivite=c.IDactivite
          WHERE c.date >= '%04d-01-01' AND c.date <= '%04d-12-31'
            AND c.etat IN ('present', 'reservation'%s)
          GROUP BY c.IDactivite, c.IDunite, a.nom, u.nom
          ORDER BY a.nom, u.nom, c.IDactivite, c.IDunite""" % (
              a, a, ", 'absenti'" if inclure_absenti else "")
        return [{"IDactivite": int(act), "IDunite": int(unit),
                 "activite": str(nom_a or ""), "unite": str(nom_u or ""),
                 "nombre": int(count)}
                for act, unit, nom_a, nom_u, count in _executer(connexion, sql)]
    finally:
        if proprietaire:
            connexion.Close()


def resoudre_villes(individus):
    """Suit adresse_auto (comme Noethys), detecte les cycles et liens rompus.

    individus: {IDindividu: (adresse_auto, ville_resid)}. La commune reelle
    a la date des presences n'est pas deduite de ce graphe actuel.
    """
    villes = {}
    for ident in individus:
        visites = set()
        courant = ident
        while courant in individus and courant not in visites:
            visites.add(courant)
            ref, ville = individus[courant]
            if ref is None or str(ref).strip() in ("", "0"):
                villes[ident] = str(ville).strip() if ville else None
                break
            try:
                courant = int(ref)
            except (ValueError, TypeError):
                break
        else:
            villes[ident] = None
        if ident not in villes:
            villes[ident] = None
    return villes


def importer_journees(annee, arrete, commune, mapping, db=None, inclure_absenti=False):
    """Importe les presences/reservations des seules unites choisies.

    Retourne seulement des totaux mensuels non nominatifs et des diagnostics
    quantifies. Aucun enregistrement d'enfant n'est sauvegarde ou retourne.
    Les contributions communales et les acomptes sont geres separement.
    """
    a = _annee(annee)
    if not isinstance(inclure_absenti, bool):
        raise ErreurFrequentation("Choix des absences non booleen")
    d = _date(arrete, "date d'arrete")
    if d.year != a:
        raise ErreurFrequentation("Arrete hors de l'annee civile")
    if not isinstance(mapping, dict) or not mapping:
        raise ErreurFrequentation("Selectionnez au moins une unite ALSH")
    conditions = []
    regles = {}
    for cle, valeur in mapping.items():
        if not isinstance(cle, str) or not isinstance(valeur, dict):
            raise ErreurFrequentation("Association d'unite invalide")
        try:
            act_str, unite_str = cle.split(":")
            act, unite = int(act_str), int(unite_str)
        except (ValueError, TypeError):
            raise ErreurFrequentation("Identifiant d'unite invalide")
        if act < 1 or unite < 1 or cle != "%d:%d" % (act, unite):
            raise ErreurFrequentation("Identifiant d'unite non canonique")
        if valeur.get("poids") != "1" or not valeur.get("convention"):
            raise ErreurFrequentation("Seules les journees entieres confirmees sont admises")
        conditions.append("(c.IDactivite=%d AND c.IDunite=%d)" % (act, unite))
        regles[cle] = {"convention": valeur["convention"], "poids": "1"}
    connexion, proprietaire = _connecter(db)
    try:
        sql = """SELECT c.IDconso, c.IDindividu, c.date, c.IDactivite,
                        c.IDunite, c.etat
                 FROM consommations AS c
                 WHERE c.date >= '%04d-01-01' AND c.date <= '%04d-12-31'
                   AND (%s)
                 ORDER BY c.IDconso""" % (a, a, " OR ".join(conditions))
        lignes = _executer(connexion, sql)
        if not lignes:
            return {"jours": [], "exclusions": {"hors_commune": 0,
                    "domiciles_indetermines": 0}, "nb_enfants_jour": 0,
                    "domiciliation_historique_verifiee": False,
            "absenti_selectionne": inclure_absenti}
        adresses = _executer(connexion, "SELECT IDindividu, adresse_auto, ville_resid FROM individus")
        villes = resoudre_villes({int(i): (reference, ville) for i, reference, ville in adresses})
        utiles = []
        indetermines = 0
        non_commune = 0
        cible = _code_commune(commune)
        for idconso, enfant, jour, activite, unite, etat in lignes:
            if enfant is None:
                indetermines += 1
                continue
            ville = villes.get(int(enfant))
            if not ville:
                indetermines += 1
                continue
            if _code_commune(ville) != cible:
                non_commune += 1
                continue
            utiles.append({"IDconso": idconso, "IDindividu": enfant,
                           "date": str(jour), "IDactivite": activite,
                           "IDunite": unite, "etat": etat,
                           "commune_residence": ville})
        r = consolider_export_consommations(utiles, regles, commune, a, d,
                                            inclure_absenti=inclure_absenti)
        r["exclusions"]["domiciles_indetermines"] = indetermines
        r["exclusions"]["hors_commune"] = non_commune
        r["domiciliation_historique_verifiee"] = False
        return r
    finally:
        if proprietaire:
            connexion.Close()