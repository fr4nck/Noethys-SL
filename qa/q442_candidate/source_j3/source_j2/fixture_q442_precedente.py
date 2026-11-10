#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Noethys-SL #442: isolated, synthetic, read-only-to-production audit.

Source contract inspected on wx branch e86fabedece82f6cc1cade70074207291f8d9dfb:
- noethys/Ctrl/CTRL_Grille.py: RechercheQF, MemorisePrestation
- noethys/Ol/OL_Prestations.py: prestations / tarifs / categories_tarifs
- noethys/Utils/UTILS_Stats_familles.py: current stats behavior

This is a SQL and billing-function qualification harness, NOT production code.
It uses sqlite3.connect(':memory:') only, with synthetic records.
"""
import csv
import datetime
import json
import pathlib
import sqlite3
import unittest
from collections import Counter

BRANCH = 'wx'
SOURCE_COMMIT = 'e86fabedece82f6cc1cade70074207291f8d9dfb'
ACTIVITIES = (10, 11)
SITE_NAMES = {10: 'Bais', 11: 'La Guerche'}
PERIOD = ('2026-07-01', '2026-07-31')
TIER_CODES = ('A', 'B', 'C', 'D')
QF_NC = 'QF non communique'
SOURCE_ROWS = ("source: noethys/Ctrl/CTRL_Grille.py#L3471-L3490")


class BillingQFReference:
    """An isolated copy of the wx RechercheQF method, without wx imports.

    The method logic below is transcribed from CTRL_Grille.py,
    read on 2026-11-10. The copy is isolated because the host UI cannot be
    initialized in the temporary SQLite test environment.
    """

    def __init__(self, dict_quotients):
        self.dictQuotientsFamiliaux = dict_quotients

    def RechercheQF(self, dictTarif=None, IDfamille=None, date=None):
        """ Pour Facturation Recherche du QF de la famille """
        # Si la famille a un QF :
        if IDfamille in self.dictQuotientsFamiliaux :
            listeQuotientsFamiliaux = self.dictQuotientsFamiliaux[IDfamille]
            for date_debut, date_fin, quotient, IDtype_quotient in listeQuotientsFamiliaux :
                if date >= date_debut and date <= date_fin and (dictTarif["IDtype_quotient"] == None or dictTarif["IDtype_quotient"] == IDtype_quotient) :
                    return quotient

        # Si la famille n'a pas de QF, on attribue le QF le plus eleve :
        listeQF = []
        for ligneCalcul in dictTarif["lignes_calcul"] :
            qf = ligneCalcul["qf_max"]
            if qf:
                qf = float(qf)
            listeQF.append(qf)
        listeQF.sort()
        if len(listeQF) > 0 :
            if listeQF[-1] != None :
                return listeQF[-1]

        return None


def create_fixture():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
    CREATE TABLE familles(IDfamille INTEGER PRIMARY KEY);
    CREATE TABLE comptes_payeurs(IDcompte_payeur INTEGER PRIMARY KEY, IDfamille INTEGER);
    CREATE TABLE individus(IDindividu INTEGER PRIMARY KEY, IDfamille INTEGER);
    CREATE TABLE categories_tarifs(IDcategorie_tarif INTEGER PRIMARY KEY, nom TEXT);
    CREATE TABLE tarifs(IDtarif INTEGER PRIMARY KEY, IDactivite INTEGER, methode TEXT, IDtype_quotient INTEGER);
    CREATE TABLE tarifs_lignes(IDligne INTEGER PRIMARY KEY, IDtarif INTEGER, num_ligne INTEGER,
       tranche TEXT, qf_min INTEGER, qf_max INTEGER, montant_unique REAL);
    CREATE TABLE prestations(IDprestation INTEGER PRIMARY KEY, date TEXT, categorie TEXT, IDactivite INTEGER,
       IDtarif INTEGER, IDcategorie_tarif INTEGER, IDfacture INTEGER, IDfamille INTEGER,
       IDindividu INTEGER, montant REAL);
    CREATE TABLE consommations(IDconso INTEGER PRIMARY KEY, date TEXT, etat TEXT,
       IDactivite INTEGER, IDindividu INTEGER, IDcompte_payeur INTEGER,
       IDcategorie_tarif INTEGER, IDprestation INTEGER, IDunite INTEGER);
    CREATE TABLE quotients(IDquotient INTEGER PRIMARY KEY, IDfamille INTEGER, IDtype_quotient INTEGER,
       date_debut TEXT, date_fin TEXT, quotient INTEGER);
    ''')
    db.executemany('INSERT INTO familles VALUES(?)', [(i,) for i in range(1, 11)])
    db.executemany('INSERT INTO comptes_payeurs VALUES(?,?)', [(1000 + i, i) for i in range(1, 11)])
    people = [(11, 1), (12, 1), (21, 2), (31, 3), (32, 3), (41, 4),
              (51, 5), (61, 6), (71, 7), (81, 8), (91, 9), (101, 10)]
    db.executemany('INSERT INTO individus VALUES(?,?)', people)
    db.executemany('INSERT INTO categories_tarifs VALUES(?,?)',
                   [(1, 'Commune'), (2, 'Hors commune')])
    db.executemany('INSERT INTO tarifs VALUES(?,?,?,?)',
                   [(100, 10, 'qf', 1), (110, 11, 'qf', 1),
                    (900, 10, 'montant_unique', None)])
    # This is a synthetic, shared logical grid for two sites.
    # A category's monetary amount is deliberately not a stable key.
    tiers = [
        (1, '1', 1000, 99999, 11.75),
        (2, '2', 700, 999, 10.50),
        (3, '3', 300, 699, 7.65),
        (4, '4', 0, 299, 6.85),
    ]
    lines = []
    for tariff_id in (100, 110):
        for n, code, qf_min, qf_max, amount in tiers:
            lines.append((tariff_id * 10 + n, tariff_id, n, code, qf_min, qf_max, amount))
    db.executemany('INSERT INTO tarifs_lignes VALUES(?,?,?,?,?,?,?)', lines)
    qf = [
        (1, 1, '2026-01-01', '2026-07-14', 650),
        (1, 1, '2026-07-15', '2026-12-31', 850),
        (3, 1, '2026-01-01', '2026-12-31', 250),
        (4, 1, '2026-01-01', '2026-12-31', 400),
        (5, 1, '2026-01-01', '2026-12-31', 500),
        (6, 1, '2026-01-01', '2026-06-30', 950),
        (7, 1, '2026-01-01', '2026-12-31', 0),
        (8, 1, '2026-01-01', '2026-12-31', 1000),
        (9, 1, '2026-01-01', '2026-12-31', 700),
        (10, 1, '2026-01-01', '2026-12-31', 350),
    ]
    db.executemany('INSERT INTO quotients VALUES(?,?,?,?,?,?)',
                   [(j, f, t, a, b, q) for j, (f, t, a, b, q) in enumerate(qf, 1)])
    # p: id, date, prestation kind, activity, tariff, inscription tariff category,
    # invoice, family, child, amount. The invoice is ALWAYS NULL here.
    ps = [
        (1101, '2026-07-10', 'consommation', 10, 100, 1, None, 1, 11, 7.65),
        (1102, '2026-07-20', 'consommation', 10, 100, 1, None, 1, 11, 10.50),
        (1103, '2026-07-22', 'consommation', 10, 100, 1, None, 1, 12, 10.50),
        (1104, '2026-07-30', 'consommation', 10, 100, 1, None, 1, 11, 11.00),
        (1105, '2026-07-31', 'consommation', 10, 900, 1, None, 1, 11, 4.25),
        (2101, '2026-07-08', 'consommation', 10, 100, 1, None, 2, 21, 11.75),
        (3101, '2026-07-09', 'consommation', 10, 100, 1, None, 3, 31, 6.85),
        (3201, '2026-07-20', 'consommation', 11, 110, 1, None, 3, 32, 6.85),
        (4101, '2026-07-11', 'consommation', 10, 100, 1, None, 4, 41, 7.65),
        (6101, '2026-07-14', 'consommation', 10, 100, 1, None, 6, 61, 11.75),
        (7101, '2026-07-15', 'consommation', 11, 110, 1, None, 7, 71, 6.85),
        (8101, '2026-07-16', 'consommation', 11, 110, 1, None, 8, 81, 12.25),
        (9101, '2026-07-17', 'consommation', 10, 100, 1, None, 9, 91, 10.50),
        (10101, '2026-07-05', 'consommation', 10, 100, 1, None, 10, 101, 7.65),
    ]
    db.executemany('INSERT INTO prestations VALUES(?,?,?,?,?,?,?,?,?,?)', ps)
    # c: id, date, status, activity, child, payer, category, prestation, unit
    cs = [
        (1, '2026-07-10', 'present', 10, 11, 1001, 1, 1101, 1),
        (2, '2026-07-20', 'present', 10, 11, 1001, 1, 1102, 1),
        (3, '2026-07-22', 'present', 10, 12, 1001, 1, 1103, 1),
        (4, '2026-07-30', 'present', 10, 11, 1001, 1, 1104, 1),
        (5, '2026-07-31', 'present', 10, 11, 1001, 1, 1105, 2),  # Meal, exclude from accueil tariff
        (6, '2026-07-08', 'present', 10, 21, 1002, 1, 2101, 1),
        (7, '2026-07-09', 'present', 10, 31, 1003, 1, 3101, 1),
        (8, '2026-07-20', 'present', 11, 32, 1003, 1, 3201, 1),
        (9, '2026-07-11', 'reservation', 10, 41, 1004, 1, 4101, 1),
        (10, '2026-07-12', 'present', 10, 51, 1005, 1, None, 1), # No prestation yet
        (11, '2026-07-14', 'present', 10, 61, 1006, 1, 6101, 1),
        (12, '2026-07-15', 'present', 11, 71, 1007, 1, 7101, 1),
        (13, '2026-07-16', 'present', 11, 81, 1008, 1, 8101, 1),
        (14, '2026-07-17', 'present', 10, 91, 1009, 1, 9101, 1),
        (15, '2026-07-05', 'present', 10, 101, 1010, 1, 10101, 1),
    ]
    db.executemany('INSERT INTO consommations VALUES(?,?,?,?,?,?,?,?,?)', cs)
    db.commit()
    return db


def billed_qf_reference(db):
    refs = {}
    for r in db.execute('SELECT IDfamille, IDtype_quotient, date_debut, date_fin, quotient '
                        'FROM quotients ORDER BY date_debut, IDquotient'):
        refs.setdefault(r['IDfamille'], []).append(
            (datetime.date.fromisoformat(r['date_debut']),
             datetime.date.fromisoformat(r['date_fin']), r['quotient'], r['IDtype_quotient']))
    return BillingQFReference(refs)


def tariff_for(db, tariff_id):
    t = db.execute('SELECT IDtype_quotient FROM tarifs WHERE IDtarif=?', (tariff_id,)).fetchone()
    assert t is not None
    lines = [dict(z) for z in db.execute(
        'SELECT qf_min, qf_max, tranche FROM tarifs_lignes WHERE IDtarif=? ORDER BY num_ligne',
        (tariff_id,))]
    return {'IDtype_quotient': t['IDtype_quotient'], 'lignes_calcul': lines}


def tier_for_qf(db, qf, tariff_id):
    if qf is None:
        return 'A'  # Synthetic top category, not a literal QF value
    hits = [str(r['tranche']) for r in db.execute(
        'SELECT tranche, qf_min, qf_max FROM tarifs_lignes WHERE IDtarif=?', (tariff_id,))
        if r['qf_min'] <= qf <= r['qf_max']]
    if len(hits) != 1:
        return 'A REVOIR'
    return dict(zip(('1', '2', '3', '4'), TIER_CODES))[hits[0]]


def current_qf(db, family_id, when, qf_type=1):
    vals = [r['quotient'] for r in db.execute(
        'SELECT quotient FROM quotients WHERE IDfamille=? AND IDtype_quotient=? '
        'AND date_debut<=? AND date_fin>=?', (family_id, qf_type, when, when))]
    if not vals:
        return None
    if len(set(vals)) > 1:
        return 'CONFLIT'
    return vals[0]


def qualifying_rows(db, a, b, activities=ACTIVITIES):
    placeholders = ','.join('?' * len(activities))
    sql = '''SELECT c.IDconso, c.date, c.IDindividu, cp.IDfamille, c.IDactivite, c.IDprestation,
      c.IDcategorie_tarif AS categorie_conso, c.IDunite,
      p.IDtarif, p.IDcategorie_tarif AS categorie_prestation,
      p.categorie AS type_prestation, p.montant, p.IDfacture, t.methode
      FROM consommations c
      JOIN comptes_payeurs cp ON cp.IDcompte_payeur=c.IDcompte_payeur
      LEFT JOIN prestations p ON p.IDprestation=c.IDprestation
      LEFT JOIN tarifs t ON t.IDtarif=p.IDtarif
      WHERE c.etat='present' AND c.date>=? AND c.date<=?
      AND c.IDactivite IN (''' + placeholders + ''')
      ORDER BY c.date, c.IDconso'''
    rows = [dict(x) for x in db.execute(sql, (a, b, *activities))]
    # Synthetic mapping of accueil units. The live application needs its own
    # authoritative mapping; a non-QF meal must not override the last accueil.
    result = []
    for r in rows:
        if r['IDunite'] != 1:
            continue
        if r['IDprestation'] is not None and not (
                r['type_prestation'] == 'consommation' and
                r['methode'] == 'qf'):
            continue
        result.append(r)
    return result


def aggregate(db, a=PERIOD[0], b=PERIOD[1], activities=ACTIVITIES, family=False):
    records = qualifying_rows(db, a, b, activities)
    groups = {}
    for r in records:
        k = r['IDfamille'] if family else r['IDindividu']
        old = groups.get(k)
        if old is None or (r['date'], r['IDconso']) > (old['date'], old['IDconso']):
            groups[k] = r
    qf_counts = Counter({code: 0 for code in (*TIER_CODES, QF_NC)})
    tariff_counts = Counter({code: 0 for code in TIER_CODES})
    detail = {}
    for key, r in groups.items():
        qf = current_qf(db, r['IDfamille'], r['date'])
        nominal_tariff = r['IDtarif'] or (100 if r['IDactivite'] == 10 else 110)
        if qf == 'CONFLIT':
            raise AssertionError('Conflicting QF values: audit must not pick arbitrarily')
        tier = tier_for_qf(db, qf, nominal_tariff)
        if tier not in TIER_CODES:
            raise AssertionError('Unclassified tariff: no automatic category')
        qf_group = tier if qf is not None else QF_NC
        qf_counts[qf_group] += 1
        tariff_counts[tier] += 1
        detail[key] = {'date': r['date'], 'family': r['IDfamille'], 'child': r['IDindividu'],
                       'site': SITE_NAMES[r['IDactivite']], 'qf': qf, 'qf_group': qf_group,
                       'tariff_group': tier,
                       'reconstructed': (r['IDprestation'] is None),
                       'historic_tier_attested': False}
    return {'denominator': len(groups), 'qf': dict(qf_counts),
            'tariffs': dict(tariff_counts), 'detail': detail,
            'prestation_missing': sum(v['reconstructed'] for v in detail.values())}


def summarize(db):
    f = aggregate(db, family=True)
    c = aggregate(db, family=False)
    sites = {name: {'families': aggregate(db, activities=(id_,), family=True)['denominator'],
                    'children': aggregate(db, activities=(id_,), family=False)['denominator']}
             for id_, name in SITE_NAMES.items()}
    # IDs are synthetic, but no individual/family ID is exported in this report.
    return {'source_commit': SOURCE_COMMIT, 'period': list(PERIOD),
            'sqlite': sqlite3.sqlite_version,
            'global': {'families': {'total': f['denominator'], 'qf': f['qf'],
                                    'tariffs': f['tariffs']},
                       'children': {'total': c['denominator'], 'qf': c['qf'],
                                    'tariffs': c['tariffs']}},
            'by_site': sites, 'presence_without_prestation': f['prestation_missing'],
            'historic_exact_tariff_line': 'NOT_ATTESTED',
            'caveats': [
                'SQL/SQLite synthetic fixture, not end-to-end Noethys or Windows',
                'wx RechercheQF logic transcribed into an isolated test class (not imported into Noethys)',
                'The inspected wx MemorisePrestation path does not persist IDligne/QF tranche',
                'QF validity dates do not establish actual date of receipt',
                'Current grids cannot prove removed historical categories',
                'Without prestation, tariff tier is reconstructed not observed',
                'IDcategorie_tarif refers to tariff category, not QF band',
            ]}


class Q442Tests(unittest.TestCase):
    def setUp(self):
        self.db = create_fixture()

    def tearDown(self):
        self.db.close()

    def test_population_present_excludes_reservations(self):
        self.assertNotIn(4, aggregate(self.db, family=True)['detail'])

    def test_presence_before_invoice_is_included(self):
        self.assertIn(2, aggregate(self.db, family=True)['detail'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM prestations WHERE IDfacture IS NOT NULL').fetchone()[0], 0)

    def test_presence_without_prestation_included_and_flagged(self):
        d = aggregate(self.db, family=True)['detail']
        self.assertTrue(d[5]['reconstructed'])
        self.assertEqual(d[5]['tariff_group'], 'C')

    def test_one_family_twice_two_children(self):
        fam = aggregate(self.db, family=True)
        children = aggregate(self.db, family=False)
        self.assertEqual(fam['denominator'], 9)
        self.assertEqual(children['denominator'], 11)

    def test_missing_qf_in_social_but_maximum_tariff(self):
        d = aggregate(self.db, family=True)['detail'][2]
        self.assertEqual((d['qf_group'], d['tariff_group']), (QF_NC, 'A'))

    def test_expired_qf_without_backdating(self):
        d = aggregate(self.db, family=True)['detail'][6]
        self.assertEqual((d['qf_group'], d['tariff_group']), (QF_NC, 'A'))

    def test_zero_qf_is_real(self):
        d = aggregate(self.db, family=True)['detail'][7]
        self.assertEqual((d['qf'], d['tariff_group']), (0, 'D'))

    def test_last_presence_drives_qf(self):
        d = aggregate(self.db, family=True)['detail'][1]
        self.assertEqual((d['date'], d['qf'], d['tariff_group']), ('2026-07-30', 850, 'B'))

    def test_month_subperiod_changes_qf(self):
        d = aggregate(self.db, a='2026-07-01', b='2026-07-14', family=True)['detail'][1]
        self.assertEqual((d['qf'], d['tariff_group']), (650, 'C'))

    def test_price_change_not_new_category(self):
        rows = self.db.execute('SELECT montant FROM prestations WHERE IDprestation IN (1102,1104)').fetchall()
        self.assertNotEqual(rows[0][0], rows[1][0])
        d = aggregate(self.db, family=True)['detail'][1]
        self.assertEqual(d['tariff_group'], 'B')

    def test_meal_does_not_override_last_accueil(self):
        rows = qualifying_rows(self.db, *PERIOD)
        self.assertNotIn(5, [r['IDconso'] for r in rows])
        self.assertEqual(aggregate(self.db, family=True)['detail'][1]['date'], '2026-07-30')

    def test_multisite_dedup(self):
        totals = [aggregate(self.db, activities=(i,), family=True)['denominator'] for i in ACTIVITIES]
        self.assertEqual(totals, [7, 3])
        self.assertEqual(aggregate(self.db, family=True)['denominator'], 9)
        self.assertGreater(sum(totals), 9)

    def test_two_units_not_same_statistic(self):
        f = aggregate(self.db, family=True)
        c = aggregate(self.db, family=False)
        self.assertEqual(sum(f['qf'].values()), 9)
        self.assertEqual(sum(c['qf'].values()), 11)
        self.assertEqual(sum(f['tariffs'].values()), 9)
        self.assertEqual(sum(c['tariffs'].values()), 11)

    def test_display_empty_categories(self):
        data = aggregate(self.db, a='2026-11-01', b='2026-11-02', family=True)
        self.assertEqual(data['denominator'], 0)
        self.assertEqual(set(data['tariffs']), set(TIER_CODES))
        self.assertTrue(all(v == 0 for v in data['tariffs'].values()))

    def test_idcategorie_tarif_is_not_qf_band(self):
        rows = self.db.execute('SELECT p.IDcategorie_tarif, p.IDtarif, p.IDfamille '
                               'FROM prestations p WHERE p.IDprestation IN (1104,3101)').fetchall()
        self.assertEqual(rows[0]['IDcategorie_tarif'], rows[1]['IDcategorie_tarif'])
        d = aggregate(self.db, family=True)['detail']
        self.assertNotEqual(d[1]['tariff_group'], d[3]['tariff_group'])

    def test_idtarif_is_not_qf_line(self):
        a = self.db.execute('SELECT IDtarif FROM prestations WHERE IDprestation=2101').fetchone()[0]
        b = self.db.execute('SELECT IDtarif FROM prestations WHERE IDprestation=3101').fetchone()[0]
        self.assertEqual(a, b)
        self.assertNotEqual(aggregate(self.db, family=True)['detail'][2]['tariff_group'],
                            aggregate(self.db, family=True)['detail'][3]['tariff_group'])

    def test_fixture_columns_do_not_store_tariff_line(self):
        fields = {r['name'] for r in self.db.execute('PRAGMA table_info(prestations)')}
        self.assertNotIn('IDligne', fields)
        self.assertNotIn('qf_applique', fields)

    def test_current_grid_can_misclassify_historical_threshold(self):
        # Same saved prestation for family 10/QF 350, with original hypothetical
        # threshold D<=399, is currently interpreted as C (D<=299).
        saved = self.db.execute('SELECT IDtarif, IDcategorie_tarif, montant '
                                'FROM prestations WHERE IDprestation=10101').fetchone()
        reconstructed = aggregate(self.db, family=True)['detail'][10]['tariff_group']
        hypothetical_historical = 'D'
        self.assertEqual(saved['IDtarif'], 100)
        self.assertEqual(reconstructed, 'C')
        self.assertNotEqual(reconstructed, hypothetical_historical)

    def test_recherche_qf_billing_valid_missing_expired_zero(self):
        obj = billed_qf_reference(self.db)
        tariff = tariff_for(self.db, 100)
        at = datetime.date(2026, 7, 20)
        self.assertEqual(obj.RechercheQF(tariff, 1, at), 850)
        self.assertEqual(obj.RechercheQF(tariff, 2, at), 99999.0)
        self.assertEqual(obj.RechercheQF(tariff, 6, at), 99999.0)
        self.assertEqual(obj.RechercheQF(tariff, 7, at), 0)

    def test_recherche_qf_first_match_for_overlap(self):
        vals = {99: [(datetime.date(2026, 1, 1), datetime.date(2026, 12, 31), 650, 1),
                     (datetime.date(2026, 7, 1), datetime.date(2026, 12, 31), 900, 1)]}
        obj = BillingQFReference(vals)
        self.assertEqual(obj.RechercheQF(tariff_for(self.db, 100), 99,
                                         datetime.date(2026, 7, 20)), 650)
        # This is a proof of a limitation, not approval of that behavior.

    def test_groups_consistent_with_common_grid(self):
        bais = aggregate(self.db, activities=(10,), family=True)
        guerche = aggregate(self.db, activities=(11,), family=True)
        self.assertEqual(set(bais['tariffs']), set(guerche['tariffs']))
        self.assertEqual(set(bais['qf']), set(guerche['qf']))


def export_aggregate_csv(path, data):
    rows = []
    for unit in ('families', 'children'):
        total = data['global'][unit]['total']
        for kind in ('qf', 'tariffs'):
            for code, count in data['global'][unit][kind].items():
                rows.append({'population': unit, 'repartition': kind,
                             'categorie': code, 'effectif': count,
                             'pourcentage': round(100.0 * count / total, 2) if total else 0.0})
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['population', 'repartition', 'categorie', 'effectif', 'pourcentage'])
        w.writeheader()
        w.writerows(rows)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default=str(pathlib.Path(__file__).parent),
                    help='Output directory (never a production database path)')
    args = ap.parse_args()
    path = pathlib.Path(args.output).resolve()
    path.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Q442Tests)
    test_names = sorted(x._testMethodName for x in suite)
    report = unittest.TestResult()
    suite.run(report)
    with create_fixture() as db:
        d = summarize(db)
    d['tests'] = {'run': report.testsRun, 'failures': len(report.failures),
                  'errors': len(report.errors), 'skipped': len(report.skipped),
                  'status': 'PASS' if report.wasSuccessful() else 'FAIL',
                  'names': test_names}
    (path / 'resultats_q442.json').write_text(json.dumps(d, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    export_aggregate_csv(path / 'preuve_q442_statistiques_agregees.csv', d)
    if not report.wasSuccessful():
        for test, err in report.failures + report.errors:
            print(test.id() + '\n' + err)
    print('AUDIT-Q442-SQLITE %s %d/%d tests | Families=%d Enfants=%d | sans prestation=%d' % (
        d['tests']['status'], d['tests']['run']-len(report.failures)-len(report.errors),
        d['tests']['run'], d['global']['families']['total'],
        d['global']['children']['total'], d['presence_without_prestation']))
    print('STOP-GATE: historical exact tranche cannot be attested with retained invoice/prestation columns')
    return int(not report.wasSuccessful())


if __name__ == '__main__':
    raise SystemExit(main())
