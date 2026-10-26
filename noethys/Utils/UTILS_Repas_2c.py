# -*- coding: utf-8 -*-
"""Contrat pur du repas meridien #433, lot 2C-1 (opt-in uniquement).

Les familles reservent une journee ou une demi-journee, jamais une
"presence repas". La plage d'accueil determine la presence midi. La
fourniture du repas est une information independante. Le module ne lit
aucune base et ne calcule ni tarifs, ni prestations, ni heures CAF/AFAS.

Les modeles historiques de UTILS_Repas_regimes ne sont pas modifies.
Les exceptions datees sont fournies par l'appelant : ce module ne les
persiste pas. Aucun schema ni migration implicites.
"""

from collections import defaultdict
from datetime import date, datetime, time
import re

TYPES_REPAS = ("standard", "sans_porc", "vegetarien", "sans_repas_pmsl")
FOURNISSEUR = TYPES_REPAS[:3]
ETATS = frozenset(("reservation", "present", "attente", "refus", "absenti", "absentj"))
MODES = {"prevision": frozenset(("reservation", "present")),
         "realise": frozenset(("present",))}


class Repas2CInvalide(ValueError):
    """Situation non qualifiable sans intervention d'un gestionnaire."""


def _date(valeur):
    if isinstance(valeur, datetime) or not isinstance(valeur, date):
        raise Repas2CInvalide("Date de l'accueil invalide")
    return valeur


def _minute(valeur):
    if isinstance(valeur, time):
        if valeur.tzinfo is not None or valeur.second or valeur.microsecond:
            raise Repas2CInvalide("Horaire non local ou trop precis")
        return valeur.hour * 60 + valeur.minute
    if isinstance(valeur, str) and re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", valeur):
        return int(valeur[:2]) * 60 + int(valeur[3:])
    raise Repas2CInvalide("Horaire HH:MM requis")


def _intervalle(debut, fin):
    debut, fin = _minute(debut), _minute(fin)
    if debut >= fin:
        raise Repas2CInvalide("Plage d'accueil non croissante")
    return debut, fin


def CouvreMidi(plages, midi_debut, midi_fin):
    """Vrai si les plages couvrent tout le service midi, faux si hors midi.

    Toute couverture partielle est bloquee, sans inventer de temps CAF.
    Les plages jointives se rejoignent sans ajouter deux fois le midi.
    """
    m0, m1 = _intervalle(midi_debut, midi_fin)
    intervalles = sorted(_intervalle(a, b) for a, b in plages)
    if not intervalles:
        return False
    fusion = []
    for debut, fin in intervalles:
        if fusion and debut <= fusion[-1][1]:
            fusion[-1] = (fusion[-1][0], max(fusion[-1][1], fin))
        else:
            fusion.append((debut, fin))
    if any(debut <= m0 and fin >= m1 for debut, fin in fusion):
        return True
    if any(debut < m1 and fin > m0 for debut, fin in fusion):
        raise Repas2CInvalide("Couverture partielle du temps meridien : a qualifier")
    return False


def _identifiant(valeur):
    if type(valeur) is int:
        nombre = valeur
    elif isinstance(valeur, str) and valeur.strip().isdigit():
        nombre = int(valeur.strip())
    else:
        raise Repas2CInvalide("Identifiant de question ou de choix invalide")
    if nombre <= 0:
        raise Repas2CInvalide("Identifiant de question ou de choix invalide")
    return nombre


def ConfigurationTypeRepas(question, correspondance, controle="liste_deroulante"):
    """Contrat opt-in : une question individuelle, quatre choix distincts."""
    identifiant = _identifiant(question)
    if controle != "liste_deroulante":
        raise Repas2CInvalide("Question individuelle a choix unique requise")
    if not isinstance(correspondance, dict) or set(correspondance) != set(TYPES_REPAS):
        raise Repas2CInvalide("Quatre choix alimentaires explicites requis")
    ids = {}
    for type_repas in TYPES_REPAS:
        ids[type_repas] = _identifiant(correspondance[type_repas])
    if len(set(ids.values())) != len(ids):
        raise Repas2CInvalide("Choix alimentaires non distincts")
    return identifiant, ids


def _reponse(reponse, choix):
    if reponse is None or reponse == "":
        return None
    if isinstance(reponse, bool):
        raise Repas2CInvalide("Reponse alimentaire invalide")
    elements = [x.strip() for x in str(reponse).split(";") if x.strip()]
    if not elements:
        return None
    if len(set(elements)) != 1:
        raise Repas2CInvalide("Plusieurs types de repas contradictoires")
    inverse = {str(v): k for k, v in choix.items()}
    if elements[0] not in inverse:
        raise Repas2CInvalide("Choix alimentaire inconnu")
    return inverse[elements[0]]


def _exceptions(exceptions):
    """Exception : (IDindividu, date, site, service) -> dict type/auteur/date."""
    resultat = {}
    for cle, valeur in (exceptions or {}).items():
        if not isinstance(cle, tuple) or len(cle) != 4:
            raise Repas2CInvalide("Cle d'exception datee invalide")
        individu, jour, site, service = cle
        if (type(individu) is not int or individu <= 0
                or not isinstance(site, str) or site != site.strip() or not site
                or not isinstance(service, str) or service != service.strip() or not service):
            raise Repas2CInvalide("Perimetre d'exception invalide")
        _date(jour)
        if not isinstance(valeur, dict) or valeur.get("type_repas") not in TYPES_REPAS:
            raise Repas2CInvalide("Type d'exception invalide")
        if not isinstance(valeur.get("auteur"), str) or not valeur["auteur"].strip():
            raise Repas2CInvalide("Auteur technique de l'exception requis")
        try:
            instant = datetime.fromisoformat(valeur["horodatage"])
        except (KeyError, TypeError, ValueError):
            raise Repas2CInvalide("Horodatage d'exception invalide")
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise Repas2CInvalide("Horodatage d'exception avec fuseau requis")
        resultat[cle] = valeur["type_repas"]
    return resultat


def RepartirAccueils(accueils, reponses, correspondance, exceptions=None, mode="prevision"):
    """Repartit les enfants presents midi par (date, site, service).

    Chaque accueil fournit IDindividu, date, site, service, etat,
    heure_debut/heure_fin, midi_debut/midi_fin et repas_pmsl_prevu (bool).
    Ce dernier indique l'offre de la FORMULE d'accueil, sans exiger une
    consommation repas independante. Les resultats sont non nominatifs.
    """
    _, choix = ConfigurationTypeRepas(1, correspondance)
    if mode not in MODES:
        raise Repas2CInvalide("Mode de repartition invalide")
    if not isinstance(reponses, dict):
        raise Repas2CInvalide("Reponses invalides")
    overrides = _exceptions(exceptions)
    groupes = defaultdict(list)
    midi_par_cle = {}
    for accueil in accueils:
        individu = accueil.get("IDindividu")
        jour = _date(accueil.get("date"))
        site, service = accueil.get("site"), accueil.get("service")
        etat = accueil.get("etat")
        if type(individu) is not int or individu <= 0 or not isinstance(site, str) or not site.strip() or not isinstance(service, str) or not service.strip():
            raise Repas2CInvalide("Enfant, site ou service invalide")
        if etat not in ETATS:
            raise Repas2CInvalide("Etat de consommation inconnu")
        if type(accueil.get("repas_pmsl_prevu")) is not bool:
            raise Repas2CInvalide("Offre repas de la formule non qualifiee")
        debut, fin = _intervalle(accueil.get("heure_debut"), accueil.get("heure_fin"))
        midi = _intervalle(accueil.get("midi_debut"), accueil.get("midi_fin"))
        cle = (individu, jour, site.strip(), service.strip())
        if cle in midi_par_cle and midi_par_cle[cle] != midi:
            raise Repas2CInvalide("Plages midi contradictoires sur un service")
        midi_par_cle[cle] = midi
        if etat in MODES[mode]:
            groupes[cle].append((debut, fin, accueil["repas_pmsl_prevu"]))

    repartitions = {}
    sites_individu = {}
    for (individu, jour, site, service), plages in sorted(groupes.items(), key=lambda item: (item[0][1], item[0][2], item[0][3], item[0][0])):
        midi0, midi1 = midi_par_cle[(individu, jour, site, service)]
        if not CouvreMidi([(time(a // 60, a % 60), time(b // 60, b % 60))
                           for a, b, _ in plages],
                          time(midi0 // 60, midi0 % 60), time(midi1 // 60, midi1 % 60)):
            continue
        indic = (individu, jour, service)
        if indic in sites_individu and sites_individu[indic] != site:
            raise Repas2CInvalide("Presence midi multisite ambigue")
        sites_individu[indic] = site
        offres = {prevu for debut, fin, prevu in plages if debut < midi1 and fin > midi0}
        if len(offres) != 1:
            raise Repas2CInvalide("Offres repas contradictoires sur le midi")
        offre = next(iter(offres))
        exception = overrides.get((individu, jour, site, service))
        if exception is not None:
            type_repas, provenance = exception, "exception_datee"
        else:
            type_repas = _reponse(reponses.get(individu), choix)
            provenance = "questionnaire" if type_repas else "defaut_standard" if offre else "a_qualifier"
        if type_repas is None and offre:
            type_repas = "standard"
        if type_repas in FOURNISSEUR and not offre:
            raise Repas2CInvalide("Repas PMSL demande sans offre repas dans la formule")
        cle_sortie = (jour, site, service)
        ligne = repartitions.setdefault(cle_sortie, {
            "presents_midi": 0, "standard": 0, "sans_porc": 0,
            "vegetarien": 0, "repas_apportes": 0, "a_qualifier": 0,
            "repas_fournisseur": 0, "provenances": {"questionnaire": 0,
                "exception_datee": 0, "defaut_standard": 0, "a_qualifier": 0},
        })
        ligne["presents_midi"] += 1
        ligne["provenances"][provenance] += 1
        if type_repas == "sans_repas_pmsl":
            ligne["repas_apportes"] += 1
        elif type_repas is None:
            ligne["a_qualifier"] += 1
        else:
            ligne[type_repas] += 1
            ligne["repas_fournisseur"] += 1
    for ligne in repartitions.values():
        if ligne["repas_fournisseur"] != sum(ligne[x] for x in FOURNISSEUR):
            raise AssertionError("Invariant du fournisseur viole")
        if ligne["presents_midi"] != ligne["repas_fournisseur"] + ligne["repas_apportes"] + ligne["a_qualifier"]:
            raise AssertionError("Invariant des presences viole")
        ligne["complet"] = ligne["a_qualifier"] == 0
    return repartitions
