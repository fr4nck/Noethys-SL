# -*- coding: utf-8 -*-
"""Real disposable localhost MySQL 5.7 attendance parity (synthetic data)."""
from __future__ import annotations

import os
import re
import unittest
from secrets import token_hex
from tests.test_stats_assiduite_synthetic import fixture,conf,DB,MOD
from tests.test_stats_assiduite_perimetre import approved, populate_metadata
from Utils import UTILS_Stats_assiduite_perimetre as SITE_PREFLIGHT

GUARD = re.compile(r'^zz_assiduite_[0-9a-f]{16}$')


@unittest.skipUnless(os.environ.get('NOETHYS_ASSIDUITE_MYSQL_EXIGER')=='1',
                     'Require explicit disposable localhost MySQL 5.7 opt-in')
class AssiduiteMySQL57(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import MySQLdb
        host=os.environ.get('NOETHYS_TEST_MYSQL_HOST','').strip().lower()
        port=int(os.environ.get('NOETHYS_TEST_MYSQL_PORT','0'))
        if host!='127.0.0.1' or port!=3402:
            raise RuntimeError('Refuse any host except 127.0.0.1:3402')
        cls.db=MySQLdb.connect(host=host,port=port,
            user=os.environ['NOETHYS_TEST_MYSQL_USER'],
            passwd=os.environ['NOETHYS_TEST_MYSQL_PASSWORD'],
            charset='utf8mb4',connect_timeout=5)
        cls.db.autocommit(False)
        cls.schema='zz_assiduite_'+token_hex(8)
        assert GUARD.fullmatch(cls.schema)
        try:
            with cls.db.cursor() as cur:
                cur.execute('SELECT VERSION()')
                version,=cur.fetchone()
                if not version.startswith('5.7.'):
                    raise RuntimeError('Need actual MySQL 5.7, got '+version)
                cls.mysql_version=version
                cur.execute('CREATE DATABASE `%s` CHARACTER SET utf8mb4' % cls.schema)
            cls.db.select_db(cls.schema)
            cls.source=fixture()
            populate_metadata(cls.source)
            with cls.db.cursor() as cur:
                cur.execute('''CREATE TABLE consommations (
                    IDconso INT PRIMARY KEY,
                    date DATE,
                    IDindividu INT,
                    IDactivite INT,
                    IDunite INT,
                    IDgroupe INT,
                    etat VARCHAR(30)
                ) ENGINE=InnoDB''')
                records=[tuple(row) for row in cls.source.execute(
                    'SELECT IDconso,date,IDindividu,IDactivite,IDunite,IDgroupe,etat FROM consommations')]
                cur.executemany('INSERT INTO consommations VALUES (%s,%s,%s,%s,%s,%s,%s)',records)
                cur.execute('CREATE TABLE activites (IDactivite INT PRIMARY KEY, nom VARCHAR(200)) ENGINE=InnoDB')
                cur.execute('CREATE TABLE unites (IDunite INT PRIMARY KEY, IDactivite INT, nom VARCHAR(200), repas INT) ENGINE=InnoDB')
                cur.execute('CREATE TABLE groupes (IDgroupe INT PRIMARY KEY, IDactivite INT, nom VARCHAR(200)) ENGINE=InnoDB')
                for table, fields in (('activites','IDactivite,nom'),
                                      ('unites','IDunite,IDactivite,nom,repas'),
                                      ('groupes','IDgroupe,IDactivite,nom')):
                    records=[tuple(row) for row in cls.source.execute(
                        'SELECT '+fields+' FROM '+table+' ORDER BY 1')]
                    fmt=','.join(['%s']*len(records[0]))
                    cur.executemany('INSERT INTO '+table+' VALUES ('+fmt+')',records)
            cls.db.commit()
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        source=getattr(cls,'source',None)
        if source is not None:
            source.close();cls.source=None
        db=getattr(cls,'db',None)
        if db is not None:
            if hasattr(cls,'schema') and GUARD.fullmatch(cls.schema):
                with db.cursor() as cur:
                    cur.execute('DROP DATABASE IF EXISTS `%s`'%cls.schema)
            db.close();cls.db=None

    def tearDown(self):
        self.db.rollback()

    def get(self,cn=None):
        cn=cn or self.db
        if cn is self.db:
            class Bridge:
                def __init__(self,db):
                    self.db=db
                    self.sql=[];self.rows=None
                def ExecuterReq(self,sql):
                    assert sql.startswith('SELECT ')
                    self.sql.append(sql)
                    with self.db.cursor() as cur:
                        cur.execute(sql)
                        self.rows=cur.fetchall()
                    return True
                def ResultatReq(self):return self.rows
            bridge=Bridge(cn)
        else:
            bridge=DB(cn)
        result=MOD.Lecteur(bridge,conf()).lire('2024-01-01','2026-12-31')
        return result,bridge.sql

    def test_01_actual_mysql_5_7(self):
        self.assertTrue(self.mysql_version.startswith('5.7.'))

    def test_02_exact_parity_2024_2026(self):
        ref,_=self.get(self.source)
        current,sql=self.get()
        for key in ('global','annees','annees_scolaires','mois','sites',
                    'sites_annees','sites_annees_scolaires','activites'):
            self.assertEqual(current[key],ref[key],key)
        self.assertEqual(len(sql),1)

    def test_03_separate_cancelled_from_unpointed(self):
        current,_=self.get()
        self.assertEqual(current['global']['lignes']['reservation'],3)
        self.assertIsNone(current['annulations']['nombre'])
        self.assertEqual(current['global']['journees_enfants']['mixte'],1)

    def test_04_qf_and_billing_not_touched(self):
        current,_=self.get()
        self.assertEqual(current['requetes_sql'],1)
        self.assertEqual(current['unites_exclues'],1)

    def test_05_invalid_site_group_fails(self):
        with self.db.cursor() as cur:
            cur.execute('UPDATE consommations SET IDgroupe=999 WHERE IDconso=1')
        with self.assertRaises(MOD.PerimetreIncomplet):
            self.get()

    def test_06_date_range_cross_engine(self):
        with self.db.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM consommations')
            count,=cur.fetchone()
        self.assertEqual(count,21)
        source,_=self.get(self.source)
        actual,_=self.get()
        self.assertEqual(source['annees']['2025'],actual['annees']['2025'])
        self.assertEqual(source['annees_scolaires']['2024-2025'],
                         actual['annees_scolaires']['2024-2025'])

    def test_07_school_year_boundaries_and_site_parity(self):
        source,_=self.get(self.source)
        actual,_=self.get()
        self.assertEqual(list(actual['annees_scolaires']),
            ['2023-2024','2024-2025','2025-2026','2026-2027'])
        self.assertEqual(actual['sites_annees_scolaires'],
                         source['sites_annees_scolaires'])
        self.assertEqual(actual['annees_scolaires']['2026-2027']
                         ['journees_pointees'],0)

    def test_08_annual_coverage_is_not_inferred_from_pointed_days(self):
        source,_=self.get(self.source)
        actual,_=self.get()
        self.assertEqual(source['annees_scolaires'],actual['annees_scolaires'])
        self.assertFalse(actual['annees_scolaires']['2023-2024']
                         ['comparable_annee_entiere'])
        self.assertTrue(actual['annees_scolaires']['2025-2026']
                        ['annee_scolaire_complete_dans_periode'])


    def test_09_site_preflight_parity_sqlite_mysql(self):
        class Bridge:
            def __init__(self, cn):
                self.cn=cn
                self.sql=[]
                self.rows=[]
            def ExecuterReq(self, query):
                if not query.startswith('SELECT '):
                    raise AssertionError('Read-only SELECT required')
                self.sql.append(query)
                with self.cn.cursor() as cur:
                    cur.execute(query)
                    self.rows=cur.fetchall()
                return True
            def ResultatReq(self):
                return self.rows

        a=SITE_PREFLIGHT.precontroler(DB(self.source),approved(),
                '2024-01-01','2026-12-31')
        bridge=Bridge(self.db)
        b=SITE_PREFLIGHT.precontroler(bridge,approved(),
                '2024-01-01','2026-12-31')
        self.assertEqual(a,b)
        self.assertEqual(a['requetes_sql'],4)
        self.assertEqual(a['lignes_total'],20)
        self.assertEqual(a['verdicts']['UNITE_EXCLUE_A_VERIFIER'],1)
        self.assertFalse(b['homologue'])
        self.assertTrue(all(q.startswith('SELECT ') for q in bridge.sql))

    def test_10_site_preflight_never_infers_unapproved_mapping(self):
        cfg=MOD.Configuration((10,),{10:(1,2)},())
        class Bridge:
            def __init__(self,cn):
                self.cn=cn
            def ExecuterReq(self,query):
                with self.cn.cursor() as cur:
                    cur.execute(query)
                    self.rows=cur.fetchall()
                return True
            def ResultatReq(self):
                return self.rows
        r=SITE_PREFLIGHT.precontroler(Bridge(self.db),cfg,
                '2024-01-01','2026-12-31')
        self.assertEqual(r['sites_candidats'],{})
        self.assertFalse(r['homologue'])
        self.assertFalse(r['candidat_a_approbation_humaine'])


if __name__=='__main__':
    unittest.main()
