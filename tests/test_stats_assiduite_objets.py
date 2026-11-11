# -*- coding: utf-8 -*-
"""Headless verification of original-style MODELES interfaces."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock
import matplotlib
matplotlib.use('Agg',force=True)
from matplotlib import pyplot as plt
from tests.test_stats_assiduite_synthetic import fixture, DB, MOD

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'noethys'/'Utils'/'UTILS_Stats_assiduite_objets.py'

class Texte:
    def __init__(self):
        self.categorie='texte';self.dictParametres={};self.texte='';self.visible=True
    def GetObjetHTML(self):
        return self.texte
class Tableau:
    def __init__(self):
        self.categorie='tableau';self.dictParametres={};self.lignes=[];self.colonnes=[];self.totaux=[];self.visible=True
class Graphe:
    def __init__(self):
        self.categorie='graphe';self.dictParametres={};self.visible=True;self.taille=(300,300)


def load_candidate():
    package=ModuleType('Utils')
    package.__path__=[]
    m=ModuleType('Utils.UTILS_Stats_modeles')
    m.Texte=Texte;m.Tableau=Tableau;m.Graphe=Graphe
    package.UTILS_Stats_modeles=m
    with mock.patch.dict(sys.modules,{'Utils':package,
                        'Utils.UTILS_Stats_modeles':m,
                        'Utils.UTILS_Stats_assiduite':MOD}):
        spec=importlib.util.spec_from_file_location('Utils.UTILS_Stats_assiduite_objets',SRC)
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


class StatObjectsTests(unittest.TestCase):
    def setUp(self):
        self.mod=load_candidate()
        self.cn=fixture()
        self.addCleanup(self.cn.close)
        self.db=DB(self.cn)
        self.params={'mode':'presents','listeActivites':[10],
                     'periode':{'date_debut':'2024-01-01','date_fin':'2026-12-31'}}
        self.addCleanup(plt.close,'all')
    def test_01_canonical_objects_in_real_categories(self):
        objects=(self.mod.TextePrecautions,self.mod.TableauAnnees,self.mod.TableauMois,
                 self.mod.TableauRepartition,self.mod.TableauSites,
                 self.mod.GrapheAnnees,self.mod.GrapheMois,self.mod.GrapheSecteurs)
        self.assertEqual(len(objects),8)
        self.assertEqual([x().categorie for x in objects],['texte']+['tableau']*4+['graphe']*3)
    def test_02_annual_table_and_partial_year(self):
        tab=self.mod.TableauAnnees().MAJ(DB=self.db,dictParametres=self.params)
        self.assertEqual(len(tab.lignes),3)
        self.assertEqual(tab.lignes[0][0],'2024')
        self.assertEqual(tab.lignes[0][1:5],(1,1,1,1))
        self.assertEqual(tab.lignes[0][6],'66.67 %')
    def test_03_monthly_table_including_zeros(self):
        tab=self.mod.TableauMois().MAJ(DB=self.db,dictParametres=self.params)
        self.assertEqual(len(tab.lignes),36)
        self.assertEqual(tab.lignes[1][0],'2024-02')
        self.assertEqual(tab.lignes[1][1:6],(0,0,0,0,0))
    def test_04_pie_preserves_empty_legend_states(self):
        fig=plt.figure()
        self.mod.GrapheSecteurs().MAJ(figure=fig,DB=self.db,dictParametres=self.params)
        self.assertEqual(len(fig.axes),1)
        self.assertEqual(len(fig.axes[0].get_legend().get_texts()),4)
    def test_05_graphs_render_with_genuine_matplotlib(self):
        for typ in (self.mod.GrapheAnnees,self.mod.GrapheMois):
            fig=plt.figure()
            self.assertIs(typ().MAJ(figure=fig,DB=self.db,dictParametres=self.params),fig)
            self.assertEqual(len(fig.axes),1)
            plt.close(fig)
    def test_06_cache_avoids_duplicate_query_in_one_page(self):
        self.mod.TableauAnnees().MAJ(DB=self.db,dictParametres=self.params)
        self.assertEqual(len(self.db.sql),1)
        self.mod.GrapheAnnees().MAJ(figure=plt.figure(),DB=self.db,dictParametres=self.params)
        self.assertEqual(len(self.db.sql),1)
    def test_07_cache_is_scoped_by_period(self):
        self.mod.TableauAnnees().MAJ(DB=self.db,dictParametres=self.params)
        p={'mode':'presents','listeActivites':[10],
           'periode':{'date_debut':'2025-01-01','date_fin':'2025-12-31'}}
        self.mod.TableauAnnees().MAJ(DB=self.db,dictParametres=p)
        self.assertEqual(len(self.db.sql),2)
    def test_08_cannot_query_in_inscrits(self):
        p=dict(self.params,mode='inscrits')
        t=self.mod.TableauAnnees().MAJ(DB=self.db,dictParametres=p)
        self.assertEqual(t.lignes,[])
        fig=plt.figure()
        self.mod.GrapheMois().MAJ(figure=fig,DB=self.db,dictParametres=p)
        self.assertEqual(len(self.db.sql),0)
    def test_09_registers_three_pages_idempotently(self):
        start=[{'nom':'Individus','code':'individus','pages':[]}]
        self.mod.preparer_pages(SimpleNamespace(Texte=Texte,Tableau=Tableau,Graphe=Graphe),start)
        self.mod.preparer_pages(SimpleNamespace(Texte=Texte,Tableau=Tableau,Graphe=Graphe),start)
        self.assertEqual(len(start),2)
        self.assertEqual(len(start[1]['pages']),3)
    def test_10_warning_omits_false_cancellation_number(self):
        obj=self.mod.TextePrecautions().MAJ(DB=self.db,dictParametres=self.params)
        self.assertIn('Annulations',obj.GetObjetHTML())
        self.assertIn('NON_RECONSTRUCTIBLES',obj.GetObjetHTML())
    def test_11_sites_hidden_without_approved_mapping(self):
        t=self.mod.TableauSites().MAJ(DB=self.db,dictParametres=self.params)
        self.assertEqual(t.lignes,[])
    def test_12_source_prepared_without_network_access(self):
        for s in self.db.sql:
            self.assertTrue(s.startswith('SELECT '))


if __name__=='__main__':
    unittest.main()
