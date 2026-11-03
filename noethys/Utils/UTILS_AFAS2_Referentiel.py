# -*- coding: utf-8 -*-
"""AFAS V2 -- référentiel des sites, équipements et séjours.

La matrice des sites admissibles par activité et par mode est la règle
métier de l'association. La correspondance de chaque site avec un groupe
Noethys (IDactivite, IDgroupe, nom attendu), son équipement de rattachement
et le registre des séjours qualifiés sont des données administrables,
enregistrées dans la table `profils` (catégorie afas_v2_referentiel) et
revérifiées contre la table `groupes` à chaque chargement : aucun
identifiant n'est supposé.

Format 2 : calendrier daté des samedis avec école par année scolaire
(`samedis_avec_ecole`) et justificatifs des rattachements non documentés
par l'intitulé des conventions (`justificatifs` : Moutiers, minicamps).
Le rattachement d'un minicamp ou de Moutiers n'est jamais déduit du nom du
groupe : il est validable seulement avec la référence du document officiel
qui le fonde (formulaire d'implantation, déclaration de l'accueil).
Régularisations qualifiées (`regularisations`) : pour chaque prestation
négative non rattachée à une consommation (avoir, régularisation), la liste
des consommations dont elle annule la facturation (éventuellement aucune)
et la pièce qui le justifie.

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

FORMAT_REFERENTIEL = 2
CLES_REFERENTIEL = {"format", "sites", "moutiers_rattachement_confirme", "sejours", "samedis_avec_ecole", "justificatifs",
                    "regularisations"}
# Sites dont le rattachement exige un justificatif (non documenté par l'intitulé des conventions).
SITES_A_JUSTIFIER = (MOUTIERS,) + MINICAMPS
TAILLE_MAX_JUSTIFICATIF = 300
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
    return {"format": FORMAT_REFERENTIEL, "sites": {}, "moutiers_rattachement_confirme": False, "sejours": [],
            "samedis_avec_ecole": {}, "justificatifs": {}, "regularisations": {}}


def MigrerReferentiel(referentiel):
    """Format 1 -> 2 sans perte : aucun calendrier des samedis établi, aucun
    justificatif (plus strict : à compléter avant toute validation)."""
    if isinstance(referentiel, dict) and referentiel.get("format") == 1:
        referentiel = dict(referentiel, format=FORMAT_REFERENTIEL, samedis_avec_ecole={}, justificatifs={}, regularisations={})
    return referentiel


def ValiderRegularisations(regularisations):
    """{"IDprestation": {"consommations_annulees": [IDconso, ...], "justification": "..."}}."""
    if not isinstance(regularisations, dict):
        raise ReferentielInvalide("Régularisations qualifiées invalides")
    for IDprestation, qualification in regularisations.items():
        if not isinstance(IDprestation, str) or not IDprestation.isdigit() or IDprestation != str(int(IDprestation)) \
                or int(IDprestation) <= 0:
            raise ReferentielInvalide("Régularisation : identifiant de prestation invalide %r" % (IDprestation,))
        if not isinstance(qualification, dict) or set(qualification) != {"consommations_annulees", "justification"}:
            raise ReferentielInvalide("Régularisation %s : qualification incomplète" % IDprestation)
        annulees = qualification["consommations_annulees"]
        if not isinstance(annulees, list) or len(set(annulees)) != len(annulees) \
                or not all(type(i) is int and i > 0 for i in annulees):
            raise ReferentielInvalide("Régularisation %s : consommations annulées invalides" % IDprestation)
        texte = qualification["justification"]
        if not isinstance(texte, str) or not texte.strip() or len(texte) > TAILLE_MAX_JUSTIFICATIF:
            raise ReferentielInvalide("Régularisation %s : justification requise (%d caractères maximum)"
                                      % (IDprestation, TAILLE_MAX_JUSTIFICATIF))
    return True


def LireSamedisTexte(texte):
    """Saisie « AAAA : AAAA-MM-JJ, AAAA-MM-JJ » ou « AAAA : aucun », une année
    scolaire (année de rentrée) par ligne -> calendrier validé."""
    resultat = {}
    for numero, ligne in enumerate(str(texte).splitlines(), 1):
        if not ligne.strip():
            continue
        if ":" not in ligne:
            raise ReferentielInvalide("Samedis avec école, ligne %d : « AAAA : dates » attendu" % numero)
        annee, dates = (morceau.strip() for morceau in ligne.split(":", 1))
        if annee in resultat:
            raise ReferentielInvalide("Samedis avec école : année scolaire %s en double" % annee)
        valeurs = [d.strip() for d in dates.replace(";", ",").split(",") if d.strip()]
        resultat[annee] = [] if [v.lower() for v in valeurs] == ["aucun"] else valeurs
        if not valeurs:
            raise ReferentielInvalide("Samedis avec école %s : indiquer les dates ou « aucun »" % annee)
    ValiderSamedis(resultat)
    return resultat


def TexteSamedis(calendrier_samedis):
    return "\n".join("%s : %s" % (annee, ", ".join(dates) if dates else "aucun")
                     for annee, dates in sorted(calendrier_samedis.items()))


def LireRegularisation(IDprestation, consommations, justification):
    """Saisie d'une régularisation qualifiée -> (clé, qualification) validées.
    consommations : IDconso séparés par des virgules, ou vide si elle n'annule aucune unité."""
    cle = str(IDprestation).strip()
    try:
        annulees = [int(x) for x in str(consommations).replace(";", ",").split(",") if x.strip()]
    except ValueError:
        raise ReferentielInvalide("Consommations annulées : identifiants numériques séparés par des virgules")
    qualification = {"consommations_annulees": annulees, "justification": str(justification).strip()}
    ValiderRegularisations({cle: qualification})
    return cle, qualification


def ValiderSamedis(calendrier_samedis):
    """{"AAAA": ["AAAA-MM-JJ", ...]} : AAAA = année de rentrée ; chaque date est
    un samedi de cette année scolaire, sans doublon. Liste vide = aucun samedi
    avec école (calendrier établi)."""
    if not isinstance(calendrier_samedis, dict):
        raise ReferentielInvalide("Calendrier des samedis avec école invalide")
    for annee, dates in calendrier_samedis.items():
        if not isinstance(annee, str) or not annee.isdigit() or len(annee) != 4:
            raise ReferentielInvalide("Samedis avec école : année scolaire AAAA attendue (%r)" % (annee,))
        if not isinstance(dates, list) or len(set(dates)) != len(dates):
            raise ReferentielInvalide("Samedis avec école %s : liste de dates sans doublon attendue" % annee)
        for texte in dates:
            date = _date(texte, "Samedi avec école %s" % annee)
            if date.weekday() != 5:
                raise ReferentielInvalide("%s n'est pas un samedi" % texte)
            if (date.year if date.month >= 9 else date.year - 1) != int(annee):
                raise ReferentielInvalide("%s n'appartient pas à l'année scolaire %s-%d" % (texte, annee, int(annee) + 1))
    return True


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
    referentiel = MigrerReferentiel(referentiel)
    if not isinstance(referentiel, dict) or referentiel.get("format") != FORMAT_REFERENTIEL:
        raise ReferentielInvalide("Référentiel illisible ou de format inconnu")
    inconnues = set(referentiel) - CLES_REFERENTIEL
    if inconnues:
        raise ReferentielInvalide("Clés inconnues dans le référentiel : %s" % ", ".join(sorted(inconnues)))
    if CLES_REFERENTIEL - set(referentiel):
        raise ReferentielInvalide("Référentiel incomplet : %s" % ", ".join(sorted(CLES_REFERENTIEL - set(referentiel))))
    ValiderSamedis(referentiel["samedis_avec_ecole"])
    ValiderRegularisations(referentiel["regularisations"])
    justificatifs = referentiel["justificatifs"]
    if not isinstance(justificatifs, dict):
        raise ReferentielInvalide("Justificatifs invalides")
    for label, texte in justificatifs.items():
        if label not in SITES_A_JUSTIFIER:
            raise ReferentielInvalide("Justificatif sans objet pour %r (rattachement documenté par la convention)" % (label,))
        if not isinstance(texte, str) or not texte.strip() or len(texte) > TAILLE_MAX_JUSTIFICATIF:
            raise ReferentielInvalide("%s : référence du justificatif requise (%d caractères maximum)"
                                      % (label, TAILLE_MAX_JUSTIFICATIF))
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
        return False, ("rattachement de Moutiers à la convention La Guerche-Moutiers non confirmé "
                       "(référence contractuelle provisoire : formulaire d'implantation à vérifier)")
    if label in SITES_A_JUSTIFIER and not referentiel.get("justificatifs", {}).get(label):
        return False, ("justificatif du rattachement non renseigné (formulaire d'implantation ou déclaration "
                       "de l'accueil désignant l'équipement organisateur)")
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
    return ValiderReferentiel(MigrerReferentiel(LireJSONProfil(profils[0][0], NOM_PARAMETRE)), ChargerGroupes())


def EnregistrerReferentiel(referentiel):
    referentiel = ValiderReferentiel(referentiel, ChargerGroupes())
    profils = ProfilsCategorie(CATEGORIE_PROFIL)
    IDprofil = profils[0][0] if profils else CreerProfil(CATEGORIE_PROFIL, "Référentiel AFAS V2")
    EcrireJSONProfil(IDprofil, NOM_PARAMETRE, referentiel)
    return referentiel
