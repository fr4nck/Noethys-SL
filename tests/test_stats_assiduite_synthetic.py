# -*- coding: utf-8 -*-
"""SQLite-only tests for synthetic, anonymised attendance data."""
import importlib.util
import sqlite3
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'noethys' / 'Utils' / 'UTILS_Stats_assiduite.py'
SPEC = importlib.util.spec_from_file_location('stats_assiduite_test_module', SOURCE)
import sys
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class DB:
    def __init__(self, connection, date_objects=False):
        self.connection = connection
        self.sql = []
        self.rows = None
        self.date_objects = date_objects
    def ExecuterReq(self, sql):
        assert sql.upper().startswith('SELECT '), 'read-only guarantee'
        self.sql.append(sql)
        self.rows = self.connection.execute(sql).fetchall()
        return True
    def ResultatReq(self):
        if not self.date_objects:
            return self.rows
        return [tuple((date.fromisoformat(val) if i == 1 and isinstance(val,str) else val)
                      for i, val in enumerate(row)) for row in self.rows]


def fixture():
    db = sqlite3.connect(':memory:')
    db.execute('''CREATE TABLE consommations (
        IDconso INTEGER PRIMARY KEY, date TEXT, IDindividu INTEGER,
        IDactivite INTEGER, IDunite INTEGER, IDgroupe INTEGER, etat TEXT)''')
    rows = [
        # 2024: 4 distinct child-days (one with both present and absent unjustified)
        (1,'2024-01-05',11,10,1,101,'present'),
        (2,'2024-01-05',11,10,2,101,'present'),  # duplicate child-day
        (3,'2024-01-06',12,10,1,101,'absentj'),
        (4,'2024-01-07',13,10,1,102,'absenti'),
        (5,'2024-01-08',14,10,1,101,'present'),
        (6,'2024-01-08',14,10,2,101,'absentj'),  # mixed; no forced classification
        (7,'2024-01-09',15,10,1,101,'reservation'),  # not an absence
        (8,'2024-01-10',15,10,1,101,'attente'),
        (9,'2024-01-11',15,10,1,101,'refus'),
        # 2025: two justified rows on the same child-day count once
        (10,'2025-07-02',12,10,1,101,'absentj'),
        (11,'2025-07-02',12,10,2,101,'absentj'),
        (12,'2025-07-03',13,10,1,102,'absenti'),
        (13,'2025-07-04',11,10,1,101,'present'),
        (14,'2025-07-04',11,10,3,101,'present'),  # optional meal unit, exclude
        (15,'2025-07-04',11,20,10,201,'present'),  # another activity, global child/day unique
        (16,'2025-07-05',11,10,1,101,'reservation'),
        (17,'2025-07-06',15,10,1,101,'nonstandard'),
        # 2026: third site Moutiers same physical activity, group different
        (18,'2026-05-01',15,10,1,103,'present'),
        (19,'2026-05-02',13,10,1,102,'absenti'),
        (20,'2026-05-02',13,10,2,102,'absenti'),
        (21,'2026-05-03',11,10,1,101,'reservation'),
    ]
    db.executemany('INSERT INTO consommations VALUES (?,?,?,?,?,?,?)', rows)
    db.commit()
    return db


def conf(with_sites=True, with_approved=True):
    rules = (MOD.RegleSite('Bais',10,1,(101,)),
             MOD.RegleSite('Bais',10,2,(101,)),
             MOD.RegleSite('La Guerche',10,1,(102,)),
             MOD.RegleSite('La Guerche',10,2,(102,)),
             MOD.RegleSite('Moutiers',10,1,(103,))) if with_sites else ()
    return MOD.Configuration(
        activites=(10,),
        unites_accueil={10:(1,2)} if with_approved else {},
        regles_sites=rules,
    )


class AssiduiteTests(unittest.TestCase):
    def setUp(self):
        self.connection = fixture()
        self.addCleanup(self.connection.close)
        self.db = DB(self.connection)
    def read(self, from_date='2024-01-01', to_date='2026-12-31', configuration=None):
        return MOD.Lecteur(self.db, configuration or conf()).lire(from_date,to_date)

    def test_01_dates_years_and_source(self):
        data=self.read()
        self.assertEqual(list(data['annees']),['2024','2025','2026'])
        self.assertTrue(all(x['annee_complete_dans_periode'] for x in data['annees'].values()))
        self.assertEqual(data['requetes_sql'],1)
        self.assertEqual(len(self.db.sql),1)
    def test_02_pointed_versus_reservations(self):
        data=self.read()
        self.assertEqual(data['global']['lignes']['reservation'],3)
        self.assertEqual(data['global']['lignes']['attente'],1)
        self.assertEqual(data['global']['lignes']['refus'],1)
        self.assertEqual(data['global']['lignes']['inconnu'],1)
        self.assertEqual(data['etats_non_reconnus'],{'nonstandard':1})
    def test_03_annual_child_days_dedup(self):
        years=self.read()['annees']
        self.assertEqual(years['2024']['journees_enfants'],{'present':1,'absentj':1,'absenti':1,'mixte':1})
        self.assertEqual(years['2025']['journees_enfants'],{'present':1,'absentj':1,'absenti':1,'mixte':0})
        self.assertEqual(years['2026']['journees_enfants'],{'present':1,'absentj':0,'absenti':1,'mixte':0})
    def test_04_annual_absence_percent_and_mixed_excluded(self):
        data=self.read()
        self.assertEqual(data['annees']['2024']['taux_absence_pct'],66.67)
        self.assertEqual(data['annees']['2025']['taux_absence_pct'],66.67)
        self.assertEqual(data['annees']['2026']['taux_absence_pct'],50.0)
        self.assertEqual(data['annees']['2024']['journees_pointees'],4)
        self.assertEqual(data['annees']['2024']['journees_clairement_classees'],3)
    def test_05_no_cancelled_from_deleted_rows(self):
        data=self.read()
        self.assertIsNone(data['annulations']['nombre'])
        self.assertNotIn('annule',data['global']['lignes'])
        self.assertEqual(data['annulations']['statut'],'HISTORIQUE_NON_RECONSTRUCTIBLE')
    def test_06_zero_years_have_no_fabricated_rate(self):
        data=self.read('2021-01-01','2026-12-31')
        self.assertEqual(data['annees']['2022']['journees_pointees'],0)
        self.assertIsNone(data['annees']['2022']['taux_absence_pct'])
    def test_07_partial_year_comparison_flag(self):
        data=self.read('2024-10-01','2025-03-31')
        self.assertFalse(data['annees']['2024']['annee_complete_dans_periode'])
        self.assertFalse(data['annees']['2025']['annee_complete_dans_periode'])
    def test_08_group_by_physical_site_with_approved_rules(self):
        data=self.read()
        self.assertEqual(set(data['sites']),{'Bais','La Guerche','Moutiers'})
        self.assertEqual(data['sites']['Moutiers']['journees_enfants']['present'],1)
        self.assertEqual(data['sites']['La Guerche']['journees_enfants']['absenti'],3)
    def test_09_unit_whitelist_excludes_meals(self):
        data=self.read()
        self.assertEqual(data['unites_exclues'],1)  # activity 20 is filtered by SQL, meal unit 3 is excluded
    def test_10_without_mapping_no_physical_site_inferred(self):
        data=self.read(configuration=conf(False))
        self.assertEqual(data['sites'],{})
        self.assertFalse(data['sites_qualifies'])
    def test_11_all_units_warns_of_mixed_services(self):
        data=self.read(configuration=conf(False,False))
        self.assertIn('toutes unit',data['perimetre_unites'])
        self.assertEqual(data['global']['journees_enfants'],self.read()['global']['journees_enfants'])
    def test_12_invalid_site_group_fails_closed(self):
        self.connection.execute('UPDATE consommations SET IDgroupe=777 WHERE IDconso=1')
        with self.assertRaises(MOD.PerimetreIncomplet):self.read()
    def test_13_ambiguous_site_rules_rejected(self):
        with self.assertRaises(ValueError):
            MOD.Configuration((10,),{10:(1,)},(MOD.RegleSite('Bais',10,1,None),
                                                MOD.RegleSite('Moutiers',10,1,(101,))))
    def test_14_site_mapping_requires_approved_units(self):
        with self.assertRaises(ValueError):
            MOD.Configuration((10,),{},(MOD.RegleSite('Bais',10,1,None),))
    def test_15_missing_child_fails_closed(self):
        self.connection.execute('UPDATE consommations SET IDindividu=NULL WHERE IDconso=1')
        with self.assertRaises(ValueError):self.read()
    def test_16_selection_restricts_activity(self):
        data=self.read()
        self.assertEqual(set(data['activites']),{'10'})
        self.assertTrue(all('20' not in sql.split('IN ')[-1] for sql in self.db.sql))
    def test_17_read_only_sqlite_changes_unmodified(self):
        original=self.connection.total_changes
        self.connection.execute('PRAGMA query_only=ON')
        self.read()
        self.assertEqual(self.connection.total_changes,original)
    def test_18_mysql_date_object_conversion(self):
        expected=self.read()
        bridge=DB(self.connection,date_objects=True)
        actual=MOD.Lecteur(bridge,conf()).lire('2024-01-01','2026-12-31')
        self.assertEqual(actual['global'],expected['global'])
        self.assertEqual(actual['sites'],expected['sites'])
    def test_19_date_inverted_rejected_before_sql(self):
        with self.assertRaises(ValueError):self.read('2026-01-01','2025-01-01')
        self.assertEqual(self.db.sql,[])
    def test_20_no_personal_ids_in_returned_json(self):
        import json
        serialized=json.dumps(self.read())
        for key in ('IDindividu','IDfamille','IDconso','prenom','nomTitulaires'):
            self.assertNotIn('"%s"'%key, serialized)
    def test_21_mixed_child_day_cannot_be_assigned_j(self):
        x=self.read('2024-01-08','2024-01-08')['global']
        self.assertEqual(x['journees_enfants']['mixte'],1)
        self.assertEqual(x['journees_enfants']['absentj'],0)
        self.assertIsNone(x['taux_absence_pct'])
    def test_22_unknown_status_does_not_inflate_absences(self):
        v=self.read('2025-07-06','2025-07-06')['global']
        self.assertEqual(v['lignes']['inconnu'],1)
        self.assertEqual(v['journees_pointees'],0)
    def test_23_year_by_site_independent_of_global(self):
        v=self.read()
        self.assertEqual(v['sites_annees']['Moutiers']['2026']['journees_enfants']['present'],1)
        self.assertEqual(v['sites_annees']['Moutiers']['2025']['journees_pointees'],0)
    def test_24_no_sql_dml_generated(self):
        self.read()
        self.assertTrue(all(s.startswith('SELECT ') and 'UPDATE' not in s
                            and 'DELETE' not in s for s in self.db.sql))


if __name__=='__main__':
    unittest.main()
