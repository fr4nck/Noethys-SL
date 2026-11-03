# -*- coding: utf-8 -*-
"""ALSH C1 : uniquement enfants et donnees synthetiques, aucune base MAD lue."""
import csv
from decimal import Decimal
from pathlib import Path
import importlib.util
import io
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
path = ROOT/'noethys'/'Utils'/'UTILS_ALSH_Commune.py'
spec = importlib.util.spec_from_file_location('alshc1', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Les codes INSEE 00001/00002/00003, noms et adresses sont fictifs.
TAUX = [
 dict(code_insee='00001', date_debut='2026-01-01', date_fin='2027-01-01', prix_jour='10.00', reference='CONV-A', IDactivite=101, IDgroupe=201),
 dict(code_insee='00002', date_debut='2026-01-01', date_fin='2027-01-01', prix_jour='12.50', reference='CONV-B', IDactivite=101, IDgroupe=201),
 dict(code_insee='00003', date_debut='2026-01-01', date_fin='2027-01-01', prix_jour='11.00', reference='CONV-C', IDactivite=101, IDgroupe=201),
]


class SituationTests(unittest.TestCase):
    def setUp(self):
        self.cn=sqlite3.connect(':memory:')
        self.cn.execute('PRAGMA foreign_keys=ON')
        self.cn.executescript('''
            CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, nom TEXT, prenom TEXT,
                                    rue_resid TEXT, cp_resid TEXT, ville_resid TEXT);
            CREATE TABLE activites (IDactivite INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE groupes (IDgroupe INTEGER PRIMARY KEY, IDactivite INTEGER, nom TEXT);
            CREATE TABLE unites (IDunite INTEGER PRIMARY KEY, IDactivite INTEGER, nom TEXT);
            CREATE TABLE consommations (IDconso INTEGER PRIMARY KEY, IDindividu INTEGER, IDactivite INTEGER,
               IDgroupe INTEGER, IDunite INTEGER, date TEXT, etat TEXT, quantite INTEGER);
            CREATE TABLE prestations (IDprestation INTEGER PRIMARY KEY, montant TEXT);
            CREATE TABLE factures (IDfacture INTEGER PRIMARY KEY, montant TEXT);
            INSERT INTO individus VALUES (1,'Martin','Léa','adresse actuelle sans histoire','99999','COMMUNE D'),
                                         (2,'Durand','Noé',NULL,NULL,NULL),
                                         (3,'=ESSAI','+TEST',NULL,NULL,NULL);
            INSERT INTO activites VALUES (101,'Accueil fictif'),(102,'Autre ALSH fictif');
            INSERT INTO groupes VALUES (201,101,'Enfants'),(202,102,'Autres');
            INSERT INTO unites VALUES (301,101,'Journée'),(302,101,'Matin'),(303,101,'Après-midi'),
                                     (304,101,'Repas'),(401,102,'Journée');
            INSERT INTO prestations VALUES (1,'50.00');
            INSERT INTO factures VALUES (1,'70.00');
        ''')
        self.cn.executescript((ROOT/'noethys'/'Data'/'Migrations'/'alsh_communes_c1_sqlite.sql').read_text())
        self.cn.commit()
        self.perm = lambda acteur,action: acteur=='direction'
        self.moteur=m.SituationCommunesALSH(self.cn,autoriser=self.perm)
        self.perimetres=[(101,201)]
        self.unites={301:'J',302:'M',303:'A',304:'exclu'}

    def tearDown(self):
        self.cn.close()

    def add(self, d, fin, name, code, kid=1):
        return self.moteur.ajouter_domicile(kid,d,fin,'4 rue des Cerisiers','35000',name,code,
                       acteur='direction',complement='Appartement 2',justificatif='attestation fictive')

    def residence3(self):
        self.add('2026-01-01','2026-04-01','COMMUNE A','00001')
        self.add('2026-04-01','2026-09-01','COMMUNE B','00002')
        self.add('2026-09-01',None,'COMMUNE C','00003')

    def conso(self, kid, day, unit, etat='present', activity=101, group=201, quantite=None):
        self.cn.execute('INSERT INTO consommations '
                        '(IDindividu,IDactivite,IDgroupe,IDunite,date,etat,quantite) '
                        'VALUES (?,?,?,?,?,?,?)',(kid,activity,group,unit,day,etat,quantite))
        self.cn.commit()

    def calc(self, tarifs=TAUX, perimetres=None, unites=None):
        return self.moteur.calculer('2026-01-01','2026-12-31',
            self.perimetres if perimetres is None else perimetres,
            self.unites if unites is None else unites,acteur='direction',tarifs=tarifs)

    def test_01_non_assujetti_aux_tables_financieres(self):
        self.residence3(); self.conso(1,'2026-02-01',301);self.calc()
        self.assertEqual(self.cn.execute('SELECT montant FROM prestations').fetchone()[0],'50.00')
        self.assertEqual(self.cn.execute('SELECT montant FROM factures').fetchone()[0],'70.00')

    def test_02_3_demenagements_participation_distincte(self):
        self.residence3()
        self.conso(1,'2026-02-01',301)
        self.conso(1,'2026-05-01',301)
        self.conso(1,'2026-10-01',301)
        r=self.calc()
        self.assertEqual(r['enfants_distincts_global'],1)
        self.assertEqual(sum(x['enfants_distincts'] for x in r['communes']),3)
        self.assertEqual([x['code_insee'] for x in r['communes']],['00001','00002','00003'])
        self.assertEqual([x['montant_eur'] for x in r['communes']],['10.00','12.50','11.00'])
        self.assertEqual(r['montant_total_eur'],'33.50')
        self.assertEqual(r['journees_global'],'3')
        self.assertTrue(r['liquidable'])

    def test_03_deux_demi_journees_egal_un(self):
        self.residence3()
        self.conso(1,'2026-03-03',302)
        self.conso(1,'2026-03-03',303)
        r=self.calc()
        self.assertEqual(r['journees_global'],'1.0')
        self.assertEqual(r['montant_total_eur'],'10.00')
        self.assertEqual([x['unite_jour'] for x in r['lignes']],['0.5','0.5'])

    def test_04_une_seule_demi_journee(self):
        self.residence3();self.conso(1,'2026-03-03',302)
        self.assertEqual(self.calc()['montant_total_eur'],'5.00')

    def test_05_pas_domicile_pas_de_commune_arbitraire(self):
        self.conso(1,'2026-03-03',301)
        r=self.calc()
        self.assertFalse(r['liquidable']);self.assertEqual(r['communes'],[])
        self.assertIn('Domicile non renseigne',str(r['anomalies']))

    def test_06_rue_actuelle_n_est_pas_utilisee_pour_passe(self):
        self.residence3();self.conso(1,'2026-03-03',301)
        r=self.calc();self.assertNotIn('adresse actuelle',str(r['lignes']))
        self.assertIn('Cerisiers',r['lignes'][0]['adresse_complete'])

    def test_07_absence_non_facturable(self):
        self.residence3();self.conso(1,'2026-02-01',301,'absentj')
        r=self.calc();self.assertEqual(r['journees_global'],'0')
        self.assertEqual(r['lignes'][0]['statut'],'non_present')

    def test_08_reservation_non_facturable(self):
        self.residence3();self.conso(1,'2026-02-01',301,'reservation')
        self.assertEqual(self.calc()['communes'],[])

    def test_09_repas_exclu(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        self.conso(1,'2026-02-01',304)
        r=self.calc();self.assertEqual(r['journees_global'],'1')
        self.assertEqual(r['lignes'][1]['statut'],'hors_perimetre')

    def test_10_deux_journees_le_meme_jour_bloquees(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        self.conso(1,'2026-02-01',301)
        r=self.calc();self.assertFalse(r['liquidable']);self.assertEqual(r['journees_global'],'0')
        self.assertEqual(len(r['anomalies']),2)

    def test_11_journee_plus_matin_bloques(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        self.conso(1,'2026-02-01',302)
        self.assertEqual(self.calc()['journees_global'],'0')

    def test_12_deux_matins_bloques(self):
        self.residence3();self.conso(1,'2026-02-01',302)
        self.conso(1,'2026-02-01',302)
        self.assertEqual(self.calc()['journees_global'],'0')

    def test_13_multisite_un_seul_jour(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        self.conso(1,'2026-02-01',401,activity=102,group=202)
        r=self.calc(perimetres=[(101,201),(102,202)],unites={**self.unites,401:'J'})
        self.assertEqual(r['journees_global'],'0')

    def test_14_unite_non_parametree_bloque(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        r=self.calc(unites={302:'M'})
        self.assertFalse(r['liquidable']);self.assertEqual(r['journees_global'],'0')

    def test_15_quantite_anormale_bloque(self):
        self.residence3();self.conso(1,'2026-02-01',301,quantite=2)
        self.assertFalse(self.calc()['liquidable'])

    def test_16_taux_non_fournis_statut_non_liquidable(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        r=self.calc(tarifs=None)
        self.assertEqual(r['lignes'][0]['statut'],'presence_sans_tarif')
        self.assertIsNone(r['montant_total_eur'])
        self.assertFalse(r['liquidable'])

    def test_17_taux_partiel_refuse_lors_d_un_calcul(self):
        self.residence3();self.conso(1,'2026-10-01',301)
        self.assertFalse(self.calc(tarifs=TAUX[:2])['liquidable'])

    def test_18_taux_chevauchants_refuses(self):
        self.residence3()
        with self.assertRaises(m.ALSHConflit):self.calc(tarifs=TAUX+[dict(TAUX[0])])

    def test_19_taux_float_interdit(self):
        bad=dict(TAUX[0],prix_jour=0.1)
        with self.assertRaises(m.ALSHErreur):self.calc(tarifs=[bad])

    def test_20_perimetre_exact_ne_croise_pas_groupes(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        self.conso(1,'2026-02-02',401,activity=102,group=202)
        r=self.calc(perimetres=[(101,201)])
        self.assertEqual(len(r['lignes']),1)

    def test_21_configuration_unite_inconnue_rejetee(self):
        with self.assertRaises(m.ALSHErreur):self.calc(unites={301:'journee'})

    def test_22_overlap_de_residence_rejete_et_audite(self):
        self.add('2026-01-01','2026-06-01','COMMUNE A','00001')
        with self.assertRaises(m.ALSHConflit):
            self.add('2026-05-01',None,'COMMUNE B','00002')
        self.assertEqual(self.cn.execute('SELECT count(*) FROM alsh_communes_domiciles').fetchone()[0],1)
        self.assertEqual(self.cn.execute('SELECT count(*) FROM alsh_communes_domiciles_audit').fetchone()[0],1)

    def test_23_residences_contigues_acceptes(self):
        self.add('2026-01-01','2026-06-01','COMMUNE A','00001')
        self.add('2026-06-01',None,'COMMUNE B','00002')
        self.assertEqual(len(self.moteur.domiciles(1,acteur='direction')),2)

    def test_24_cloture_et_nouvelle_residence(self):
        a=self.add('2026-01-01',None,'COMMUNE A','00001')
        self.moteur.cloturer_domicile(a,'2026-04-01',acteur='direction')
        self.add('2026-04-01',None,'COMMUNE B','00002')
        self.assertEqual(self.cn.execute('SELECT count(*) FROM alsh_communes_domiciles_audit').fetchone()[0],3)

    def test_25_cloture_invalide_ne_modifie_pas(self):
        a=self.add('2026-01-01',None,'COMMUNE A','00001')
        with self.assertRaises(m.ALSHErreur):
            self.moteur.cloturer_domicile(a,'2025-12-01',acteur='direction')
        self.assertIsNone(self.cn.execute('SELECT date_fin FROM alsh_communes_domiciles').fetchone()[0])

    def test_26_acces_refuse(self):
        with self.assertRaises(m.ALSHAcces):
            self.moteur.calculer('2026-01-01','2026-12-31',[(101,201)],self.unites,acteur='observateur')
        with self.assertRaises(m.ALSHAcces):
            self.moteur.ajouter_domicile(1,'2026-01-01',None,'rue','35000','Ville','00001',
                                         acteur='observateur',justificatif='preuve')

    def test_27_export_nominatif_filtre_commune(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        self.conso(1,'2026-05-01',301)
        r=self.calc(); s=self.moteur.csv_nominatif(r,acteur='direction',code_insee='00001')
        self.assertIn('2026-02-01',s);self.assertNotIn('2026-05-01',s)
        self.assertIn('Cerisiers',s)
        self.assertEqual(self.cn.execute('SELECT code_insee,nombre_lignes FROM alsh_communes_exports').fetchone(),
                         ('00001',1))

    def test_28_export_anonyme_sans_identite_ni_adresse(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        r=self.calc(); s=self.moteur.csv_anonyme(r,acteur='direction')
        self.assertNotIn('Martin',s);self.assertNotIn('Cerisiers',s)

    def test_29_export_nom_formule_excel_ne_s_execute_pas(self):
        self.add('2026-01-01',None,'COMMUNE A','00001',kid=3)
        self.conso(3,'2026-02-01',301)
        s=self.moteur.csv_nominatif(self.calc(),acteur='direction',code_insee='00001')
        self.assertIn("'=ESSAI",s);self.assertIn("'+TEST",s)

    def test_30_export_nominatif_necessite_commune(self):
        r=self.calc()
        with self.assertRaises(m.ALSHErreur):self.moteur.csv_nominatif(r,acteur='direction')

    def test_31_dates_incoherentes_refusees(self):
        with self.assertRaises(m.ALSHErreur):
            self.moteur.calculer('2026-12-31','2026-01-01',self.perimetres,self.unites,acteur='direction')
        with self.assertRaises(m.ALSHErreur):
            self.add('2026-02-30',None,'COMMUNE A','00001')

    def test_32_double_perimetre_refuse(self):
        with self.assertRaises(m.ALSHErreur):self.calc(perimetres=[(101,201),(101,201)])

    def test_33_deux_enfants_distincts_meme_commune(self):
        self.residence3();self.add('2026-01-01',None,'COMMUNE A','00001',kid=2)
        self.conso(1,'2026-02-01',301);self.conso(2,'2026-02-01',301)
        r=self.calc()
        self.assertEqual(r['communes'][0]['enfants_distincts'],2)
        self.assertEqual(r['montant_total_eur'],'20.00')

    def test_34_insee_invalide_rejete(self):
        with self.assertRaises(m.ALSHErreur):self.add('2026-01-01',None,'COMMUNE A','Bais')

    def test_35_une_transaction_externe_n_est_pas_commitee(self):
        self.cn.execute("UPDATE individus SET prenom='Z' WHERE IDindividu=1")
        with self.assertRaises(m.ALSHConflit):self.add('2026-01-01',None,'COMMUNE A','00001')
        self.cn.rollback()
        self.assertEqual(self.cn.execute('SELECT prenom FROM individus WHERE IDindividu=1').fetchone()[0], 'Léa')

    def test_36_cles_etrangeres_sqlite_ok(self):
        self.residence3()
        self.assertEqual(self.cn.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_37_mysql_non_valide_ne_passe_pas(self):
        class Faux: pass
        with self.assertRaises(m.ALSHErreur):m.SituationCommunesALSH(Faux(),dialecte='mysql',autoriser=self.perm)

    def test_38_schema_mysql_ne_modifie_pas_factures(self):
        sql=(ROOT/'noethys'/'Data'/'Migrations'/'alsh_communes_c1_mysql57.sql').read_text().lower()
        self.assertEqual(sql.count('engine=innodb'),3)
        self.assertNotIn('alter table',sql)
        self.assertNotIn('insert into',sql)
        self.assertNotIn('create table factures',sql)

    def test_39_justificatif_obligatoire(self):
        with self.assertRaises(m.ALSHErreur):
            self.moteur.ajouter_domicile(1,'2026-01-01',None,'rue','35000','Ville','00001',
                                         acteur='direction',justificatif='')

    def test_41_arrondi_demi_journees_conserve_centime(self):
        self.residence3()
        self.conso(1,'2026-02-01',302)
        self.conso(1,'2026-02-01',303)
        rates=[dict(TAUX[0],prix_jour='11.55')]
        r=self.calc(tarifs=rates)
        self.assertEqual(r['montant_total_eur'],'11.55')
        self.assertEqual(sum(Decimal(x['montant_eur']) for x in r['lignes']),Decimal('11.55'))

    def test_42_tarifs_distincts_pour_activites_et_sites(self):
        self.residence3()
        self.conso(1,'2026-02-01',301)
        self.conso(1,'2026-02-02',401,activity=102,group=202)
        rates=TAUX+[dict(TAUX[0],IDactivite=102,IDgroupe=202,prix_jour='19.55',reference='ADOS')]
        r=self.calc(perimetres=[(101,201),(102,202)],unites={**self.unites,401:'J'},tarifs=rates)
        self.assertEqual(r['montant_total_eur'],'29.55')
        self.assertTrue(r['liquidable'])

    def test_43_autre_presence_non_qualifiee_bloque_jour_entier(self):
        self.residence3()
        self.conso(1,'2026-02-01',302)
        self.conso(1,'2026-02-01',401,activity=102,group=202)
        r=self.calc(perimetres=[(101,201),(102,202)],unites=self.unites)
        self.assertEqual(r['journees_global'],'0')
        self.assertFalse(r['liquidable'])

    def test_44_pas_de_present_jamais_liquidable(self):
        self.residence3();self.conso(1,'2026-02-01',301,'reservation')
        r=self.calc()
        self.assertFalse(r['liquidable'])

    def test_45_exports_contiennent_bornes_domicile(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        r=self.calc()
        self.assertEqual(r['enfants'][0]['domicile_date_fin'],'2026-04-01')
        s=self.moteur.csv_nominatif(r,acteur='direction',code_insee='00001')
        self.assertIn('domicile_date_fin',s)
        self.assertIn('2026-04-01',s)

    def test_46_csv_recap_enfants_par_commune(self):
        self.residence3()
        self.conso(1, '2026-02-01', 301)
        self.conso(1, '2026-05-01', 301)
        r=self.calc()
        s=self.moteur.csv_recap_enfants(r,acteur='direction',code_insee='00001')
        self.assertIn('Léa',s)
        self.assertIn('COMMUNE A',s)
        self.assertNotIn('COMMUNE B',s)
        self.assertIn('domicile_date_debut',s)
        self.assertIn('10.00',s)

    def test_47_export_nominatif_bloque_si_anomalie(self):
        self.residence3()
        self.conso(1,'2026-02-01',301)
        self.conso(2,'2026-02-01',301)
        r=self.calc()
        self.assertEqual(len(r['anomalies']),1)
        with self.assertRaises(m.ALSHConflit):
            self.moteur.csv_nominatif(r,acteur='direction',code_insee='00001')
        with self.assertRaises(m.ALSHConflit):
            self.moteur.csv_recap_enfants(r,acteur='direction',code_insee='00001')
        self.assertEqual(self.cn.execute('SELECT count(*) FROM alsh_communes_exports').fetchone()[0],0)

    def test_48_domicile_fin_exclusive(self):
        self.residence3()
        self.conso(1,'2026-03-31',301)
        self.conso(1,'2026-04-01',301)
        r=self.calc()
        self.assertEqual([x['code_insee'] for x in r['lignes']],['00001','00002'])

    def test_49_csv_bom_lisible_dans_excel(self):
        self.residence3();self.conso(1,'2026-02-01',301)
        s=self.moteur.csv_nominatif(self.calc(),acteur='direction',code_insee='00001')
        self.assertTrue(s.startswith('\ufeff'))
        lignes=list(csv.reader(io.StringIO(s[1:]),delimiter=';'))
        self.assertTrue(len(lignes)>=3)
        self.assertIn('adresse_complete',lignes[1])

    def test_50_deux_processus_une_residence_sans_chevauchement(self):
        import threading
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'test_concurrent.sqlite'
            main=sqlite3.connect(path)
            main.execute('PRAGMA foreign_keys=ON')
            main.execute('CREATE TABLE individus(IDindividu INTEGER PRIMARY KEY)')
            main.execute('INSERT INTO individus VALUES (1)')
            main.executescript((ROOT/'noethys'/'Data'/'Migrations'/
                                'alsh_communes_c1_sqlite.sql').read_text())
            main.commit();main.close()
            barrier=threading.Barrier(2)
            result=[]
            def worker(start):
                cn=sqlite3.connect(path,timeout=5)
                cn.execute('PRAGMA foreign_keys=ON')
                o=m.SituationCommunesALSH(cn,autoriser=self.perm)
                barrier.wait()
                try:
                    o.ajouter_domicile(1,start,None,'Rue test','35000','VILLE','00001',
                                       acteur='direction',justificatif='preuve fictive')
                    result.append('ok')
                except m.ALSHConflit:
                    result.append('conflit')
                finally:
                    cn.close()
            a=threading.Thread(target=worker,args=('2026-01-01',))
            b=threading.Thread(target=worker,args=('2026-02-01',))
            a.start();b.start();a.join(10);b.join(10)
            self.assertEqual(sorted(result),['conflit','ok'])
            cn=sqlite3.connect(path)
            self.assertEqual(cn.execute('SELECT count(*) FROM alsh_communes_domiciles').fetchone()[0],1)
            cn.close()

    def test_51_mysql_connector_start_transaction_admis_mais_non_qualifie(self):
        class Pilote:
            def get_autocommit(self):return False
            def start_transaction(self):pass
        o=m.SituationCommunesALSH(Pilote(),dialecte='mysql',autoriser=self.perm)
        self.assertTrue(callable(o._demarrer_mysql))

    def test_52_mysql_autocommit_on_refuse(self):
        class Pilote:
            def get_autocommit(self):return True
            def start_transaction(self):pass
        with self.assertRaises(m.ALSHErreur):
            m.SituationCommunesALSH(Pilote(),dialecte='mysql',autoriser=self.perm)

    def test_40_connexion_sans_fk_refusee(self):
        other=sqlite3.connect(':memory:')
        self.addCleanup(other.close)
        with self.assertRaises(m.ALSHErreur):m.SituationCommunesALSH(other,autoriser=self.perm)

if __name__=='__main__':
    unittest.main()
