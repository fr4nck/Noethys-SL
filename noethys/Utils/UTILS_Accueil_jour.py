# -*- coding: utf-8 -*-
"""Lectures de l'accueil : aucune écriture ni déduction depuis les inscriptions."""
import datetime as dt
import re
import unicodedata


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
                                   order=max(0, int(item.get('order', 0))),
                                   morning_unit=int(item['morning_unit']) if item.get('morning_unit') else None,
                                   afternoon_unit=int(item['afternoon_unit']) if item.get('afternoon_unit') else None)
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
    M/A suit les unités de remplissage configurées, jamais un découpage à midi.
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
    scheduled = {(row[0], row[1]) for row in read("""SELECT DISTINCT u.IDactivite, o.IDgroupe
        FROM ouvertures o INNER JOIN unites u ON u.IDunite=o.IDunite
        WHERE o.date='%s' AND (u.date_debut IS NULL OR u.date_debut<='%s')
        AND (u.date_fin IS NULL OR u.date_fin>='%s');""" % (date, date, date))}
    scheduled.update((row[0], row[1]) for row in read(
        "SELECT DISTINCT IDactivite, IDgroupe FROM evenements WHERE date='%s';" % date))
    group_labels = {row[0]: (row[1], row[2]) for row in read('SELECT IDgroupe, nom, abrege FROM groupes;')}
    slots = {}
    for slot_id, activity, name, short, start, end, tags, unit in read("""SELECT r.IDunite_remplissage,
        r.IDactivite, r.nom, r.abrege, r.heure_min, r.heure_max, r.etiquettes, l.IDunite
        FROM unites_remplissage r LEFT JOIN unites_remplissage_unites l
        ON l.IDunite_remplissage=r.IDunite_remplissage
        WHERE (r.date_debut IS NULL OR r.date_debut<='%s')
        AND (r.date_fin IS NULL OR r.date_fin>='%s');""" % (date, date)):
        slot = slots.setdefault(slot_id, dict(id=slot_id, activity=activity, name=name or short or '',
                                             short=short or '', start=minutes(start), end=minutes(end),
                                             tags=set(str(tags or '').split(';'))-{''}, units=set()))
        if unit is not None:
            slot['units'].add(unit)
    options = preferences(settings)['activities']
    resolved = {}
    def normal(value):
        return ''.join(c for c in unicodedata.normalize('NFD',value.casefold()) if not unicodedata.combining(c))
    for activity, name, short in catalog:
        option = options.get(str(activity), dict(visible=True, alsh=is_alsh(name or ''), order=0))
        available = [s for s in slots.values() if s['activity']==activity]
        option = dict(option)
        for key, pattern in (('morning_unit',r'\b(mat|matin|matinee)\b'),
                             ('afternoon_unit',r'\b(apm|apres[ -]?midi|aprem)\b')):
            selected = option.get(key)
            if selected:
                option[key] = selected if any(s['id']==selected for s in available) else None
            else:
                matches = [s['id'] for s in available if re.search(pattern,normal(s['name']+' '+s['short']))]
                option[key] = matches[0] if len(matches)==1 else None
        labels = ['%s · %s' % (s['name'],s['short']) for s in available]
        option['slot_choices'] = [dict(id=s['id'],label=label if labels.count(label)==1 else '%s [%s]' % (label,s['id']))
                                  for s,label in zip(available,labels)]
        resolved[activity] = option
    rows = read("""SELECT c.IDactivite, c.IDindividu, c.etat,
        c.heure_debut, c.heure_fin, c.IDgroupe, c.IDunite, c.etiquettes
        FROM consommations c
        WHERE c.date='%s';""" % date)
    groups = {}
    totals = {}
    for activity, person, state, start, end, group_id, unit, tags in rows:
        scheduled.add((activity, group_id))
        group = groups.setdefault((activity, group_id), dict(total=set(), morning=set(), afternoon=set(), unknown=False))
        if state not in ('reservation', 'present') or person is None:
            continue
        totals.setdefault(activity, set()).add(person)
        group['total'].add(person)
        for key in ('morning','afternoon'):
            slot = slots.get(resolved.get(activity,{}).get(key+'_unit'))
            if not slot:
                group['unknown'] = True
                continue
            if unit not in slot['units']:
                continue
            # Même condition horaire et mêmes étiquettes que CTRL_Remplissage.
            a,b = minutes(start), minutes(end)
            if None not in (slot['start'],slot['end'],a,b) and not (a<=slot['end'] and b>=slot['start']):
                continue
            if slot['tags'] and not slot['tags'].intersection(set(str(tags or '').split(';'))):
                continue
            group[key].add(person)
    result, choices = [], []
    for activity, name, short in catalog:
        option = resolved[activity]
        item = dict(id=activity, name=name or '', label=short or name or '', **option)
        choices.append(item)
        scheduled_groups = sorted({group for act, group in scheduled if act == activity}, key=lambda group: group or 0)
        if not scheduled_groups or not item['visible']:
            continue
        if not item['alsh']:
            result.append(dict(item, total=len(totals.get(activity, set())), morning=None, afternoon=None))
            continue
        for group_id in scheduled_groups:
            group = groups.get((activity, group_id), dict(total=set(), morning=set(), afternoon=set(), unknown=False))
            unknown = group['unknown'] or not option.get('morning_unit') or not option.get('afternoon_unit')
            group_name, group_short = group_labels.get(group_id, ('', ''))
            result.append(dict(item, group=group_id, label=group_short or group_name or item['label'],
                               name=('%s · %s' % (item['name'], group_name)) if group_name else item['name'],
                               total=len(group['total']),
                               morning=None if unknown else len(group['morning']),
                               afternoon=None if unknown else len(group['afternoon'])))
    result.sort(key=lambda item: (0 if item['order'] else 1,
                                  item['order'], not item['alsh'], item['name'].casefold(), item['id']))
    return result, choices
