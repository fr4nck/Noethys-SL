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
    statuts inconnus doivent être détectés, pas filtrés en amont), avec la
    prestation qui les facture et sa facture. Le montant n'est lu que pour
    détecter une prestation négative : il n'est jamais converti en heures."""
    req = """SELECT c.IDconso, c.IDindividu, c.date, c.IDunite, c.IDactivite, c.IDgroupe, c.heure_debut, c.heure_fin,
        c.etat, c.quantite, c.IDprestation, p.montant, p.forfait, p.forfait_date_debut, p.IDindividu, p.IDfamille,
        f.IDfacture, f.etat, i.nom, i.prenom
        FROM consommations c
        LEFT JOIN prestations p ON p.IDprestation = c.IDprestation
        LEFT JOIN factures f ON f.IDfacture = p.IDfacture
        LEFT JOIN individus i ON i.IDindividu = c.IDindividu
        WHERE c.date>='%s' AND c.date<='%s' AND %s
        ORDER BY c.date, c.IDindividu, c.IDconso;""" % (_date(date_debut), _date(date_fin), ConditionCouples(couples, "c"))
    resultat = []
    for (IDconso, IDindividu, date, IDunite, IDactivite, IDgroupe, heure_debut, heure_fin, etat, quantite, IDprestation,
         montant, forfait, forfait_debut, prestation_IDindividu, IDfamille, IDfacture, facture_etat, nom, prenom) in _requete(req):
        resultat.append({
            "IDconso": IDconso, "IDindividu": IDindividu, "individu": " ".join(x for x in (nom, prenom) if x),
            "date": _date(date), "IDunite": IDunite, "IDactivite": IDactivite, "IDgroupe": IDgroupe,
            "heure_debut": heure_debut, "heure_fin": heure_fin, "etat": etat, "quantite": quantite,
            "IDprestation": IDprestation, "prestation_montant": montant, "prestation_forfait": forfait,
            "prestation_forfait_debut": forfait_debut, "prestation_IDindividu": prestation_IDindividu,
            "IDfamille": IDfamille, "IDfacture": IDfacture, "facture_etat": facture_etat})
    return resultat


def ChargerRegularisations(IDactivites, IDindividus, IDfamilles, date_debut, date_fin):
    """Prestations négatives (avoirs, régularisations) non rattachées à une
    consommation, datées de la période, portant sur les activités du
    périmètre, ses enfants ou leurs familles."""
    IDactivites = sorted({i for i in IDactivites if type(i) is int})
    IDindividus = sorted({i for i in IDindividus if type(i) is int})
    IDfamilles = sorted({i for i in IDfamilles if type(i) is int})
    conditions = []
    if IDactivites:
        conditions.append("p.IDactivite IN (%s)" % ", ".join(map(str, IDactivites)))
    if IDindividus:
        conditions.append("p.IDindividu IN (%s)" % ", ".join(map(str, IDindividus)))
    if IDfamilles:
        conditions.append("p.IDfamille IN (%s)" % ", ".join(map(str, IDfamilles)))
    if not conditions:
        return []
    req = """SELECT p.IDprestation, p.IDindividu, p.IDfamille, p.IDactivite, p.date, p.montant, p.label, p.categorie,
        f.IDfacture, f.etat
        FROM prestations p
        LEFT JOIN factures f ON f.IDfacture = p.IDfacture
        WHERE p.montant < 0 AND p.date>='%s' AND p.date<='%s' AND (%s)
        ORDER BY p.date, p.IDprestation;""" % (_date(date_debut), _date(date_fin), " OR ".join(conditions))
    candidates = _requete(req)
    if not candidates:
        return []
    # consommations.IDprestation n'est pas indexé : une seule requête pour toutes les candidates.
    rattachees = {IDprestation for (IDprestation,) in _requete(
        "SELECT DISTINCT IDprestation FROM consommations WHERE IDprestation IN (%s);"
        % ", ".join(str(ligne[0]) for ligne in candidates))}
    return [{"IDprestation": IDprestation, "IDindividu": IDindividu or None, "IDfamille": IDfamille,
             "IDactivite": IDactivite, "date": _date(date), "montant": montant, "label": label, "categorie": categorie,
             "IDfacture": IDfacture, "facture_etat": facture_etat}
            for IDprestation, IDindividu, IDfamille, IDactivite, date, montant, label, categorie, IDfacture, facture_etat
            in candidates if IDprestation not in rattachees]


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
