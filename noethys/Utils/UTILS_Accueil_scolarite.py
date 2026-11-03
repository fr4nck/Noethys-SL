# -*- coding: utf-8 -*-
"""Scolarite de la fiche enfant PMSL, depuis les tables Noethys existantes.

Lecture uniquement : scolarite / classes / niveaux_scolaires / ecoles.
La date de reference determine l'etape active, sans deviner la classe
a partir de l'age ni ecraser les scolarites historiques.
"""
from datetime import date


def LireScolariteActuelle(IDindividu, au=None, DB=None):
    """Retourne la classe et l'ecole a la date donnee, ou un etat explicite.

    Un enfant peut avoir un historique scolaire, mais deux affectations
    actives le meme jour ne doivent pas etre choisies arbitrairement.
    """
    if type(IDindividu) is not int or IDindividu <= 0:
        raise ValueError("Identifiant enfant invalide")
    if au is None:
        au = date.today()
    if isinstance(au, str):
        try:
            au = date.fromisoformat(au)
        except ValueError:
            raise ValueError("Date de consultation invalide")
    if type(au) is not date:
        raise ValueError("Date de consultation invalide")

    propre = DB is None
    if propre:
        import GestionDB
        DB = GestionDB.DB()
    try:
        if getattr(DB, "echec", 0):
            raise RuntimeError("Base Noethys indisponible")
        marqueur = "%s" if DB.isNetwork else "?"
        req = """
            SELECT s.IDscolarite, s.date_debut, s.date_fin,
                   e.nom, c.nom, n.nom, n.abrege
            FROM scolarite AS s
            LEFT JOIN ecoles AS e ON e.IDecole=s.IDecole
            LEFT JOIN classes AS c ON c.IDclasse=s.IDclasse
            LEFT JOIN niveaux_scolaires AS n ON n.IDniveau=s.IDniveau
            WHERE s.IDindividu=""" + marqueur + """
              AND s.date_debut <= """ + marqueur + """
              AND (s.date_fin IS NULL OR s.date_fin >= """ + marqueur + """)
            ORDER BY s.date_debut DESC, s.IDscolarite DESC
            LIMIT 2
        """
        DB.cursor.execute(req, (IDindividu, au.isoformat(), au.isoformat()))
        lignes = DB.cursor.fetchall()
    finally:
        if propre:
            DB.Close()

    if not lignes:
        return {"etat": "absent", "classe": "", "niveau": "", "ecole": ""}
    if len(lignes) > 1:
        return {"etat": "a_verifier", "classe": u"À vérifier : scolarités simultanées",
                "niveau": "", "ecole": ""}

    _id, _debut, _fin, nom_ecole, nom_classe, nom_niveau, abrege = lignes[0]
    niveau = str(abrege or nom_niveau or "").strip()
    nom_classe = str(nom_classe or "").strip()
    if niveau and nom_classe and niveau != nom_classe:
        classe = u"%s (%s)" % (niveau, nom_classe)
    else:
        classe = niveau or nom_classe
    return {"etat": "ok", "classe": classe, "niveau": niveau,
            "ecole": str(nom_ecole or "").strip()}
