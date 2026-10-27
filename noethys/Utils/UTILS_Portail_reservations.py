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


class ArbitrageManuelRequis(ValueError):
    """Une écriture automatique risquerait une perte ou un doublon."""


def planifier_priorites(reservations, unites, etat_existant, place_disponible):
    """Retourne (réservations retenues, décisions) sans toucher aux sources.

    Les callbacks lisent la grille durable du même enfant / inscription.
    etat_existant(reservation, role) -> etat ou None ; une origine incertaine
    doit lever ArbitrageManuelRequis, et non être assimilée à une case vide.
    place_disponible(reservation) -> bool ; None signifie « non vérifiable ».
    Les annulations ne sont jamais transformées ou effacées ici.
    """
    groupes = defaultdict(list)
    for r in reservations:
        if r['etat'] == 1:
            groupes[(r['date'], r['IDinscription'])].append(r)

    exclus = set()
    decisions = []
    for contexte, demandes in groupes.items():
        par_role = defaultdict(list)
        for demande in demandes:
            par_role[role(unites[demande['IDunite']])].append(demande)
        for nom_role in PERIODS:
            ids = {r['IDunite'] for r in par_role[nom_role]}
            if len(ids) > 1:
                raise ArbitrageManuelRequis(
                    'Plusieurs unités %s pour un même accueil : arbitrage requis.' % nom_role)
            # Les demandes repetees pour une meme unite et un meme accueil
            # ne doivent produire qu'une seule ecriture.
            if len(par_role[nom_role]) > 1:
                exclus.update(r['IDreservation']
                              for r in par_role[nom_role][1:])
                decisions.append(('doublon_demande', contexte))

        if not any(par_role[nom_role] for nom_role in PERIODS):
            continue
        reference = demandes[0]
        jour = par_role['journee']
        moities = par_role['matin'] + par_role['apres_midi']
        etat_jour = etat_existant(reference, 'journee')
        if etat_jour in ('reservation', 'present'):
            # Un cumul deja persiste avec une demi-journee ne doit pas etre
            # camoufle : l'operateur doit arbitrer avant toute reprise.
            if any(etat_existant(reference, demi) is not None
                   for demi in ('matin', 'apres_midi')):
                raise ArbitrageManuelRequis(
                    'Journee et demi-journee deja enregistrees : arbitrage necessaire.')
            # La journee acquise couvre les demandes de demi-journee
            # suivantes, meme si elle provient d'une autre action.
            exclus.update(r['IDreservation'] for r in jour + moities)
            if jour or moities:
                decisions.append(('journee_deja_presente', contexte))
        elif etat_jour not in (None, 'attente'):
            raise ArbitrageManuelRequis(
                'Journée déjà enregistrée dans un état à arbitrer : %s.' % etat_jour)
        elif etat_jour == 'attente' and jour:
            raise ArbitrageManuelRequis(
                'Journée déjà en attente : vérifier avant de la modifier.')
        elif jour:
            disponible = place_disponible(jour[0])
            if disponible is None:
                raise ArbitrageManuelRequis('Disponibilité Journée indéterminée.')
            if disponible:
                # Remplacer des demi-journées déjà enregistrées peut modifier
                # une prestation ou une consommation protégée.
                for nom_role in ('matin', 'apres_midi'):
                    if etat_existant(reference, nom_role) is not None:
                        raise ArbitrageManuelRequis(
                            'Demi-journée existante : conversion en Journée à vérifier manuellement.')
                exclus.update(r['IDreservation'] for r in moities)
                if moities:
                    decisions.append(('journee_prioritaire', contexte))
            else:
                # Sans alternative explicite, la journée conserve son attente.
                if moities:
                    exclus.update(r['IDreservation'] for r in jour)
                    decisions.append(('journee_complete_repli_demi', contexte))
                for demi in moities:
                    if etat_existant(demi, role(unites[demi['IDunite']])) is not None:
                        continue
                    disponible = place_disponible(demi)
                    if disponible is None:
                        raise ArbitrageManuelRequis('Disponibilité demi-journée indéterminée.')
                    if not disponible:
                        exclus.add(demi['IDreservation'])
                        decisions.append(('demi_journee_complete', contexte))
                if moities and all(demi['IDreservation'] in exclus for demi in moities):
                    raise ArbitrageManuelRequis(
                        'Journée et deux demi-journées complètes : arbitrage ou attente nécessaires.')

        # Rejouer une demande ne doit pas ajouter de seconde consommation.
        for demande in demandes:
            if demande['IDreservation'] in exclus:
                continue
            nom_role = role(unites[demande['IDunite']])
            if nom_role not in PERIODS:
                continue
            etat = etat_existant(demande, nom_role)
            if etat in ('reservation', 'present'):
                exclus.add(demande['IDreservation'])
                decisions.append(('deja_enregistre', contexte))
            elif etat == 'attente':
                # Une attente existante peut être requalifiée par les règles
                # normales de disponibilité de la grille, sans nouvelle ligne.
                continue
            elif etat is not None:
                raise ArbitrageManuelRequis(
                    'Consommation %s déjà dans un état à vérifier : %s.' % (nom_role, etat))

    retenues = [dict(r) for r in reservations if r['IDreservation'] not in exclus]
    return retenues, decisions


def decision_quantite(case, IDinscription, etat_cible):
    """Décider sans écrire si une demande Quantite peut être rejouée.

    Retourne 'creer', 'existant' ou 'requalifier'. Le cas existant doit
    produire zéro appel à SaisieConso ; les deux autres utilisent une
    quantité CIBLE ABSOLUE de 1 dans le parcours Connecthys uniquement.
    Ne jamais appliquer cette règle aux saisies manuelles ordinaires.
    """
    if etat_cible not in ('reservation', 'attente'):
        raise ArbitrageManuelRequis('État cible Quantite non admissible.')
    if case is None:
        raise ArbitrageManuelRequis('Case Quantite inaccessible.')
    if (getattr(case, 'IDfacture', None) is not None or
            getattr(case, 'verrouillage', 0)):
        raise ArbitrageManuelRequis('Case Quantite facturée ou verrouillée.')
    presentes = [c for c in case.GetListeConso()
                 if c is not None and getattr(c, 'etat', None) is not None]
    if not presentes:
        if (getattr(case, 'etat', None) is not None or
                getattr(case, 'quantite', None) not in (None, 0)):
            raise ArbitrageManuelRequis('Quantite sans consommation attribuable.')
        return 'creer'
    if len(presentes) != 1:
        raise ArbitrageManuelRequis('Plusieurs consommations sur la case Quantite.')
    conso = presentes[0]
    if getattr(conso, 'IDinscription', None) != IDinscription:
        raise ArbitrageManuelRequis('Quantite attribuée à une autre inscription.')
    if (getattr(conso, 'IDfacture', None) is not None or
            getattr(conso, 'verrouillage', 0)):
        raise ArbitrageManuelRequis('Quantite protégée : arbitrage obligatoire.')
    if getattr(case, 'quantite', None) != 1:
        raise ArbitrageManuelRequis('Quantite différente de 1 : ne pas écraser.')
    etat = getattr(conso, 'etat', None)
    if etat == etat_cible:
        return 'existant'
    if etat == 'attente' and etat_cible == 'reservation':
        return 'requalifier'
    raise ArbitrageManuelRequis(
        'Quantite déjà en état %s : arbitrage nécessaire.' % etat)


def planifier_sur_grille(reservations, unites, grille, IDactivite):
    """Prévol lecture seule des demandes sur la grille de l'enfant.

    Aucune écriture : ambiguïtés, ancien pointage, rattachement inconnu
    ou ancien montant ne sont jamais inférés comme une place libre.
    Retour : (demandes conservées, décisions journalisables).
    """
    from collections import defaultdict
    par_role = defaultdict(set)
    for unite in unites.values():
        if unite.get('IDactivite') != IDactivite:
            continue
        nom_role = role(unite)
        if nom_role in PERIODS:
            par_role[nom_role].update(
                unite.get('unites_principales', ()))
            par_role[nom_role].update(
                unite.get('unites_secondaires', ()))

    demandes_periodes = [
        r for r in reservations
        if r['etat'] == 1 and role(unites[r['IDunite']]) in PERIODS
    ]
    if demandes_periodes:
        for x in PERIODS:
            for y in PERIODS:
                if x < y and par_role[x] & par_role[y]:
                    raise ArbitrageManuelRequis(
                        'Unité physique commune aux formules %s et %s : vérification manuelle.' % (x, y))

    def lire_etat(demande, nom_role):
        etats = []
        ids = par_role[nom_role]
        for IDunite in sorted(ids):
            case = grille.GetCase(IDunite, demande['date'])
            if case is None:
                continue
            conso_liste = [c for c in case.GetListeConso()
                          if c is not None and getattr(c, 'etat', None) is not None]
            if getattr(case, 'etat', None) is not None and not conso_liste:
                raise ArbitrageManuelRequis('Case déjà remplie mais origine illisible.')
            for c in conso_liste:
                if getattr(c, 'IDinscription', None) != demande['IDinscription']:
                    raise ArbitrageManuelRequis('Consommation d’une autre inscription.')
                if (getattr(case, 'IDfacture', None) is not None or
                        getattr(case, 'verrouillage', 0) or
                        getattr(c, 'IDfacture', None) is not None or
                        getattr(c, 'verrouillage', 0)):
                    raise ArbitrageManuelRequis('Consommation facturée ou verrouillée.')
                etats.append(c.etat)
        if not etats:
            return None
        if len(etats) != len(ids) or len(set(etats)) != 1:
            raise ArbitrageManuelRequis('Consommations partielles ou contradictoires.')
        return etats[0]

    def place_disponible(demande):
        config = unites[demande['IDunite']]
        physiques = (list(config.get('unites_principales', ())) +
                     list(config.get('unites_secondaires', ())))
        if not physiques:
            return None
        for IDunite in physiques:
            if (grille.GetCase(IDunite, demande['date']) is None or
                    not grille.IsOuvert(IDunite=IDunite, date=demande['date'])):
                return False
            place = grille.HasPlacesDisponibles(
                IDunite=IDunite, date=demande['date'])
            if place is None:
                return None
            if not place:
                return False
        return True

    if demandes_periodes:
        retenues, decisions = planifier_priorites(
            reservations, unites, lire_etat, place_disponible)
    else:
        retenues, decisions = ([dict(r) for r in reservations], [])

    # Le sous-parcours Quantite ne doit jamais augmenter la même case
    # à chaque nouveau passage ni écraser une quantité légitime de 2.
    types = getattr(getattr(grille, 'grille', None), 'dictUnites', {})
    deja_vues = set()
    cible = []
    for demande in retenues:
        if demande['etat'] != 1:
            cible.append(demande)
            continue
        unite = unites[demande['IDunite']]
        physiques = (list(unite.get('unites_principales', ())) +
                     list(unite.get('unites_secondaires', ())))
        quantites = [i for i in physiques if types.get(i, {}).get('type') == 'Quantite']
        if not quantites:
            cible.append(demande)
            continue
        if len(physiques) != len(quantites) or len(set(quantites)) != len(quantites):
            raise ArbitrageManuelRequis(
                'Formule combinant Quantite et unités incompatibles.')
        signature = (demande['date'], demande['IDinscription'],
                     tuple(sorted(quantites)))
        if signature in deja_vues:
            decisions.append(('quantite_demande_repetee', signature[:2]))
            continue
        deja_vues.add(signature)
        choix = []
        for IDunite in quantites:
            decision = decision_quantite(
                grille.GetCase(IDunite, demande['date']),
                demande['IDinscription'], 'reservation')
            choix.append(decision)
        if all(x == 'existant' for x in choix):
            decisions.append(('quantite_deja_presente', signature[:2]))
            continue
        if len(set(choix)) > 1:
            raise ArbitrageManuelRequis(
                'Unités Quantite partiellement enregistrées : reprise manuelle.')
        cible.append(demande)
    return cible, decisions
