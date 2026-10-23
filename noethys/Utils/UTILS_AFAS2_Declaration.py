# -*- coding: utf-8 -*-
"""AFAS V2 -- exécution d'une déclaration, phases, historique et exports.

Une déclaration = un preset permanent + une année + une phase choisies à
l'exécution. Le preset n'est jamais modifié : un instantané (avec son
empreinte) est figé dans chaque rapport, chaque historique et chaque export.

Phases (UTILS_AFAS.GetCycleAFAS) :
- prévisionnel annuel : prévision du 01/01 au 31/12 ;
- actualisation de juin : réalisé du 01/01 au 30/06, prévision du 01/07 au 31/12 ;
- actualisation de septembre : réalisé du 01/01 au 30/09, prévision du 01/10 au 31/12 ;
- réel annuel : réalisé du 01/01 au 31/12.
Prévision : même période de N-1 ajustée aux jours d'ouverture programmés,
ou saisie manuelle contrôlée. Aucun prévisionnel n'est inventé en cas
d'historique incomplet.
"""
import csv
import datetime
import json
import math
import os

from Utils import UTILS_AFAS
from Utils import UTILS_AFAS2_Calcul as Calcul
from Utils import UTILS_AFAS2_Calendrier as Calendrier
from Utils import UTILS_AFAS2_Conventions as Conventions
from Utils import UTILS_AFAS2_Presets as Presets
from Utils import UTILS_AFAS2_Referentiel as Referentiel

PHASES = (
    (UTILS_AFAS.PHASE_PREVISIONNEL, "Prévisionnel annuel"),
    (UTILS_AFAS.PHASE_ACTUALISATION_JUIN, "Actualisation de juin"),
    (UTILS_AFAS.PHASE_ACTUALISATION_SEPTEMBRE, "Actualisation de septembre"),
    (UTILS_AFAS.PHASE_REEL, "Réel annuel"),
)
LIBELLES_PHASES = dict(PHASES)
METHODE_N1 = "n1_ajuste"
METHODE_MANUELLE = "manuelle"
# Indicateurs pouvant recevoir une prévision manuelle (les autres restent
# « non qualifiés » en saisie manuelle, jamais remplacés par un zéro).
INDICATEURS_PREVISION_MANUELLE = ("heures_realisees", "heures_facturees", "heures_realisees_aeeh", "heures_facturees_aeeh")
FORMAT_RAPPORT = 1
CATEGORIE_HISTORIQUE = "afas_v2_historique"
NOM_PARAMETRE_HISTORIQUE = "declaration_json"
TAILLE_MAX_HISTORIQUE = 28000  # profils_parametres.parametre : VARCHAR(30000)


class DeclarationImpossible(ValueError):
    pass


def Periodes(annee, phase):
    """(debut_realise, fin_realise, debut_prevision, fin_prevision) ; None si absent."""
    if type(annee) is not int or not 2000 <= annee <= 2100:
        raise DeclarationImpossible("Année invalide")
    if phase not in LIBELLES_PHASES:
        raise DeclarationImpossible("Phase inconnue")
    cycle = UTILS_AFAS.GetCycleAFAS(annee)[phase]
    debut, fin, situation = cycle["date_debut"], cycle["date_fin"], cycle["date_situation"]
    if phase == UTILS_AFAS.PHASE_PREVISIONNEL:
        return None, None, debut, fin
    if phase == UTILS_AFAS.PHASE_REEL:
        return debut, fin, None, None
    return debut, situation, situation + datetime.timedelta(days=1), fin


def _annee_precedente(date):
    try:
        return date.replace(year=date.year - 1)
    except ValueError:  # 29 février
        return date.replace(year=date.year - 1, day=28)


class Source(object):
    """Accès aux données Noethys ; remplaçable en test."""

    def Groupes(self):
        return Referentiel.ChargerGroupes()

    def Unites(self, IDactivites):
        from Utils import UTILS_AFAS2_Donnees
        return UTILS_AFAS2_Donnees.ChargerUnites(IDactivites)

    def Consommations(self, couples, debut, fin):
        from Utils import UTILS_AFAS2_Donnees
        return UTILS_AFAS2_Donnees.ChargerConsommations(couples, debut, fin)

    def Ouvertures(self, couples, debut, fin):
        from Utils import UTILS_AFAS2_Donnees
        return UTILS_AFAS2_Donnees.ChargerOuvertures(couples, debut, fin)

    def AEEH(self, IDindividus):
        from Utils import UTILS_AFAS2_Donnees
        return UTILS_AFAS2_Donnees.ChargerAEEH(IDindividus)

    def Calendrier(self, debut, fin):
        return Calendrier.ChargerCalendrier(debut, fin)


def Perimetre(preset, referentiel):
    """Couples, sites validables et motifs ; lève DeclarationImpossible si un site n'est pas relié."""
    preset = Presets.ValiderPreset(preset)
    couples, motifs = {}, []
    for site in preset["sites"]:
        if site not in referentiel["sites"]:
            raise DeclarationImpossible("Le site %s n'est relié à aucun groupe Noethys dans le référentiel" % site)
        lien = referentiel["sites"][site]
        if lien["equipement"] not in (None, preset["equipement"]):
            raise DeclarationImpossible("Le site %s est rattaché à un autre équipement (périmètres mélangés)" % site)
        couples[(lien["IDactivite"], lien["IDgroupe"])] = site
        validable, motif = Referentiel.StatutSite(referentiel, site, preset["mode"])
        if not validable:
            motifs.append("%s : %s" % (site, motif))
    return preset, couples, motifs


def _contexte(preset, referentiel, couples, source, debut, fin, date_reference):
    IDactivites = sorted({a for a, g in couples})
    unites_noethys = source.Unites(IDactivites)
    unites = {}
    for cle, categorie in preset["unites"].items():
        IDunite = int(cle)
        if IDunite not in unites_noethys:
            raise DeclarationImpossible("L'unité %d classée dans le preset n'existe plus dans Noethys" % IDunite)
        unites[IDunite] = dict(unites_noethys[IDunite], categorie=categorie)
    sites = set(couples.values())
    return {
        "mode": preset["mode"], "equipement": preset["equipement"], "couples": couples, "unites": unites,
        "etats_realise": preset["etats_realise"], "etats_facture": preset["etats_facture"],
        "options": dict(preset["criteres_periodes"], **preset["choix_conventionnels"]),
        "calendrier": source.Calendrier(debut, fin), "ouvertures": source.Ouvertures(list(couples), debut, fin),
        "aeeh": {}, "sejours": [s for s in referentiel["sejours"] if s["site"] in sites],
        "date_reference": date_reference,
    }


def CalculerPeriode(preset, referentiel, couples, source, debut, fin, date_reference):
    contexte = _contexte(preset, referentiel, couples, source, debut, fin, date_reference)
    consommations = source.Consommations(list(couples), debut, fin)
    contexte["aeeh"] = source.AEEH({c["IDindividu"] for c in consommations})
    resultat = Calcul.Calculateur(contexte).Calculer(consommations, debut, fin)
    resultat["jours_ouverts"] = len({date for a, u, g, date in contexte["ouvertures"]})
    resultat["periode"] = (debut, fin)
    return resultat


def _prevision_manuelle(valeurs, mode):
    prevision = {}
    for cle, libelle in Calcul.INDICATEURS:
        if cle in Calcul.NON_APPLICABLES[mode]:
            prevision[cle] = None
        elif cle in INDICATEURS_PREVISION_MANUELLE:
            if valeurs is None or cle not in valeurs:
                raise DeclarationImpossible("Prévision manuelle manquante : %s" % libelle)
            texte = str(valeurs[cle]).replace(",", ".").strip()
            try:
                heures = float(texte)
            except ValueError:
                raise DeclarationImpossible("Prévision manuelle invalide : %s" % libelle)
            if not math.isfinite(heures) or heures < 0:
                raise DeclarationImpossible("Prévision manuelle invalide : %s" % libelle)
            prevision[cle] = int(round(heures * 3600))
        else:
            prevision[cle] = "non_qualifie"
    for total, part in (("heures_realisees", "heures_realisees_aeeh"), ("heures_facturees", "heures_facturees_aeeh")):
        if isinstance(prevision.get(part), int) and isinstance(prevision.get(total), int) and prevision[part] > prevision[total]:
            raise DeclarationImpossible("Le sous-total AEEH prévisionnel dépasse le total")
    return prevision


def Executer(preset, referentiel, annee, phase, methode=METHODE_N1, valeurs_manuelles=None, source=None,
             date_reference=None, maintenant=None):
    """Calcule une déclaration. Le preset fourni n'est jamais modifié."""
    source = source or Source()
    date_reference = date_reference or datetime.date.today()
    maintenant = maintenant or datetime.datetime.now()
    instantane_preset = Presets.ValiderPreset(preset)
    referentiel = Referentiel.ValiderReferentiel(referentiel, source.Groupes())
    preset, couples, motifs = Perimetre(instantane_preset, referentiel)
    debut_r, fin_r, debut_p, fin_p = Periodes(annee, phase)
    try:
        convention = Conventions.ResoudreConventionAnnee(preset["equipement"], preset["mode"], annee)
    except Conventions.ConventionNonApplicable as erreur:
        convention = None
        motifs.append(str(erreur))

    if debut_r and fin_r >= date_reference:
        motifs.append("période réalisée non terminée (%s au %s, calcul du %s) : chiffres provisoires"
                      % (debut_r.strftime("%d/%m/%Y"), fin_r.strftime("%d/%m/%Y"), date_reference.strftime("%d/%m/%Y")))
    realise = CalculerPeriode(preset, referentiel, couples, source, debut_r, fin_r, date_reference) if debut_r else None
    historique_n1 = None
    prevision = None
    jours_prevision = 0
    if debut_p:
        jours_prevision = len({d for a, u, g, d in source.Ouvertures(list(couples), debut_p, fin_p)})
        if methode == METHODE_MANUELLE:
            prevision = _prevision_manuelle(valeurs_manuelles, preset["mode"])
        elif methode == METHODE_N1:
            if jours_prevision == 0:
                raise DeclarationImpossible("Aucun jour d'ouverture programmé sur la période à prévoir : "
                                            "compléter le calendrier d'ouverture ou saisir le prévisionnel")
            debut_n1, fin_n1 = _annee_precedente(debut_p), _annee_precedente(fin_p)
            historique_n1 = CalculerPeriode(preset, referentiel, couples, source, debut_n1, fin_n1, date_reference)
            if historique_n1["bloquant"]:
                raise DeclarationImpossible("L'historique N-1 comporte des anomalies bloquantes : "
                                            "les corriger ou saisir le prévisionnel manuellement")
            if historique_n1["jours_ouverts"] == 0:
                raise DeclarationImpossible("Aucun jour d'ouverture sur la même période de N-1 : saisir le prévisionnel")
            prevision = {}
            for cle, valeur in historique_n1["indicateurs"].items():
                prevision[cle] = None if valeur is None else int(round(UTILS_AFAS.EstimerPeriode(
                    UTILS_AFAS.METHODE_N1_AJUSTE, [{"heures": valeur, "jours_ouverts": historique_n1["jours_ouverts"]}],
                    jours_prevision)))
        else:
            raise DeclarationImpossible("Méthode de prévision inconnue")

    lignes = []
    for cle, libelle in Calcul.INDICATEURS:
        valeur_r = realise["indicateurs"][cle] if realise else (None if cle in Calcul.NON_APPLICABLES[preset["mode"]] else 0)
        valeur_p = prevision[cle] if prevision else (None if cle in Calcul.NON_APPLICABLES[preset["mode"]] else 0)
        if valeur_r is None or valeur_p is None:
            total = None
        elif valeur_p == "non_qualifie":
            total = "non_qualifie"
        else:
            total = valeur_r + valeur_p
        lignes.append({"cle": cle, "libelle": libelle, "realise": valeur_r, "prevision": valeur_p, "total": total})

    anomalies = (realise["anomalies"] if realise else [])
    bloquant = any(a["bloquante"] for a in anomalies)
    validable = not bloquant and not motifs and convention is not None
    rapport = {
        "format": FORMAT_RAPPORT,
        "date_execution": maintenant.isoformat(timespec="seconds"),
        "annee": annee, "phase": phase, "libelle_phase": LIBELLES_PHASES[phase],
        "periode_realise": [str(debut_r), str(fin_r)] if debut_r else None,
        "periode_prevision": [str(debut_p), str(fin_p)] if debut_p else None,
        "methode_prevision": methode if debut_p else None,
        "jours_ouverts_realise": realise["jours_ouverts"] if realise else 0,
        "jours_ouverts_prevision": jours_prevision,
        "jours_ouverts_n1": historique_n1["jours_ouverts"] if historique_n1 else None,
        "convention": convention, "version_regles": Conventions.VERSION_REGLES,
        "preset": instantane_preset, "empreinte_preset": Presets.Empreinte(instantane_preset),
        "sites": {site: referentiel["sites"][site] for site in instantane_preset["sites"]},
        "indicateurs": lignes, "anomalies": anomalies, "bloquant": bloquant,
        "validable": validable, "motifs_non_validable": motifs + (["anomalies bloquantes à corriger"] if bloquant else []),
        "jours": realise["jours"] if realise else [], "lignes": realise["lignes"] if realise else [],
    }
    rapport["empreinte"] = Presets.Empreinte({k: v for k, v in rapport.items() if k not in ("jours", "lignes", "empreinte")})
    return rapport


# --------------------------------------------------------------------------
# Présentation, historique et exports
# --------------------------------------------------------------------------

def Heures(valeur):
    """Valeur affichable : heures décimales françaises ou mention explicite."""
    if valeur is None:
        return "non applicable"
    if valeur == "non_qualifie":
        return "non qualifié"
    return ("%.2f" % (valeur / 3600.0)).replace(".", ",")


def ResumeHistorique(rapport):
    """Résumé conservable (sans le détail par consommation), borné en taille."""
    resume = {k: v for k, v in rapport.items() if k not in ("jours", "lignes")}
    anomalies = [a for a in rapport["anomalies"] if a["bloquante"]]
    resume["nombre_anomalies"] = len(rapport["anomalies"])
    resume["anomalies"] = anomalies
    while len(json.dumps(resume, ensure_ascii=False, default=str)) > TAILLE_MAX_HISTORIQUE and resume["anomalies"]:
        resume["anomalies"] = resume["anomalies"][:len(resume["anomalies"]) // 2]
        resume["anomalies_tronquees"] = True
    resume = json.loads(json.dumps(resume, ensure_ascii=False, default=str))
    resume["empreinte_archive"] = Presets.Empreinte(resume)
    return resume


def EnregistrerHistorique(rapport):
    """Archive la déclaration produite ; indépendant du preset (qui peut ensuite évoluer)."""
    resume = ResumeHistorique(rapport)
    libelle = "%s — %s %d — %s" % (rapport["preset"]["nom"], rapport["libelle_phase"], rapport["annee"], rapport["date_execution"])
    IDprofil = Referentiel.CreerProfil(CATEGORIE_HISTORIQUE, libelle[:400])
    Referentiel.EcrireJSONProfil(IDprofil, NOM_PARAMETRE_HISTORIQUE, resume)
    return IDprofil


def ListerHistorique():
    return Referentiel.ProfilsCategorie(CATEGORIE_HISTORIQUE)


def ChargerHistorique(IDprofil):
    resume = Referentiel.LireJSONProfil(IDprofil, NOM_PARAMETRE_HISTORIQUE)
    if not isinstance(resume, dict) or resume.get("format") != FORMAT_RAPPORT:
        raise ValueError("Déclaration archivée illisible")
    attendue = resume.pop("empreinte_archive", None)
    resume["integrite"] = attendue is not None and attendue == Presets.Empreinte(resume)
    return resume


def _ecrire_csv(chemin, lignes):
    with open(chemin, "w", encoding="utf-8-sig", newline="") as fichier:
        writer = csv.writer(fichier, delimiter=";")
        writer.writerows(lignes)


def ExporterControle(dossier, rapport, prefixe):
    """Export de contrôle toujours autorisé : détail et anomalies."""
    os.makedirs(dossier, exist_ok=True)
    chemins = {}
    chemins["detail"] = os.path.join(dossier, prefixe + "_detail.csv")
    entete = ["Date", "IDindividu", "Individu", "IDconso", "IDactivite", "IDgroupe", "Site", "IDunite", "Unité",
              "Catégorie", "Statut conso", "Mode du jour", "Traitement", "Motif"]
    _ecrire_csv(chemins["detail"], [entete] + [
        [l["date"], l["IDindividu"], l["individu"], l["IDconso"], l["IDactivite"], l["IDgroupe"], l["site"], l["IDunite"],
         l["unite"], l["categorie"], l["etat"], l["mode_jour"], l["statut"], l["motif"]] for l in rapport["lignes"]])
    chemins["jours"] = os.path.join(dossier, prefixe + "_jours.csv")
    cles = [cle for cle, libelle in Calcul.INDICATEURS if cle != "garderie_total"]
    _ecrire_csv(chemins["jours"], [["Date", "IDindividu", "AEEH", "Amplitude"] + [libelle for cle, libelle in Calcul.INDICATEURS if cle != "garderie_total"]] + [
        [j["date"], j["IDindividu"], "oui" if j["aeeh"] else "non", Heures(j["amplitude"]) if j["amplitude"] else ""]
        + [Heures(j.get(cle, 0)) for cle in cles] for j in rapport["jours"]])
    chemins["anomalies"] = os.path.join(dossier, prefixe + "_anomalies.csv")
    _ecrire_csv(chemins["anomalies"], [["Date", "IDindividu", "Individu", "IDconso", "IDactivite", "IDgroupe", "Site",
                                        "IDunite", "Unité", "Nature", "Conséquence", "Bloquante"]] + [
        [a["date"], a["IDindividu"], a["individu"], a["IDconso"], a["IDactivite"], a["IDgroupe"], a["site"], a["IDunite"],
         a["unite"], a["nature"], a["consequence"], "oui" if a["bloquante"] else "non"] for a in rapport["anomalies"]])
    return chemins


def ExporterDeclaration(dossier, rapport, prefixe):
    """Synthèse déclarative + instantané + contrôle. Refusé si non validable."""
    if not rapport["validable"]:
        raise DeclarationImpossible("Déclaration non validable : " + " ; ".join(rapport["motifs_non_validable"]))
    chemins = ExporterControle(dossier, rapport, prefixe)
    chemins["synthese"] = os.path.join(dossier, prefixe + "_synthese.csv")
    preset = rapport["preset"]
    entete = [
        ["Déclaration AFAS ALSH — données d'activité (aucune transmission automatique à la Caf)"],
        ["Équipement", Conventions.EQUIPEMENTS[preset["equipement"]]["libelle"]],
        ["Mode", preset["mode"]], ["Sites", ", ".join(preset["sites"])],
        ["Année", rapport["annee"]], ["Phase", rapport["libelle_phase"]],
        ["Période réalisée", " au ".join(rapport["periode_realise"]) if rapport["periode_realise"] else "aucune"],
        ["Période prévue", " au ".join(rapport["periode_prevision"]) if rapport["periode_prevision"] else "aucune"],
        ["Méthode de prévision", rapport["methode_prevision"] or ""],
        ["Convention", rapport["convention"]], ["Version des règles", rapport["version_regles"]],
        ["Preset", "%s (id %s, version %d)" % (preset["nom"], preset["preset_id"], preset["version"])],
        ["Empreinte du preset", rapport["empreinte_preset"]], ["Empreinte de la déclaration", rapport["empreinte"]],
        ["Date d'exécution", rapport["date_execution"]],
        ["Statuts retenus — réalisé", ", ".join(preset["etats_realise"])],
        ["Statuts retenus — facturé", ", ".join(preset["etats_facture"])],
        [],
        ["Indicateur (heures)", "Réalisé", "Prévision", "Total"],
    ]
    _ecrire_csv(chemins["synthese"], entete + [[l["libelle"], Heures(l["realise"]), Heures(l["prevision"]), Heures(l["total"])]
                                               for l in rapport["indicateurs"]])
    chemins["instantane"] = os.path.join(dossier, prefixe + "_instantane.json")
    with open(chemins["instantane"], "w", encoding="utf-8") as fichier:
        json.dump(ResumeHistorique(rapport), fichier, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    return chemins
