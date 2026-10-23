"""AFAS V2: contrat autonome sans wx, sans base et sans identifiants inventes."""
from __future__ import annotations
import copy
import json

ALSH = 'ALSH'
ADOS = 'ALSH Ados'
PERI = 'Périscolaire'
EXTRA = 'Extrascolaire'
MATRIX = {
    (ALSH, PERI): ('Bais +6 ans', 'Bais -6 ans', 'Moutiers', 'La Guerche-de-Bretagne'),
    (ALSH, EXTRA): ('Bais +6 ans', 'Bais -6 ans', 'Moutiers', 'La Guerche-de-Bretagne', 'Minicamps 6/8', 'Minicamps 8/10'),
    (ADOS, PERI): ('Bais Club Ados',),
    (ADOS, EXTRA): ('Bais Club Ados', 'Minicamps Ados'),
}

class ConfigurationError(ValueError):
    pass


def validate_catalog(catalog):
    """Catalogue modifiable; exige ID activite + ID groupe explicites, sans correspondance supposee."""
    for key, labels in MATRIX.items():
        if key not in catalog:
            raise ConfigurationError('Combinaison absente: %s' % (key,))
        found = catalog[key]
        if tuple(found) != labels:
            raise ConfigurationError('Matrice incorrecte pour %s' % (key,))
        for label, ids in found.items():
            if not isinstance(ids, dict) or not isinstance(ids.get('IDactivite'), int) or not isinstance(ids.get('IDgroupe'), int):
                raise ConfigurationError('Identifiants non verifies pour '+label)
    return True


def options_for(activity, mode, catalog=None):
    if catalog is None:
        return MATRIX[(activity, mode)]
    return tuple(catalog[(activity, mode)])


def change_context(selection, activity, mode, catalog=None):
    eligible = set(options_for(activity, mode, catalog))
    return [item for item in selection if item in eligible]


def resolve_pairs(activity, mode, selection, catalog):
    allowed = catalog[(activity, mode)]
    if len(selection) != len(set(selection)) or any(label not in allowed for label in selection):
        raise ConfigurationError('Selection invalide ou dupliquee')
    pairs = []
    for label in selection:
        ids = allowed[label]
        if not isinstance(ids.get('IDactivite'), int) or not isinstance(ids.get('IDgroupe'), int):
            raise ConfigurationError('Correspondance non qualifiee: '+label)
        pair = (ids['IDactivite'], ids['IDgroupe'])
        if pair in pairs:
            raise ConfigurationError('Meme couple activite/groupe affecte a deux sites')
        pairs.append(pair)
    return pairs


def validate_units(included, excluded, garderie, states, rules):
    groups = [set(included), set(excluded), set(garderie)]
    if any(groups[i] & groups[j] for i in range(3) for j in range(i+1, 3)):
        raise ConfigurationError('Unite affectee a plusieurs categories')
    if not states or not rules.get('qualified'):
        raise ConfigurationError('Etats ou regles conventionnees non qualifies')
    return True


def save_profile(profile):
    """Serialization pure; stockage durable a raccorder seulement apres qualification."""
    return json.dumps(profile, ensure_ascii=False, sort_keys=True)


def load_profile(payload):
    profile = json.loads(payload)
    required = ('profile_id', 'activity', 'mode', 'selected_sites', 'included_units', 'excluded_units',
                'garderie_units', 'admissible_states', 'rules', 'config_version')
    if any(k not in profile for k in required):
        raise ConfigurationError('Profil incomplet')
    if profile['activity'] not in (ALSH, ADOS) or profile['mode'] not in (PERI, EXTRA):
        raise ConfigurationError('Activite ou mode invalide')
    if set(profile['selected_sites']) - set(options_for(profile['activity'], profile['mode'])):
        raise ConfigurationError('Sites incompatibles')
    return profile


def duplicate_profile(profile, new_id):
    clone = copy.deepcopy(profile)
    clone['profile_id'] = new_id
    return clone
