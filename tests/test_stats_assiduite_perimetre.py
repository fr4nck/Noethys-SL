# -*- coding: utf-8 -*-
"""Q445 J5: anonymised read-only site preflight on wholly synthetic SQLite."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'noethys'))

from Utils import UTILS_Stats_assiduite as stats
from Utils import UTILS_Stats_assiduite_perimetre as pre
from tests.test_stats_assiduite_synthetic import DB, fixture


def populate_metadata(db):
    db.executescript("""
        CREATE TABLE activites (IDactivite INT PRIMARY KEY, nom TEXT);
        CREATE TABLE unites (IDunite INT PRIMARY KEY, IDactivite INT, nom TEXT, repas INT);
        CREATE TABLE groupes (IDgroupe INT PRIMARY KEY, IDactivite INT, nom TEXT);
        INSERT INTO activites VALUES (10,'ALSH FICTIF'),(20,'AUTRE FICTIF');
        INSERT INTO unites VALUES
            (1,10,'Accueil matin',0),(2,10,'Accueil soir',0),
            (3,10,'Repas',1),(10,20,'Accueil autre activite',0);
        INSERT INTO groupes VALUES
            (101,10,'Groupe A'),(102,10,'Groupe B'),
            (103,10,'Groupe C'),(201,20,'Autre groupe');
    """)


def approved():
    return stats.Configuration(
        activites=(10,), unites_accueil={10:(1,2)},
        regles_sites=(
            stats.RegleSite('Site Alpha',10,1,(101,)),
            stats.RegleSite('Site Alpha',10,2,(101,)),
            stats.RegleSite('Site Beta',10,1,(102,)),
            stats.RegleSite('Site Beta',10,2,(102,)),
            stats.RegleSite('Site Gamma',10,1,(103,)),
        )
    )


class Preflight(unittest.TestCase):
    def setUp(self):
        self.cn=fixture()
        self.addCleanup(self.cn.close)
        populate_metadata(self.cn)
        self.db=DB(self.cn)

    def report(self, cfg=None, start='2024-01-01', end='2026-12-31'):
        return pre.precontroler(self.db, cfg if cfg is not None else approved(),
                                start, end)

    def test_01_aggregated_no_names_no_automatic_approval(self):
        v=self.report()
        self.assertEqual(v['lignes_total'],20)
        self.assertEqual(v['verdicts'],{'OK':19,'UNITE_EXCLUE_A_VERIFIER':1})
        self.assertEqual(v['etats_inconnus'],{'nonstandard':1})
        self.assertFalse(v['homologue'])
        self.assertFalse(v['candidat_a_approbation_humaine'])
        self.assertEqual(v['requetes_sql'],4)
        self.assertEqual(len(self.db.sql),4)
        self.assertTrue(all(s.startswith('SELECT ') for s in self.db.sql))
        self.assertNotIn('IDindividu',json.dumps(v))
        self.assertNotIn('IDfamille',json.dumps(v))
        self.assertEqual(v['sites_candidats']['Site Gamma'],1)

    def test_02_requires_human_approval_even_with_full_mapping(self):
        self.cn.execute("UPDATE consommations SET etat='reservation' WHERE IDconso=17")
        v=self.report()
        self.assertTrue(v['candidat_a_approbation_humaine'])
        self.assertFalse(v['homologue'])
        self.assertEqual(v['catalogue_anomalies'],[])

    def test_03_missing_group_is_not_guessed(self):
        self.cn.execute("UPDATE consommations SET IDgroupe=777 WHERE IDconso=1")
        v=self.report()
        self.assertEqual(v['verdicts']['GROUPE_INCONNU'],1)
        self.assertNotIn('Site Alpha',
                         [row['site_propose'] for row in v['observations']
                          if row['groupe']==777])
        self.assertFalse(v['candidat_a_approbation_humaine'])

    def test_04_cross_activity_group_is_rejected(self):
        self.cn.execute("UPDATE consommations SET IDgroupe=201 WHERE IDconso=1")
        v=self.report()
        self.assertEqual(v['verdicts']['GROUPE_INCONNU'],1)
        self.assertFalse(v['candidat_a_approbation_humaine'])

    def test_05_wrong_activity_unit_is_rejected(self):
        self.cn.execute("UPDATE unites SET IDactivite=20 WHERE IDunite=2")
        v=self.report()
        self.assertIn('UNITE_AUTRE_ACTIVITE:2',v['catalogue_anomalies'])
        self.assertGreater(v['verdicts']['UNITE_AUTRE_ACTIVITE'],0)
        self.assertFalse(v['candidat_a_approbation_humaine'])

    def test_06_configured_group_not_in_catalogue_is_reported(self):
        c=stats.Configuration((10,),{10:(1,2)},(
            stats.RegleSite('Example',10,1,(888,)),
            stats.RegleSite('Example',10,2,(101,)),
        ))
        v=self.report(c)
        self.assertIn('REGLE_GROUPE_INVALIDE:888',v['catalogue_anomalies'])
        self.assertFalse(v['candidat_a_approbation_humaine'])

    def test_07_no_site_rules_does_not_infer_sites(self):
        v=self.report(stats.Configuration((10,),{10:(1,2)},()))
        self.assertEqual(v['sites_candidats'],{})
        self.assertEqual(v['verdicts']['SITES_NON_CONFIGURES'],19)
        self.assertFalse(v['homologue'])

    def test_08_no_approved_accueil_units_does_not_infer(self):
        v=self.report(stats.Configuration((10,),{},()))
        self.assertEqual(v['sites_candidats'],{})
        self.assertEqual(v['verdicts']['PERIMETRE_ACCUEIL_NON_VALIDE'],20)
        self.assertFalse(v['candidat_a_approbation_humaine'])

    def test_09_empty_range_cannot_homologate(self):
        v=self.report(start='2020-01-01',end='2020-12-31')
        self.assertEqual(v['lignes_total'],0)
        self.assertFalse(v['candidat_a_approbation_humaine'])
        self.assertEqual(v['sites_candidats'],{})

    def test_10_invalid_dates_rejected_before_first_query(self):
        with self.assertRaises(ValueError):
            self.report(start='2027-01-01',end='2026-01-01')
        self.assertEqual(self.db.sql,[])

    def test_11_unknown_activity_catalogue_is_not_approved(self):
        c=stats.Configuration((99,),{99:(1,)},())
        v=self.report(c)
        self.assertIn('ACTIVITE_ABSENTE:99',v['catalogue_anomalies'])
        self.assertFalse(v['candidat_a_approbation_humaine'])

    def test_12_no_write_even_with_failing_mapping(self):
        previous=self.cn.total_changes
        self.cn.execute('PRAGMA query_only=ON')
        self.report()
        self.assertEqual(self.cn.total_changes,previous)

    def test_13_no_automatic_meal_label_assumption(self):
        v=self.report()
        excluded=[row for row in v['observations']
                  if row['verdict']=='UNITE_EXCLUE_A_VERIFIER']
        self.assertEqual(len(excluded),1)
        self.assertEqual(excluded[0]['unite_nom'],'Repas')
        self.assertEqual(excluded[0]['repas_inclus'],1)
        self.assertIsNone(excluded[0]['site_propose'])


if __name__ == '__main__':
    unittest.main()
