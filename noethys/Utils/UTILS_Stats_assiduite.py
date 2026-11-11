# -*- coding: utf-8 -*-
"""Read-only attendance/absence statistics for Noethys-SL.

Only recorded consumption states are counted. Deleting a reservation removes
its row: past cancellations CANNOT be reconstructed from consumption states.
The unstructured historical deletion log does not prove cancellations.

The activity date (not data-entry date) determines the statistical year.
All datasets are aggregated; no child/family identifiers leave this reader.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Mapping, Optional

POINTED = ('present', 'absentj', 'absenti')
OTHER = ('reservation', 'attente', 'refus')
DAY_KEYS = ('present', 'absentj', 'absenti', 'mixte')
ROW_KEYS = POINTED + OTHER + ('inconnu',)
CANCELLATIONS = (
    'NON_RECONSTRUCTIBLES : les consommations supprimees ne figurent plus '
    'dans le registre actuel. La categorie 10 de l historique trace des '
    'suppressions, pas des annulations identifiables par activite, site et date.'
)


def _id(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError('%s must be a positive integer' % label)
    return value


def _iso(value):
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError('Expected ISO YYYY-MM-DD date')
    return date.fromisoformat(value).isoformat()


@dataclass(frozen=True)
class RegleSite:
    site: str
    activite: int
    unite: int
    groupes: Optional[tuple] = None

    def __post_init__(self):
        if not isinstance(self.site, str) or not self.site.strip():
            raise ValueError('Site must have a name')
        _id(self.activite, 'activity')
        _id(self.unite, 'unit')
        if self.groupes is not None:
            if not self.groupes or len(self.groupes) != len(set(self.groupes)):
                raise ValueError('Site groups must be nonempty and unique')
            for group in self.groupes:
                if group is not None:
                    _id(group, 'group')

    def match(self, activity, unit, group):
        return (self.activite == activity and self.unite == unit and
                (self.groupes is None or group in self.groupes))


@dataclass(frozen=True)
class Configuration:
    activites: tuple
    unites_accueil: Mapping[int, tuple] = field(default_factory=dict)
    regles_sites: tuple[RegleSite, ...] = ()

    def __post_init__(self):
        if not self.activites or len(self.activites) != len(set(self.activites)):
            raise ValueError('Nonempty unique activity list required')
        for activity in self.activites:
            _id(activity, 'activity')
        if self.unites_accueil and set(self.unites_accueil) != set(self.activites):
            raise ValueError('Every selected activity needs approved accueil units')
        for activity, ids in self.unites_accueil.items():
            if not ids or len(ids) != len(set(ids)):
                raise ValueError('Approved units must be nonempty and unique')
            for unit in ids:
                _id(unit, 'unit')
        for r in self.regles_sites:
            if not isinstance(r, RegleSite) or r.activite not in self.activites:
                raise ValueError('Invalid site rule outside the selected activities')
            if self.unites_accueil and r.unite not in self.unites_accueil[r.activite]:
                raise ValueError('Site rule references excluded unit')
        if self.regles_sites and not self.unites_accueil:
            raise ValueError('Site mapping requires a complete accueil unit whitelist')
        for idx, a in enumerate(self.regles_sites):
            for b in self.regles_sites[idx + 1:]:
                if (a.activite == b.activite and a.unite == b.unite and
                    (a.groupes is None or b.groupes is None or
                     bool(set(a.groupes) & set(b.groupes)))):
                    raise ValueError('Overlapping site rules')


class PerimetreIncomplet(ValueError):
    """A physical location cannot be established without guessing."""


class _Compteur:
    def __init__(self):
        self.lignes = Counter()
        self.jours = defaultdict(set)
        self.enfants = set()

    def add(self, record, state):
        self.lignes[state] += 1
        if state in POINTED:
            daykey = (record['child'], record['date'])
            self.jours[daykey].add(state)
            self.enfants.add(record['child'])

    def result(self):
        details = Counter({key: 0 for key in DAY_KEYS})
        for states in self.jours.values():
            if len(states) != 1:
                details['mixte'] += 1
            else:
                details[next(iter(states))] += 1
        lines = {key: self.lignes[key] for key in ROW_KEYS}
        jours = {key: details[key] for key in DAY_KEYS}
        clean = sum(jours[key] for key in POINTED)
        absences = jours['absentj'] + jours['absenti']
        return {
            'lignes': lines,
            'journees_enfants': jours,
            'journees_pointees': clean + jours['mixte'],
            'journees_clairement_classees': clean,
            'enfants_distincts_pointes': len(self.enfants),
            'taux_absence_pct': round(100 * absences / clean, 2) if clean else None,
            'part_injustifiee_pct': round(100 * jours['absenti'] / absences, 2) if absences else None,
            'lignes_total': sum(lines.values()),
        }


class Lecteur:
    """One SELECT, no writes and no modifications to billing data."""
    def __init__(self, db, configuration: Configuration):
        if not isinstance(configuration, Configuration):
            raise ValueError('Explicit activity scope required')
        self.db = db
        self.conf = configuration
        self.requetes = []

    def _read(self, sql):
        if not sql.lstrip().upper().startswith('SELECT '):
            raise ValueError('Read-only SQL required')
        self.requetes.append(sql)
        status = self.db.ExecuterReq(sql)
        if status is False:
            raise RuntimeError('Attendance SELECT failed')
        result = self.db.ResultatReq()
        if result is None:
            raise RuntimeError('Attendance SELECT returned no collection')
        return result

    def _site(self, activity, unit, group):
        matches = [r.site for r in self.conf.regles_sites
                   if r.match(activity, unit, group)]
        if len(matches) != 1:
            raise PerimetreIncomplet('Presence without an unambiguous approved physical site')
        return matches[0]

    def lire(self, date_debut, date_fin):
        a, b = _iso(date_debut), _iso(date_fin)
        if b < a:
            raise ValueError('End date before start')
        acts = tuple(sorted(self.conf.activites))
        sqlids = '(' + ','.join(str(_id(v, 'activity')) for v in acts) + ')'
        sql = ("SELECT c.IDconso,c.date,c.IDindividu,c.IDactivite,c.IDunite,"
               "c.IDgroupe,c.etat FROM consommations c "
               "WHERE c.date>='%s' AND c.date<='%s' "
               "AND c.IDactivite IN %s ORDER BY c.date,c.IDconso" % (a, b, sqlids))
        global_count = _Compteur()
        by_year = defaultdict(_Compteur)
        by_month = defaultdict(_Compteur)
        by_activity = defaultdict(_Compteur)
        by_site = defaultdict(_Compteur)
        by_site_year = defaultdict(_Compteur)
        excluded_units = 0
        unknown_states = Counter()
        for record in self._read(sql):
            ident, day, child, activity, unit, group, state = record
            day = _iso(day)
            if activity not in self.conf.activites:
                raise ValueError('SELECT returned an unexpected activity')
            if (self.conf.unites_accueil and
                    unit not in self.conf.unites_accueil[activity]):
                excluded_units += 1
                continue
            if child is None:
                raise ValueError('Consumption without child identifier: cannot deduplicate')
            _id(child, 'child')
            actual = state if state in ROW_KEYS[:-1] else 'inconnu'
            if actual == 'inconnu':
                unknown_states[str(state)] += 1
            row = {'child': child, 'date': day}
            year = day[:4]
            month = day[:7]
            group_counters = (global_count, by_year[year], by_month[month],
                              by_activity[str(activity)])
            if self.conf.regles_sites:
                site = self._site(activity, unit, group)
                group_counters += (by_site[site], by_site_year[(site, year)])
            for cnt in group_counters:
                cnt.add(row, actual)
        years = range(int(a[:4]), int(b[:4]) + 1)
        # Explicitly include empty months: a missing observation is not a missing month.
        monthly_keys = []
        yy, mm = int(a[:4]), int(a[5:7])
        while (yy, mm) <= (int(b[:4]), int(b[5:7])):
            monthly_keys.append('%04d-%02d' % (yy, mm))
            mm += 1
            if mm == 13:
                yy, mm = yy + 1, 1
        result = {
            'statut': 'CANDIDAT_LECTURE_SEULE_NON_HOMOLOGUE',
            'periode': [a, b],
            'perimetre_unites': ('unités approuvées' if self.conf.unites_accueil
                                 else 'toutes unités, repas et accueil éventuellement mélangés'),
            'sites_qualifies': bool(self.conf.regles_sites),
            'global': global_count.result(),
            'annees': {str(year): by_year[str(year)].result() for year in years},
            'mois': {key: by_month[key].result() for key in monthly_keys},
            'activites': {str(v): by_activity[str(v)].result() for v in acts},
            'sites': dict(sorted((name, cnt.result()) for name, cnt in by_site.items())),
            'sites_annees': {name: {str(year): by_site_year[(name, str(year))].result()
                                   for year in years}
                             for name in sorted(by_site)},
            'unites_exclues': excluded_units,
            'etats_non_reconnus': dict(sorted(unknown_states.items())),
            'annulations': {
                'nombre': None,
                'statut': 'HISTORIQUE_NON_RECONSTRUCTIBLE',
                'explication': CANCELLATIONS,
            },
            'precautions': [
                'The selected date is the activity date, not the data-entry date',
                'A row represents one consumption; a child-day is deduplicated',
                'Mixed child-days cannot be assigned to a single presence/absence state',
                'Unpointed reservations do not imply absence or cancellation',
                'Cancellation totals are unavailable without structured event history',
                'Partial years are not directly comparable to complete calendar years',
            ],
            'requetes_sql': len(self.requetes),
        }
        # Even if there are no attendance rows, the requested years are present.
        for year in years:
            k = str(year)
            result['annees'][k]['annee_complete_dans_periode'] = (
                (a <= k + '-01-01') and (b >= k + '-12-31'))
        return result
