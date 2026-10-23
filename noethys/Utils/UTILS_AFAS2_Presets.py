# -*- coding: utf-8 -*-
"""AFAS V2 -- presets permanents de déclaration.

Un preset ne conserve que des choix métier durables (activité, mode,
équipement, sites, classement des unités, statuts retenus, critères de
période, choix conventionnels). Il ne contient JAMAIS d'année, de phase ni
de date : le schéma est fermé (toute clé inconnue est refusée, à tous les
niveaux) et le nom est contrôlé. L'année, la phase et les dates résolues
appartiennent à la demande de calcul et à son historique.

Persistance : table `profils` (catégorie afas_v2_preset), un unique
paramètre texte JSON par preset, réécrit intégralement (aucun résidu,
aucun eval). Le cœur (validation, migration, empreinte) n'importe ni wx ni
GestionDB.
"""
import copy
import hashlib
import json
import re
import unicodedata
import uuid

from Utils import UTILS_AFAS2_Calcul as Calcul
from Utils import UTILS_AFAS2_Calendrier as Calendrier
from Utils import UTILS_AFAS2_Conventions as Conventions
from Utils import UTILS_AFAS2_Referentiel as Referentiel

FORMAT_PRESET = 1
CATEGORIE_PROFIL = "afas_v2_preset"
NOM_PARAMETRE = "preset_json"

CHAMPS = {"format", "preset_id", "nom", "version", "source_preset_id", "activite", "mode", "equipement", "sites",
          "unites", "etats_realise", "etats_facture", "criteres_periodes", "choix_conventionnels"}
CHAMPS_CRITERES = {"samedis_avec_ecole"}
CHAMPS_CHOIX = {"inclure_repas_meridien", "inclure_garderie_caf"}

_TERMES_INTERDITS = ("annee", "year", "phase", "exercice", "millesime", "previsionnel", "actualisation",
                     "juin", "septembre", "date")
_ANNEE = re.compile(r"(?<!\d)(19|20|21)\d\d(?!\d)")
_IDENTIFIANT = re.compile(r"^[0-9a-f]{32}$")


class PresetInvalide(ValueError):
    pass


def _normalise(texte):
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode("ascii")
    return texte.lower()


def _controler_nom(nom):
    if not isinstance(nom, str) or not nom.strip():
        raise PresetInvalide("Nom du preset requis")
    if len(nom) > 120:
        raise PresetInvalide("Nom du preset trop long")
    normalise = _normalise(nom)
    if _ANNEE.search(normalise) or any(terme in normalise for terme in _TERMES_INTERDITS):
        raise PresetInvalide("Le nom du preset ne doit contenir ni année, ni phase, ni date : "
                             "elles sont choisies à chaque calcul")
    return nom.strip()


def _fermer(objet, attendus, contexte):
    if not isinstance(objet, dict):
        raise PresetInvalide("%s : objet attendu" % contexte)
    manquants = attendus - set(objet)
    inconnus = set(objet) - attendus
    if inconnus:
        raise PresetInvalide("%s : clés non admises %s (année, phase ou date interdites, schéma fermé)"
                             % (contexte, ", ".join(sorted(map(str, inconnus)))))
    if manquants:
        raise PresetInvalide("%s : clés manquantes %s" % (contexte, ", ".join(sorted(manquants))))


def _booleen(valeur, nom):
    if type(valeur) is not bool:
        raise PresetInvalide("%s : vrai ou faux attendu" % nom)


def ValiderPreset(preset):
    """Validation complète et indépendante de la base ; renvoie une copie."""
    _fermer(preset, CHAMPS, "Preset")
    if preset["format"] != FORMAT_PRESET:
        raise PresetInvalide("Format de preset inconnu : %r (migration requise)" % (preset["format"],))
    if not isinstance(preset["preset_id"], str) or not _IDENTIFIANT.match(preset["preset_id"]):
        raise PresetInvalide("Identifiant de preset invalide")
    if preset["source_preset_id"] is not None and (not isinstance(preset["source_preset_id"], str)
                                                   or not _IDENTIFIANT.match(preset["source_preset_id"])):
        raise PresetInvalide("Référence au preset source invalide")
    if preset["source_preset_id"] == preset["preset_id"]:
        raise PresetInvalide("Un preset ne peut pas être sa propre source")
    _controler_nom(preset["nom"])
    if type(preset["version"]) is not int or preset["version"] < 1:
        raise PresetInvalide("Version invalide")
    if preset["activite"] not in Referentiel.ACTIVITES:
        raise PresetInvalide("Activité non prise en charge : %r (ALSH uniquement dans cette version)" % (preset["activite"],))
    if preset["mode"] not in Conventions.MODES:
        raise PresetInvalide("Mode d'accueil inconnu")
    if preset["equipement"] not in Conventions.EQUIPEMENTS:
        raise PresetInvalide("Équipement inconnu")
    sites = preset["sites"]
    if not isinstance(sites, list) or not sites or len(set(sites)) != len(sites):
        raise PresetInvalide("Sites : liste non vide et sans doublon attendue")
    admissibles = Referentiel.SitesAdmissibles(preset["activite"], preset["mode"])
    for site in sites:
        if site not in admissibles:
            raise PresetInvalide("Site non admissible en %s : %r" % (preset["mode"], site))
        documente = Referentiel.EQUIPEMENT_DOCUMENTE.get(site)
        if documente is not None and documente != preset["equipement"]:
            raise PresetInvalide("Le site %s n'appartient pas à l'équipement %s (périmètres mélangés)"
                                 % (site, Conventions.EQUIPEMENTS[preset["equipement"]]["libelle"]))
    unites = preset["unites"]
    if not isinstance(unites, dict) or not unites:
        raise PresetInvalide("Classement des unités requis")
    for cle, categorie in unites.items():
        if not isinstance(cle, str) or not cle.isdigit() or int(cle) <= 0 or cle != str(int(cle)):
            raise PresetInvalide("Identifiant d'unité invalide : %r" % (cle,))
        if categorie not in Calcul.CODES_CATEGORIES:
            raise PresetInvalide("Catégorie d'unité inconnue : %r" % (categorie,))
    try:
        Calendrier.ValiderEtats(preset["etats_realise"], "Statuts du réalisé")
        Calendrier.ValiderEtats(preset["etats_facture"], "Statuts du facturé")
    except ValueError as erreur:
        raise PresetInvalide(str(erreur))
    _fermer(preset["criteres_periodes"], CHAMPS_CRITERES, "Critères de période")
    _booleen(preset["criteres_periodes"]["samedis_avec_ecole"], "samedis_avec_ecole")
    _fermer(preset["choix_conventionnels"], CHAMPS_CHOIX, "Choix conventionnels")
    for cle in CHAMPS_CHOIX:
        _booleen(preset["choix_conventionnels"][cle], cle)
    return copy.deepcopy(preset)


def NouveauPreset(nom, mode, equipement, sites=None, unites=None):
    preset = {
        "format": FORMAT_PRESET, "preset_id": uuid.uuid4().hex, "nom": nom, "version": 1, "source_preset_id": None,
        "activite": Referentiel.ACTIVITE_ALSH, "mode": mode, "equipement": equipement,
        "sites": list(sites or []), "unites": dict(unites or {}),
        "etats_realise": list(Calendrier.ETATS_REALISE_DEFAUT), "etats_facture": list(Calendrier.ETATS_FACTURE_DEFAUT),
        "criteres_periodes": {"samedis_avec_ecole": False},
        "choix_conventionnels": {"inclure_repas_meridien": True, "inclure_garderie_caf": False},
    }
    return preset


def Empreinte(objet):
    """SHA-256 du JSON canonique (clés triées, UTF-8)."""
    texte = json.dumps(objet, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def Dupliquer(preset, nouveau_nom):
    copie = ValiderPreset(preset)
    copie.update(preset_id=uuid.uuid4().hex, nom=nouveau_nom, version=1, source_preset_id=preset["preset_id"])
    return ValiderPreset(copie)


def AjusterSitesAuMode(sites, activite, mode):
    """Retire les sites devenus incompatibles après un changement d'activité ou de mode."""
    admissibles = Referentiel.SitesAdmissibles(activite, mode)
    return [site for site in sites if site in admissibles]


_LIBELLES_VERS_CODES = {libelle: code for code, libelle in Calendrier.STATUTS}
_MODES_ANCIENS = {"Périscolaire": Conventions.PERISCOLAIRE, "Extrascolaire": Conventions.EXTRASCOLAIRE}


def MigrerAncienFormat(ancien):
    """Conversion explicite des prototypes précédents (docs/afas/v2_preparation :
    lot 1 `config_version`, lot 4 `version` + `caf_billed_states`).

    Renvoie (brouillon, a_completer) : le brouillon n'est jamais validé tel
    quel ; chaque information absente ou non transposable est listée."""
    if not isinstance(ancien, dict):
        raise PresetInvalide("Ancien preset illisible")
    a_completer = []
    if ancien.get("activity") != "ALSH":
        raise PresetInvalide("Seuls les anciens presets ALSH sont migrables (ALSH Ados : convention attendue)")
    if ancien.get("mode") not in _MODES_ANCIENS:
        raise PresetInvalide("Mode de l'ancien preset inconnu")
    nom = ancien.get("name") or ancien.get("profile_id") or "Preset migré"
    try:
        _controler_nom(nom)
    except PresetInvalide:
        a_completer.append("nom (contenait une année, une phase ou une date)")
        nom = "Preset migré"
    sites = list(ancien.get("sites", ancien.get("selected_sites", [])))
    brouillon = NouveauPreset(nom, _MODES_ANCIENS[ancien["mode"]], None, sites=sites)
    for liste, categorie in (("included_units", "accueil"), ("excluded_units", "exclue"), ("garderie_units", "a_qualifier")):
        for IDunite in ancien.get(liste, []):
            brouillon["unites"][str(IDunite)] = categorie
    if ancien.get("garderie_units"):
        a_completer.append("garderies : préciser matin ou soir")
    realise = ancien.get("realised_states", ancien.get("admissible_states"))
    if realise:
        brouillon["etats_realise"] = [_LIBELLES_VERS_CODES.get(libelle, libelle) for libelle in realise]
    if "caf_billed_states" in ancien:
        brouillon["etats_facture"] = [_LIBELLES_VERS_CODES.get(libelle, libelle) for libelle in ancien["caf_billed_states"]]
    else:
        a_completer.append("statuts retenus pour le facturé (absents de l'ancien format)")
    a_completer.append("équipement")
    ignorees = sorted(set(ancien) - {"profile_id", "name", "activity", "mode", "sites", "selected_sites", "included_units",
                                     "excluded_units", "garderie_units", "realised_states", "admissible_states",
                                     "caf_billed_states", "version", "config_version"})
    if ignorees or ancien.get("period_criteria") or ancien.get("rules"):
        a_completer.append("informations non reprises : %s" % ", ".join(ignorees or ["critères et règles libres"]))
    return brouillon, a_completer


# --------------------------------------------------------------------------
# Persistance dans Noethys
# --------------------------------------------------------------------------

def ListerPresets():
    """[(IDprofil, nom)] triés par nom."""
    return Referentiel.ProfilsCategorie(CATEGORIE_PROFIL)


def ChargerPreset(IDprofil):
    contenu = Referentiel.LireJSONProfil(IDprofil, NOM_PARAMETRE)
    if isinstance(contenu, dict) and contenu.get("format") != FORMAT_PRESET and ("profile_id" in contenu):
        raise PresetInvalide("Preset au format prototype : utiliser la migration explicite")
    return ValiderPreset(contenu)


def _autres(IDprofil):
    resultat = []
    for ID, nom in ListerPresets():
        if ID == IDprofil:
            continue
        try:
            resultat.append((ID, nom, Referentiel.LireJSONProfil(ID, NOM_PARAMETRE).get("preset_id")))
        except (ValueError, AttributeError):
            resultat.append((ID, nom, None))
    return resultat


def EnregistrerPreset(preset, IDprofil=None):
    """Crée ou met à jour un preset ; la version est incrémentée à chaque
    mise à jour. Retourne (IDprofil, preset enregistré)."""
    import GestionDB
    preset = ValiderPreset(preset)
    for ID, nom, preset_id in _autres(IDprofil):
        if preset_id == preset["preset_id"]:
            raise PresetInvalide("Identifiant de preset déjà utilisé (profil %d)" % ID)
        if _normalise(nom).strip() == _normalise(preset["nom"]).strip():
            raise PresetInvalide("Un preset porte déjà ce nom")
    if IDprofil is None:
        IDprofil = Referentiel.CreerProfil(CATEGORIE_PROFIL, preset["nom"])
    else:
        ancien = Referentiel.LireJSONProfil(IDprofil, NOM_PARAMETRE)
        if ancien.get("preset_id") != preset["preset_id"]:
            raise PresetInvalide("Le profil %d porte un autre preset" % IDprofil)
        preset["version"] = ancien.get("version", 0) + 1
        DB = GestionDB.DB()
        try:
            DB.ReqMAJ("profils", [("label", preset["nom"])], "IDprofil", IDprofil)
        finally:
            DB.Close()
    Referentiel.EcrireJSONProfil(IDprofil, NOM_PARAMETRE, preset)
    return IDprofil, preset


def DupliquerPreset(IDprofil, nouveau_nom):
    return EnregistrerPreset(Dupliquer(ChargerPreset(IDprofil), nouveau_nom))


def RenommerPreset(IDprofil, nouveau_nom):
    preset = ChargerPreset(IDprofil)
    preset["nom"] = nouveau_nom
    return EnregistrerPreset(preset, IDprofil)


def SupprimerPreset(IDprofil):
    import GestionDB
    DB = GestionDB.DB()
    try:
        DB.ExecuterReq("DELETE FROM profils_parametres WHERE IDprofil=%d;" % IDprofil)
        DB.ExecuterReq("DELETE FROM profils WHERE IDprofil=%d AND categorie='%s';" % (IDprofil, CATEGORIE_PROFIL))
        DB.Commit()
    finally:
        DB.Close()
