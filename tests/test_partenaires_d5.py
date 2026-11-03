# -*- coding: utf-8 -*-
"""D5 : recette SQLite fictive; aucune connexion ni table de production ouverte."""
import threading
import sqlite3
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'noethys'))
from Utils.UTILS_Partenaires_D1 import AnnuairePartenaires, AutorisationRefusee
from Utils.UTILS_Partenaires_D2 import RegistreConventions, ConventionIntegrite
from Utils.UTILS_Partenaires_D34 import InterventionsPartenaires, PlanningConflit
from Utils.UTILS_Partenaires_D5 import (BordereauxPartenaires, BordereauInvalide,
                                        BordereauConflit,BordereauIntegrite,_prix)

SCRIPTS=[ROOT/'noethys/Data/Migrations'/f'partenaires_{nom}_sqlite.sql'
         for nom in ('d1','d2','d34','d5')]


class D5Tests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.conn.execute('PRAGMA foreign_keys=ON')
        # The historic schema is deliberately represented by non-billing sentinels.
        for t,ident in [('familles','IDfamille'),('consommations','IDconso'),
                        ('prestations','IDprestation'),('factures','IDfacture'),
                        ('compta_tiers','IDtiers'),('comptes_payeurs','IDcompte_payeur')]:
            self.conn.execute(f'CREATE TABLE {t} ({ident} INTEGER PRIMARY KEY, val TEXT)')
            self.conn.execute(f'INSERT INTO {t} VALUES (1,?)',(f'sentinel-{t}',))
        self.conn.commit()
        self.avant=self.sentinelles()
        for s in SCRIPTS:
            self.conn.executescript(s.read_text(encoding='utf-8'))
        self.droit=lambda acteur,action: acteur=='direction'
        self.d1=AnnuairePartenaires(self.conn,autoriser=self.droit)
        self.d2=RegistreConventions(self.conn,autoriser=self.droit)
        self.d34=InterventionsPartenaires(self.conn,autoriser=self.droit)
        self.d5=BordereauxPartenaires(self.conn,autoriser=self.droit)
        self.part=self.d1.creer_structure({'raison_sociale':'Ecole fictive',
                                            'categorie':'ecole'},acteur='direction')
        self.conv=self.d2.creer_convention(self.part,'CV-25','EPS','scolaire',
                '2025-09-01','2026-08-31',acteur='direction')
        self.version=self.d2.ouvrir_version(self.conv,'2025-09-01','Clauses fictives',
                  'word','Template','payante',acteur='direction')
        self.d2.remplacer_tarifs(self.version,[
            {'categorie':'scolaires','libelle':'EPS','unite':'heure','montant':'20.00',
             'date_debut':'2025-09-01','date_fin':'2026-08-31'},
            {'categorie':'scolaires','libelle':'Atelier','unite':'seance','montant':'24.00',
             'date_debut':'2025-09-01','date_fin':'2026-08-31'}],acteur='direction')
        self.d2.signer_version(self.version,'2025-08-25','Direction fictive','a'*64,
                               acteur='direction')
        self.tarifs=self.d2.obtenir_version(self.version,acteur='direction')['tarifs']
        self.t_heure=next(t['IDtarif_convention'] for t in self.tarifs if t['unite']=='heure')
        self.t_seance=next(t['IDtarif_convention'] for t in self.tarifs if t['unite']=='seance')
        self.prog=self.d34.creer_programmation(self.version,'P1','Cycle','2025-09-01',
                                    '2025-12-31',acteur='direction')
        self.d34.ajouter_creneau(self.prog,'hebdomadaire','2025-10-01','2025-10-31',
              '09:00','10:00','CP','EPS','scolaires',acteur='direction',jour_semaine=3,
              intervenant='E1')
        self.d34.valider_programmation(self.prog,acteur='direction')
        self.ids=[x['IDintervention'] for x in self.d34.lister_interventions(self.prog,
                                                          acteur='direction')]
        self.bid=self.d5.creer_bordereau(self.part,self.conv,'OCT-25','2025-10-01',
                                        '2025-10-31',acteur='direction')

    def tearDown(self):
        self.conn.close()

    def sentinelles(self):
        return {t:self.conn.execute(f'SELECT * FROM {t}').fetchall() for t in
                ('familles','consommations','prestations','factures','compta_tiers','comptes_payeurs')}

    def constater(self, index=0, horaire=('09:00','10:00'), decision='eligible'):
        x=self.d34.lister_interventions(self.prog,acteur='direction')[index]
        iid=x['IDintervention']
        self.d34.marquer_realisee(iid,x['date_prevue'],*horaire,'E1',acteur='direction')
        if decision is not None:
            self.d34.decider_facturation(iid,decision,'Accord humain',acteur='direction')
        return iid

    def choix(self, iid=None, tarif=None):
        return [{'IDintervention':iid or self.ids[0],
                 'IDtarif_convention':tarif or self.t_heure}]

    def preview(self, choix=None, bid=None):
        return self.d5.proposer_bordereau(bid or self.bid,choix or self.choix(),acteur='direction')

    def valider(self, choix=None, bid=None):
        choix=choix or self.choix(); bid=bid or self.bid
        return self.d5.valider_bordereau(bid,choix,self.preview(choix,bid)['empreinte'],
                                        acteur='direction')

    def test_two_lines_realised_only_and_no_double_counting(self):
        self.constater(0,horaire=('09:00','10:30'))
        self.constater(1,horaire=('09:00','10:15'))
        selections=self.choix(iid=self.ids[0])+self.choix(iid=self.ids[1])
        p=self.preview(selections)
        self.assertEqual(p['nombre_lignes'],2)
        self.assertEqual(p['total'],'55.00')
        result=self.valider(selections)
        self.assertEqual(result['total'],'55.00')
        self.assertEqual(len(self.d5.lire_bordereau(self.bid,acteur='direction')['lignes']),2)

    def test_two_concurrent_validations_only_one_wins(self):
        self.constater()
        b2=self.d5.creer_bordereau(self.part,self.conv,'OCT-2','2025-10-01',
                                    '2025-10-31',acteur='direction')
        preview1=self.preview(bid=self.bid)['empreinte']
        preview2=self.preview(bid=b2)['empreinte']
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'competition.db')
            target=sqlite3.connect(path)
            self.conn.backup(target)
            target.close()
            barrier=threading.Barrier(2)
            outcomes=[]
            lock=threading.Lock()
            def worker(bid,empreinte):
                co=sqlite3.connect(path,timeout=10)
                co.execute('PRAGMA foreign_keys=ON')
                moteur=BordereauxPartenaires(co,autoriser=self.droit)
                barrier.wait(timeout=10)
                try:
                    moteur.valider_bordereau(bid,self.choix(),empreinte,acteur='direction')
                    resultat='ok'
                except BordereauConflit:
                    resultat='refuse'
                except Exception as e:
                    resultat='erreur:'+repr(e)
                finally:
                    co.close()
                with lock:outcomes.append(resultat)
            a=threading.Thread(target=worker,args=(self.bid,preview1))
            b=threading.Thread(target=worker,args=(b2,preview2))
            a.start();b.start();a.join(15);b.join(15)
            self.assertFalse(a.is_alive() or b.is_alive())
            self.assertCountEqual(outcomes,['ok','refuse'])
            verification=sqlite3.connect(path)
            self.assertEqual(verification.execute('SELECT count(*) FROM partenaires_bordereaux_lignes').fetchone()[0],1)
            self.assertEqual(verification.execute('PRAGMA foreign_key_check').fetchall(),[])
            verification.close()

    def test_reference_ascii_and_case_insensitive(self):
        with self.assertRaises(BordereauInvalide):
            self.d5.creer_bordereau(self.part,self.conv,'=2+2','2025-10-01',
                                    '2025-10-31',acteur='direction')
        with self.assertRaises(BordereauConflit):
            self.d5.creer_bordereau(self.part,self.conv,'oct-25','2025-10-01',
                                    '2025-10-31',acteur='direction')

    def test_csv_escapes_untrusted_contract_label(self):
        # New signed contract version, no mutation of the earlier signed version.
        newv=self.d2.ouvrir_version(self.conv,'2025-11-01','Clauses avenant',
                      'word','Template','payante',acteur='direction')
        self.d2.remplacer_tarifs(newv,[{'categorie':'scolaires',
                 'libelle':'=2+2','unite':'heure','montant':'20.00',
                 'date_debut':'2025-11-01','date_fin':'2026-08-31'}],acteur='direction')
        self.d2.signer_version(newv,'2025-10-30','Direction fictive','b'*64,acteur='direction')
        tarif=self.d2.obtenir_version(newv,acteur='direction')['tarifs'][0]['IDtarif_convention']
        prog=self.d34.creer_programmation(newv,'NOV','Novembre','2025-11-01','2025-11-30',acteur='direction')
        self.d34.ajouter_creneau(prog,'ponctuel','2025-11-06','2025-11-06',
             '09:00','10:00','CP','EPS','scolaires',acteur='direction')
        self.d34.valider_programmation(prog,acteur='direction')
        iv=self.d34.lister_interventions(prog,acteur='direction')[0]['IDintervention']
        self.d34.marquer_realisee(iv,'2025-11-06','09:00','10:00','E1',acteur='direction')
        self.d34.decider_facturation(iv,'eligible','Bon',acteur='direction')
        lot=self.d5.creer_bordereau(self.part,self.conv,'NOV','2025-11-01','2025-11-30',acteur='direction')
        self.valider(self.choix(iid=iv,tarif=tarif),bid=lot)
        csv=self.d5.preparer_csv(lot,acteur='direction')
        self.assertIn("'=2+2",csv)
        self.assertNotIn(';=2+2;',csv)

    def test_forfait_not_priced_per_intervention_without_allocation(self):
        newv=self.d2.ouvrir_version(self.conv,'2025-11-01','Clauses avenant',
                      'word','Template','payante',acteur='direction')
        self.d2.remplacer_tarifs(newv,[{'categorie':'scolaires',
                 'libelle':'Cycle','unite':'forfait','montant':'300.00',
                 'date_debut':'2025-11-01','date_fin':'2026-08-31'}],acteur='direction')
        self.d2.signer_version(newv,'2025-10-31','Direction fictive','b'*64,acteur='direction')
        t=self.d2.obtenir_version(newv,acteur='direction')['tarifs'][0]['IDtarif_convention']
        prog=self.d34.creer_programmation(newv,'NOV','Novembre','2025-11-01','2025-11-30',acteur='direction')
        self.d34.ajouter_creneau(prog,'ponctuel','2025-11-06','2025-11-06',
             '09:00','10:00','CP','EPS','scolaires',acteur='direction')
        self.d34.valider_programmation(prog,acteur='direction')
        iv=self.d34.lister_interventions(prog,acteur='direction')[0]['IDintervention']
        self.d34.marquer_realisee(iv,'2025-11-06','09:00','10:00','E1',acteur='direction')
        self.d34.decider_facturation(iv,'eligible','Bon',acteur='direction')
        lot=self.d5.creer_bordereau(self.part,self.conv,'NOV','2025-11-01','2025-11-30',acteur='direction')
        with self.assertRaises(BordereauInvalide):
            self.preview(self.choix(iid=iv,tarif=t),bid=lot)

    def test_initialement_aucun_mouvement_historique(self):
        self.assertEqual(self.sentinelles(),self.avant)
        self.assertEqual(self.conn.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM partenaires_bordereaux_lignes').fetchone()[0],0)

    def test_permissions_lecture_et_ecriture_refusees_par_defaut(self):
        autre=BordereauxPartenaires(self.conn)
        for op in (lambda: autre.creer_bordereau(self.part,self.conv,'B','2025-10-01','2025-10-31',acteur='direction'),
                   lambda: autre.proposer_bordereau(self.bid,self.choix(),acteur='direction'),
                   lambda: autre.lire_bordereau(self.bid,acteur='direction'),
                   lambda: autre.preparer_csv(self.bid,acteur='direction')):
            with self.assertRaises(AutorisationRefusee):op()
        with self.assertRaises(AutorisationRefusee):
            self.d5.lire_bordereau(self.bid,acteur='observateur')

    def test_month_restriction_and_duplicate_reference(self):
        with self.assertRaises(BordereauInvalide):
            self.d5.creer_bordereau(self.part,self.conv,'B','2025-10-01','2025-11-01',acteur='direction')
        with self.assertRaises(BordereauConflit):
            self.d5.creer_bordereau(self.part,self.conv,'OCT-25','2025-10-01','2025-10-30',acteur='direction')

    def test_only_realised_eligible(self):
        with self.assertRaises(BordereauInvalide):self.preview()
        self.constater(decision=None)
        with self.assertRaises(BordereauInvalide):self.preview()
        self.d34.decider_facturation(self.ids[0],'non_facturable','Decide',acteur='direction')
        with self.assertRaises(BordereauInvalide):self.preview()

    def test_hourly_price_exact_90min_and_rounding(self):
        self.constater(horaire=('09:00','10:30'))
        p=self.preview()
        self.assertEqual((p['total'],p['nombre_lignes']),('30.00',1))
        self.assertEqual(p['lignes'][0]['prix_unitaire'],'20.00')
        self.assertEqual(p['lignes'][0]['minutes_reelles'],90)

    def test_price_session_not_multiplied_by_duration(self):
        self.constater(horaire=('09:00','10:30'))
        p=self.preview(self.choix(tarif=self.t_seance))
        self.assertEqual(p['total'],'24.00')

    def test_rounded_per_line_including_one_minute(self):
        self.constater(horaire=('09:00','09:01'))
        self.assertEqual(self.preview()['total'],'0.33')

    def test_validated_lot_contains_no_duplicate_and_source_invariant(self):
        self.constater()
        res=self.valider()
        self.assertEqual(res['total'],'20.00')
        self.assertEqual(len(self.d5.lire_bordereau(self.bid,acteur='direction')['lignes']),1)
        self.assertEqual(self.sentinelles(),self.avant)
        with self.assertRaises(BordereauConflit):self.valider()
        with self.assertRaises(PlanningConflit):
            self.d34.decider_facturation(self.ids[0],'a_arbitrer','Revenir',acteur='direction')
        with self.assertRaises(PlanningConflit):
            self.d34.remplacer_intervenant(self.ids[0],'E2','Changement tardif',acteur='direction')

    def test_duplicate_billing_other_lot_refused(self):
        self.constater(); self.valider()
        b2=self.d5.creer_bordereau(self.part,self.conv,'OCT-2','2025-10-01',
                                    '2025-10-31',acteur='direction')
        with self.assertRaises(BordereauConflit):self.preview(bid=b2)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM partenaires_bordereaux_lignes').fetchone()[0],1)

    def test_duplicate_intervention_in_one_selection_rejected(self):
        self.constater()
        with self.assertRaises(BordereauConflit):self.preview(self.choix()*2)

    def test_tariff_version_mismatch_and_missing(self):
        self.constater()
        with self.assertRaises(BordereauInvalide):self.preview(self.choix(tarif=99999))
        with self.assertRaises(BordereauInvalide):self.preview(self.choix(iid=self.ids[1]))

    def test_tariff_category_mismatch(self):
        self.constater()
        self.assertEqual(self.preview()['total'],'20.00')
        self.conn.execute("UPDATE partenaires_interventions SET categorie_tarif='enfants' WHERE IDintervention=?",(self.ids[0],))
        self.conn.commit()
        with self.assertRaises(BordereauInvalide):self.preview()

    def test_explicit_preview_and_stale_hash_prevents_validation(self):
        self.constater()
        sel=self.choix()
        p=self.preview(sel)
        self.conn.execute('UPDATE partenaires_interventions SET minutes_reelles=30 WHERE IDintervention=?',(self.ids[0],))
        self.conn.commit()
        with self.assertRaises(BordereauConflit):
            self.d5.valider_bordereau(self.bid,sel,p['empreinte'],acteur='direction')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM partenaires_bordereaux_lignes').fetchone()[0],0)

    def test_detect_post_validation_tamper_with_finance_line(self):
        self.constater();self.valider()
        self.conn.execute("UPDATE partenaires_bordereaux_lignes SET montant='0.01'")
        self.conn.commit()
        with self.assertRaises(BordereauIntegrite):
            self.d5.lire_bordereau(self.bid,acteur='direction')

    def test_detect_post_validation_tamper_with_source(self):
        self.constater();self.valider()
        self.conn.execute('UPDATE partenaires_interventions SET minutes_reelles=32 WHERE IDintervention=?',(self.ids[0],))
        self.conn.commit()
        with self.assertRaises(BordereauIntegrite):
            self.d5.lire_bordereau(self.bid,acteur='direction')

    def test_detect_signed_contract_modification(self):
        self.constater()
        self.conn.execute("UPDATE partenaires_conventions_tarifs SET montant='999.00' WHERE IDtarif_convention=?",(self.t_heure,))
        self.conn.commit()
        with self.assertRaises(ConventionIntegrite):self.preview()

    def test_csv_is_explicitly_not_invoice(self):
        self.constater()
        with self.assertRaises(BordereauInvalide):self.d5.preparer_csv(self.bid,acteur='direction')
        self.valider()
        a=self.d5.preparer_csv(self.bid,acteur='direction')
        self.assertIn('DOCUMENT PREPARATOIRE - PAS UNE FACTURE',a)
        self.assertIn('TOTAL;;;;;;;20.00',a)
        self.assertNotIn('FACTURE N',a)
        self.assertEqual(a,self.d5.preparer_csv(self.bid,acteur='direction'))

    def test_declared_external_reference_not_payment_or_invoice_issue(self):
        self.constater();self.valider()
        with self.assertRaises(BordereauInvalide):
            self.d5.declarer_facture_externe(self.bid,'FAC-1','21.00','a'*64,acteur='direction')
        x=self.d5.declarer_facture_externe(self.bid,'FAC-1','20.00','b'*64,acteur='direction')
        self.assertEqual((x['facture_emise_automatiquement'],x['paiement_verifie']),(False,False))
        self.assertEqual(self.d5.lire_bordereau(self.bid,acteur='direction')['bordereau']['etat'],'reference_externe')
        self.assertEqual(self.sentinelles(),self.avant)
        with self.assertRaises(BordereauConflit):
            self.d5.declarer_facture_externe(self.bid,'FAC-2','20.00','b'*64,acteur='direction')

    def test_external_reference_unique_per_partner(self):
        self.constater(0);self.constater(1)
        self.valider()
        self.d5.declarer_facture_externe(self.bid,'FAC-1','20.00','b'*64,acteur='direction')
        b2=self.d5.creer_bordereau(self.part,self.conv,'OCT-2','2025-10-01','2025-10-31',acteur='direction')
        self.valider(self.choix(iid=self.ids[1]),bid=b2)
        with self.assertRaises(BordereauConflit):
            self.d5.declarer_facture_externe(b2,'FAC-1','20.00','c'*64,acteur='direction')

    def test_no_float_or_negative_money(self):
        for x in (20.0, float('nan'),True,None,'-5','1e2','1.234','10000000000.00','0.00'):
            with self.subTest(x=x),self.assertRaises(BordereauInvalide):_prix(x)
        self.assertEqual(_prix(Decimal('20.00')),Decimal('20.00'))

    def test_validation_rolls_back_all_rows_if_insertion_fails(self):
        self.constater(0);self.constater(1)
        choix=self.choix(iid=self.ids[0])+self.choix(iid=self.ids[1])
        p=self.preview(choix)
        original=self.d5._inserer
        index=[0]
        def broken(table,data):
            if table=='partenaires_bordereaux_lignes':
                index[0]+=1
                if index[0]==2:raise RuntimeError('Injected failure')
            return original(table,data)
        self.d5._inserer=broken
        with self.assertRaises(RuntimeError):
            self.d5.valider_bordereau(self.bid,choix,p['empreinte'],acteur='direction')
        self.d5._inserer=original
        self.assertEqual(self.conn.execute('SELECT count(*) FROM partenaires_bordereaux_lignes').fetchone()[0],0)
        self.assertEqual(self.d5.lire_bordereau(self.bid,acteur='direction')['bordereau']['etat'],'brouillon')
        self.assertEqual(self.sentinelles(),self.avant)

    def test_backup_restore_of_disposable_sqlite(self):
        self.constater();self.valider()
        with tempfile.TemporaryDirectory() as tmp:
            disk=sqlite3.connect(str(Path(tmp)/'copy.db'))
            self.conn.backup(disk)
            disk.execute('PRAGMA foreign_keys=ON')
            d5=BordereauxPartenaires(disk,autoriser=self.droit)
            self.assertEqual(d5.lire_bordereau(self.bid,acteur='direction')['bordereau']['total'],'20.00')
            self.assertEqual(disk.execute('PRAGMA foreign_key_check').fetchall(),[])
            disk.close()

    def test_migration_replay_refused_and_no_historic_table_names(self):
        script=SCRIPTS[-1].read_text(encoding='utf-8')
        with self.assertRaises(sqlite3.OperationalError):self.conn.executescript(script)
        for forbidden in ('ALTER TABLE prestations','UPDATE factures','INSERT INTO factures',
                          'DROP TABLE','DELETE FROM prestations'):
            self.assertNotIn(forbidden,script.upper())

    def test_mysql_sql_only_proposal_has_restrict_and_unsigned_fks(self):
        script=(ROOT/'noethys/Data/Migrations/partenaires_d5_mysql57.sql').read_text(encoding='utf-8')
        for s in ('ENGINE=InnoDB','INT UNSIGNED','UNIQUE KEY uq_part_ligne_intervention',
                  'ON DELETE RESTRICT','DECIMAL(12,2)'):
            self.assertIn(s,script)

    def test_history_no_pii_and_not_invoices(self):
        self.constater();self.valider()
        ev=self.d5.lister_evenements(self.bid,acteur='direction')
        self.assertEqual([x['action'] for x in ev],['creation','validation'])
        self.assertTrue(all(x['informations']=='' or 'nombre=' in x['informations'] for x in ev))

if __name__=='__main__':unittest.main()
