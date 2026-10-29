# -*- coding: utf-8 -*-
"""#436 - Lecture explicite des informations MEDICALES DEJA existantes.

Ne cree aucun champ ni PAI, ne modifie aucun dossier. Cette lecture
de detail est reservee a un administrateur authentifie de Noethys.
Aucune liaison portail, log, export ou cache.
"""
from Utils import UTILS_Accueil_autorisations as acl


class LectureMedicaleRefusee(PermissionError):
    pass


def AdministrateurActuel(utilisateur):
    return (
        acl.AccesUtilisateur(utilisateur, "consulter") is True
        and isinstance(utilisateur.get("profil"), str)
        and utilisateur["profil"].startswith("administrateur")
    )


def LireMedicalExistant(IDindividu, utilisateur, DB=None):
    if type(IDindividu) is not int or IDindividu <= 0:
        raise ValueError("Identifiant enfant incorrect")
    if not AdministrateurActuel(utilisateur):
        # STOP avant la premiere requete et avant l'ouverture d'une connexion.
        raise LectureMedicaleRefusee("Lecture de la fiche medicale reservee")
    propre = DB is None
    if propre:
        import GestionDB
        DB = GestionDB.DB()
    try:
        if getattr(DB, "echec", 0):
            raise RuntimeError("Base Noethys indisponible")
        placeholder = "%s" if DB.isNetwork else "?"
        DB.cursor.execute("""
            SELECT i.IDmedecin, m.nom, m.prenom, m.tel_cabinet
            FROM individus i LEFT JOIN medecins m ON i.IDmedecin=m.IDmedecin
            WHERE i.IDindividu=""" + placeholder, (IDindividu,))
        medecin = DB.cursor.fetchone()
        if medecin is None:
            raise ValueError("Enfant introuvable")
        DB.cursor.execute(
            "SELECT COUNT(*) FROM vaccins WHERE IDindividu=" + placeholder,
            (IDindividu,))
        nb_vaccins = int(DB.cursor.fetchone()[0])
        DB.cursor.execute("""
            SELECT intitule, date_debut, date_fin, description,
                   traitement_medical, description_traitement
            FROM problemes_sante WHERE IDindividu=""" + placeholder +
            " ORDER BY date_debut DESC, IDprobleme DESC", (IDindividu,))
        problemes = []
        for titre, debut, fin, description, traitement, consignes in DB.cursor.fetchall():
            problemes.append({
                "intitule": titre or "",
                "date_debut": str(debut) if debut is not None else None,
                "date_fin": str(fin) if fin is not None else None,
                "description": description or "",
                "traitement_medical": traitement == 1,
                "description_traitement": consignes or "",
            })
        return {
            "medecin": {
                "nom": (medecin[1] or ""),
                "prenom": (medecin[2] or ""),
                "telephone": (medecin[3] or ""),
            } if medecin[0] is not None else None,
            "vaccins_enregistres": nb_vaccins,
            "problemes": problemes,
        }
    finally:
        if propre:
            DB.Close()
