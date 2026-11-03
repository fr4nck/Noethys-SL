# -*- coding: utf-8 -*-
"""Coordonnees de la fiche enfant PMSL depuis les liens Noethys existants.

Aucune creation de contact ni de rattachement. Les personnes sont
selectionnees par l'autorisation deja renseignee dans l'onglet Liens :
1 = responsable legal, 3 = raccompagnement autorise (DATA_Liens).
Un simple rattachement « Contact » ne suffit pas a declarer une personne
autorisee a reprendre un enfant.
"""

from Data import DATA_Civilites, DATA_Liens


def _texte(valeur):
    return str(valeur).strip() if valeur is not None else ""


def _fiche(ligne):
    (identifiant, nom, prenom, civilite, code_lien, rue, cp, ville,
     domicile, mobile, travail, adresse_auto, rue_auto, cp_auto,
     ville_auto) = ligne
    if adresse_auto is not None:
        rue = rue_auto if rue_auto not in (None, "") else rue
        cp = cp_auto if cp_auto not in (None, "") else cp
        ville = ville_auto if ville_auto not in (None, "") else ville
    sexe = DATA_Civilites.GetDictCivilites().get(civilite, {}).get("sexe")
    lien = DATA_Liens.DICT_TYPES_LIENS.get(code_lien, {})
    intitule = lien.get(sexe) if sexe is not None else None
    telephones = [
        libelle + " : " + _texte(numero)
        for libelle, numero in (("Mobile", mobile), ("Domicile", domicile),
                                ("Travail", travail))
        if _texte(numero)
    ]
    return {
        "IDindividu": int(identifiant),
        "identite": " ".join(x for x in (_texte(nom), _texte(prenom)) if x),
        "nom": _texte(nom), "prenom": _texte(prenom),
        "adresse": ", ".join(x for x in (
            _texte(rue), " ".join(x for x in (_texte(cp), _texte(ville)) if x))
            if x),
        "telephone": " / ".join(telephones),
        "telephone_court": next((_texte(n) for n in
                                (mobile, domicile, travail) if _texte(n)), ""),
        "lien": intitule or u"Lien à vérifier dans Noethys",
    }


def LireContactsEnfant(IDindividu, DB=None):
    """Lit responsables legaux et raccompagnants explicitement autorises.

    Ne lit aucune donnee de sante. Les familles sont rapprochees par
    rattachements pour exclure des liens hors dossier de l'enfant.
    Retourne deux listes ordonnees, sans modification de la base.
    """
    if type(IDindividu) is not int or IDindividu <= 0:
        raise ValueError("Identifiant enfant invalide")
    propre = DB is None
    if propre:
        import GestionDB
        DB = GestionDB.DB()
    try:
        if getattr(DB, "echec", 0):
            raise RuntimeError("Base Noethys inaccessible")
        marqueur = "%s" if DB.isNetwork else "?"
        requete = """
            SELECT DISTINCT i.IDindividu, i.nom, i.prenom,
                   i.IDcivilite, l.IDtype_lien, i.rue_resid, i.cp_resid,
                   i.ville_resid, i.tel_domicile, i.tel_mobile, i.travail_tel,
                   i.adresse_auto, adresse.rue_resid, adresse.cp_resid,
                   adresse.ville_resid, l.IDautorisation
            FROM liens AS l
            JOIN rattachements AS enfant
              ON enfant.IDindividu=l.IDindividu_objet
             AND enfant.IDfamille=l.IDfamille
            JOIN rattachements AS adulte
              ON adulte.IDindividu=l.IDindividu_sujet
             AND adulte.IDfamille=l.IDfamille
            JOIN individus AS i ON i.IDindividu=l.IDindividu_sujet
            LEFT JOIN individus AS adresse ON adresse.IDindividu=i.adresse_auto
            WHERE l.IDindividu_objet=""" + marqueur + """
              AND l.IDautorisation IN (1, 3)
            ORDER BY l.IDautorisation, i.nom, i.prenom, i.IDindividu
        """
        DB.cursor.execute(requete, (IDindividu,))
        lignes = DB.cursor.fetchall()
        responsables, accompagnants = [], []
        personnes_vues = set()
        for ligne in lignes:
            identifiant = int(ligne[0])
            if identifiant in personnes_vues:
                continue
            personnes_vues.add(identifiant)
            contact = _fiche(ligne[:15])
            if ligne[15] == 1:
                responsables.append(contact)
            elif ligne[15] == 3:
                accompagnants.append(contact)
        return {"responsables": responsables, "accompagnants": accompagnants}
    finally:
        if propre:
            DB.Close()
