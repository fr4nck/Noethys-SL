# -*- coding: utf-8 -*-
"""AFAS V2 -- référentiel des sites, équipements et séjours.

La matrice des sites admissibles par activité et par mode est la règle
métier de l'association. La correspondance de chaque site avec un groupe
Noethys (IDactivite, IDgroupe, nom attendu), son équipement de rattachement
et le registre des séjours qualifiés sont des données administrables,
enregistrées dans la table `profils` (catégorie afas_v2_referentiel) et
revérifiées contre la table `groupes` à chaque chargement : aucun
identifiant n'est supposé.

Le cœur (validation) n'importe ni wx ni GestionDB.
"""
import datetime
import json
import unicodedata

from Utils import UTILS_AFAS2_Conventions as Conventions

ACTIVITE_ALSH = "ALSH"
ACTIVITES = (ACTIVITE_ALSH,)  # ALSH Ados : après réception de sa convention.

PERI = Conventions.PERISCOLAIRE
EXTRA = Conventions.EXTRASCOLAIRE

BAIS_PLUS_6 = "Bais +6 ans"
BAIS_MOINS_6 = "Bais -6 ans"
MOUTIERS = "Moutiers"
LA_GUERCHE = "La Guerche-de-Bretagne"
MINICAMPS_6_8 = "Minicamps 6/8"
MINICAMPS_8_10 = "Minicamps 8/10"

MATRICE = {
    (ACTIVITE_ALSH, PERI): (BAIS_PLUS_6, BAIS_MOINS_6, MOUTIERS, LA_GUERCHE),
    (ACTIVITE_ALSH, EXTRA): (BAIS_PLUS_6, BAIS_MOINS_6, MOUTIERS, LA_GUERCHE, MINICAMPS_6_8, MINICAMPS_8_10),
}
SITES = MATRICE[(ACTIVITE_ALSH, EXTRA)]
MINICAMPS = (MINICAMPS_6_8, MINICAMPS_8_10)

# Rattachement documenté par l'intitulé des structures conventionnées
# (couverture des conventions). Minicamps : à choisir par l'administrateur.
EQUIPEMENT_DOCUMENTE = {
    BAIS_PLUS_6: Conventions.EQUIPEMENT_BAIS,
    BAIS_MOINS_6: Conventions.EQUIPEMENT_BAIS,
    LA_GUERCHE: Conventions.EQUIPEMENT_LA_GUERCHE_MOUTIERS,
    MOUTIERS: Conventions.EQUIPEMENT_LA_GUERCHE_MOUTIERS,
}

FORMAT_REFERENTIEL = 1
CATEGORIE_PROFIL = "afas_v2_referentiel"
NOM_PARAMETRE = "referentiel_json"


class ReferentielInvalide(ValueError):
    pass


def SitesAdmissibles(activite, mode):
    if (activite, mode) not in MATRICE:
        raise ReferentielInvalide("Activité ou mode non pris en charge : %s / %s" % (activite, mode))
    return MATRICE[(activite, mode)]


def NomNormalise(texte):
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode("ascii")
    return " ".join(texte.lower().split())


def ReferentielVide():
    return {"format": FORMAT_REFERENTIEL, "sites": {}, "moutiers_rattachement_confirme": False, "sejours": []}


def _entier(valeur, champ):
    if type(valeur) is not int or valeur <= 0:
        raise ReferentielInvalide("%s : identifiant entier positif attendu" % champ)
    return valeur


def _date(valeur, champ):
    try:
        return datetime.date.fromisoformat(valeur)
    except (TypeError, ValueError):
        raise ReferentielInvalide("%s : date AAAA-MM-JJ attendue" % champ)


def ValiderReferentiel(referentiel, groupes):
    """Contrôle complet du référentiel contre les groupes Noethys.

    groupes : {IDgroupe: (IDactivite, nom_groupe)} lus dans la base.
    Retourne le référentiel normalisé ; lève ReferentielInvalide sinon."""
    if not isinstance(referentiel, dict) or referentiel.get("format") != FORMAT_REFERENTIEL:
        raise ReferentielInvalide("Référentiel illisible ou de format inconnu")
    inconnues = set(referentiel) - {"format", "sites", "moutiers_rattachement_confirme", "sejours"}
    if inconnues:
        raise ReferentielInvalide("Clés inconnues dans le référentiel : %s" % ", ".join(sorted(inconnues)))
    sites = referentiel.get("sites")
    if not isinstance(sites, dict):
        raise ReferentielInvalide("Sites du référentiel invalides")
    couples = {}
    for label, lien in sites.items():
        if label not in SITES:
            raise ReferentielInvalide("Site hors matrice : %r" % (label,))
        if not isinstance(lien, dict) or set(lien) != {"IDactivite", "IDgroupe", "nom_groupe", "equipement"}:
            raise ReferentielInvalide("Lien incomplet pour %s" % label)
        IDactivite = _entier(lien["IDactivite"], label + " / IDactivite")
        IDgroupe = _entier(lien["IDgroupe"], label + " / IDgroupe")
        if IDgroupe not in groupes:
            raise ReferentielInvalide("%s : le groupe %d n'existe plus dans Noethys" % (label, IDgroupe))
        activite_reelle, nom_reel = groupes[IDgroupe]
        if activite_reelle != IDactivite:
            raise ReferentielInvalide("%s : le groupe %d appartient à l'activité %d, pas %d"
                                      % (label, IDgroupe, activite_reelle, IDactivite))
        if not isinstance(lien["nom_groupe"], str) or NomNormalise(lien["nom_groupe"]) != NomNormalise(nom_reel):
            raise ReferentielInvalide("%s : le groupe %d s'appelle « %s » dans Noethys, « %s » attendu "
                                      "(groupe renommé ou permuté)" % (label, IDgroupe, nom_reel, lien["nom_groupe"]))
        if lien["equipement"] is not None and lien["equipement"] not in Conventions.EQUIPEMENTS:
            raise ReferentielInvalide("%s : équipement inconnu %r" % (label, lien["equipement"]))
        if label in EQUIPEMENT_DOCUMENTE and lien["equipement"] != EQUIPEMENT_DOCUMENTE[label]:
            raise ReferentielInvalide("%s : rattachement contraire à la structure conventionnée" % label)
        couple = (IDactivite, IDgroupe)
        if couple in couples:
            raise ReferentielInvalide("%s et %s pointent vers le même groupe" % (couples[couple], label))
        couples[couple] = label
    if type(referentiel.get("moutiers_rattachement_confirme")) is not bool:
        raise ReferentielInvalide("Confirmation du rattachement de Moutiers invalide")
    sejours = referentiel.get("sejours")
    if not isinstance(sejours, list):
        raise ReferentielInvalide("Registre des séjours invalide")
    identifiants = set()
    for sejour in sejours:
        ValiderSejour(sejour, sites)
        if sejour["id"] in identifiants:
            raise ReferentielInvalide("Séjour en double : %s" % sejour["id"])
        identifiants.add(sejour["id"])
    return json.loads(json.dumps(referentiel))


CHAMPS_SEJOUR = {"id", "libelle", "site", "date_debut", "date_fin", "nuits",
                 "prevu_declaration_annuelle", "integre_projet_educatif", "declare_sejour_vacances"}


def ValiderSejour(sejour, sites):
    """Séjour éligible (conventions extrascolaires, art. 2-1 et 2-2).

    1 à 4 nuits : activité accessoire intégrée au projet éducatif ;
    5 nuits / 6 jours : prévu dès la déclaration annuelle, intégré au projet
    éducatif et déclaré en séjour de vacances. Au-delà : refusé."""
    if not isinstance(sejour, dict) or set(sejour) != CHAMPS_SEJOUR:
        raise ReferentielInvalide("Séjour incomplet")
    if not isinstance(sejour["id"], str) or not sejour["id"].strip():
        raise ReferentielInvalide("Séjour sans identifiant")
    if sejour["site"] not in sites:
        raise ReferentielInvalide("Séjour %s : site non relié à un groupe Noethys" % sejour["id"])
    debut = _date(sejour["date_debut"], "Séjour %s / date_debut" % sejour["id"])
    fin = _date(sejour["date_fin"], "Séjour %s / date_fin" % sejour["id"])
    nuits = sejour["nuits"]
    if type(nuits) is not int or nuits < 1 or nuits > 5:
        raise ReferentielInvalide("Séjour %s : 1 à 5 nuits admissibles" % sejour["id"])
    if (fin - debut).days != nuits:
        raise ReferentielInvalide("Séjour %s : dates incohérentes avec %d nuit(s)" % (sejour["id"], nuits))
    for champ in ("prevu_declaration_annuelle", "integre_projet_educatif", "declare_sejour_vacances"):
        if type(sejour[champ]) is not bool:
            raise ReferentielInvalide("Séjour %s : %s doit être vrai ou faux" % (sejour["id"], champ))
    if not sejour["integre_projet_educatif"]:
        raise ReferentielInvalide("Séjour %s : non intégré au projet éducatif" % sejour["id"])
    if nuits == 5 and not (sejour["prevu_declaration_annuelle"] and sejour["declare_sejour_vacances"]):
        raise ReferentielInvalide("Séjour %s : un séjour de 5 nuits doit être prévu dès la déclaration "
                                  "annuelle et déclaré en séjour de vacances" % sejour["id"])
    return True


def StatutSite(referentiel, label, mode):
    """(validable, motif) pour l'export contractuel d'un site."""
    if label not in referentiel["sites"]:
        return False, "site non relié à un groupe Noethys"
    equipement = referentiel["sites"][label]["equipement"]
    if equipement is None:
        return False, "équipement de rattachement non choisi"
    if label == MOUTIERS and not referentiel["moutiers_rattachement_confirme"]:
        return False, "rattachement de Moutiers à la convention La Guerche-Moutiers non confirmé"
    return True, ""


def Couples(referentiel, labels):
    return {(referentiel["sites"][l]["IDactivite"], referentiel["sites"][l]["IDgroupe"]): l for l in labels}


# --------------------------------------------------------------------------
# Lecture / écriture dans Noethys (sans eval : un seul paramètre texte JSON)
# --------------------------------------------------------------------------

def ChargerGroupes():
    import GestionDB
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq("SELECT IDgroupe, IDactivite, nom FROM groupes;")
        return {IDgroupe: (IDactivite, nom) for IDgroupe, IDactivite, nom in DB.ResultatReq()}
    finally:
        DB.Close()


def LireJSONProfil(IDprofil, nom_parametre):
    import GestionDB
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq("SELECT nom, parametre, type_donnee FROM profils_parametres WHERE IDprofil=%d;" % IDprofil)
        lignes = DB.ResultatReq()
    finally:
        DB.Close()
    if [nom for nom, parametre, type_donnee in lignes] != [nom_parametre] or lignes[0][2] != "texte":
        raise ValueError("Profil %d : contenu inattendu (paramètres résiduels ou absents)" % IDprofil)
    try:
        return json.loads(lignes[0][1])
    except ValueError as erreur:
        raise ValueError("Profil %d : JSON illisible (%s)" % (IDprofil, erreur))


def EcrireJSONProfil(IDprofil, nom_parametre, contenu):
    """Remplace tous les paramètres du profil par un unique paramètre JSON (aucun résidu)."""
    import GestionDB
    texte = json.dumps(contenu, ensure_ascii=False, sort_keys=True)
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq("DELETE FROM profils_parametres WHERE IDprofil=%d;" % IDprofil)
        DB.Executermany("INSERT INTO profils_parametres (nom, parametre, type_donnee, IDprofil) VALUES (?, ?, ?, ?)",
                        [(nom_parametre, texte, "texte", IDprofil)], commit=False)
        DB.Commit()
    finally:
        DB.Close()


def ProfilsCategorie(categorie):
    import GestionDB
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq("SELECT IDprofil, label FROM profils WHERE categorie='%s' ORDER BY label;" % categorie)
        return DB.ResultatReq()
    finally:
        DB.Close()


def CreerProfil(categorie, label):
    import GestionDB
    DB = GestionDB.DB()
    try:
        return DB.ReqInsert("profils", [("label", label), ("categorie", categorie), ("defaut", 0)])
    finally:
        DB.Close()


def ChargerReferentiel():
    """Référentiel validé contre la base ; référentiel vide si jamais enregistré."""
    profils = ProfilsCategorie(CATEGORIE_PROFIL)
    if not profils:
        return ReferentielVide()
    if len(profils) != 1:
        raise ReferentielInvalide("Plusieurs référentiels AFAS V2 enregistrés")
    return ValiderReferentiel(LireJSONProfil(profils[0][0], NOM_PARAMETRE), ChargerGroupes())


def EnregistrerReferentiel(referentiel):
    referentiel = ValiderReferentiel(referentiel, ChargerGroupes())
    profils = ProfilsCategorie(CATEGORIE_PROFIL)
    IDprofil = profils[0][0] if profils else CreerProfil(CATEGORIE_PROFIL, "Référentiel AFAS V2")
    EcrireJSONProfil(IDprofil, NOM_PARAMETRE, referentiel)
    return referentiel
