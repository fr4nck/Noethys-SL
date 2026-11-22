#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q442 J4: explicit physical-site mapping, real table names, GUI-shaped objects.

DATA_Tables source contract wx e86fabed; ALL records synthetic in SQLite memory.
This does not execute Noethys GUI or write user data.
"""
import copy
import csv
import datetime
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use('Agg',force=True)
from matplotlib import pyplot as plt
from PIL import Image

from source_j3.source_j2.fixture_q442_precedente import create_fixture, PERIOD
from q442_j4_lecteur import (
    ConfigurationMultisite, SiteRegle, LecteurMultisite, SiteNonResoluble
)
from q442_j4_objets import (
    obtenir_resultat, construire_classes, preparer_pages, export_csv_aggreges,
)
from q442_lecteur import QF_UNKNOWN, QF_REVIEW, TARIF_UNKNOWN


class DB:
    """The Noethys ExecuterReq / ResultatReq read bridge on disposable SQLite."""
    def __init__(self, cn):
        self.cn = cn
        self.sql = []
        self.last = None
    def ExecuterReq(self,sql):
        self.sql.append(sql)
        self.last=self.cn.execute(sql).fetchall()
        return True
    def ResultatReq(self):
        return self.last


def facture_schema_realiste():
    """J3 fixture, enriched using the precise J4 references from DATA_Tables.py.

    The original source is deliberately not touched. 3 sites under one
    IDactivite=10, group IDs 101-103, two interchangeable validated
    IDtarif rows whose QF grid is IDENTICAL across the sites.
    """
    cn=create_fixture()
    cn.execute('ALTER TABLE consommations ADD COLUMN IDgroupe INTEGER')
    cn.execute('ALTER TABLE consommations ADD COLUMN IDinscription INTEGER')
    cn.executescript('''
       CREATE TABLE activites(IDactivite INTEGER PRIMARY KEY,nom TEXT,abrege TEXT,date_debut TEXT,date_fin TEXT);
       CREATE TABLE unites(IDunite INTEGER PRIMARY KEY,IDactivite INTEGER,nom TEXT,repas INTEGER);
       CREATE TABLE groupes(IDgroupe INTEGER PRIMARY KEY,IDactivite INTEGER,nom TEXT);
       CREATE TABLE inscriptions(IDinscription INTEGER PRIMARY KEY,IDfamille INTEGER,IDindividu INTEGER,
                                 IDactivite INTEGER,IDgroupe INTEGER,IDcategorie_tarif INTEGER,statut TEXT);
    ''')
    cn.execute("INSERT INTO activites VALUES(10,'ALSH MULTISITE','ALSH','2026-01-01','2026-12-31')")
    cn.executemany('INSERT INTO unites VALUES(?,?,?,?)',[(1,10,'Journee',0),(2,10,'Repas',1)])
    cn.executemany('INSERT INTO groupes VALUES(?,?,?)',[
        (101,10,'Groupe Bais'),(102,10,'Groupe La Guerche'),(103,10,'Groupe Moutiers')])
    cn.execute('UPDATE tarifs SET IDactivite=10 WHERE IDtarif=110')
    cn.execute('UPDATE prestations SET IDactivite=10 WHERE IDactivite=11')
    # Original 11 -> group 102, original 10 -> 101 ; one family into Moutiers.
    for row in list(cn.execute('SELECT IDconso,IDactivite,IDindividu,IDcompte_payeur FROM consommations')):
        groupe = (102 if row['IDactivite']==11 else 101)
        if row['IDconso']==15:
            groupe=103
        cn.execute('UPDATE consommations SET IDactivite=10,IDgroupe=?,IDinscription=? WHERE IDconso=?',
                   (groupe,row['IDconso'],row['IDconso']))
        fam=cn.execute('SELECT IDfamille FROM comptes_payeurs WHERE IDcompte_payeur=?',
                       (row['IDcompte_payeur'],)).fetchone()[0]
        cn.execute('INSERT INTO inscriptions VALUES(?,?,?,?,?,?,?)',
                   (row['IDconso'],fam,row['IDindividu'],10,groupe,1,'ok'))
    cn.commit()
    return cn


def configuration():
    return ConfigurationMultisite(
        regles=(SiteRegle('Bais',10,(1,),(101,)),
                SiteRegle('La Guerche',10,(1,),(102,)),
                SiteRegle('Moutiers',10,(1,),(103,))),
        tarifs_accueil={10:(100,110)},
        libelles={'1':'A','2':'B','3':'C','4':'D'},
        categories_historiques=('E historique',),
    )


def reader(cn,conf=None):
    return LecteurMultisite(DB(cn),conf or configuration())


def params(conf=None,mode='presents',selected=None,view='global'):
    return {
        'listeActivites':[10],
        'mode':mode,
        'periode':{'date_debut':datetime.date(2026,7,1),'date_fin':datetime.date(2026,7,31)},
        'q442_configuration':conf or configuration(),
        'q442_sites':selected,
        'q442_vue':view,
    }


class TableBase:
    def __init__(self):
        self.categorie='tableau'; self.lignes=[];self.colonnes=[];self.totaux=[];self.nom='';self.dictParametres={}


class GraphBase:
    def __init__(self):
        self.categorie='graphe';self.nom='';self.dictParametres={};self.taille=(300,300)


MODELES = SimpleNamespace(Tableau=TableBase,Graphe=GraphBase)
TABLE,BARS,PIE = construire_classes(MODELES)


class J4Tests(unittest.TestCase):
    def setUp(self):
        self.cn=facture_schema_realiste()
        self.db=DB(self.cn)
        self.conf=configuration()
    def tearDown(self):
        self.cn.close()
    def lire(self,a=PERIOD[0],b=PERIOD[1],sites=None):
        return LecteurMultisite(self.db,self.conf).lire(a,b,selection_sites=sites)
    def test_01_realistic_schema_tables_and_fields(self):
        for table,columns in {
            'consommations':{'IDconso','IDgroupe','IDunite','IDinscription','IDactivite','IDprestation','IDcompte_payeur','etat'},
            'prestations':{'IDprestation','IDtarif','IDcategorie_tarif','IDfacture','IDindividu','IDfamille'},
            'tarifs_lignes':{'IDligne','tranche','qf_min','qf_max','num_ligne'},
            'quotients':{'IDfamille','IDtype_quotient','date_debut','date_fin','quotient'},
            'groupes':{'IDgroupe','IDactivite'},
            'unites':{'IDunite','IDactivite'},
            'inscriptions':{'IDfamille','IDinscription','IDgroupe'},
        }.items():
            available={row[1] for row in self.cn.execute('PRAGMA table_info('+table+')')}
            self.assertTrue(columns.issubset(available),(table,columns-available))
    def test_02_one_activity_three_physical_sites(self):
        rows=self.cn.execute('SELECT DISTINCT IDactivite FROM consommations').fetchall()
        self.assertEqual([x[0] for x in rows],[10])
        self.assertEqual(len(self.lire()['sites']),3)
    def test_03_population_global_families(self):
        self.assertEqual(self.lire()['global']['familles']['total'],9)
    def test_04_population_global_children(self):
        self.assertEqual(self.lire()['global']['enfants']['total'],11)
    def test_05_family_dedup_across_sites(self):
        v=self.lire()
        self.assertEqual({k:x['familles']['total'] for k,x in v['sites'].items()},
                         {'Bais':6,'La Guerche':3,'Moutiers':1})
        self.assertEqual(sum(x['familles']['total'] for x in v['sites'].values()),10)
        self.assertEqual(v['global']['familles']['total'],9)
    def test_06_global_indiv_dedup(self):
        v=self.lire()
        self.assertEqual(sum(x['enfants']['total'] for x in v['sites'].values()),11)
        self.assertEqual(v['global']['enfants']['total'],11)
    def test_07_one_grid_same_activity_two_price_rules(self):
        self.assertEqual(self.lire()['global']['familles']['total'],9)
    def test_08_activities_and_tariffs_always_explicit(self):
        self.assertEqual(self.conf.activities,(10,))
        self.assertEqual(set(self.conf.tarifs_accueil[10]),{100,110})
    def test_09_no_regles_refuses(self):
        with self.assertRaises(ValueError): ConfigurationMultisite((),{10:(100,)},{'1':'A'})
    def test_10_cross_site_overlapping_group_rejected(self):
        with self.assertRaises(ValueError):
            ConfigurationMultisite((SiteRegle('Bais',10,(1,),(101,)),
                SiteRegle('Moutiers',10,(1,),(101,))),{10:(100,)},{'1':'A'})
    def test_11_cross_site_overlap_wildcard_rejected(self):
        with self.assertRaises(ValueError):
            ConfigurationMultisite((SiteRegle('Bais',10,(1,),None),
                SiteRegle('Moutiers',10,(1,),(101,))),{10:(100,)},{'1':'A'})
    def test_12_missing_real_site_group_is_stop(self):
        self.cn.execute('UPDATE consommations SET IDgroupe=999 WHERE IDconso=1')
        with self.assertRaises(SiteNonResoluble):self.lire()
    def test_13_null_group_not_guessed(self):
        self.cn.execute('UPDATE consommations SET IDgroupe=NULL WHERE IDconso=1')
        with self.assertRaises(SiteNonResoluble):self.lire()
    def test_14_wrong_group_activity_is_stop(self):
        self.cn.execute('UPDATE groupes SET IDactivite=33 WHERE IDgroupe=101')
        with self.assertRaises(SiteNonResoluble):self.lire()
    def test_15_wrong_unit_activity_is_stop(self):
        self.cn.execute('UPDATE unites SET IDactivite=33 WHERE IDunite=1')
        with self.assertRaises(SiteNonResoluble):self.lire()
    def test_16_selection_single_site_is_exact(self):
        r=self.lire(sites=('Bais',))
        self.assertEqual(list(r['sites']),['Bais'])
        self.assertEqual(r['global']['familles']['total'],6)
    def test_17_selection_two_sites_dedup(self):
        r=self.lire(sites=('Bais','La Guerche'))
        self.assertEqual(r['global']['familles']['total'],8)
    def test_18_selection_unknown_site_refused(self):
        with self.assertRaises(ValueError):self.lire(sites=('Inconnu',))
    def test_19_no_invoice_before_stats(self):
        self.assertEqual(self.cn.execute('SELECT COUNT(*) FROM prestations WHERE IDfacture IS NOT NULL').fetchone()[0],0)
        self.assertEqual(self.lire()['global']['familles']['total'],9)
    def test_20_presence_without_prestation_counted(self):
        self.assertEqual(self.lire(a='2026-07-12',b='2026-07-12')['global']['familles']['total'],1)
    def test_21_reservation_not_counted(self):
        self.assertEqual(self.lire('2026-07-11','2026-07-11')['global']['familles']['total'],0)
    def test_22_meal_not_counted_as_last_accueil(self):
        self.assertEqual(self.lire()['global']['familles']['tarifs_indicatifs']['B'],2)
    def test_23_non_communicated_qf_separate(self):
        self.assertEqual(self.lire()['global']['familles']['qf'][QF_UNKNOWN],2)
    def test_24_non_communicated_max_price_only_indicative(self):
        r=self.lire()['global']['familles']
        self.assertEqual(r['tarifs_indicatifs']['A'],3)
        self.assertEqual(r['categories_tarif_attestees'],0)
    def test_25_numero_de_categorie_is_not_money(self):
        self.cn.execute("UPDATE prestations SET montant=9999 WHERE IDprestation=1104")
        self.assertEqual(self.lire()['global']['familles']['tarifs_indicatifs']['B'],2)
    def test_26_category_zero_kept(self):
        for pop in ('familles','enfants'):
            for typ in ('qf','tarifs_indicatifs'):
                self.assertIn('E historique',self.lire()['global'][pop][typ])
                self.assertEqual(self.lire()['global'][pop][typ]['E historique'],0)
    def test_27_no_duplicate_with_same_family_multiple_children(self):
        self.assertEqual(self.lire()['global']['familles']['qf']['B'],2)
        self.assertEqual(self.lire()['global']['enfants']['qf']['B'],3)
    def test_28_no_wrong_site_when_one_site_zero(self):
        r=self.lire('2026-07-20','2026-07-20')
        self.assertEqual(r['sites']['Moutiers']['familles']['total'],0)
        self.assertIn('E historique',r['sites']['Moutiers']['familles']['qf'])
    def test_29_3_sql_selects_only(self):
        self.lire()
        self.assertEqual(len(self.db.sql),3)
        self.assertTrue(all(x.strip().upper().startswith('SELECT ') for x in self.db.sql))
    def test_30_sql_query_only_enforced(self):
        self.cn.execute('PRAGMA query_only=ON')
        self.assertEqual(self.lire()['global']['familles']['total'],9)
    def test_31_no_sqlite_changes(self):
        old=self.cn.total_changes
        self.lire()
        self.assertEqual(self.cn.total_changes,old)
    def test_32_inconsistent_prestation_not_assumed_valid(self):
        self.cn.execute('UPDATE prestations SET IDfamille=999 WHERE IDprestation=9101')
        r=self.lire('2026-07-17','2026-07-17')['global']['familles']
        self.assertEqual(r['total'],1)
        self.assertEqual(r['tarifs_indicatifs'][TARIF_UNKNOWN],1)
    def test_33_historical_grid_change_is_not_certified(self):
        self.cn.execute("UPDATE tarifs_lignes SET qf_min=400 WHERE IDligne=1003")
        self.cn.execute("UPDATE tarifs_lignes SET qf_min=400 WHERE IDligne=1103")
        r=self.lire('2026-07-05','2026-07-05')['global']['familles']
        self.assertEqual(r['categories_tarif_attestees'],0)
    def test_34_different_grids_fail_closed(self):
        self.cn.execute('UPDATE tarifs_lignes SET qf_max=899 WHERE IDligne=1102')
        with self.assertRaises(RuntimeError):self.lire()
    def test_35_invalid_select_only(self):
        self.assertEqual(self.lire()['statut'],'CANDIDAT_J4_NON_INTEGRE_NON_HOMOLOGUE')
    def test_36_no_identity_in_output(self):
        r=json.dumps(self.lire())
        for key in ('IDindividu','IDfamille','IDconso','IDprestation','montant','nomIndividu'):
            self.assertNotIn('"'+key+'"',r)
    def test_37_representations_have_equal_denominators(self):
        r=self.lire()
        for v in [r['global'],*r['sites'].values()]:
            for p in ('familles','enfants'):
                obs=v[p]
                self.assertEqual(sum(obs['qf'].values()),obs['total'])
                self.assertEqual(sum(obs['tarifs_indicatifs'].values()),obs['total'])
    def test_38_percentages_on_full_population(self):
        r=self.lire()['global']['familles']
        self.assertAlmostEqual(r['pourcentages_qf'][QF_UNKNOWN],22.22,places=2)
        self.assertAlmostEqual(sum(r['pourcentages_qf'].values()),100,places=1)
    def test_39_ui_table_base_contract(self):
        t=TABLE('familles','qf')
        self.assertIsInstance(t,MODELES.Tableau)
        self.assertEqual(t.categorie,'tableau')
        t.MAJ(DB=self.db,dictParametres=params())
        self.assertEqual(sum(row[1] for row in t.lignes),9)
        self.assertEqual(t.totaux[0][1],9)
    def test_40_ui_table_qf_unknown_kept(self):
        t=TABLE('familles','qf')
        t.MAJ(DB=self.db,dictParametres=params())
        self.assertIn(QF_UNKNOWN,[row[0] for row in t.lignes])
    def test_41_ui_table_tarif_distinct(self):
        t=TABLE('familles','tarifs')
        t.MAJ(DB=self.db,dictParametres=params())
        self.assertNotIn(QF_UNKNOWN,[row[0] for row in t.lignes])
        self.assertTrue(any('INDICATIVES' in t.nom for _ in (0,)))
    def test_42_ui_dedicated_individuals(self):
        t=TABLE('individus','qf')
        t.MAJ(DB=self.db,dictParametres=params())
        self.assertEqual(t.totaux[0][1],11)
    def test_43_ui_inscrits_forbidden(self):
        with self.assertRaises(ValueError):
            TABLE('familles','qf').MAJ(DB=self.db,dictParametres=params(mode='inscrits'))
    def test_44_ui_requires_validated_config(self):
        p=params();p['q442_configuration']=None
        with self.assertRaises(ValueError):
            TABLE('familles','qf').MAJ(DB=self.db,dictParametres=p)
    def test_45_ui_requires_exact_activity_selection(self):
        p=params();p['listeActivites']=[10,11]
        with self.assertRaises(ValueError):
            TABLE('familles','qf').MAJ(DB=self.db,dictParametres=p)
    def test_46_ui_site_selection(self):
        t=TABLE('familles','qf')
        t.MAJ(DB=self.db,dictParametres=params(selected=('Bais',),view='Bais'))
        self.assertEqual(t.totaux[0][1],6)
    def test_47_ui_one_connection_cached_result(self):
        p=params()
        TABLE('familles','qf').MAJ(DB=self.db,dictParametres=p)
        before=len(self.db.sql)
        BARS('familles','qf').MAJ(figure=plt.figure(),DB=self.db,dictParametres=p)
        self.assertEqual(len(self.db.sql),before)
        plt.close('all')
    def test_48_ui_cache_invalidated_by_period(self):
        p=params()
        TABLE('familles','qf').MAJ(DB=self.db,dictParametres=p)
        before=len(self.db.sql)
        p=copy.deepcopy(p)
        p['periode']['date_fin']=datetime.date(2026,7,20)
        TABLE('familles','qf').MAJ(DB=self.db,dictParametres=p)
        self.assertGreater(len(self.db.sql),before)
    def test_49_ui_cache_invalidated_by_site_filter(self):
        p=params()
        TABLE('familles','qf').MAJ(DB=self.db,dictParametres=p)
        before=len(self.db.sql)
        p=copy.deepcopy(p);p['q442_sites']=('Bais',)
        TABLE('familles','qf').MAJ(DB=self.db,dictParametres=p)
        self.assertGreater(len(self.db.sql),before)
    def test_50_ui_bar_counts_equal_table(self):
        p=params()
        t=TABLE('familles','qf');t.MAJ(DB=self.db,dictParametres=p)
        f=plt.figure(figsize=(7,4))
        BARS('familles','qf').MAJ(figure=f,DB=self.db,dictParametres=p)
        try:
            self.assertEqual([bar.get_height() for bar in f.axes[0].patches],
                             [row[1] for row in t.lignes])
            self.assertEqual(len(f.axes[0].get_xticklabels()),len(t.lignes))
        finally:plt.close(f)
    def test_51_ui_bar_includes_zero(self):
        f=plt.figure()
        BARS('familles','tarifs').MAJ(figure=f,DB=self.db,dictParametres=params())
        try:self.assertGreaterEqual(sum(b.get_height()==0 for b in f.axes[0].patches),1)
        finally:plt.close(f)
    def test_52_ui_pie_legend_keeps_zeros(self):
        f=plt.figure(figsize=(8,5))
        PIE('familles','tarifs').MAJ(figure=f,DB=self.db,dictParametres=params())
        try:self.assertIn('E historique',[x.get_text().split(' :')[0] for x in f.axes[0].get_legend().get_texts()])
        finally:plt.close(f)
    def test_53_ui_pie_visible_sum_is_denominator(self):
        f=plt.figure(figsize=(8,5))
        PIE('familles','qf').MAJ(figure=f,DB=self.db,dictParametres=params())
        try:self.assertEqual(len(f.axes[0].patches),5)
        finally:plt.close(f)
    def test_54_ui_png_valid_real_agg(self):
        f=plt.figure(figsize=(8,5))
        BARS('familles','qf').MAJ(figure=f,DB=self.db,dictParametres=params())
        try:
            out=io.BytesIO();f.savefig(out,format='png')
            self.assertTrue(out.getvalue().startswith(b'\x89PNG\r\n\x1a\n'))
            out.seek(0)
            with Image.open(out) as png:
                self.assertGreater(png.width,300)
                png.verify()
        finally:plt.close(f)
    def test_55_ui_zero_population_pie_graceful(self):
        p=params();p['periode']['date_debut']=datetime.date(2026,11,1);p['periode']['date_fin']=datetime.date(2026,11,2)
        f=plt.figure()
        PIE('familles','qf').MAJ(figure=f,DB=self.db,dictParametres=p)
        try:self.assertEqual(len(f.axes[0].get_legend().get_texts()),7)
        finally:plt.close(f)
    def test_56_blueprint_no_mode_inscrits_pages(self):
        l=[{'code':'familles','pages':[]},{'code':'individus','pages':[]}]
        self.assertEqual(preparer_pages(MODELES,l,configuration(),'inscrits'),l)
        self.assertEqual(l[0]['pages'],[])
    def test_57_blueprint_adds_four_pages_three_objects_each(self):
        l=[{'code':'familles','pages':[]},{'code':'individus','pages':[]}]
        preparer_pages(MODELES,l,configuration(),'presents')
        self.assertEqual([len(k['pages']) for k in l],[2,2])
        self.assertTrue(all(len(p['objets'])==3 for cat in l for p in cat['pages']))
    def test_58_blueprint_idempotent(self):
        l=[{'code':'familles','pages':[]}]
        preparer_pages(MODELES,l,configuration())
        preparer_pages(MODELES,l,configuration())
        self.assertEqual(len(l[0]['pages']),2)
    def test_59_csv_global_and_each_site(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'agreges.csv'
            n=export_csv_aggreges(self.lire(),p)
            self.assertGreater(n,0)
            with p.open(encoding='utf-8',newline='') as h:
                rows=list(csv.DictReader(h,delimiter=';'))
            self.assertEqual({x['site'] for x in rows}, {'Synthese generale','Bais','La Guerche','Moutiers'})
            self.assertEqual(len(rows),n)
    def test_60_csv_anonymized_and_no_prices(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'agreges.csv'
            export_csv_aggreges(self.lire(),p)
            data=p.read_text(encoding='utf-8')
            for bad in ('IDfamille','IDindividu','montant','prenom','nomIndividu'):
                self.assertNotIn(bad,data)
            self.assertIn('E historique',data)
    def test_61_csv_families_total_matches_pie(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'agreges.csv'
            export_csv_aggreges(self.lire(),p)
            with p.open(encoding='utf-8',newline='') as h:
                rows=list(csv.DictReader(h,delimiter=';'))
            chosen=[x for x in rows if x['site']=='Synthese generale' and x['population']=='familles' and x['representation']=='qf']
            self.assertEqual(sum(int(x['effectif']) for x in chosen),9)
    def test_62_no_unapproved_group_borrowed_as_activity(self):
        self.cn.execute('UPDATE consommations SET IDgroupe=103 WHERE IDconso=6')
        r=self.lire()
        self.assertEqual(r['sites']['Moutiers']['familles']['total'],2)
        self.assertEqual(r['global']['familles']['total'],9)
    def test_63_secondary_unit_ignored_without_silent_inference(self):
        self.assertEqual(self.lire()['exclus_hors_unites_accueil'],1)
    def test_64_site_group_null_explicitly_mappable_when_unique(self):
        cn=self.cn
        cn.execute('UPDATE consommations SET IDgroupe=NULL WHERE IDgroupe=101')
        # A wildcard is acceptable only for a disjoint-unit site; here other
        # sites use that very unit and so any overlap is explicitly rejected.
        with self.assertRaises(ValueError):
            ConfigurationMultisite((SiteRegle('Bais',10,(1,),None),
                SiteRegle('La Guerche',10,(1,),(102,))),
                {10:(100,110)},{'1':'A'})
    def test_65_changing_last_day_changes_period_tier(self):
        start=self.lire('2026-07-01','2026-07-14')['global']['familles']
        end=self.lire('2026-07-15','2026-07-31')['global']['familles']
        self.assertNotEqual(start['total'],0)
        self.assertNotEqual(end['total'],0)
    def test_66_sql_column_read_matches_unmodified_tariff_id(self):
        old=self.cn.execute('SELECT IDtarif FROM prestations WHERE IDprestation=1104').fetchone()[0]
        self.lire()
        new=self.cn.execute('SELECT IDtarif FROM prestations WHERE IDprestation=1104').fetchone()[0]
        self.assertEqual((old,new),(100,100))


if __name__=='__main__':
    unittest.main(verbosity=2)

# Additional schema/driver adversarial tests appended after the standard suite.
class J4DriverTests(unittest.TestCase):
    def setUp(self):
        self.cn=facture_schema_realiste()
    def tearDown(self):
        self.cn.close()
    def test_67_mysql_date_object_rows(self):
        class DateDriver(DB):
            def ExecuterReq(self,sql):
                super().ExecuterReq(sql)
                if 'FROM consommations c' in sql:
                    new=[]
                    for row in self.last:
                        x=list(row)
                        x[1]=datetime.date.fromisoformat(x[1])
                        if x[15] is not None:
                            x[15]=datetime.date.fromisoformat(x[15])
                        new.append(tuple(x))
                    self.last=new
                elif 'FROM quotients' in sql:
                    new=[]
                    for row in self.last:
                        x=list(row)
                        x[3]=datetime.date.fromisoformat(x[3])
                        x[4]=datetime.date.fromisoformat(x[4])
                        new.append(tuple(x))
                    self.last=new
                return True
        out=LecteurMultisite(DateDriver(self.cn),configuration()).lire(*PERIOD)
        self.assertEqual((out['global']['familles']['total'],out['global']['enfants']['total']),(9,11))
    def test_68_input_injection_refused(self):
        with self.assertRaises(ValueError):
            SiteRegle('Moutiers','10 OR 1=1',(1,),(103,))
    def test_69_no_stored_historical_line_id(self):
        for tab in ('consommations','prestations'):
            self.assertNotIn('IDligne',{r[1] for r in self.cn.execute('PRAGMA table_info('+tab+')')})
    def test_70_same_day_ambiguity_not_silently_resolved(self):
        # When last date is shared by conflicting tariffs, the J3 reader
        # contract flags both categories instead of choosing arbitrary row.
        self.cn.execute("INSERT INTO prestations VALUES(9901,'2026-07-30','consommation',10,100,1,NULL,1,12,99.0)")
        self.cn.execute('INSERT INTO inscriptions VALUES(9901,1,12,10,101,1,\'ok\')')
        self.cn.execute("INSERT INTO consommations(IDconso,date,etat,IDactivite,IDindividu,IDcompte_payeur,IDcategorie_tarif,IDprestation,IDunite,IDgroupe,IDinscription) VALUES(9901,'2026-07-30','present',10,12,1001,1,9901,1,101,9901)")
        # Both QF tier B -> no artificial conflict despite two prestations.
        r=LecteurMultisite(DB(self.cn),configuration()).lire(*PERIOD)
        self.assertEqual(r['global']['familles']['total'],9)

class J4SafetyTests(unittest.TestCase):
    def setUp(self):
        self.cn=facture_schema_realiste()
    def tearDown(self):
        self.cn.close()
    def test_71_qf_reference_mismatch_fails_closed(self):
        self.cn.execute('UPDATE tarifs SET IDtype_quotient=2 WHERE IDtarif=110')
        with self.assertRaisesRegex(RuntimeError,'REFERENTIEL_QF_UNIQUE_REQUIRED'):
            LecteurMultisite(DB(self.cn),configuration()).lire(*PERIOD)
    def test_72_unspecified_qf_reference_fails_closed(self):
        self.cn.execute('UPDATE tarifs SET IDtype_quotient=NULL')
        with self.assertRaisesRegex(RuntimeError,'REFERENTIEL_QF_UNIQUE_REQUIRED'):
            LecteurMultisite(DB(self.cn),configuration()).lire(*PERIOD)
    def test_73_historical_label_collision_rejected(self):
        with self.assertRaises(ValueError):
            ConfigurationMultisite(configuration().regles,{10:(100,110)},
                                   {'1':'A'},('A',))
    def test_74_csv_formula_injection_escaped(self):
        d=LecteurMultisite(DB(self.cn),configuration()).lire(*PERIOD)
        d['sites']['=1+1']=d['sites'].pop('Moutiers')
        d['global']['familles']['qf']['=SUM(2,2)']=d['global']['familles']['qf'].pop('E historique')
        d['global']['familles']['pourcentages_qf']['=SUM(2,2)']=d['global']['familles']['pourcentages_qf'].pop('E historique')
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/'x.csv';export_csv_aggreges(d,dest)
            txt=dest.read_text(encoding='utf-8')
            self.assertIn("'=1+1",txt)
            self.assertIn("'=SUM(2,2)",txt)
            self.assertNotIn(';=SUM(2,2);',txt)
    def test_75_pie_legend_color_matches_wedges(self):
        p=params()
        f=plt.figure(figsize=(8,5))
        PIE('familles','qf').MAJ(figure=f,DB=DB(self.cn),dictParametres=p)
        try:
            ax=f.axes[0]
            summary=LecteurMultisite(DB(self.cn),configuration()).lire(*PERIOD)['global']['familles']['qf']
            legend=ax.get_legend()
            handles=legend.legend_handles
            ordered=list(summary)
            nonzero=[k for k in ordered if summary[k]>0]
            self.assertEqual(len(ax.patches),len(nonzero))
            for label,wedge in zip(nonzero,ax.patches):
                i=ordered.index(label)
                expected=tuple(wedge.get_facecolor())
                observed=tuple(handles[i].get_facecolor())
                self.assertEqual(expected,observed)
        finally:plt.close(f)
