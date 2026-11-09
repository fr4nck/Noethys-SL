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
FORMAT_RAPPORT = 2
FORMATS_RAPPORT_LISIBLES = (1, 2)
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

    def Regularisations(self, IDactivites, IDindividus, IDfamilles, debut, fin):
        from Utils import UTILS_AFAS2_Donnees
        return UTILS_AFAS2_Donnees.ChargerRegularisations(IDactivites, IDindividus, IDfamilles, debut, fin)

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
        unites[IDunite] = dict(unites_noethys[IDunite], categorie=categorie,
                               plage_declaree=preset["plages_declarees"].get(cle))
    sites = set(couples.values())
    return {
        "mode": preset["mode"], "equipement": preset["equipement"], "couples": couples, "unites": unites,
        "etats_realise": preset["etats_realise"], "etats_facture": preset["etats_facture"],
        "options": dict(preset["choix_conventionnels"]),
        "calendrier": source.Calendrier(debut, fin),
        "samedis_avec_ecole": Calendrier.SamedisAvecEcole(referentiel["samedis_avec_ecole"]),
        "ouvertures": source.Ouvertures(list(couples), debut, fin),
        "aeeh": {}, "sejours": [s for s in referentiel["sejours"] if s["site"] in sites],
        "regularisations": [], "regularisations_qualifiees": referentiel["regularisations"],
        "date_reference": date_reference,
    }


# Une régularisation est souvent émise après la période qu'elle corrige :
# elles sont recherchées jusqu'à trois mois après la fin de la période.
DELAI_REGULARISATIONS = datetime.timedelta(days=92)


def JoursOuvertsEligibles(ouvertures, mode, calendrier, samedis_avec_ecole,
                          unites=None, couples=None, sejours=None):
    """Jours ouverts du mode déclaré, sans dates scolaires en extrascolaire."""
    valides, inconnus = set(), set()
    for activite, IDunite, groupe, jour in ouvertures:
        classe = Calendrier.ModeDate(jour, calendrier, samedis_avec_ecole)
        if classe in (Calendrier.INCONNU, Calendrier.SAMEDI_A_QUALIFIER):
            inconnus.add(jour)
            continue
        if mode == Conventions.PERISCOLAIRE:
            if classe == Calendrier.PERISCOLAIRE:
                valides.add(jour)
            continue
        if mode != Conventions.EXTRASCOLAIRE:
            raise DeclarationImpossible("Mode AFAS inconnu")
        unite = (unites or {}).get(IDunite)
        categorie = unite.get("categorie") if isinstance(unite, dict) else unite
        if unites is None:
            # Compatibilité de l'ancien appel : filtrage par mode de date.
            categorie = "accueil"
        if classe == Calendrier.EXTRASCOLAIRE and categorie in Calcul.CATEGORIES_OUVERTURE:
            valides.add(jour)
        elif categorie == "sejour" and classe in (Calendrier.EXTRASCOLAIRE, Calendrier.DIMANCHE):
            site = (couples or {}).get((activite, groupe))
            if any(sejour["site"] == site
                   and str(sejour["date_debut"])[:10] <= str(jour)[:10] <= str(sejour["date_fin"])[:10]
                   for sejour in (sejours or ())):
                valides.add(jour)
    if inconnus:
        raise DeclarationImpossible(
            "Calendrier AFAS non qualifié pour %d jour(s) d'ouverture, dont %s"
            % (len(inconnus), min(inconnus)))
    return valides


def CalculerPeriode(preset, referentiel, couples, source, debut, fin, date_reference):
    contexte = _contexte(preset, referentiel, couples, source, debut, fin, date_reference)
    consommations = source.Consommations(list(couples), debut, fin)
    contexte["aeeh"] = source.AEEH({c["IDindividu"] for c in consommations})
    if preset["mode"] == Conventions.EXTRASCOLAIRE:
        contexte["regularisations"] = source.Regularisations(
            {a for a, g in couples}, {c["IDindividu"] for c in consommations},
            {c.get("IDfamille") for c in consommations}, debut, fin + DELAI_REGULARISATIONS)
    resultat = Calcul.Calculateur(contexte).Calculer(consommations, debut, fin)
    resultat["jours_ouverts"] = len(JoursOuvertsEligibles(
        contexte["ouvertures"], preset["mode"], contexte["calendrier"],
        contexte["samedis_avec_ecole"], contexte["unites"], couples, contexte["sejours"]))
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
    base_prevision = None
    jours_prevision = 0
    if debut_p:
        ouvertures_prevision = source.Ouvertures(list(couples), debut_p, fin_p)
        unites_prevision = {int(cle): categorie for cle, categorie in preset["unites"].items()}
        jours_prevision = len(JoursOuvertsEligibles(
            ouvertures_prevision, preset["mode"],
            source.Calendrier(debut_p, fin_p),
            Calendrier.SamedisAvecEcole(referentiel["samedis_avec_ecole"]),
            unites_prevision, couples, referentiel["sejours"]))
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
            # Justification reproductible de la projection. Ne la confondre
            # ni avec les réservations futures ni avec le bilan historique
            # d'une autre période/paramétrage.
            base_prevision = {
                "methode": METHODE_N1,
                "periode_reference": [str(debut_n1), str(fin_n1)],
                "periode_cible": [str(debut_p), str(fin_p)],
                "jours_ouverts_reference": historique_n1["jours_ouverts"],
                "jours_ouverts_cible": jours_prevision,
                "heures_reference": dict(historique_n1["indicateurs"]),
                "heures_projetees": dict(prevision),
            }
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
        lignes.append({"cle": cle, "libelle": libelle, "nature": Calcul.NATURES_INDICATEURS[cle],
                       "realise": valeur_r, "prevision": valeur_p, "total": total})
    sejours = [l for l in lignes if l["cle"] == "heures_sejours"][0]
    if any(isinstance(sejours[champ], int) and sejours[champ] > 0 for champ in ("realise", "prevision")) \
            and not Conventions.RUBRIQUE_SEJOURS_CONFIRMEE:
        motifs.append("heures de séjours intégrées aux actes : rubrique AFAS des séjours non confirmée par la Caf")

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
        "base_prevision": base_prevision,
        "convention": convention, "version_regles": Conventions.VERSION_REGLES,
        "preset": instantane_preset, "empreinte_preset": Presets.Empreinte(instantane_preset),
        "sites": {site: referentiel["sites"][site] for site in instantane_preset["sites"]},
        "justificatifs": {site: referentiel["justificatifs"][site] for site in instantane_preset["sites"]
                          if site in referentiel["justificatifs"]},
        "samedis_avec_ecole": {scolaire: dates for scolaire, dates in referentiel["samedis_avec_ecole"].items()
                               if scolaire in (str(annee - 1), str(annee))},
        "regularisations_qualifiees": referentiel["regularisations"],
        "indicateurs": lignes, "anomalies": anomalies, "bloquant": bloquant,
        "validable": validable, "motifs_non_validable": motifs + (["anomalies bloquantes à corriger"] if bloquant else []),
        "jours": realise["jours"] if realise else [], "lignes": realise["lignes"] if realise else [],
    }
    rapport["empreinte"] = Presets.Empreinte({k: v for k, v in rapport.items() if k not in ("jours", "lignes", "empreinte")})
    return rapport




def RealiseSeptembreSansPrevision(preset, referentiel, annee, source=None,
                                 date_reference=None):
    """Recupere le realise au 30/09 si la prevision N-1 n'est pas calculable.

    Rapport strictement de controle, non validable. La prevision reste
    inconnue ; les heures du realise ne sont jamais remplacees par zero.
    """
    source = source or Source()
    referentiel = Referentiel.ValiderReferentiel(referentiel, source.Groupes())
    preset, couples, motifs = Perimetre(preset, referentiel)
    debut_r, fin_r, _, _ = Periodes(annee, UTILS_AFAS.PHASE_ACTUALISATION_SEPTEMBRE)
    resultat = CalculerPeriode(preset, referentiel, couples, source, debut_r, fin_r,
                              date_reference or datetime.date.today())
    return {
        "validable": False,
        "motifs_non_validable": motifs + ["Prévision du dernier trimestre non établie"],
        "indicateurs": [
            {"cle": cle, "libelle": libelle, "realise": resultat["indicateurs"][cle],
             "prevision": "non_qualifie", "total": "non_qualifie"}
            for cle, libelle in Calcul.INDICATEURS
        ],
        "jours_ouverts_realise": resultat["jours_ouverts"],
        "anomalies": resultat["anomalies"],
        "jours": resultat["jours"],
        "lignes": resultat["lignes"],
    }


def CampagneSeptembre(annee, referentiel, presets, source=None, date_reference=None):
    """Calcule plusieurs dossiers AFAS avec isolation des erreurs par dossier.

    Utilise la même méthode N-1 que le calcul individuel, sans recopier ni
    inventer de prévision. Les déclarations non validables restent visibles.
    Aucune écriture dans Noethys, ni transmission à la Caf.
    """
    if type(annee) is not int or not 2000 <= annee <= 2100:
        raise DeclarationImpossible("Année de campagne invalide")
    if not isinstance(presets, (list, tuple)) or not presets:
        raise DeclarationImpossible("Aucun profil AFAS pour la campagne de septembre")
    source = source or Source()
    lignes = []
    vus = set()
    for preset in presets:
        candidat = Presets.ValiderPreset(preset)
        if candidat["preset_id"] in vus:
            raise DeclarationImpossible("Profil répété dans la campagne : %s" % candidat["nom"])
        vus.add(candidat["preset_id"])
        try:
            rapport = Executer(
                candidat, referentiel, annee,
                UTILS_AFAS.PHASE_ACTUALISATION_SEPTEMBRE,
                methode=METHODE_N1, source=source, date_reference=date_reference)
            motif = " ; ".join(rapport["motifs_non_validable"])
            etat = "VALIDABLE" if rapport["validable"] else "A_CORRIGER"
        except (ValueError, Calendrier.CalendrierIncomplet) as erreur:
            motif = str(erreur)
            rapport, etat = None, "CALCUL_IMPOSSIBLE"
            # Ne pas perdre le realise annuel au seul motif que les jours
            # de prevision ou l'historique N-1 ne sont pas qualifies.
            if any(marqueur in motif.lower()
                   for marqueur in ("prévision", "n-1", "jour d'ouverture")):
                try:
                    rapport = RealiseSeptembreSansPrevision(
                        candidat, referentiel, annee, source=source,
                        date_reference=date_reference)
                    etat = "PREVISION_A_COMPLETER"
                except (ValueError, Calendrier.CalendrierIncomplet) as detail:
                    motif += " ; réalisé indisponible : " + str(detail)
        lignes.append({"nom": candidat["nom"], "equipement": candidat["equipement"],
                       "mode": candidat["mode"], "etat": etat, "motif": motif,
                       "rapport": rapport})
    return lignes



def CompterJourneesAdos(consommations, unites):
    """Inventaire anonymise des journees facturees Club Ados, sans heures CAF.

    Unites Noethys Journee=2 demi-journees, Matin/Apres-midi=1 chacune.
    Au maximum une journee par enfant et date ; repas/garderie exclus de
    ce COMPTEUR DE JOURNEES (pas des factures). Tous statuts admis si
    la facture est valide, y compris absences justifiees.
    """
    resultat = {}
    non_classees = 0
    for c in consommations:
        if c.get("IDindividu") is None or c.get("date") is None:
            continue
        etat_facture = Referentiel.NomNormalise(c.get("facture_etat") or "")
        if (c.get("IDprestation") is None or c.get("IDfacture") is None
                or etat_facture.startswith("annul") or etat_facture == "avoir"
                or (c.get("prestation_montant") is not None
                    and c["prestation_montant"] < 0)):
            continue
        unite = unites.get(c.get("IDunite"), {})
        nom = Referentiel.NomNormalise(unite.get("nom", ""))
        cle = (c["IDindividu"], str(c["date"])[:10])
        if nom in ("journee", "journee entiere", "journee complete"):
            categorie = "journee"
        elif nom in ("matin", "matinee", "demi-journee matin"):
            categorie = "matin"
        elif nom in ("apres-midi", "apres midi", "apresmidi", "demi-journee apres-midi"):
            categorie = "apres_midi"
        else:
            # Repas/garderie ne créent pas une seconde journée facturée.
            if nom not in ("repas", "garderie du matin", "garderie du soir",
                           "animation", "sortie", "majoration garderie"):
                non_classees += 1
            continue
        resultat.setdefault(cle, set()).add(categorie)
    demies = sum((2 if "journee" in types else
                  int("matin" in types) + int("apres_midi" in types))
                 for types in resultat.values())
    chevauchements = sum(
        "journee" in types and len(types) > 1 for types in resultat.values())
    return {
        "demi_journees_facturees": demies,
        "jours_factures": demies / 2.0,
        "enfants_jours": len(resultat),
        "chevauchements": chevauchements,
        "unites_non_classees": non_classees,
    }


def DossierAdosEnAttente(source=None, annee=2026):
    """Cinquieme dossier CAF. Le comptage facturé ne valide pas la convention."""
    donnees = None
    motif = ("Club Ados : convention et règles CAF spécifiques non qualifiées. "
             "Le mini-camp de l'activité 74 n'est pas intégré.")
    if source is not None:
        try:
            groupes = source.Groupes()
            couples = [(68, groupe) for groupe, (activite, nom) in groupes.items()
                       if activite == 68]
            if couples:
                consos = source.Consommations(
                    couples, datetime.date(annee, 1, 1),
                    datetime.date(annee, 9, 30))
                unites = source.Unites([68])
                donnees = CompterJourneesAdos(consos, unites)
                if donnees["unites_non_classees"]:
                    motif += (" %d ligne(s) facturée(s) avec unité non reconnue."
                              % donnees["unites_non_classees"])
                if donnees["chevauchements"]:
                    motif += (" %d chevauchement(s) journée/demi-journée plafonné(s)."
                              % donnees["chevauchements"])
            else:
                motif += " Aucun groupe de l'activité Noethys 68 trouvé."
        except (ValueError, KeyError, TypeError) as erreur:
            motif += " Inventaire impossible : %s" % erreur
    return {
        "nom": "ACC ADOS ASS BAIS",
        "equipement": Conventions.EQUIPEMENT_BAIS,
        "mode": "ados",
        "etat": "CONVENTION_A_QUALIFIER",
        "motif": motif,
        "rapport": None,
        "controle_ados": donnees,
    }


BUDGET_INITIAL_2026_AG = (
    ("CHARGES", "60", "Achats", 46195),
    ("CHARGES", "61", "Services extérieurs", 4440),
    ("CHARGES", "62", "Autres services extérieurs", 8532),
    ("CHARGES", "64", "Charges de personnel", 364765),
    ("PRODUITS", "70", "Produits des services", 290048),
    ("PRODUITS", "74", "Subventions d'exploitation", 125342),
    ("PRODUITS", "75", "Autres produits de gestion", 5160),
    ("PRODUITS", "76", "Produits financiers", 1382),
    ("PRODUITS", "79", "Transferts de charges (BP détaillé)", 2000),
)


def ExporterReferenceBudget2026(dossier, prefixe, campagne):
    """Budget initial AG 2026, sans imputation fictive aux cinq dossiers.

    Chaque ligne dossier laisse volontairement le realise jusqu'a septembre
    et la prevision du quatrieme trimestre vides, a completer avec la
    comptabilite analytique. Les colonnes initiales sont associatives.
    """
    charges = sum(valeur for nature, pcg, nom, valeur in BUDGET_INITIAL_2026_AG
                  if nature == "CHARGES")
    produits = sum(valeur for nature, pcg, nom, valeur in BUDGET_INITIAL_2026_AG
                   if nature == "PRODUITS")
    if charges != 423932 or produits != charges:
        raise DeclarationImpossible("Budget AG 2026 incohérent")
    lignes = [[
        "Périmètre", "Dossier", "Nature", "Compte",
        "Poste", "Budget initial 2026 EUR",
        "Réel janvier-septembre EUR", "Prévision octobre-décembre EUR",
        "Source", "Statut",
    ]]
    source = "Rapport financier et d'activité 2025 ; AG du 30/03/2026 ; budget détaillé 2026 page 33"
    for nature, pcg, nom, montant in BUDGET_INITIAL_2026_AG:
        lignes.append(["ASSOCIATION", "", nature, pcg, nom, montant, "", "",
                       source, "GLOBAL NON VENTILÉ"])
    lignes.extend([
        ["ASSOCIATION", "", "CHARGES", "TOTAL", "Total charges initial", charges,
         "", "", source, "GLOBAL NON VENTILÉ"],
        ["ASSOCIATION", "", "PRODUITS", "TOTAL", "Total produits initial", produits,
         "", "", source, "GLOBAL NON VENTILÉ"],
    ])
    for item in campagne:
        for nature in ("CHARGES", "PRODUITS"):
            lignes.append(["DOSSIER CAF", item["nom"], nature, "TOTAL",
                           "Total à renseigner par dossier", "",
                           "", "", "Comptabilité analytique 2026",
                           "À COMPLÉTER - ne pas reprendre le budget associatif global"])
    destination = os.path.join(dossier, prefixe + "_BUDGET_INITIAL_AG_2026.csv")
    _ecrire_csv(destination, lignes)
    return destination


def ExporterCampagneSeptembre(dossier, annee, campagne):
    """Exports de CONTROLE uniquement, par dossier, plus tableau récapitulatif.

    La production d'un contrôle ne signifie ni validation CAF ni dépôt.
    Chaque export porte le nom de son équipement et de son mode.
    """
    if not isinstance(campagne, list) or not campagne:
        raise DeclarationImpossible("Campagne vide")
    os.makedirs(dossier, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefixe = "AFAS_%d_SEPT_CONTROLE_%s" % (annee, stamp)
    tableaux = [[
        "Dossier", "Équipement", "Mode", "Résultat", "Heures réalisées",
        "Heures facturées", "Jours ouverts", "Anomalies", "Motif",
        "Fichier anomalies", "Journées facturées Ados (contrôle)",
    ]]
    for index, element in enumerate(campagne, 1):
        rapport = element["rapport"]
        heures = {l["cle"]: l for l in rapport["indicateurs"]} if rapport else {}
        chemins = {}
        if rapport is not None:
            nom = "%s_%02d_%s_%s" % (
                prefixe, index, element["equipement"], element["mode"])
            chemins = ExporterControle(dossier, rapport, nom)
        tableaux.append([
            element["nom"], element["equipement"], element["mode"],
            element["etat"],
            Heures(heures["heures_realisees"]["realise"]) if "heures_realisees" in heures else "",
            Heures(heures["heures_facturees"]["realise"]) if "heures_facturees" in heures else "",
            rapport["jours_ouverts_realise"] if rapport else "",
            len(rapport["anomalies"]) if rapport else "",
            element["motif"],
            os.path.basename(chemins.get("anomalies", "")),
            (element.get("controle_ados") or {}).get("jours_factures", ""),
        ])
    cible = os.path.join(dossier, prefixe + "_RECAP.csv")
    _ecrire_csv(cible, tableaux)
    if annee == 2026:
        ExporterReferenceBudget2026(dossier, prefixe, campagne)
    return cible



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
    if not isinstance(resume, dict) or resume.get("format") not in FORMATS_RAPPORT_LISIBLES:
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
              "Catégorie", "Statut conso", "Mode du jour", "Traitement", "Motif", "IDprestation", "IDfacture"]
    _ecrire_csv(chemins["detail"], [entete] + [
        [l["date"], l["IDindividu"], l["individu"], l["IDconso"], l["IDactivite"], l["IDgroupe"], l["site"], l["IDunite"],
         l["unite"], l["categorie"], l["etat"], l["mode_jour"], l["statut"], l["motif"], l.get("IDprestation") or "",
         l.get("IDfacture") or ""] for l in rapport["lignes"]])
    chemins["jours"] = os.path.join(dossier, prefixe + "_jours.csv")
    cles = [cle for cle, libelle in Calcul.INDICATEURS if cle != "garderie_total"]
    _ecrire_csv(chemins["jours"], [["Date", "IDindividu", "AEEH", "Amplitude", "Plages d'ouverture retenues",
                                    "Justification de la facturation"]
                                   + [libelle for cle, libelle in Calcul.INDICATEURS if cle != "garderie_total"]] + [
        [j["date"], j["IDindividu"], "oui" if j["aeeh"] else "non", Heures(j["amplitude"]) if j["amplitude"] else "",
         j.get("plages_ouverture", ""), j.get("justification_facture", "")]
        + [Heures(j.get(cle, 0)) for cle in cles] for j in rapport["jours"]])
    # Ecarts journaliers tracables pour comparer sans repas le controle
    # historique aux actes conventionnels CAF. Aucun de ces controles ne
    # modifie le champ realise ni une consommation.
    chemins["ecarts_presence"] = os.path.join(dossier, prefixe + "_ECARTS_PRESENCE.csv")
    _ecrire_csv(chemins["ecarts_presence"], [[
        "Date", "IDindividu", "Heures physiques", "Heures CAF conventionnelles",
        "Ecart physique - CAF", "Garderie du matin", "Garderie du soir",
        "Observation",
    ]] + [[
        jour["date"], jour["IDindividu"],
        Heures(jour.get("heures_physiques")),
        Heures(jour.get("heures_realisees")),
        Heures(jour.get("heures_physiques", 0) - jour.get("heures_realisees", 0)),
        Heures(jour.get("garderie_matin")),
        Heures(jour.get("garderie_soir")),
        "Contrôler plafonnement à 9 h, plages déclarées et catégories de l'accueil",
    ] for jour in rapport["jours"]])
    base = rapport.get("base_prevision")
    if base:
        chemins["prevision_justification"] = os.path.join(
            dossier, prefixe + "_JUSTIFICATIF_PREVISION.csv")
        base_source = base["heures_reference"]
        base_cible = base["heures_projetees"]
        jours_source = base["jours_ouverts_reference"]
        jours_cible = base["jours_ouverts_cible"]
        _ecrire_csv(chemins["prevision_justification"], [[
            "Indicateur", "Période de référence N-1", "Heures référence N-1",
            "Jours ouverts N-1", "Période projetée", "Jours ouverts projetés",
            "Heures projetées", "Méthode",
        ]] + [[
            libelle, " au ".join(base["periode_reference"]),
            Heures(base_source.get(cle)),
            jours_source, " au ".join(base["periode_cible"]),
            jours_cible, Heures(base_cible.get(cle)),
            "heures N-1 × jours ouverts projetés / jours ouverts N-1",
        ] for cle, libelle in Calcul.INDICATEURS])
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
        ["Base prévision N-1", " au ".join(rapport["base_prevision"]["periode_reference"])
         if rapport.get("base_prevision") else "prévision manuelle ou non applicable"],
        ["Jours d'ouverture N-1", rapport["jours_ouverts_n1"] or ""],
        ["Jours d'ouverture prévus", rapport["jours_ouverts_prevision"] or ""],
        ["Convention", rapport["convention"]], ["Version des règles", rapport["version_regles"]],
        ["Preset", "%s (id %s, version %d)" % (preset["nom"], preset["preset_id"], preset["version"])],
        ["Empreinte du preset", rapport["empreinte_preset"]], ["Empreinte de la déclaration", rapport["empreinte"]],
        ["Date d'exécution", rapport["date_execution"]],
        ["Statuts retenus — réalisé", ", ".join(preset["etats_realise"])],
        ["Statuts retenus — facturé", ", ".join(preset["etats_facture"])],
        ["Complément inclusif", "présence effective brute et arrondi par jour présentés ; aucun n'est retenu "
                                "automatiquement tant que la modalité Caf n'est pas confirmée"],
        [],
        ["Indicateur (heures)", "Nature", "Réalisé", "Prévision", "Total"],
    ]
    _ecrire_csv(chemins["synthese"], entete + [[l["libelle"], l["nature"], Heures(l["realise"]), Heures(l["prevision"]),
                                                Heures(l["total"])] for l in rapport["indicateurs"]])
    chemins["instantane"] = os.path.join(dossier, prefixe + "_instantane.json")
    with open(chemins["instantane"], "w", encoding="utf-8") as fichier:
        json.dump(ResumeHistorique(rapport), fichier, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    return chemins
