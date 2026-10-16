# -*- coding: utf-8 -*-
"""Lectures de l'accueil : aucune écriture ni déduction depuis les inscriptions."""
import datetime as dt
import re


def preferences(value=None):
    value = value if isinstance(value, dict) else {}
    try:
        count = max(0, int(value.get('event_count', 0)))  # 0 = tout
    except (ValueError, TypeError, OverflowError):
        count = 0
    activities = {}
    source = value.get('activities', {})
    for key, item in (source if isinstance(source, dict) else {}).items():
        try:
            key = str(int(key))
            if not isinstance(item, dict):
                continue
            activities[key] = dict(visible=bool(item.get('visible', True)),
                                   alsh=bool(item.get('alsh', False)),
                                   order=max(0, int(item.get('order', 0))))
        except (TypeError, ValueError, OverflowError):
            continue
    return dict(event_count=count, activities=activities)


def is_alsh(name):
    return bool(re.search(r'\b(alsh|alshh|alshm)\b|accueil.*loisirs', name.lower()))


def minutes(value):
    if isinstance(value, dt.timedelta):
        return value.total_seconds() / 60
    if isinstance(value, dt.time):
        return value.hour * 60 + value.minute
    try:
        bits = str(value).split(':')
        return int(bits[0]) * 60 + int(bits[1])
    except (TypeError, ValueError, IndexError):
        return None


def read_day(db, today, settings=None):
    """MySQL/SQLite : SELECT portables, date ISO issue de datetime.date seulement.

    Réservations et présences dédoublonnées par personne ; ni attente, ni absences.
    Les unités sans horaires restent comptées au total, M/A est alors indéterminé.
    Une ouverture ou un événement du jour reste visible avec zéro réservation.
    """
    date = today.isoformat()

    def read(sql):
        if not db.ExecuterReq(sql):
            raise ValueError('Lecture du programme du jour impossible')
        return db.ResultatReq()

    catalog = read("""SELECT IDactivite, nom, abrege FROM activites
        WHERE (date_debut IS NULL OR date_debut <= '%s')
        AND (date_fin IS NULL OR date_fin >= '%s') ORDER BY nom;""" % (date, date))
    scheduled = {row[0] for row in read("""SELECT DISTINCT u.IDactivite
        FROM ouvertures o INNER JOIN unites u ON u.IDunite=o.IDunite
        WHERE o.date='%s' AND (u.date_debut IS NULL OR u.date_debut<='%s')
        AND (u.date_fin IS NULL OR u.date_fin>='%s');""" % (date, date, date))}
    scheduled.update(row[0] for row in read(
        "SELECT DISTINCT IDactivite FROM evenements WHERE date='%s';" % date))
    rows = read("""SELECT c.IDactivite, c.IDindividu, c.etat,
        c.heure_debut, c.heure_fin, u.heure_debut, u.heure_fin
        FROM consommations c LEFT JOIN unites u ON u.IDunite=c.IDunite
        WHERE c.date='%s';""" % date)
    groups = {}
    for activity, person, state, start, end, unit_start, unit_end in rows:
        scheduled.add(activity)
        group = groups.setdefault(activity, dict(total=set(), morning=set(), afternoon=set(), unknown=False))
        if state not in ('reservation', 'present') or person is None:
            continue
        group['total'].add(person)
        start = minutes(start if start is not None else unit_start)
        end = minutes(end if end is not None else unit_end)
        if start is None or end is None or end <= start:
            group['unknown'] = True
            continue
        if start < 12 * 60 and end > 0:
            group['morning'].add(person)
        if end > 12 * 60 and start < 24 * 60:
            group['afternoon'].add(person)
    options = preferences(settings)['activities']
    result, choices = [], []
    for activity, name, short in catalog:
        default = dict(visible=True, alsh=is_alsh(name or ''), order=0)
        option = options.get(str(activity), default)
        item = dict(id=activity, name=name or '', label=short or name or '', **option)
        choices.append(item)
        if activity not in scheduled or not item['visible']:
            continue
        group = groups.get(activity, dict(total=set(), morning=set(), afternoon=set(), unknown=False))
        result.append(dict(item, total=len(group['total']),
                           morning=None if group['unknown'] else len(group['morning']),
                           afternoon=None if group['unknown'] else len(group['afternoon'])))
    result.sort(key=lambda item: (0 if item['order'] else 1,
                                  item['order'], not item['alsh'], item['name'].casefold(), item['id']))
    return result, choices
