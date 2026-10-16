# -*- coding: utf-8 -*-
"""Cohérence des choix Connecthys, sans accès DB ni écriture de consommation."""
import unicodedata
from collections import defaultdict

CATEGORY = 'noethys_sl_portail_roles_v1'
ROLES = ('auto', 'normal', 'matin', 'repas', 'apres_midi', 'journee')
ROLE_LABELS = ('Automatique selon le nom', 'Autre choix indépendant', 'Matin',
               'Repas', 'Après-midi', 'Journée complète')
PERIODS = {'matin', 'apres_midi', 'journee'}


def role(unit):
    explicit = unit.get('role_portail', 'auto')
    if explicit in ROLES and explicit != 'auto':
        return explicit
    name = ''.join(c for c in unicodedata.normalize('NFD', (unit.get('nom') or '').casefold())
                   if not unicodedata.combining(c))
    name = ' '.join(name.replace('-', ' ').split())
    # Noms complets seulement : « matin avec repas » n'est pas un repas seul.
    return {'matin': 'matin', 'matinee': 'matin', 'mat': 'matin',
            'apres midi': 'apres_midi', 'apm': 'apres_midi',
            'journee': 'journee', 'journee complete': 'journee',
            'repas': 'repas', 'repas seul': 'repas', 'dejeuner': 'repas', 'midi': 'repas'}.get(name, 'normal')


def prepare(reservations, units):
    """Copie les demandes ; les suppressions restent inchangées.

    Le contexte d'appel est une activité et un individu. IDinscription sépare
    encore les éventuelles inscriptions multiples, en plus de la date.
    """
    additions = defaultdict(list)
    for item in reservations:
        if item['etat'] == 1:
            additions[(item['date'], item['IDinscription'])].append(item)
    excluded, notices = set(), []
    for key, items in additions.items():
        by_role = defaultdict(list)
        for item in items:
            by_role[role(units[item['IDunite']])].append(item)
        if all(by_role[r] for r in PERIODS):
            if len({i['IDunite'] for i in by_role['journee']}) != 1:
                raise ValueError('Plusieurs formules Journée sont sélectionnées : traitement manuel nécessaire.')
            excluded.update(i['IDreservation'] for r in ('matin', 'apres_midi') for i in by_role[r])
            notices.append(key[0])
    kept = [dict(i) for i in reservations if i['IDreservation'] not in excluded]
    for item in kept:
        item['role_portail'] = role(units[item['IDunite']])
    # Conserve l'ordre de chaque famille de choix ; repas après les autres ajouts.
    kept.sort(key=lambda i: (i['date'], i['etat'], i['role_portail'] == 'repas' if i['etat'] == 1 else False))
    return kept, notices


def context(item):
    return item['date'], item['IDinscription']


def linked_meal(item, requests):
    return item['role_portail'] == 'repas' and any(
        r['etat'] == 1 and r['role_portail'] in PERIODS and context(r) == context(item)
        for r in requests)


def protected(case):
    """Ne pas requalifier un repas facturé, pointé ou verrouillé."""
    if case is None:
        return False
    if getattr(case, 'IDfacture', None) is not None:
        return True
    records = case.GetListeConso()
    return any(getattr(c, 'etat', None) in ('present', 'absenti', 'absentj') or
               getattr(c, 'verrouillage', 0) or getattr(c, 'IDfacture', None) is not None
               for c in records)


def current_period_states(units, grid, meal, activity):
    """Accueil déjà demandé avant cette action, pour la même inscription.

    Exclut les unités de repas incluses dans une formule Journée pour ne pas
    créer de dépendance du repas envers lui-même.
    """
    relevant = [u for u in units.values() if u.get('IDactivite') == activity]
    meal_units = {ID for u in relevant if role(u) == 'repas'
                  for ID in u['unites_principales']+u['unites_secondaires']}
    period_units = {ID for u in relevant if role(u) in PERIODS
                    for ID in u['unites_principales']+u['unites_secondaires']} - meal_units
    states = []
    for ID in period_units:
        case = grid.GetCase(ID, meal['date'])
        if case is None:
            continue
        for record in case.GetListeConso():
            inscription = getattr(record, 'IDinscription', None)
            if inscription is None and getattr(record, 'etat', None) == 'attente':
                raise ValueError("Une attente d'accueil sans inscription identifiable nécessite un traitement manuel.")
            if inscription == meal['IDinscription']:
                states.append(getattr(record, 'etat', None))
    return states
