# -*- coding: utf-8 -*-
"""AFAS V2 -- lecture des données Noethys nécessaires au calcul.

Seul module du moteur qui lit la base (via GestionDB, sans wx à l'appel).
Toutes les requêtes sont restreintes aux couples exacts (IDactivite,
IDgroupe) du périmètre déclaré : jamais au produit croisé des activités et
des groupes. Les dates sont rendues en datetime.date.
"""
import datetime


def _date(valeur):
    if valeur in (None, ""):
        return None
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    return datetime.date.fromisoformat(str(valeur)[:10])


def ConditionCouples(couples, prefixe):
    couples = sorted(set(couples))
    if not couples or not all(type(a) is int and type(g) is int for a, g in couples):
        raise ValueError("Couples (IDactivite, IDgroupe) entiers requis")
    return "(%s)" % " OR ".join("(%s.IDactivite=%d AND %s.IDgroupe=%d)" % (prefixe, a, prefixe, g) for a, g in couples)


def _requete(req):
    import GestionDB
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq(req)
        return DB.ResultatReq()
    finally:
        DB.Close()


def ChargerUnites(IDactivites):
    """{IDunite: {nom, type, heure_debut, heure_fin, IDactivite}} des activités données."""
    IDactivites = sorted(set(IDactivites))
    if not IDactivites or not all(type(i) is int for i in IDactivites):
        raise ValueError("Activités entières requises")
    lignes = _requete("SELECT IDunite, IDactivite, nom, type, heure_debut, heure_fin FROM unites WHERE IDactivite IN (%s);"
                      % ", ".join(str(i) for i in IDactivites))
    return {IDunite: {"IDactivite": IDactivite, "nom": nom, "type": type_unite,
                      "heure_debut": heure_debut or None, "heure_fin": heure_fin or None}
            for IDunite, IDactivite, nom, type_unite, heure_debut, heure_fin in lignes}


def ChargerConsommations(couples, date_debut, date_fin):
    """Toutes les consommations du périmètre, quel que soit leur statut (les
    statuts inconnus doivent être détectés, pas filtrés en amont)."""
    req = """SELECT c.IDconso, c.IDindividu, c.date, c.IDunite, c.IDactivite, c.IDgroupe, c.heure_debut, c.heure_fin,
        c.etat, c.IDprestation, f.IDfacture, f.etat, i.nom, i.prenom
        FROM consommations c
        LEFT JOIN prestations p ON p.IDprestation = c.IDprestation
        LEFT JOIN factures f ON f.IDfacture = p.IDfacture
        LEFT JOIN individus i ON i.IDindividu = c.IDindividu
        WHERE c.date>='%s' AND c.date<='%s' AND %s
        ORDER BY c.date, c.IDindividu, c.IDconso;""" % (_date(date_debut), _date(date_fin), ConditionCouples(couples, "c"))
    resultat = []
    for (IDconso, IDindividu, date, IDunite, IDactivite, IDgroupe, heure_debut, heure_fin, etat, IDprestation,
         IDfacture, facture_etat, nom, prenom) in _requete(req):
        resultat.append({
            "IDconso": IDconso, "IDindividu": IDindividu, "individu": " ".join(x for x in (nom, prenom) if x),
            "date": _date(date), "IDunite": IDunite, "IDactivite": IDactivite, "IDgroupe": IDgroupe,
            "heure_debut": heure_debut, "heure_fin": heure_fin, "etat": etat, "IDprestation": IDprestation,
            "IDfacture": IDfacture, "facture_etat": facture_etat})
    return resultat


def ChargerOuvertures(couples, date_debut, date_fin):
    req = """SELECT o.IDactivite, o.IDunite, o.IDgroupe, o.date FROM ouvertures o
        WHERE o.date>='%s' AND o.date<='%s' AND %s;""" % (_date(date_debut), _date(date_fin), ConditionCouples(couples, "o"))
    return {(IDactivite, IDunite, IDgroupe, _date(date)) for IDactivite, IDunite, IDgroupe, date in _requete(req)}


def ChargerAEEH(IDindividus):
    """{IDindividu: [(date_debut, date_fin ou None)]} -- seule `aeeh_periodes` fait foi."""
    IDindividus = sorted(set(i for i in IDindividus if type(i) is int))
    if not IDindividus:
        return {}
    resultat = {}
    for IDindividu, debut, fin in _requete("SELECT IDindividu, date_debut, date_fin FROM aeeh_periodes WHERE IDindividu IN (%s);"
                                          % ", ".join(str(i) for i in IDindividus)):
        resultat.setdefault(IDindividu, []).append((_date(debut), _date(fin)))
    return resultat


def ChargerDatesOuverture(couples, date_debut, date_fin):
    """Dates distinctes d'ouverture du périmètre (jours ouverts, union des groupes)."""
    return sorted({date for a, u, g, date in ChargerOuvertures(couples, date_debut, date_fin)})
