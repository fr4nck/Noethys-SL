#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q442 Jalon 2 - caracterisation de methodes wx extraites, SQLite 100% fictif.

Aucune connexion aux bases de l'association, aucun write vers GitHub, wx,
le dossier precedent ou la sauvegarde .nod. Le code de production n'est pas
importe : les passages cites sont reproduits isoles avec shims d'interface.
Les PASS de ce banc valident l'observation de comportements et de limites,
PAS l'approbation fonctionnelle des comportements incorrects.
"""
import argparse
import collections
import datetime
import hashlib
import json
import pathlib
import sqlite3
import sys
import unittest
import matplotlib.pyplot as plt

from fixture_q442_precedente import create_fixture, PERIOD, aggregate, tariff_for
import extraits_wx_isoles as wxsrc

SRC_REF = 'e86fabedece82f6cc1cade70074207291f8d9dfb'


class DBLectureSQLite:
    """Bridge de lecture seule pour requetes SQL du moteur (SQLite fictif)."""
    def __init__(self, db):
        self.db = db
        self.last_result = []
        self.sql = []

    def ExecuterReq(self, query):
        if not query.lstrip().upper().startswith('SELECT '):
            raise AssertionError('Ecriture interdite dans le bridge de stats')
        self.sql.append(query)
        self.last_result = [tuple(row) for row in self.db.execute(query)]
        return True

    def ResultatReq(self):
        return self.last_result


def fixture_pour_moteur():
    db = create_fixture()
    # La fixture precedente avait un schema abrege des lignes tarifaires;
    # ajout de la colonne reelle de la table tarifs_lignes, en RAM uniquement.
    db.execute('ALTER TABLE tarifs_lignes ADD COLUMN IDactivite INTEGER')
    db.execute('UPDATE tarifs_lignes SET IDactivite = '
               '(SELECT IDactivite FROM tarifs t WHERE t.IDtarif=tarifs_lignes.IDtarif)')
    db.execute('CREATE TABLE inscriptions (IDinscription INTEGER PRIMARY KEY, '
               'IDcompte_payeur INTEGER, IDactivite INTEGER, statut TEXT)')
    db.execute("INSERT INTO inscriptions VALUES (1,1001,10,'ok')")
    db.commit()
    return db


def param(a='2026-07-01', b='2026-07-31', sites=(10,11), mode='presents'):
    return {'mode': mode, 'listeActivites': list(sites),
            'periode': {'date_debut': datetime.date.fromisoformat(a),
                        'date_fin': datetime.date.fromisoformat(b)}}


def resultat_initial():
    db = fixture_pour_moteur()
    bridge = DBLectureSQLite(db)
    donnees = wxsrc.GetDictQuotients(bridge, param())
    tab = wxsrc.Tableau_qf_tarifs()
    tab.MAJ(DB=bridge, dictParametres=param())
    graphe = wxsrc.Graphe_qf_defaut()
    figure = plt.figure(figsize=(6,4), dpi=100)
    graphe.MAJ(figure=figure, DB=bridge, dictParametres=param())
    bars = [(patch.get_x(), patch.get_height()) for patch in figure.axes[0].patches]
    output = {'reference': SRC_REF, 'date_reference': str(donnees['date_reference']),
              'total_ancien': sum(donnees['dictTranchesTarifs'].values()),
              'tranches_tarif': {str(k):v for k,v in donnees['dictTranchesTarifs'].items()},
              'qf_manquant': donnees['dictTranchesTarifs']['pasqf'],
              'qf_verifier': donnees['dictTranchesTarifs']['a_verifier'],
              'lignes_tableau': tab.lignes,
              'graphique_barres_defaut': len(bars),
              'graphique_effectif': int(sum(h for _,h in bars)),
              'population_cible': {'familles': aggregate(db, family=True)['denominator'],
                                   'enfants': aggregate(db, family=False)['denominator']},
              'SQL_modele': bridge.sql,
             }
    db.close()
    return output, figure


class Qualification(unittest.TestCase):
    def setUp(self):
        self.db = fixture_pour_moteur()
        self.bridge = DBLectureSQLite(self.db)

    def tearDown(self):
        self.db.close()

    def test_01_code_source_ouvre_uniquement_des_selects(self):
        wxsrc.GetDictQuotients(self.bridge, param())
        self.assertTrue(self.bridge.sql)
        self.assertTrue(all(q.lstrip().upper().startswith('SELECT ') for q in self.bridge.sql))

    def test_02_methode_source_reproduit_la_population_initiale(self):
        d = wxsrc.GetDictQuotients(self.bridge, param())['dictTranchesTarifs']
        self.assertEqual(sum(d.values()), 10)

    def test_03_population_metier_attendue_ne_compte_que_presences(self):
        self.assertEqual(aggregate(self.db, family=True)['denominator'], 9)
        self.assertEqual(aggregate(self.db, family=False)['denominator'], 11)

    def test_04_ecart_source_inclut_une_famille_uniquement_reservee(self):
        d = wxsrc.GetDictQuotients(self.bridge, param())['dictTranchesTarifs']
        self.assertEqual(sum(d.values()) - aggregate(self.db, family=True)['denominator'], 1)
        self.assertIn("'reservation', 'present'", self.bridge.sql[0])

    def test_05_source_prend_date_fin_plutot_que_derniere_presence(self):
        d = wxsrc.GetDictQuotients(self.bridge, param())
        self.assertEqual(d['date_reference'], datetime.date(2026,7,31))

    def test_06_source_date_fin_cree_un_contresens_qf_apres_derniere_presence(self):
        # Ajout IN-MEMORY : une famille presente le 10 juillet sous QF 550,
        # puis passe a QF 850 le 16 juillet sans nouvelle presence.
        self.db.execute('INSERT INTO familles VALUES(11)')
        self.db.execute('INSERT INTO comptes_payeurs VALUES(1011,11)')
        self.db.execute('INSERT INTO individus VALUES(111,11)')
        self.db.execute("INSERT INTO quotients VALUES(80,11,1,'2026-01-01','2026-07-15',550)")
        self.db.execute("INSERT INTO quotients VALUES(81,11,1,'2026-07-16','2026-12-31',850)")
        self.db.execute("INSERT INTO consommations VALUES(80,'2026-07-10','present',10,111,1011,1,NULL,1)")
        result = wxsrc.GetDictQuotients(self.bridge, param())['dictTranchesTarifs']
        db_original = fixture_pour_moteur()
        try:
            original = wxsrc.GetDictQuotients(DBLectureSQLite(db_original), param())['dictTranchesTarifs']
        finally:
            db_original.close()
        self.assertEqual(result[(700,999)], original[(700,999)] + 1)
        self.assertEqual(wxsrc._QuotientsAlaDate([(11,80,'2026-01-01','2026-07-15',550),
                                                   (11,81,'2026-07-16','2026-12-31',850)],'2026-07-10')[11],550)

    def test_07_denominateur_tableau_comprend_sans_qf(self):
        d = wxsrc.GetDictQuotients(self.bridge, param())['dictTranchesTarifs']
        self.assertEqual(d['pasqf'], 2)

    def test_08_tableau_source_contient_sans_qf(self):
        tab = wxsrc.Tableau_qf_tarifs()
        tab.MAJ(DB=self.bridge, dictParametres=param())
        self.assertIn(('Sans QF',2), tab.lignes)

    def test_09_graphique_source_exclut_sans_qf(self):
        d = wxsrc.GetDictQuotients(self.bridge, param())['dictTranchesDefaut']
        graph = wxsrc.Graphe_qf_defaut()
        fig = plt.figure()
        try:
            graph.MAJ(figure=fig, DB=self.bridge, dictParametres=param())
            self.assertEqual(len(fig.axes),1)
            self.assertEqual(sum(p.get_height() for p in fig.axes[0].patches), sum(d.values())-d['pasqf']-d['a_verifier']-d['autre'])
        finally: plt.close(fig)

    def test_10_recherche_qf_de_source_sur_absent_ou_expire(self):
        data = {6: [(datetime.date(2026,1,1),datetime.date(2026,6,30),950,1)]}
        obj = wxsrc.CTRLGrilleRechercheQF(data)
        t = tariff_for(self.db,100)
        self.assertEqual(obj.RechercheQF(t,6,datetime.date(2026,7,15)),99999.)
        self.assertEqual(obj.RechercheQF(t,2,datetime.date(2026,7,15)),99999.)

    def test_11_recherche_qf_source_valeur_zero_connue(self):
        obj = wxsrc.CTRLGrilleRechercheQF({7:[(datetime.date(2026,1,1), datetime.date(2026,12,31),0,1)]})
        self.assertEqual(obj.RechercheQF(tariff_for(self.db,100),7,datetime.date(2026,7,15)),0)

    def test_12_recherche_qf_source_tous_types_par_defaut(self):
        data={1:[(datetime.date(2026,1,1),datetime.date(2026,12,31),700,2)]}
        obj=wxsrc.CTRLGrilleRechercheQF(data)
        t=tariff_for(self.db,100)
        self.assertEqual(obj.RechercheQF(t,1,datetime.date(2026,7,15)),99999.0)
        t['IDtype_quotient']=None
        self.assertEqual(obj.RechercheQF(t,1,datetime.date(2026,7,15)),700)

    def test_13_recherche_qf_source_chevauchement_choisit_premier(self):
        data={1:[(datetime.date(2026,1,1),datetime.date(2026,12,31),650,1),
                 (datetime.date(2026,7,1),datetime.date(2026,12,31),900,1)]}
        obj=wxsrc.CTRLGrilleRechercheQF(data)
        self.assertEqual(obj.RechercheQF(tariff_for(self.db,100),1,datetime.date(2026,7,20)),650)

    def test_14_agregateur_source_marque_conflit_multitypes(self):
        q=wxsrc._QuotientsAlaDate([(2,11,'2026-01-01','2026-12-31',600,1),
                                   (2,12,'2026-01-01','2026-12-31',900,2)],'2026-07-15')
        self.assertEqual(q[2],'a_verifier')

    def test_15_agregateur_source_accepte_egalite_multitypes(self):
        q=wxsrc._QuotientsAlaDate([(2,11,'2026-01-01','2026-12-31',600,1),
                                   (2,12,'2026-01-01','2026-12-31',600,2)],'2026-07-15')
        self.assertEqual(q[2],600)

    def test_16_source_peut_marquer_periode_mal_formee_meme_ancienne(self):
        q=wxsrc._QuotientsAlaDate([(2,11,'2022-12-01','2022-01-01',600,1),
                                   (2,12,'2026-01-01','2026-12-31',600,1)],'2026-07-15')
        self.assertEqual(q[2],'a_verifier')

    def test_17_tranches_source_en_union_peuvent_decouper_autrement_la_grille(self):
        # Deux barèmes pour une activite deguisee: sans l'IDtarif, des
        # plages divergentes sont fusionnees en fragments (300-399,400-699).
        out=wxsrc._TranchesTarifsExclusives([(0,399),(300,699)])
        self.assertIn((300,399),out)
        self.assertIn((400,699),out)

    def test_18_tarif_pratique_nest_pas_la_tranche_qf(self):
        row=self.db.execute('SELECT IDtarif, IDcategorie_tarif FROM prestations WHERE IDprestation=2101').fetchone()
        row2=self.db.execute('SELECT IDtarif, IDcategorie_tarif FROM prestations WHERE IDprestation=3101').fetchone()
        self.assertEqual(tuple(row),tuple(row2))
        fam=aggregate(self.db, family=True)['detail']
        self.assertNotEqual(fam[2]['tariff_group'],fam[3]['tariff_group'])

    def test_19_les_prestations_davant_facture_sont_lisibles(self):
        x=self.db.execute('SELECT COUNT(*) FROM prestations WHERE IDfacture IS NULL').fetchone()[0]
        self.assertGreater(x,0)
        self.assertIn(2, aggregate(self.db,family=True)['detail'])

    def test_20_la_presence_sans_prestation_reste_present(self):
        row=self.db.execute("SELECT IDprestation FROM consommations WHERE IDconso=10 AND etat='present'").fetchone()
        self.assertIsNone(row[0])
        self.assertIn(5,aggregate(self.db,family=True)['detail'])

    def test_21_les_prestations_nenregistrent_pas_idligne(self):
        cols={row['name'] for row in self.db.execute('PRAGMA table_info(prestations)')}
        self.assertNotIn('IDligne',cols)
        self.assertNotIn('IDtype_quotient',cols)
        self.assertNotIn('QF_applique',cols)

    def test_22_montant_egal_ne_permet_pas_de_retrouver_tranche(self):
        # Deux histoires tarifaires imaginables ont les memes champs de
        # prestation et le meme montant, malgre des tranches differentes.
        prestation=dict(self.db.execute('SELECT * FROM prestations WHERE IDprestation=10101').fetchone())
        histoires=[{'qf':350,'tranche':'D','ancienne_borne_max_d':399,'montant':prestation['montant']},
                   {'qf':350,'tranche':'C','ancienne_borne_max_d':299,'montant':prestation['montant']}]
        traces=[(prestation['IDtarif'],prestation['IDcategorie_tarif'],prestation['montant'],prestation['date']) for _ in histoires]
        self.assertEqual(traces[0],traces[1]); self.assertNotEqual(histoires[0]['tranche'],histoires[1]['tranche'])

    def test_23_qf_et_tarif_deux_repartitions_distinctes(self):
        a=aggregate(self.db,family=True)
        self.assertEqual(sum(a['qf'].values()),a['denominator'])
        self.assertEqual(sum(a['tariffs'].values()),a['denominator'])
        self.assertNotEqual(a['qf'],a['tariffs'])

    def test_24_statistiques_multisites_dedoublonnees(self):
        f=aggregate(self.db,family=True)
        a=aggregate(self.db,family=True,activities=(10,))
        b=aggregate(self.db,family=True,activities=(11,))
        self.assertEqual((a['denominator'],b['denominator'],f['denominator']),(7,3,9))

    def test_25_periode_partielle_prend_le_qf_correspondant(self):
        debut=aggregate(self.db,a='2026-07-01',b='2026-07-14',family=True)['detail'][1]
        fin=aggregate(self.db,a='2026-07-01',b='2026-07-31',family=True)['detail'][1]
        self.assertEqual((debut['qf'],fin['qf']),(650,850))

    def test_26_sans_tarif_accueil_ne_pas_prendre_repas(self):
        a=aggregate(self.db,family=True)['detail'][1]
        self.assertEqual(a['date'],'2026-07-30')

    def test_27_source_barres_ninclut_pas_a_verifier(self):
        self.db.execute('INSERT INTO quotients VALUES(91,9,1,\'2026-07-01\',\'2026-07-31\',900)')
        result=wxsrc.GetDictQuotients(self.bridge,param())
        self.assertEqual(result['dictTranchesTarifs']['a_verifier'],1)
        fig=plt.figure()
        try:
            wxsrc.Graphe_qf_defaut().MAJ(figure=fig,DB=self.bridge,dictParametres=param())
            total=sum(int(x.get_height()) for x in fig.axes[0].patches)
            self.assertEqual(total,sum(result['dictTranchesDefaut'].values())-result['dictTranchesDefaut']['pasqf']-result['dictTranchesDefaut']['a_verifier']-result['dictTranchesDefaut']['autre'])
        finally: plt.close(fig)

    def test_28_zero_presences_graphe_ne_devrait_pas_crasher(self):
        result=wxsrc.GetDictQuotients(self.bridge,param(a='2026-02-01',b='2026-02-28'))
        self.assertEqual(sum(result['dictTranchesTarifs'].values()),0)
        fig=plt.figure()
        try:
            wxsrc.Graphe_qf_defaut().MAJ(figure=fig,DB=self.bridge,dictParametres=param(a='2026-02-01',b='2026-02-28'))
            self.assertEqual(len(fig.axes[0].patches),0)
        finally: plt.close(fig)


    def test_29_qf_absent_max_qf_nest_pas_necessairement_prix_max(self):
        # CONTRE-EXEMPLE strictement fictif : un bareme inverse les montants.
        # Le code RechercheQF selectionne un QF fictif de la derniere tranche.
        tarif = {'IDtype_quotient': 1, 'lignes_calcul': [
            {'qf_max': 499, 'montant_unique': 12.0},
            {'qf_max': 99999, 'montant_unique': 6.0},
        ]}
        qf_applique = wxsrc.CTRLGrilleRechercheQF({}).RechercheQF(tarif, 2, datetime.date(2026,7,15))
        self.assertEqual(qf_applique, 99999.0)
        self.assertGreater(tarif['lignes_calcul'][0]['montant_unique'],
                           tarif['lignes_calcul'][1]['montant_unique'])

    def test_30_sans_qf_fallback_non_distingue_par_code_source(self):
        # On ne peut pas inferer du QF renvoye si c'est un justificatif CAF
        # a QF eleve, ou le substitut du cas non communique.
        vrai = wxsrc.CTRLGrilleRechercheQF({1:[
            (datetime.date(2026,1,1),datetime.date(2026,12,31),99999.0,1)]})
        absent = wxsrc.CTRLGrilleRechercheQF({})
        t = tariff_for(self.db,100)
        self.assertEqual(vrai.RechercheQF(t,1,datetime.date(2026,7,15)),
                         absent.RechercheQF(t,2,datetime.date(2026,7,15)))


def run(path):
    path=path.resolve()
    path.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Qualification)
    result=unittest.TestResult()
    suite.run(result)
    data,fig=resultat_initial()
    png=path/'graphe_actuel_qf_defaut_fictif.png'
    fig.savefig(png)
    plt.close(fig)
    data['tests']={'runs':result.testsRun,'success':result.testsRun-len(result.failures)-len(result.errors),
                   'failures':[{'name':x.id(),'trace':trace[-1700:]} for x,trace in result.failures],
                   'errors':[{'name':x.id(),'trace':trace[-1700:]} for x,trace in result.errors],
                   'status':'PASS_OBSERVATION' if result.wasSuccessful() else 'TESTS_NON_PASS'}
    data['exec_mode']='METHODES_SOURCE_ISOLEES / shims wx+MODELES / SQLite fictif'
    data['pas_de_validation_metier']='Les tests valident les observations de divergences, pas les fonctionnalites cibles.'
    data['files_sha256']={x:hashlib.sha256((path/x).read_bytes()).hexdigest() for x in ['extraits_wx_isoles.py','fixture_q442_precedente.py','qualification_q442_wx.py']}
    (path/'constats_methods_wx.json').write_text(json.dumps(data,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
    print('Q442-J2 MODELES WX ISOLES %d/%d %s' %(data['tests']['success'], result.testsRun,data['tests']['status']))
    print('Actuel: %s familles; objectif: %s familles'%(data['total_ancien'],data['population_cible']['familles']))
    print('Graphique barres (%s) : %s observations; Sans QF=%s' % (data['graphique_barres_defaut'],data['graphique_effectif'],data['qf_manquant']))
    for f in data['tests']['failures']+data['tests']['errors']:
        print('FAILED',f['name'],f['trace'])
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path(__file__).parent)
    args=ap.parse_args()
    sys.exit(run(args.output))
