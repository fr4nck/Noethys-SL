#!/usr/bin/env python3
# -*- coding: ascii -*-
"""J3 acceptance characterization. All SQL data synthetic and in memory."""
import collections
import datetime
import json
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parent/'source_j2'))
from fixture_q442_precedente import create_fixture, PERIOD
import extraits_wx_isoles as source_j2
from q442_lecteur import (Configuration,Lecteur,QF_UNKNOWN,QF_REVIEW,QF_OUTSIDE,
                          TARIF_UNKNOWN,TARIF_TIE,TARIF_UNPROVEN)


class FakeDB:
    def __init__(self, cn):
        self.cn=cn
        self.sql=[]
        self.res=[]
    def ExecuterReq(self,q):
        self.sql.append(q)
        self.res=self.cn.execute(q).fetchall()
        return True
    def ResultatReq(self):
        return self.res


def config():
    return Configuration(sites={10:'Bais',11:'La Guerche'},
      unites_accueil={10:(1,),11:(1,)},
      tarifs_accueil={10:(100,),11:(110,)},
      libelles={'1':'A','2':'B','3':'C','4':'D'},
      categories_historiques=('E historique',))


def env():
    cn=create_fixture()
    bridge=FakeDB(cn)
    reader=Lecteur(bridge,config())
    return cn,bridge,reader


class Jalon3Tests(unittest.TestCase):
    def setUp(self):
        self.cn,self.bridge,self.reader=env()
    def tearDown(self):
        self.cn.close()
    def lire(self,a=PERIOD[0],b=PERIOD[1]):
        return self.reader.lire(a,b)
    def test_01_reader_date_iso(self):
        self.assertEqual(self.lire()['dates'],['2026-07-01','2026-07-31'])
    def test_02_den_familles(self):
        self.assertEqual(self.lire()['global']['familles']['total'],9)
    def test_03_den_enfants(self):
        self.assertEqual(self.lire()['global']['enfants']['total'],11)
    def test_04_barres_qf_somme_total(self):
        x=self.lire()['global']['familles']
        self.assertEqual(sum(x['qf'].values()),x['total'])
    def test_05_barres_tarif_somme_total(self):
        x=self.lire()['global']['familles']
        self.assertEqual(sum(x['tarifs_indicatifs'].values()),x['total'])
    def test_06_compte_non_communique(self):
        self.assertEqual(self.lire()['global']['familles']['qf'][QF_UNKNOWN],2)
    def test_07_qf_non_communique_tarif_max_indicatif(self):
        x=self.lire()['global']['familles']
        self.assertEqual(x['tarifs_indicatifs']['A'],3)
        self.assertEqual(x['qf']['A'],1)
    def test_08_tarifs_tous_libelles(self):
        self.assertEqual(set(self.lire()['global']['familles']['tarifs_indicatifs']),
                         {'A','B','C','D','E historique'})
    def test_09_tarif_historique_zero(self):
        self.assertEqual(self.lire()['global']['familles']['tarifs_indicatifs']['E historique'],0)
    def test_10_exclut_reservations(self):
        self.assertEqual(self.lire()['global']['familles']['total'],9)
        self.assertNotEqual(self.lire()['global']['familles']['total'],10)
    def test_11_changement_qf_retenir_derniere_presence(self):
        self.assertEqual(self.lire()['global']['familles']['qf']['B'],2)
    def test_12_fin_juillet_repas_ne_devient_derniere_presence(self):
        x=self.lire('2026-07-31','2026-07-31')
        self.assertEqual(x['global']['familles']['total'],0)
    def test_13_periode_courte_change_qf(self):
        x=self.lire('2026-07-01','2026-07-14')
        self.assertEqual(x['global']['familles']['qf'].get('B',0),0)
        self.assertGreater(x['global']['familles']['qf']['C'],0)
    def test_14_0_qf_est_qf_reel(self):
        x=self.lire('2026-07-15','2026-07-15')
        self.assertEqual(x['global']['familles']['qf']['D'],1)
    def test_15_prestation_non_facturee_comptee(self):
        self.assertEqual(self.cn.execute('SELECT count(*) FROM prestations WHERE IDfacture IS NOT NULL').fetchone()[0],0)
        self.assertEqual(self.lire()['global']['enfants']['total'],11)
    def test_16_presence_sans_prestation_preservee(self):
        x=self.lire()['global']['familles']
        self.assertIn('PRESTATION_ABSENTE',x['anomalies'])
        self.assertGreaterEqual(x['anomalies']['PRESTATION_ABSENTE'],1)
    def test_17_une_famille_sur_deux_sites_une_fois_global(self):
        x=self.lire()
        self.assertEqual((x['sites']['Bais']['familles']['total'],x['sites']['La Guerche']['familles']['total']), (7,3))
        self.assertEqual(x['global']['familles']['total'],9)
    def test_18_une_famille_somme_sites_peut_depasser_global(self):
        x=self.lire()
        self.assertGreater(sum(s['familles']['total'] for s in x['sites'].values()),x['global']['familles']['total'])
    def test_19_tableau_par_site_famille_consistant(self):
        x=self.lire()['sites']
        for val in x.values():
            f=val['familles']
            self.assertEqual(sum(f['qf'].values()),f['total'])
            self.assertEqual(sum(f['tarifs_indicatifs'].values()),f['total'])
    def test_20_tableau_par_site_enfant_consistant(self):
        x=self.lire()['sites']
        for val in x.values():
            f=val['enfants']
            self.assertEqual(sum(f['qf'].values()),f['total'])
            self.assertEqual(sum(f['tarifs_indicatifs'].values()),f['total'])
    def test_21_no_sensitive_records_in_aggregate(self):
        x=json.dumps(self.lire(),ensure_ascii=True)
        for word in ('IDfamille','IDindividu','nom','prenom'):
            self.assertNotIn('"'+word+'"',x)
    def test_22_all_sql_read_only(self):
        self.lire()
        self.assertTrue(self.bridge.sql)
        self.assertTrue(all(q.lstrip().upper().startswith('SELECT ') for q in self.bridge.sql))
    def test_23_reader_rejects_delete(self):
        with self.assertRaises(ValueError):
            self.reader._read('DELETE FROM familles')
    def test_24_sqlite_authorizer_rejects_write_after_fixture(self):
        deny={sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE,
              sqlite3.SQLITE_ALTER_TABLE,sqlite3.SQLITE_DROP_TABLE}
        self.cn.set_authorizer(lambda action,a,b,c,d: sqlite3.SQLITE_DENY if action in deny else sqlite3.SQLITE_OK)
        self.lire()
    def test_25_empty_period_cat_zero(self):
        x=self.lire('2026-02-01','2026-02-28')
        self.assertEqual(x['global']['familles']['total'],0)
        self.assertEqual(x['global']['familles']['tarifs_indicatifs']['A'],0)
        self.assertEqual(x['global']['familles']['tarifs_indicatifs']['E historique'],0)
    def test_26_sql_iso_injection_rejected(self):
        with self.assertRaises(ValueError):self.lire('2026-07-01\';DELETE FROM familles;','2026-07-31')
    def test_27_bad_activity_rejected(self):
        with self.assertRaises(ValueError):Configuration({10:'Bais'},{10:(1,)},{11:(100,)})
    def test_28_missing_unit_whitelist_rejected(self):
        with self.assertRaises(ValueError):Configuration({10:'Bais'},{10:()},{10:(100,)})
    def test_29_nonint_activity_rejected(self):
        with self.assertRaises(ValueError):Configuration({'10':'Bais'},{'10':(1,)},{'10':(100,)})
    def test_30_missing_tariff_rejected(self):
        with self.assertRaises(ValueError):Configuration({10:'Bais'},{10:(1,)},{10:()})
    def test_31_tarif_and_categorie_not_equivalent(self):
        a=self.cn.execute('SELECT IDcategorie_tarif FROM prestations WHERE IDprestation=2101').fetchone()[0]
        b=self.cn.execute('SELECT IDcategorie_tarif FROM prestations WHERE IDprestation=3101').fetchone()[0]
        self.assertEqual(a,b)
        self.assertEqual((self.lire()['global']['familles']['tarifs_indicatifs']['A'],
                          self.lire()['global']['familles']['tarifs_indicatifs']['D']),(3,2))
    def test_32_audit_marks_historical_unproven(self):
        x=self.lire()['global']['familles']
        self.assertEqual(x['categories_tarif_attestees'],0)
        self.assertEqual(x['categories_historiques_non_attestees'],9)
    def test_33_duplicate_performance_with_same_date_child_no_double(self):
        self.cn.execute('INSERT INTO consommations VALUES(200,\'2026-07-20\',\'present\',10,11,1001,1,1102,1)')
        self.assertEqual(self.lire()['global']['enfants']['total'],11)
    def test_34_qf_later_updated_after_last_presence_no_backdating(self):
        self.cn.execute('INSERT INTO quotients VALUES(90,1,1,\'2026-08-01\',\'2026-12-31\',1300)')
        x=self.lire('2026-07-01','2026-07-14')
        self.assertEqual(x['global']['familles']['qf']['C'],3)
    def test_35_multi_type_different_value_selected_by_tariff(self):
        self.cn.execute('INSERT INTO quotients VALUES(90,8,2,\'2026-01-01\',\'2026-12-31\',200)')
        x=self.lire('2026-07-16','2026-07-16')
        self.assertEqual(x['global']['familles']['qf']['A'],1)
    def test_36_same_qf_multiple_types_not_globally_inferred(self):
        # Explicit tariff type 1 correctly resolves 1000 despite type 2 match.
        self.cn.execute('INSERT INTO quotients VALUES(90,8,2,\'2026-01-01\',\'2026-12-31\',1000)')
        x=self.lire('2026-07-16','2026-07-16')
        self.assertEqual(x['global']['familles']['qf']['A'],1)
    def test_37_same_type_overlap_different_values_flag(self):
        self.cn.execute('INSERT INTO quotients VALUES(90,8,1,\'2026-07-01\',\'2026-12-31\',200)')
        x=self.lire('2026-07-16','2026-07-16')
        self.assertEqual(x['global']['familles']['qf'][QF_REVIEW],1)
    def test_38_missing_qf_not_reclassified_as_true_99999(self):
        x=self.lire('2026-07-08','2026-07-08')
        self.assertEqual(x['global']['familles']['qf'][QF_UNKNOWN],1)
        self.assertEqual(x['global']['familles']['tarifs_indicatifs']['A'],1)
    def test_39_read_only_not_call_billing_calculation(self):
        self.lire()
        s=' '.join(self.bridge.sql)
        self.assertNotIn('INSERT INTO',s)
        self.assertNotIn('UPDATE prestations',s)
    def test_40_presences_with_mismatched_prestation_flagged(self):
        self.cn.execute('UPDATE prestations SET IDfamille=88 WHERE IDprestation=9101')
        x=self.lire('2026-07-17','2026-07-17')['global']['familles']
        self.assertEqual(x['total'],1)
        self.assertEqual(x['tarifs_indicatifs'][TARIF_UNKNOWN],1)
        self.assertGreaterEqual(x['anomalies']['LIEN_PRESTATION_INCOHERENT'],1)
    def test_41_bad_service_tariff_flagged(self):
        self.cn.execute('UPDATE prestations SET IDtarif=900 WHERE IDprestation=9101')
        x=self.lire('2026-07-17','2026-07-17')['global']['familles']
        self.assertEqual(x['total'],1)
        self.assertEqual(x['tarifs_indicatifs'][TARIF_UNKNOWN],1)
    def test_42_historical_threshold_reconstruction_is_not_historical_proof(self):
        x=self.lire('2026-07-05','2026-07-05')['global']['familles']
        self.assertEqual(x['tarifs_indicatifs']['C'],1)
        self.assertEqual(x['categories_tarif_attestees'],0)
    def test_43_same_day_two_tariffs_need_tie_warning(self):
        self.cn.execute('INSERT INTO tarifs VALUES(111,10,\'qf\',1)')
        self.cn.executemany('INSERT INTO tarifs_lignes VALUES(?,?,?,?,?,?,?)',[
            (5001,111,1,'1',0,99999,100.0)])
        conf=Configuration(sites={10:'Bais'},unites_accueil={10:(1,)},
          tarifs_accueil={10:(100,111)},libelles={'1':'A','2':'B','3':'C','4':'D'},exiger_grille_commune=False)
        cn = self.cn
        # Same day, second child of family 1 with another tariff -> category A.
        cn.execute('INSERT INTO prestations VALUES(9901,\'2026-07-30\',\'consommation\',10,111,1,NULL,1,12,99.0)')
        cn.execute('INSERT INTO consommations VALUES(9901,\'2026-07-30\',\'present\',10,12,1001,1,9901,1)')
        result=Lecteur(FakeDB(cn),conf).lire('2026-07-30','2026-07-30')
        self.assertEqual(result['global']['familles']['tarifs_indicatifs'][TARIF_TIE],1)
    def test_44_source_j2_confirms_previous_bug_without_modifying(self):
        # Executes isolated historical source method, not a running Noethys app.
        from qualification_q442_wx import fixture_pour_moteur, DBLectureSQLite, param
        db=fixture_pour_moteur()
        try:
            source_old=source_j2.GetDictQuotients(DBLectureSQLite(db),param())
            self.assertEqual(sum(source_old['dictTranchesTarifs'].values()),10)
        finally:db.close()
    def test_45_input_does_not_mutate_database(self):
        changes=self.cn.total_changes
        self.lire()
        self.assertEqual(self.cn.total_changes,changes)
    def test_46_dates_invalid_order_rejected(self):
        with self.assertRaises(ValueError):self.lire('2026-08-01','2026-07-01')
    def test_47_obsolete_zero_works(self):
        x=self.lire('2026-07-31','2026-07-31')
        self.assertEqual(sum(x['global']['familles']['tarifs_indicatifs'].values()),0)
    def test_48_catalogue_preserves_indicative_status(self):
        x=self.lire()
        self.assertEqual(x['statut'],'PROTOTYPE_NON_HOMOLOGUE')
        self.assertTrue(any('CURRENT' in s for s in x['precautions']))



    def test_49_qf_vide_a_toujours_toutes_tranches(self):
        x=self.lire('2026-07-31','2026-07-31')['global']['familles']
        self.assertEqual(x['qf'],{'A':0,'B':0,'C':0,'D':0,'E historique':0,
                                  QF_UNKNOWN:0,QF_REVIEW:0})
    def test_50_taux_sur_toute_population(self):
        x=self.lire()['global']['familles']
        self.assertAlmostEqual(sum(x['pourcentages_qf'].values()),100.0,places=1)
        self.assertAlmostEqual(sum(x['pourcentages_tarifs_indicatifs'].values()),100.0,places=1)
        self.assertAlmostEqual(x['pourcentages_qf'][QF_UNKNOWN],200/9,places=2)
    def test_51_meme_site_regroupant_deux_activites(self):
        conf=Configuration({10:'ALSH',11:'ALSH'},{10:(1,),11:(1,)},
                           {10:(100,),11:(110,)}, {'1':'A','2':'B','3':'C','4':'D'})
        x=Lecteur(FakeDB(self.cn),conf).lire(*PERIOD)
        self.assertEqual(x['sites']['ALSH']['familles']['total'],9)
        self.assertEqual(x['global']['familles']['total'],9)
    def test_52_couche_sqlite_pragmas_query_only(self):
        self.cn.execute('PRAGMA query_only = ON')
        self.assertEqual(self.lire()['global']['familles']['total'],9)
    def test_53_absence_injustifiee_ne_constitue_pas_presence(self):
        self.cn.execute("UPDATE consommations SET etat='absenti' WHERE IDconso=6")
        x=self.lire()['global']['familles']
        self.assertEqual(x['total'],8)
    def test_54_conflit_intervalles_qf_nest_pas_choisi_au_hasard(self):
        self.cn.execute("INSERT INTO tarifs_lignes VALUES(9099,100,8,'8',300,900,9.0)")
        conf=Configuration({10:'Bais'},{10:(1,)},{10:(100,)},
                           {'1':'A','2':'B','3':'C','4':'D','8':'H'})
        x=Lecteur(FakeDB(self.cn),conf).lire('2026-07-20','2026-07-20')
        self.assertEqual(x['global']['familles']['qf'][QF_OUTSIDE],1)
        self.assertEqual(x['global']['familles']['tarifs_indicatifs'][TARIF_UNKNOWN],1)
    def test_55_collision_libelles_rejetee(self):
        conf=Configuration({10:'Bais'},{10:(1,)},{10:(100,)},
                           {'1':'A','2':'A','3':'C','4':'D'})
        with self.assertRaises(ValueError): Lecteur(FakeDB(self.cn),conf).lire(*PERIOD)
    def test_56_grilles_divergentes_refus_fusion(self):
        self.cn.execute('UPDATE tarifs_lignes SET qf_max=900 WHERE IDligne=1102')
        with self.assertRaises(RuntimeError):self.lire()
    def test_57_changement_montant_ne_change_pas_grille(self):
        self.cn.execute("UPDATE tarifs_lignes SET montant_unique=9.99 WHERE IDtarif=100 AND tranche='2'")
        self.assertEqual(self.lire()['global']['familles']['tarifs_indicatifs']['B'],2)
    def test_58_validite_qf_expiree_pas_de_valeur_fictive_sociale(self):
        x=self.lire('2026-07-14','2026-07-14')['global']['familles']
        self.assertEqual(x['qf'][QF_UNKNOWN],1)
        self.assertEqual(x['tarifs_indicatifs']['A'],1)
    def test_59_date_invalid_rejetee(self):
        with self.assertRaises(ValueError):self.lire('2026-02-30','2026-07-31')
    def test_60_export_json_ne_contient_ni_montant_ni_id(self):
        x=json.dumps(self.lire())
        self.assertNotIn('montant_initial',x)
        self.assertNotIn('IDprestation',x)
        self.assertNotIn('IDconso',x)

def run():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Jalon3Tests)
    report=unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if report.wasSuccessful() else 1

if __name__=='__main__':
    raise SystemExit(run())
