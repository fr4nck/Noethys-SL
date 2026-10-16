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
    openings = read("""SELECT DISTINCT u.IDactivite, o.IDgroupe, u.IDunite,
        u.heure_debut, u.heure_fin, u.nom
        FROM ouvertures o INNER JOIN unites u ON u.IDunite=o.IDunite
        WHERE o.date='%s' AND (u.date_debut IS NULL OR u.date_debut<='%s')
        AND (u.date_fin IS NULL OR u.date_fin>='%s');""" % (date, date, date))
    events = read("""SELECT IDactivite, IDgroupe, IDunite, heure_debut, heure_fin,
        nom, IDevenement FROM evenements WHERE date='%s';""" % date)
    scheduled = {(row[0], row[1]) for row in openings + events}
    sessions = {}

    def session(activity, group, unit, start, end, name='', event=None):
        a, b = minutes(start), minutes(end)
        # Une séance identifiée reste distincte, même à horaire identique.
        # Sans séance : même groupe/plage = personnes dédoublonnées entre unités.
        identity = ('event', event) if event is not None else ('hours', a, b, unit if a is None or b is None else None)
        key = (activity, group, identity)
        return sessions.setdefault(key, dict(group=group, start=a, end=b,
                    event=event, name=name or '', people=set()))

    event_units = {(a,g,u) for a,g,u,*_ in events}
    for activity, group, unit, start, end, name, event in events:
        session(activity, group, unit, start, end, name, event)
    for activity, group, unit, start, end, name in openings:
        if (activity, group, unit) not in event_units:
            session(activity, group, unit, start, end, name)
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
        c.heure_debut, c.heure_fin, c.IDgroupe, c.IDunite, c.etiquettes,
        c.IDevenement, u.heure_debut, u.heure_fin, u.nom,
        e.heure_debut, e.heure_fin, e.nom
        FROM consommations c LEFT JOIN unites u ON u.IDunite=c.IDunite AND u.IDactivite=c.IDactivite
        LEFT JOIN evenements e ON e.IDevenement=c.IDevenement AND e.IDactivite=c.IDactivite AND e.date=c.date
        WHERE c.date='%s';""" % date)
    groups = {}
    for activity, person, state, start, end, group_id, unit, tags, event, unit_start, unit_end, unit_name, event_start, event_end, event_name in rows:
        scheduled.add((activity, group_id))
        group = groups.setdefault((activity, group_id), dict(total=set(), morning=set(), afternoon=set(), unknown=False))
        if state not in ('reservation', 'present') or person is None:
            continue
        group['total'].add(person)
        if event:
            slot = session(activity, group_id, unit, event_start, event_end, event_name, event)
        elif (activity, group_id, unit) in event_units:
            # Ancienne consommation sans lien de séance : ne pas inventer son créneau.
            slot = session(activity, group_id, unit, None, None, 'Créneau non renseigné')
        else:
            slot = session(activity, group_id, unit, unit_start if unit_start is not None else start,
                           unit_end if unit_end is not None else end, unit_name)
        slot['people'].add(person)
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
            activity_sessions = [(key, s) for key, s in sessions.items() if key[0] == activity]
            activity_sessions.sort(key=lambda pair: (pair[1]['start'] is None, pair[1]['start'] or 0,
                                                       pair[1]['end'] or 0, str(pair[1]['group']), str(pair[1]['event'])))
            for key, s in activity_sessions:
                def hour(value):
                    return '%02dh%02d' % divmod(int(value), 60) if value is not None else '?'
                period = '%s–%s' % (hour(s['start']), hour(s['end'])) if s['start'] is not None or s['end'] is not None else 'horaire non renseigné'
                group_name, group_short = group_labels.get(s['group'], ('', ''))
                group_text = group_short or group_name
                # Le groupe distingue aussi deux séances simultanées.
                event_text = (s['name'] or 'Séance %s' % s['event']) + ' · ' if s['event'] is not None else ''
                label = '%s · %s%s%s' % (item['label'], (group_text+' · ') if group_text else '', event_text, period)
                result.append(dict(item, label=label, name='%s · %s · %s' % (item['name'], s['name'], period),
                                   session=key[2], activity_name=item['name'], session_start=s['start'], group=s['group'], total=len(s['people']), morning=None, afternoon=None))
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
                                  item['order'], not item['alsh'], item.get('activity_name', item['name']).casefold(), item['id'],
                                  item.get('session_start') is None, item.get('session_start') or 0, item['name'].casefold()))
    return result, choices
