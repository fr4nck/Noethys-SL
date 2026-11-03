# -*- coding: utf-8 -*-
"""#436 - Lecture explicite des informations MEDICALES DEJA existantes.

Ne cree aucun champ ni PAI, ne modifie aucun dossier. Cette lecture
de detail est reservee a un administrateur authentifie de Noethys.
Aucune liaison portail, log, export ou cache.
"""
from datetime import date, datetime
import re
import unicodedata

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
            SELECT ps.intitule, ps.date_debut, ps.date_fin, ps.description,
                   ps.traitement_medical, ps.description_traitement,
                   cat.nom, ps.date_debut_traitement, ps.date_fin_traitement
            FROM problemes_sante AS ps
            LEFT JOIN categories_medicales AS cat ON cat.IDcategorie=ps.IDtype
            WHERE ps.IDindividu=""" + placeholder +
            " ORDER BY ps.date_debut DESC, ps.IDprobleme DESC", (IDindividu,))
        problemes = []
        for (titre, debut, fin, description, traitement, consignes,
             categorie, debut_traitement, fin_traitement) in DB.cursor.fetchall():
            problemes.append({
                "intitule": titre or "",
                "categorie": categorie or "",
                "date_debut": str(debut) if debut is not None else None,
                "date_fin": str(fin) if fin is not None else None,
                "description": description or "",
                "traitement_medical": traitement == 1,
                "description_traitement": consignes or "",
                "date_debut_traitement": (
                    str(debut_traitement) if debut_traitement is not None else None),
                "date_fin_traitement": (
                    str(fin_traitement) if fin_traitement is not None else None),
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



def _mot_cle(texte):
    texte = str(texte or "").casefold()
    return "".join(c for c in unicodedata.normalize("NFKD", texte)
                   if not unicodedata.combining(c))


def _date_source(valeur):
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    if valeur in (None, ""):
        return None
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (ValueError, TypeError):
        return None


def _periode_active(probleme, au, debut="date_debut", fin="date_fin"):
    d = _date_source(probleme.get(debut))
    f = _date_source(probleme.get(fin))
    return (d is None or d <= au) and (f is None or au <= f)


def PreparerRubriquesMedicales(medical, au=None):
    """Remplit la fiche PMSL depuis les informations deja saisies dans Noethys.

    Seule la mention explicite « PAI » ou une categorie ainsi nommee
    permet de renseigner le champ PAI ; jamais une maladie generique.
    Une allergie est reconnue dans la categorie existante « Allergie »
    ou un intitule explicite. Pas de statut officiel PAI ni d'ordonnance
    inferes de la presence d'une fiche.
    """
    if au is None:
        au = date.today()
    au = _date_source(au)
    if au is None:
        raise ValueError("Date de fiche medicale invalide")
    if not isinstance(medical, dict):
        raise ValueError("Dossier medical invalide")
    pai, allergies, traitements, informations = [], [], [], []
    for pb in medical.get("problemes") or []:
        if not _periode_active(pb, au):
            continue
        titre = str(pb.get("intitule") or "").strip()
        categorie = str(pb.get("categorie") or "").strip()
        description = str(pb.get("description") or "").strip()
        consignes = str(pb.get("description_traitement") or "").strip()
        marqueur = _mot_cle(categorie + " " + titre)
        est_allergie = bool(re.search(r"\ballerg\w*", marqueur))
        est_pai = bool(re.search(
            r"\bp[.\s]*a[.\s]*i(?:\b|[.])|projet d.accueil individualis",
            marqueur))
        nom = titre or categorie or u"Information médicale"
        details = [nom]
        if description:
            details.append(description)
        if pb.get("traitement_medical") is True and consignes and _periode_active(
                pb, au, "date_debut_traitement", "date_fin_traitement"):
            traitements.append(u"%s : %s" % (nom, consignes))
            details.append(u"Traitement : %s" % consignes)
        informations.append(u" — ".join(details))
        if est_allergie:
            allergies.append(u" : ".join(x for x in (nom, description) if x))
        if est_pai:
            pai.append(u" : ".join(x for x in (nom, description) if x))
    return {
        "pai": (u"PAI mentionné : " + u" ; ".join(pai)
                if pai else u"Non renseigné dans Noethys"),
        "allergies": (u" ; ".join(allergies)
                      if allergies else u"Non renseigné dans Noethys"),
        "traitement": (u" ; ".join(traitements)
                       if traitements else u"Non renseigné dans Noethys"),
        "medical": informations,
    }


def LireRepasExistant(IDindividu, utilisateur, DB=None):
    """Lit la reponse au questionnaire repas existant, sans valeur implicite.

    L'absence de reponse ne devient jamais Standard. Le libelle du portail,
    les formulaires de facturation et les questions medicales sont exclus.
    """
    if type(IDindividu) is not int or IDindividu <= 0:
        raise ValueError("Identifiant enfant incorrect")
    if not acl.AccesUtilisateur(utilisateur, "consulter"):
        raise LectureMedicaleRefusee("Lecture des preferences non autorisee")
    from Utils import UTILS_Repas_questionnaire
    propre = DB is None
    if propre:
        import GestionDB
        DB = GestionDB.DB()
    try:
        if getattr(DB, "echec", 0):
            raise RuntimeError("Base Noethys indisponible")
        parametrage = UTILS_Repas_questionnaire.ExaminerQuestionnaire(base=DB)
        if parametrage["etat"] != "pret":
            return "non_configure" if parametrage["etat"] == "absent" else "a_verifier"
        placeholder = "%s" if DB.isNetwork else "?"
        DB.cursor.execute("""
            SELECT reponse FROM questionnaire_reponses
            WHERE IDquestion=""" + placeholder +
            " AND IDindividu=" + placeholder + " ORDER BY IDreponse",
            (parametrage["question"], IDindividu))
        reponses = DB.cursor.fetchall()
        if len(reponses) > 1:
            return "a_verifier"
        brut = reponses[0][0] if reponses else None
        if brut is None or str(brut).strip() == "":
            return "non_renseigne"
        elements = [x.strip() for x in str(brut).split(";") if x.strip()]
        if len(set(elements)) != 1:
            return "a_verifier"
        inverse = {str(id_): role for role, id_ in parametrage["choix"].items()}
        return inverse.get(elements[0], "a_verifier")
    finally:
        if propre:
            DB.Close()
