# -*- coding: utf-8 -*-
"""Q445 / J5 - read-only preflight for an explicitly approved site perimeter.

This module does not guess where a child attended, never writes to the
database, and does not mark real sites as approved. It produces an aggregate
inventory to be checked by an authorised operator on a disposable replica.
"""
from __future__ import annotations

from collections import Counter
from Utils.UTILS_Stats_assiduite import Configuration, _id, _iso

EXPECTED_STATES = frozenset((
    'present', 'absentj', 'absenti', 'reservation', 'attente', 'refus'
))


def _read(db, sql, evidence):
    if not sql.lstrip().upper().startswith('SELECT '):
        raise ValueError('Only read-only SELECT statements are permitted')
    evidence.append(sql)
    if db.ExecuterReq(sql) is False:
        raise RuntimeError('Site perimeter SELECT failed')
    rows = db.ResultatReq()
    if rows is None:
        raise RuntimeError('Site perimeter SELECT returned no collection')
    return rows


def _ids(values):
    return ','.join(map(str, sorted(_id(int(v), 'identifier') for v in values)))


def precontroler(db, configuration, debut, fin):
    """Return anonymised activity/unit/group counts, never a site approval.

    `configuration` is the director's proposed, not inferred, set of accueil
    units and optional site rules. A successful result is an *audit proposal*,
    not evidence of historical completeness or an automatic homologation.
    """
    if not isinstance(configuration, Configuration):
        raise ValueError('Explicit Configuration required')
    start, end = _iso(debut), _iso(fin)
    if end < start:
        raise ValueError('Invalid period')
    acts = _ids(configuration.activites)
    evidence = []
    activities = {
        int(i): str(name or '')
        for i, name in _read(
            db, 'SELECT IDactivite,nom FROM activites WHERE IDactivite IN (%s) '
                'ORDER BY IDactivite' % acts, evidence)
    }
    unit_ids = set()
    for seq in configuration.unites_accueil.values():
        unit_ids.update(seq)
    unit_ids.update(r.unite for r in configuration.regles_sites)
    unit_filter = (' OR IDunite IN (%s)' % _ids(unit_ids)) if unit_ids else ''
    units = {
        int(i): (int(activity), str(name or ''), repas)
        for i, activity, name, repas in _read(
            db, 'SELECT IDunite,IDactivite,nom,repas FROM unites '
                'WHERE IDactivite IN (%s)%s ORDER BY IDunite'
                % (acts, unit_filter), evidence)
    }
    group_ids = set()
    for r in configuration.regles_sites:
        if r.groupes is not None:
            group_ids.update(g for g in r.groupes if g is not None)
    group_filter = (' OR IDgroupe IN (%s)' % _ids(group_ids)) if group_ids else ''
    groups = {
        int(i): (int(activity), str(name or ''))
        for i, activity, name in _read(
            db, 'SELECT IDgroupe,IDactivite,nom FROM groupes '
                'WHERE IDactivite IN (%s)%s ORDER BY IDgroupe'
                % (acts, group_filter), evidence)
    }
    observations = _read(
        db,
        "SELECT IDactivite,IDunite,IDgroupe,etat,COUNT(*) FROM consommations "
        "WHERE date>='%s' AND date<='%s' AND IDactivite IN (%s) "
        "GROUP BY IDactivite,IDunite,IDgroupe,etat "
        "ORDER BY IDactivite,IDunite,IDgroupe,etat" % (start, end, acts),
        evidence)

    catalogue = []
    for activity in configuration.activites:
        if activity not in activities:
            catalogue.append('ACTIVITE_ABSENTE:%s' % activity)
    for activity, approved in configuration.unites_accueil.items():
        for unit in approved:
            row = units.get(unit)
            if row is None:
                catalogue.append('UNITE_ABSENTE:%s' % unit)
            elif row[0] != activity:
                catalogue.append('UNITE_AUTRE_ACTIVITE:%s' % unit)
    for rule in configuration.regles_sites:
        row = units.get(rule.unite)
        if row is None or row[0] != rule.activite:
            catalogue.append('REGLE_UNITE_INVALIDE:%s' % rule.unite)
        if rule.groupes:
            for group in rule.groupes:
                if group is None:
                    continue
                item = groups.get(group)
                if item is None or item[0] != rule.activite:
                    catalogue.append('REGLE_GROUPE_INVALIDE:%s' % group)

    result_rows = []
    status_totals = Counter()
    site_counts = Counter()
    unknown_states = Counter()
    total = 0
    for activity, unit, group, state, quantity in observations:
        activity = int(activity)
        unit = int(unit) if unit is not None else None
        group = int(group) if group is not None else None
        quantity = int(quantity)
        if quantity < 0:
            raise RuntimeError('Negative aggregate count')
        total += quantity
        state_text = str(state) if state is not None else 'NULL'
        unit_meta = units.get(unit)
        group_meta = groups.get(group) if group is not None else None
        if unit_meta is None:
            verdict = 'UNITE_INCONNUE'
        elif unit_meta[0] != activity:
            verdict = 'UNITE_AUTRE_ACTIVITE'
        elif group is not None and group_meta is None:
            verdict = 'GROUPE_INCONNU'
        elif group_meta is not None and group_meta[0] != activity:
            verdict = 'GROUPE_AUTRE_ACTIVITE'
        elif not configuration.unites_accueil:
            verdict = 'PERIMETRE_ACCUEIL_NON_VALIDE'
        elif unit not in configuration.unites_accueil[activity]:
            verdict = 'UNITE_EXCLUE_A_VERIFIER'
        elif not configuration.regles_sites:
            verdict = 'SITES_NON_CONFIGURES'
        else:
            sites = [r.site for r in configuration.regles_sites
                     if r.match(activity, unit, group)]
            verdict = 'OK' if len(sites) == 1 else (
                'SITE_AMBIGU' if len(sites) > 1 else 'SITE_NON_RATTACHE')
        if state not in EXPECTED_STATES:
            unknown_states[state_text] += quantity
        status_totals[verdict] += quantity
        site = None
        if verdict == 'OK':
            site = sites[0]
            site_counts[site] += quantity
        result_rows.append({
            'activite': activity,
            'activite_nom': activities.get(activity, ''),
            'unite': unit,
            'unite_nom': unit_meta[1] if unit_meta else '',
            # "repas" means "meal included", not "meal-only".
            'repas_inclus': unit_meta[2] if unit_meta else None,
            'groupe': group,
            'groupe_nom': group_meta[1] if group_meta else '',
            'etat': state_text,
            'lignes': quantity,
            'verdict': verdict,
            'site_propose': site,
        })
    # Excluded units might be meal/extras, but only the director can confirm.
    critical = sum(v for k, v in status_totals.items()
                   if k not in ('OK', 'UNITE_EXCLUE_A_VERIFIER'))
    eligible = (bool(configuration.regles_sites) and total > 0
                and not catalogue and critical == 0 and not unknown_states)
    return {
        'statut': 'PRECONTROLE_MANUEL_JAMAIS_HOMOLOGATION_AUTOMATIQUE',
        'periode': [start, end],
        'activites': list(configuration.activites),
        'lignes_total': total,
        'verdicts': dict(sorted(status_totals.items())),
        'sites_candidats': dict(sorted(site_counts.items())),
        'catalogue_anomalies': sorted(set(catalogue)),
        'etats_inconnus': dict(sorted(unknown_states.items())),
        'observations': result_rows,
        'candidat_a_approbation_humaine': bool(eligible),
        'homologue': False,
        'avertissements': [
            'Review excluded units with the person responsible for each site',
            'The configured site rules are proposed, not inferred',
            'No historical completeness is established by these counts',
            'No family/child identifiers, names or financial amounts are selected',
        ],
        'requetes_sql': len(evidence),
    }
