# -*- coding: utf-8 -*-
"""Fiches famille Pêle-Mêle : lecture seule du dossier Noethys existant.

Une édition famille commune ALSH / Club ados ; aucune création de famille,
aucun formulaire parallèle et aucune autorisation implicite.
"""

from datetime import date
from Data import DATA_Civilites
from Utils import UTILS_Accueil_scolarite as scolarite


def _texte(valeur):
    return str(valeur).strip() if valeur is not None else ""


def _date_fr(valeur):
    if valeur is None or valeur == "":
        return ""
    try:
        valeur = str(valeur)[:10]
        return date.fromisoformat(valeur).strftime("%d/%m/%Y")
    except ValueError:
        return _texte(valeur)


def _contacts(ligne):
    (ident, categorie, titulaire, civilite, nom, prenom, naissance,
     rue, cp, ville, auto, rue_auto, cp_auto, ville_auto,
     domicile, mobile, professionnel, mail, employeur) = ligne
    if auto is not None:
        rue = rue_auto if _texte(rue_auto) else rue
        cp = cp_auto if _texte(cp_auto) else cp
        ville = ville_auto if _texte(ville_auto) else ville
    sexe = DATA_Civilites.GetDictCivilites().get(civilite, {}).get("sexe", "")
    return {
        "IDindividu": int(ident),
        "categorie": int(categorie) if categorie is not None else None,
        "titulaire": titulaire == 1,
        "nom": _texte(nom), "prenom": _texte(prenom),
        "sexe": sexe or "", "date_naiss": _date_fr(naissance),
        "adresse": _texte(rue), "cp": _texte(cp), "ville": _texte(ville),
        "domicile": _texte(domicile), "mobile": _texte(mobile),
        "travail_tel": _texte(professionnel),
        "mail": _texte(mail), "employeur": _texte(employeur),
        "statut": "", "situation": "", "ecole": "", "classe": "",
    }


def LireFamille(IDfamille, au=None, DB=None):
    """Prépare les deux types de fiche à partir d'une famille existante.

    Les catégories de rattachement sont celles de Noethys :
    1=representant, 2=enfant, 3=contact. On ne crée pas de responsable
    légal à partir d'une civilité ou d'un âge.
    """
    if type(IDfamille) is not int or IDfamille <= 0:
        raise ValueError("Famille invalide")
    if au is None:
        au = date.today()
    if isinstance(au, str):
        au = date.fromisoformat(au)
    if type(au) is not date:
        raise ValueError("Date invalide")
    proprietaire = DB is None
    if proprietaire:
        import GestionDB
        DB = GestionDB.DB()
    try:
        if getattr(DB, "echec", 0):
            raise RuntimeError("Base Noethys inaccessible")
        p = "%s" if DB.isNetwork else "?"
        DB.cursor.execute("""
            SELECT f.IDfamille, f.num_allocataire,
                   regime.nom, caisse.nom
            FROM familles f
            LEFT JOIN caisses caisse ON caisse.IDcaisse=f.IDcaisse
            LEFT JOIN regimes regime ON regime.IDregime=caisse.IDregime
            WHERE f.IDfamille=""" + p, (IDfamille,))
        entete = DB.cursor.fetchone()
        if not entete:
            raise ValueError("Famille introuvable")

        DB.cursor.execute("""
            SELECT i.IDindividu, r.IDcategorie, r.titulaire,
                   i.IDcivilite, i.nom, i.prenom, i.date_naiss,
                   i.rue_resid, i.cp_resid, i.ville_resid,
                   i.adresse_auto, adresse.rue_resid,
                   adresse.cp_resid, adresse.ville_resid,
                   i.tel_domicile, i.tel_mobile, i.travail_tel,
                   i.mail, i.employeur
            FROM rattachements r
            JOIN individus i ON i.IDindividu=r.IDindividu
            LEFT JOIN individus adresse ON adresse.IDindividu=i.adresse_auto
            WHERE r.IDfamille=""" + p + """
              AND r.IDcategorie IN (1, 2)
            ORDER BY r.IDcategorie, r.titulaire DESC,
                     i.nom, i.prenom, i.IDindividu
        """, (IDfamille,))
        personnes = [_contacts(row) for row in DB.cursor.fetchall()]
        parents = [p for p in personnes if p["categorie"] == 1]
        enfants = [p for p in personnes if p["categorie"] == 2]
        # Scolarité réellement active au jour de l'édition.
        for enfant in enfants:
            resultat = scolarite.LireScolariteActuelle(
                enfant["IDindividu"], au, DB=DB)
            enfant["classe"] = resultat["classe"]
            enfant["ecole"] = resultat["ecole"]
        return {
            "IDfamille": IDfamille, "responsables": parents,
            "enfants": enfants, "regime": _texte(entete[2]),
            "caisse": _texte(entete[3]),
            "num_allocataire": _texte(entete[1]),
        }
    finally:
        if proprietaire:
            DB.Close()


def SelectionnerEnfants(donnees, identifiants):
    """Sélection explicite des enfants ALSH ou ados à inscrire."""
    if not isinstance(donnees, dict):
        raise ValueError("Données de famille invalides")
    resultat = dict(donnees)
    enfants = list(donnees.get("enfants") or [])
    ids_valides = {enfant["IDindividu"] for enfant in enfants}
    ids = list(identifiants)
    if not ids or len(ids) != len(set(ids)) or not set(ids).issubset(ids_valides):
        raise ValueError("Choisissez les enfants de cette famille à inscrire")
    resultat["enfants"] = [e for e in enfants if e["IDindividu"] in ids]
    return resultat

ACCUEILS = (
    "ALSH LA GUERCHE", "ALSH MOUTIERS", "ALSH BAIS", "CLUB ADOS BAIS",
)


def AffecterAccueils(donnees, affectations):
    """Attribue les accueils aux enfants sélectionnés, pour l'impression seule.

    Un enfant peut fréquenter un ALSH et le Club ados, mais pas plusieurs
    sites ALSH sur le même document. On n'invente aucune inscription à
    partir de l'âge ou de la scolarité.
    """
    if not isinstance(donnees, dict) or not isinstance(affectations, dict):
        raise ValueError("Affectations des accueils invalides")
    enfants = donnees.get("enfants") or []
    attendus = {e["IDindividu"] for e in enfants}
    if not attendus or set(affectations) != attendus:
        raise ValueError("Indiquez un accueil pour chaque enfant sélectionné")
    copie = dict(donnees)
    copie["enfants"] = []
    for e in enfants:
        values = affectations[e["IDindividu"]]
        if isinstance(values, str):
            raise ValueError("Choix d'accueils invalide")
        choix = list(values)
        if (not choix or len(choix) != len(set(choix))
                or not set(choix).issubset(ACCUEILS)
                or sum(code.startswith("ALSH ") for code in choix) > 1):
            raise ValueError("Sélectionnez un ALSH au maximum et/ou le Club ados")
        enfant = dict(e)
        enfant["accueils"] = [code for code in ACCUEILS if code in choix]
        copie["enfants"].append(enfant)
    return copie
