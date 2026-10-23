"""AFAS V2: profil metier permanent, independant de l'annee et de la phase.

Prototype sans wxPython ni DB. Aucun calcul CAF. Les dates d'execution
appartiennent exclusivement a la demande de calcul et a sa trace.
"""
import copy
import json
from datetime import datetime, timezone

ACTIVITIES = ("ALSH", "ALSH Ados")
MODES = ("Périscolaire", "Extrascolaire")
PHASES = ("previsionnel", "actualisation_juin", "actualisation_septembre", "reel")
STATES = ("Pointage en attente", "Présent", "Absence justifiée", "Absence injustifiée")
FORBIDDEN_PROFILE_FIELDS = frozenset(("annee", "année", "year", "phase", "phase_actualisation",
                                      "date_debut", "date_fin", "date_situation"))
REQUIRED = frozenset(("profile_id", "name", "activity", "mode", "sites",
                      "included_units", "excluded_units", "garderie_units",
                      "realised_states", "caf_billed_states", "period_criteria",
                      "rules", "version"))

class PresetError(ValueError):
    pass

def _unique(values, field):
    if not isinstance(values, list):
        raise PresetError(field + ": liste requise")
    try:
        if len(values) != len(set(values)):
            raise PresetError(field + ": doublons")
    except TypeError:
        raise PresetError(field + ": elements non hachables")
    return True

def validate_preset(profile):
    if not isinstance(profile, dict):
        raise PresetError("Preset invalide")
    missing = REQUIRED - set(profile)
    if missing:
        raise PresetError("Champs manquants: " + ", ".join(sorted(missing)))
    forbidden = FORBIDDEN_PROFILE_FIELDS & set(profile)
    if forbidden:
        raise PresetError("Annee/phase/date interdites dans le preset: " + ", ".join(sorted(forbidden)))
    if not isinstance(profile["profile_id"], str) or not profile["profile_id"].strip():
        raise PresetError("Identifiant stable requis")
    if not isinstance(profile["name"], str) or not profile["name"].strip():
        raise PresetError("Nom requis")
    if profile["activity"] not in ACTIVITIES or profile["mode"] not in MODES:
        raise PresetError("Activite ou type d'accueil inconnu")
    for field in ("sites", "included_units", "excluded_units", "garderie_units",
                  "realised_states", "caf_billed_states"):
        _unique(profile[field], field)
    if not profile["sites"]:
        raise PresetError("Aucun site retenu")
    unit_groups = [set(profile[field]) for field in
                   ("included_units", "excluded_units", "garderie_units")]
    if any(unit_groups[i] & unit_groups[j] for i in range(3) for j in range(i+1, 3)):
        raise PresetError("Unites presentes dans plusieurs categories")
    for field in ("realised_states", "caf_billed_states"):
        if any(state not in STATES for state in profile[field]):
            raise PresetError("Etat de consommation inconnu")
    if not isinstance(profile["period_criteria"], dict) or not isinstance(profile["rules"], dict):
        raise PresetError("Criteres de periode et regles attendus sous forme d'objets")
    if type(profile["version"]) is not int or profile["version"] < 1:
        raise PresetError("Version invalide")
    return copy.deepcopy(profile)

def serialize_preset(profile):
    return json.dumps(validate_preset(profile), ensure_ascii=False, sort_keys=True)

def deserialize_preset(payload):
    try:
        return validate_preset(json.loads(payload))
    except (ValueError, TypeError) as exc:
        raise PresetError("Preset JSON invalide: " + str(exc)) from exc

def duplicate_preset(profile, new_id, new_name):
    clone = validate_preset(profile)
    clone["profile_id"] = new_id
    clone["name"] = new_name
    clone["version"] = 1
    return validate_preset(clone)

def calculation_request(profile, year, phase, *, now=None):
    snapshot = validate_preset(profile)
    if type(year) is not int or not 1900 <= year <= 2200:
        raise PresetError("Annee de calcul invalide")
    if phase not in PHASES:
        raise PresetError("Phase de calcul inconnue")
    return {"preset_snapshot": snapshot, "year": year, "phase": phase,
            "created_at": now or datetime.now(timezone.utc).isoformat()}
