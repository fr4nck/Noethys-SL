# -*- coding: utf-8 -*-
"""C2: synthetic Noethys address history and municipal attendance only."""
import csv
import importlib.util
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'noethys'/'Utils'))
import UTILS_ALSH_Commune as c1
import UTILS_ALSH_AdresseAuto as c2

TARIFFS = [dict(code_insee='00001', IDactivite=101, IDgroupe=201,
                date_debut='2025-01-01',date_fin='2027-01-01',
                prix_jour='11.55',reference='CONVENTION-FICTIVE-A'),
           dict(code_insee='00002', IDactivite=101, IDgroupe=201,
                date_debut='2025-01-01',date_fin='2027-01-01',
                prix_jour='12.50',reference='CONVENTION-FICTIVE-B'),
           dict(code_insee='00003', IDactivite=101, IDgroupe=201,
                date_debut='2025-01-01',date_fin='2027-01-01',
                prix_jour='13.00',reference='CONVENTION-FICTIVE-C')]

class AdresseAutomatiqueTests(unittest.TestCase):
    def setUp(self):
        self.cn=sqlite3.connect(':memory:')
        self.cn.execute('PRAGMA foreign_keys=ON')
        self.cn.executescript('''
            CREATE TABLE individus (IDindividu INTEGER PRIMARY KEY, nom TEXT, prenom TEXT,
                adresse_auto INTEGER, rue_resid TEXT, cp_resid TEXT, ville_resid TEXT, mail TEXT);
            CREATE TABLE activites (IDactivite INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE groupes (IDgroupe INTEGER PRIMARY KEY,IDactivite INTEGER,nom TEXT);
            CREATE TABLE unites (IDunite INTEGER PRIMARY KEY,IDactivite INTEGER,nom TEXT);
            CREATE TABLE consommations (IDconso INTEGER PRIMARY KEY,IDindividu INTEGER,
                IDactivite INTEGER,IDgroupe INTEGER,IDunite INTEGER,date TEXT,
                etat TEXT,quantite INTEGER);
            CREATE TABLE factures (IDfacture INTEGER PRIMARY KEY, montant TEXT);
            CREATE TABLE prestations (IDprestation INTEGER PRIMARY KEY, montant TEXT);
            INSERT INTO individus VALUES
                (1,'Parent','Fictif',NULL,'1 rue des Chenes','35000','COMMUNE A',''),
                (2,'Enfant','Exemple',1,NULL,NULL,NULL,''),
                (3,'Deuxieme','Exemple',1,NULL,NULL,NULL,'');
            INSERT INTO activites VALUES (101,'Accueil enfants test');
            INSERT INTO groupes VALUES (201,101,'ALSH fictif');
            INSERT INTO unites VALUES (301,101,'Jour'),(302,101,'Matin'),
                                     (303,101,'Apres-midi'),(304,101,'Repas');
            INSERT INTO factures VALUES (1,'42.00');
            INSERT INTO prestations VALUES (1,'31.00');
        ''')
        self.cn.executescript((ROOT/'noethys'/'Data/Migrations/alsh_communes_c1_sqlite.sql').read_text())
        self.cn.executescript((ROOT/'noethys'/'Data/Migrations/alsh_communes_c2_sqlite.sql').read_text())
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
                        'WHERE source=?',('2026-01-01','etat_initial'))
        self.cn.commit()
        self.perms=lambda a,op:a=='direction'
        self.base=c1.SituationCommunesALSH(self.cn,autoriser=self.perms)
        self.auto=c2.FrequentationCommunesAuto(self.base)
        for cp,name,code in [('35000','COMMUNE A','00001'),
                             ('35001','COMMUNE B','00002'),
                             ('35002','COMMUNE C','00003')]:
            self.auto.correspondance(cp,name,code,name,acteur='direction')
        self.auto.enregistrer_profil('ALSH',[[101,201]],
                 {301:'J',302:'M',303:'A',304:'exclu'}, TARIFFS,acteur='direction')
    def tearDown(self): self.cn.close()
    def conso(self,day,kid=2,unit=301,etat='present'):
        self.cn.execute('INSERT INTO consommations '
          '(IDindividu,IDactivite,IDgroupe,IDunite,date,etat,quantite) '
          'VALUES (?,?,?,?,?,?,1)',(kid,101,201,unit,day,etat))
        self.cn.commit()
    def move(self,when,rue,cp,name,who=1):
        self.cn.execute('UPDATE individus SET rue_resid=?,cp_resid=?,ville_resid=? '
                        'WHERE IDindividu=?',(rue,cp,name,who))
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
          'WHERE IDobservation=(SELECT MAX(IDobservation) FROM alsh_communes_c2_observations)',(when,))
        self.cn.commit()
    def calc(self,frm='2026-01-01',to='2026-12-31'):
        return self.auto.calculer_automatiquement(frm,to,'ALSH',acteur='direction')

    def test_01_baseline_has_only_observation_date(self):
        rows=self.cn.execute('SELECT source,jour_constat FROM alsh_communes_c2_observations').fetchall()
        self.assertEqual(len(rows),3)
        self.assertTrue(all(x==('etat_initial','2026-01-01') for x in rows))

    def test_02_unmodified_phone_or_mail_no_new_snapshot(self):
        before=self.cn.execute('SELECT COUNT(*) FROM alsh_communes_c2_observations').fetchone()[0]
        self.cn.execute('UPDATE individus SET mail=? WHERE IDindividu=1',('email@example.test',))
        self.cn.commit()
        self.assertEqual(self.cn.execute('SELECT COUNT(*) FROM alsh_communes_c2_observations').fetchone()[0],before)

    def test_03_noop_address_update_no_new_snapshot(self):
        self.cn.execute('UPDATE individus SET rue_resid=rue_resid WHERE IDindividu=1')
        self.cn.commit()
        self.assertEqual(self.cn.execute('SELECT COUNT(*) FROM alsh_communes_c2_observations').fetchone()[0],3)

    def test_04_real_update_is_recorded_without_ui_callback(self):
        self.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        self.assertEqual(self.cn.execute('SELECT source FROM alsh_communes_c2_observations '
                         'ORDER BY IDobservation DESC LIMIT 1').fetchone()[0],'modification')

    def test_05_three_communes_and_two_children_follow_parent(self):
        self.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        self.move('2026-09-01','3 rue Haute','35002','COMMUNE C')
        for day in ('2026-02-01','2026-05-01','2026-10-01'):
            self.conso(day)
        self.conso('2026-10-02',kid=3)
        r=self.calc()
        self.assertEqual(r['journees_global'],'4')
        self.assertEqual({x['code_insee']:x['journees'] for x in r['communes']},
                         {'00001':'1','00002':'1','00003':'2'})
        self.assertEqual(r['montant_total_eur'],'50.05')
        self.assertFalse(r['liquidable'])
        self.assertTrue(r['calcul_complet'])
        self.assertEqual(len(r['enfants']),4)
        self.assertEqual(len(r['anomalies']),0)
        self.assertIn('3 rue Haute',r['lignes'][-1]['adresse_complete'])

    def test_06_child_has_no_direct_update_when_parent_moves(self):
        self.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        ids=[x[0] for x in self.cn.execute('SELECT IDindividu FROM alsh_communes_c2_observations '
                                           "WHERE source='modification'")]
        self.assertEqual(ids,[1])
        self.conso('2026-05-15',kid=2)
        self.assertEqual(self.calc()['lignes'][0]['code_insee'],'00002')

    def test_07_direct_child_address_overrides_inherited(self):
        self.cn.execute('UPDATE individus SET adresse_auto=NULL,rue_resid=?,cp_resid=?,ville_resid=? '
                        'WHERE IDindividu=2',('15 chemin du Pont','35002','COMMUNE C'))
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
           'WHERE IDindividu=2 AND source=?',('2026-03-01','modification'))
        self.cn.commit()
        self.conso('2026-05-03')
        self.assertEqual(self.calc()['lignes'][0]['code_insee'],'00003')

    def test_08_automatic_pointer_change_to_another_person(self):
        self.cn.execute('INSERT INTO individus VALUES (4,?,?,?,?,?,?,?)',
                        ('Autre','Parent',None,'4 passage Bas','35002','COMMUNE C',''))
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
           'WHERE IDindividu=4',('2026-01-01',))
        self.cn.execute('UPDATE individus SET adresse_auto=4 WHERE IDindividu=2')
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
           "WHERE IDindividu=2 AND source='modification'",('2026-05-01',))
        self.cn.commit()
        self.conso('2026-02-01');self.conso('2026-06-01')
        self.assertEqual([x['code_insee'] for x in self.calc()['lignes']],['00001','00003'])

    def test_09_unknown_cp_ville_is_not_guessed(self):
        self.move('2026-04-01','chemin Non-reference','35098','VILLAGE INCONNU')
        self.conso('2026-05-01')
        r=self.calc()
        self.assertFalse(r['calcul_complet'])
        self.assertIn('Domicile non renseigne',str(r['anomalies']))
        self.assertEqual(r['communes'],[])

    def test_10_date_before_baseline_is_unattributed(self):
        self.conso('2025-12-31')
        r=self.calc('2025-12-01','2026-01-31')
        self.assertEqual(r['journees_global'],'0')
        self.assertFalse(r['calcul_complet'])

    def test_11_day_of_multiple_address_edits_is_ambiguous(self):
        self.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        self.move('2026-04-01','3 rue Haute','35002','COMMUNE C')
        self.conso('2026-04-01')
        r=self.calc()
        self.assertEqual(r['communes'],[])
        self.assertGreater(len(r['anomalies']),0)

    def test_12_next_day_after_multiple_edits_is_resolvable(self):
        self.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        self.move('2026-04-01','3 rue Haute','35002','COMMUNE C')
        self.conso('2026-04-02')
        self.assertEqual(self.calc()['lignes'][0]['code_insee'],'00003')

    def test_13_cycle_adresse_auto_is_rejected(self):
        self.cn.execute('UPDATE individus SET adresse_auto=2 WHERE IDindividu=1')
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
           "WHERE source='modification'",('2026-04-01',))
        self.cn.commit()
        self.conso('2026-05-01')
        self.assertGreater(len(self.calc()['anomalies']),0)

    def test_14_missing_parent_is_rejected(self):
        self.cn.execute('UPDATE individus SET adresse_auto=999 WHERE IDindividu=2')
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
           "WHERE source='modification'",('2026-04-01',))
        self.cn.commit()
        self.conso('2026-05-01')
        self.assertGreater(len(self.calc()['anomalies']),0)

    def test_15_absent_day_and_meal_are_excluded(self):
        self.conso('2026-05-01',unit=301,etat='absentj')
        self.conso('2026-05-02',unit=304)
        self.assertEqual(self.calc()['journees_global'],'0')

    def test_16_two_halves_fractional_rounding(self):
        self.conso('2026-05-01',unit=302);self.conso('2026-05-01',unit=303)
        r=self.calc()
        self.assertEqual(r['journees_global'],'1.0')
        self.assertEqual(r['montant_total_eur'],'11.55')

    def test_17_config_is_persisted_and_loaded_on_each_calculation(self):
        self.conso('2026-05-01')
        a=self.calc();b=c2.FrequentationCommunesAuto(self.base).calculer_automatiquement(
            '2026-01-01','2026-12-31','ALSH',acteur='direction')
        self.assertEqual(a['communes'],b['communes'])

    def test_18_duplicate_profile_does_not_replace_rules(self):
        with self.assertRaises(c1.ALSHConflit):
            self.auto.enregistrer_profil('ALSH',[[101,201]],{301:'J'},[],acteur='direction')

    def test_19_change_of_insee_alias_is_not_silent(self):
        with self.assertRaises(c1.ALSHConflit):
            self.auto.correspondance('35000','Commune A','99999','Wrong',acteur='direction')

    def test_20_authorization_is_required_for_config(self):
        with self.assertRaises(c1.ALSHAcces):
            self.auto.correspondance('35004','COMMUNE D','00004','Test',acteur='public')

    def test_21_authorization_is_required_for_read(self):
        with self.assertRaises(c1.ALSHAcces):
            self.auto.calculer_automatiquement('2026-01-01','2026-12-31','ALSH',acteur='public')

    def test_22_address_recording_rolls_back_with_parent_change(self):
        before=self.cn.execute('SELECT COUNT(*) FROM alsh_communes_c2_observations').fetchone()[0]
        self.cn.execute('UPDATE individus SET rue_resid=? WHERE IDindividu=1',('provisoire',))
        self.cn.rollback()
        self.assertEqual(self.cn.execute('SELECT COUNT(*) FROM alsh_communes_c2_observations').fetchone()[0],before)
        self.assertEqual(self.cn.execute('SELECT rue_resid FROM individus WHERE IDindividu=1').fetchone()[0],
                         '1 rue des Chenes')

    def test_23_new_individu_insert_is_captured_automatically(self):
        self.cn.execute('INSERT INTO individus VALUES (5,?,?,?,?,?,?,?)',
                        ('Nouvel','Enfant',1,None,None,None,''))
        self.cn.commit()
        self.assertEqual(self.cn.execute('SELECT source FROM alsh_communes_c2_observations '
          'WHERE IDindividu=5').fetchone()[0],'creation')

    def test_24_csv_stays_commune_scoped_and_preparatory(self):
        self.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        self.conso('2026-02-01');self.conso('2026-05-01')
        res=self.calc()
        csv1=self.base.csv_nominatif(res,acteur='direction',code_insee='00001')
        self.assertIn('1 rue des Chenes',csv1)
        self.assertNotIn('2 rue Neuve',csv1)
        self.assertIn('DOCUMENT PREPARATOIRE',csv1)

    def test_25_historical_manual_rows_do_not_override_auto_source(self):
        self.base.ajouter_domicile(2,'2026-01-01',None,'rue MANUELLE','35002','COMMUNE C',
            '00003',acteur='direction',justificatif='manuel fictif')
        self.conso('2026-05-01')
        r=self.calc()
        self.assertIsNone(r['lignes'][0]['code_insee'])
        self.assertEqual(r['source_domiciles'],'observations_automatiques_noethys')
        self.assertTrue(r['anomalies'])

    def test_26_unknown_effective_date_cannot_be_historically_invented(self):
        self.conso('2025-08-01')
        self.assertEqual(self.calc('2025-01-01','2026-12-31')['journees_global'],'0')

    def test_27_date_correction_requires_proof(self):
        event=self.cn.execute("SELECT IDobservation FROM alsh_communes_c2_observations "
            "WHERE IDindividu=1 AND source='etat_initial'").fetchone()[0]
        with self.assertRaises(c1.ALSHErreur):
            self.auto.valider_date_effet(event,'2025-01-01','',acteur='direction')

    def test_28_proved_date_backfill_is_explicit(self):
        event=self.cn.execute("SELECT IDobservation FROM alsh_communes_c2_observations "
            "WHERE IDindividu=1 AND source='etat_initial'").fetchone()[0]
        self.auto.valider_date_effet(event,'2025-01-01','copie justificatif fictif',acteur='direction')
        # The inherited link itself also needs evidence for this past period.
        child_event=self.cn.execute("SELECT IDobservation FROM alsh_communes_c2_observations "
            "WHERE IDindividu=2 AND source='etat_initial'").fetchone()[0]
        self.auto.valider_date_effet(child_event,'2025-01-01','preuve lien domicile fictive',acteur='direction')
        self.conso('2025-08-01')
        r=self.calc('2025-01-01','2026-12-31')
        self.assertEqual(r['journees_global'],'1')

    def test_29_cannot_rewrite_validated_date_silently(self):
        event=self.cn.execute("SELECT IDobservation FROM alsh_communes_c2_observations "
            "WHERE IDindividu=1 AND source='etat_initial'").fetchone()[0]
        self.auto.valider_date_effet(event,'2025-01-01','preuve fictive',acteur='direction')
        with self.assertRaises(c1.ALSHConflit):
            self.auto.valider_date_effet(event,'2024-01-01','autre preuve',acteur='direction')

    def test_30_no_write_to_family_invoice_tables(self):
        self.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        self.conso('2026-05-01');self.calc()
        self.assertEqual(self.cn.execute('SELECT montant FROM factures').fetchone()[0],'42.00')
        self.assertEqual(self.cn.execute('SELECT montant FROM prestations').fetchone()[0],'31.00')

    def test_31_c2_mysql_ddl_is_safely_separate(self):
        s=(ROOT/'noethys/Data/Migrations/alsh_communes_c2_mysql57.sql').read_text()
        self.assertIn('CREATE TRIGGER alsh_c2_suivi_modification',s)
        self.assertIn('OLD.adresse_auto <=> NEW.adresse_auto',s)
        self.assertNotIn('ALTER TABLE individus',s)
        self.assertNotIn('CREATE TABLE factures',s)

    def test_32_french_city_name_normalized_to_same_key(self):
        self.assertEqual(c2._nom_ville('  La GuErChE  '),'LA GUERCHE')
        self.assertEqual(c2._nom_ville('Ecole'),c2._nom_ville('ÉCOLE'))


    def test_33_direct_bulk_update_does_not_skip_triggers(self):
        self.cn.execute('UPDATE individus SET rue_resid=? WHERE IDindividu IN (1,2)',
                        ('test modification directe',))
        self.cn.commit()
        self.assertEqual(self.cn.execute("SELECT COUNT(*) FROM alsh_communes_c2_observations "
           "WHERE source='modification'").fetchone()[0],2)

    def test_34_two_connections_serialize_and_capture_both_changes(self):
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            dbfile=Path(tmp)/'communes.db'
            dest=sqlite3.connect(str(dbfile))
            self.cn.backup(dest)
            dest.close()
            errors=[]
            start=threading.Barrier(2)
            def worker(address):
                db=sqlite3.connect(str(dbfile),timeout=10)
                try:
                    start.wait(timeout=10)
                    db.execute('UPDATE individus SET rue_resid=? WHERE IDindividu=1',
                               (address,))
                    db.commit()
                except Exception as exc:
                    errors.append(str(exc))
                finally: db.close()
            a=threading.Thread(target=worker,args=('rue concurrente A',))
            b=threading.Thread(target=worker,args=('rue concurrente B',))
            a.start();b.start();a.join(20);b.join(20)
            self.assertFalse(errors,errors)
            check=sqlite3.connect(str(dbfile))
            try:
                self.assertEqual(check.execute("SELECT COUNT(*) FROM alsh_communes_c2_observations "
                    "WHERE source='modification' AND IDindividu=1").fetchone()[0],2)
            finally: check.close()

    def test_35_previous_proved_manual_period_is_usable_before_observations(self):
        self.base.ajouter_domicile(2,'2025-01-01','2026-01-01',
            '5 rue ancienne','35000','COMMUNE A','00001',
            acteur='direction',justificatif='preuve passe fictive')
        self.conso('2025-08-01')
        r=self.calc('2025-01-01','2026-12-31')
        self.assertEqual(r['journees_global'],'1')
        self.assertIn('5 rue ancienne',r['lignes'][0]['adresse_complete'])

    def test_36_non_recognized_identity_stays_review_pending(self):
        self.cn.execute('UPDATE individus SET adresse_auto=NULL, rue_resid=NULL, '
                        'cp_resid=NULL, ville_resid=NULL WHERE IDindividu=2')
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
           "WHERE IDindividu=2 AND source='modification'",('2026-04-01',))
        self.cn.commit()
        self.conso('2026-05-01')
        self.assertTrue(self.calc()['anomalies'])

    def test_37_nested_parent_address_auto_is_recomputed(self):
        self.cn.execute('INSERT INTO individus VALUES (4,?,?,?,?,?,?,?)',
                        ('Aieul','Fictif',None,'12 rue Haute','35002','COMMUNE C',''))
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
                        'WHERE IDindividu=4',('2026-01-01',))
        self.cn.execute('UPDATE individus SET adresse_auto=4 WHERE IDindividu=1')
        self.cn.execute('UPDATE alsh_communes_c2_observations SET jour_constat=? '
            "WHERE IDindividu=1 AND source='modification'",('2026-04-01',))
        self.cn.commit()
        self.conso('2026-02-01');self.conso('2026-05-01')
        result=self.calc()
        self.assertEqual([r['code_insee'] for r in result['lignes']],['00001','00003'])

    def test_38_changes_only_impact_real_attendance_units(self):
        self.move('2026-04-01','rue deux','35001','COMMUNE B')
        self.conso('2026-02-01',unit=304)
        self.conso('2026-05-01',unit=301,etat='reservation')
        self.assertEqual(self.calc()['communes'],[])

    def test_39_exact_postcode_city_matching_no_name_guess(self):
        self.move('2026-04-01','rue deux','35001','COMMUNE A')
        self.conso('2026-05-01')
        self.assertEqual(self.calc()['journees_global'],'0')

    def test_40_no_rewrite_of_legacy_numbered_invoices(self):
        before=self.cn.execute('SELECT * FROM factures').fetchall()
        self.move('2026-04-01','rue deux','35001','COMMUNE B')
        self.conso('2026-05-01');self.calc()
        self.assertEqual(self.cn.execute('SELECT * FROM factures').fetchall(),before)

if __name__=='__main__': unittest.main()
