# -*- coding: utf-8 -*-
"""D6 : recette sur D1-D5 reconstitues, sans factures et comptes payeurs reels."""
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'noethys'))
import test_partenaires_d5 as fixture_module
from Utils.UTILS_Partenaires_D1 import AutorisationRefusee, PartenairesErreur
from Utils.UTILS_Partenaires_D5 import BordereauConflit
from Utils.UTILS_Partenaires_D6 import (
    FacturesPartenaires, FactureInvalide, FactureConflit, FactureIntegrite)

SQL = ROOT / 'noethys/Data/Migrations/partenaires_d6_sqlite.sql'
EMETTEUR = {
    'raison_sociale': 'ASSOCIATION SPORTIVE FICTIVE',
    'adresse_ligne1': '4 rue des Tests', 'code_postal': '35000',
    'commune': 'Rennes', 'siret': '12345678901234',
    'mention_fiscale': 'TVA non applicable - motif fiscal a valider par la direction',
    'conditions_paiement': 'A reception de la facture, virement ou cheque',
    'penalites_retard': 'Conditions contractuelles de retard a verifier',
    'indemnite_recouvrement': 'Le cas echeant selon la qualite du client',
}


class D6Tests(unittest.TestCase):
    def setUp(self):
        self.f = fixture_module.D5Tests('test_initialement_aucun_mouvement_historique')
        self.f.setUp()
        self.conn = self.f.conn
        self.conn.executescript(SQL.read_text(encoding='utf8'))
        self.f.d1.modifier_structure(self.f.part, {
            'adresse_ligne1':'1 rue Fictive', 'code_postal':'35000',
            'commune':'Rennes'}, acteur='direction')
        self.d6 = FacturesPartenaires(self.conn, autoriser=self.f.droit)

    def tearDown(self):
        self.f.tearDown()

    def valider_lot(self):
        self.f.constater()
        self.f.valider()
        return self.f.bid

    def apercu(self, bid=None, profil=None, date='2025-11-03', echeance='2025-11-10'):
        return self.d6.preparer_facture(bid or self.f.bid, profil or EMETTEUR,
                           date, echeance, acteur='direction')

    def enregistrer(self, bid=None, profil=None, date='2025-11-03', echeance='2025-11-10'):
        bid = bid or self.f.bid
        profil = profil or EMETTEUR
        empreinte = self.apercu(bid, profil, date, echeance)['empreinte_preparation']
        return self.d6.enregistrer_facture(bid, profil, date, echeance,
                                           empreinte, acteur='direction')

    def seconde_seance(self):
        self.f.constater(1)
        b2=self.f.d5.creer_bordereau(self.f.part,self.f.conv,'OCT-B','2025-10-01',
                                      '2025-10-31',acteur='direction')
        self.f.valider(self.f.choix(iid=self.f.ids[1]),bid=b2)
        return b2

    def janvier(self):
        prog=self.f.d34.creer_programmation(self.f.version,'JAN-26','Janvier',
                    '2026-01-01','2026-01-31',acteur='direction')
        self.f.d34.ajouter_creneau(prog,'ponctuel','2026-01-08','2026-01-08',
                    '09:00','10:00','CP','EPS','scolaires',acteur='direction')
        self.f.d34.valider_programmation(prog,acteur='direction')
        ident=self.f.d34.lister_interventions(prog,acteur='direction')[0]['IDintervention']
        self.f.d34.marquer_realisee(ident,'2026-01-08','09:00','10:00','E1',acteur='direction')
        self.f.d34.decider_facturation(ident,'eligible','Accord',acteur='direction')
        bid=self.f.d5.creer_bordereau(self.f.part,self.f.conv,'JAN-26',
                '2026-01-01','2026-01-31',acteur='direction')
        choix=[{'IDintervention':ident,'IDtarif_convention':self.f.t_heure}]
        self.f.valider(choix,bid=bid)
        return bid

    def test_01_aucune_tva_comptable_et_montant_unique(self):
        self.valider_lot()
        p=self.apercu()
        self.assertEqual(p['donnees']['total_eur'],'20.00')
        self.assertIn('Association loi 1901',p['donnees']['emetteur']['forme'])
        self.assertEqual(p['donnees']['emetteur']['mention_fiscale'], EMETTEUR['mention_fiscale'])
        self.assertFalse(any(x in p['donnees'] for x in ('taux_tva','montant_tva','total_ht','total_ttc')))
        self.assertFalse(any(x in p['donnees']['lignes'][0] for x in ('taux_tva','montant_tva')))

    def test_02_interdiction_brouillon_et_absence_d_realisation(self):
        with self.assertRaises(FactureConflit):
            self.apercu()

    def test_03_interdiction_adresse_client_incomplete(self):
        self.valider_lot()
        self.conn.execute('UPDATE partenaires_structures SET adresse_ligne1=NULL WHERE IDpartenaire=?',(self.f.part,))
        self.conn.commit()
        with self.assertRaises(FactureInvalide):self.apercu()

    def test_04_echeance_et_date_precedant_service(self):
        self.valider_lot()
        with self.assertRaises(FactureInvalide):self.apercu(date='2025-11-03',echeance='2025-11-02')
        with self.assertRaises(FactureInvalide):self.apercu(date='2025-09-30',echeance='2025-11-10')

    def test_05_emetteur_incomplet_refuse(self):
        self.valider_lot()
        p=dict(EMETTEUR);p.pop('siret')
        with self.assertRaises(FactureInvalide):self.apercu(profil=p)
        p=dict(EMETTEUR,siret='ABC')
        with self.assertRaises(FactureInvalide):self.apercu(profil=p)

    def test_06_aucune_colonne_taxe_autorisee(self):
        self.valider_lot()
        p=dict(EMETTEUR,taux_tva='20')
        with self.assertRaises(FactureInvalide):self.apercu(profil=p)

    def test_07_reference_unique_au_bordereau(self):
        self.valider_lot()
        doc=self.enregistrer()
        self.assertEqual(doc['numero'],'PMSL-2025-000001')
        self.assertFalse(doc['pdf_genere'] or doc['transmise'])
        assertdoc=self.d6.lire_facture(doc['IDfacture_partenaire'],acteur='direction')
        self.assertEqual(assertdoc['facture']['numero'],doc['numero'])
        self.assertEqual(assertdoc['facture']['total_eur'],'20.00')
        self.assertEqual(self.f.sentinelles(),self.f.avant)
        with self.assertRaises(FactureConflit):self.enregistrer()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM partenaires_factures_officielles').fetchone()[0],1)

    def test_08_bordereau_deja_externe_refuse(self):
        self.valider_lot()
        self.f.d5.declarer_facture_externe(self.f.bid,'EXTERNAL-123','20.00','a'*64,acteur='direction')
        with self.assertRaises(FactureConflit):self.apercu()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM partenaires_factures_officielles').fetchone()[0],0)

    def test_09_facture_d6_interdit_reference_externe_d5(self):
        self.valider_lot();self.enregistrer()
        with self.assertRaises(BordereauConflit):
            self.f.d5.declarer_facture_externe(self.f.bid,'EX-01','20.00','b'*64,acteur='direction')

    def test_10_compteur_sequence_meme_annee(self):
        self.valider_lot()
        b2=self.seconde_seance()
        a=self.enregistrer();b=self.enregistrer(b2)
        self.assertEqual([a['numero'],b['numero']], ['PMSL-2025-000001','PMSL-2025-000002'])
        self.assertEqual(self.f.sentinelles(),self.f.avant)

    def test_11_compteur_reset_nouvel_exercice(self):
        self.valider_lot()
        first=self.enregistrer()
        new_bid=self.janvier()
        second=self.enregistrer(new_bid,date='2026-02-01',echeance='2026-02-10')
        self.assertEqual(first['numero'],'PMSL-2025-000001')
        self.assertEqual(second['numero'],'PMSL-2026-000001')

    def test_12_antidatage_interdit(self):
        self.valider_lot();self.seconde_seance()
        self.enregistrer()
        b2=self.f.d5.creer_bordereau(self.f.part,self.f.conv,'ALT-25',
                       '2025-10-01','2025-10-31',acteur='direction')
        # La 2eme intervention deja engagee par OCT-B : ne peut etre reengagee.
        # Test directement l'antidatage sur son bordereau valide.
        p=self.apercu(self.f.d5._lire('SELECT IDbordereau FROM partenaires_bordereaux WHERE reference=?',('OCT-B',))[0]['IDbordereau'],
                      date='2025-11-02')
        with self.assertRaises(FactureConflit):
            self.d6.enregistrer_facture(p['donnees']['IDbordereau'],EMETTEUR,'2025-11-02','2025-11-10',
                                       p['empreinte_preparation'],acteur='direction')
        self.assertEqual(self.conn.execute('SELECT dernier_numero FROM partenaires_factures_sequence').fetchone()[0],1)

    def test_13_preparation_obsolete_pas_de_numero_consomme(self):
        self.valider_lot();p=self.apercu()
        self.f.d1.modifier_structure(self.f.part,{'adresse_ligne1':'2 rue du Changement'},acteur='direction')
        with self.assertRaises(FactureConflit):
            self.d6.enregistrer_facture(self.f.bid,EMETTEUR,'2025-11-03','2025-11-10',
                                       p['empreinte_preparation'],acteur='direction')
        self.assertEqual(self.conn.execute('SELECT dernier_numero FROM partenaires_factures_sequence').fetchone()[0],0)

    def test_14_doc_altere_detecte(self):
        self.valider_lot();d=self.enregistrer()
        self.conn.execute('UPDATE partenaires_factures_officielles SET donnees_json=? WHERE IDfacture_partenaire=?',
                 ('{}',d['IDfacture_partenaire']))
        self.conn.commit()
        with self.assertRaises(FactureIntegrite):
            self.d6.lire_facture(d['IDfacture_partenaire'],acteur='direction')

    def test_15_index_altere_detecte(self):
        self.valider_lot();d=self.enregistrer()
        self.conn.execute('UPDATE partenaires_factures_officielles SET total=? WHERE IDfacture_partenaire=?',
                 ('120.00',d['IDfacture_partenaire']))
        self.conn.commit()
        with self.assertRaises(FactureIntegrite):self.d6.lire_facture(d['IDfacture_partenaire'],acteur='direction')

    def test_16_d5_source_altere_detecte(self):
        self.valider_lot();d=self.enregistrer()
        self.conn.execute('UPDATE partenaires_bordereaux_lignes SET montant=? WHERE IDbordereau=?',
                 ('21.00',self.f.bid))
        self.conn.commit()
        with self.assertRaises(PartenairesErreur):
            self.d6.lire_facture(d['IDfacture_partenaire'],acteur='direction')

    def test_17_compteur_altere_detecte(self):
        self.valider_lot();self.enregistrer();b2=self.seconde_seance()
        self.conn.execute('UPDATE partenaires_factures_sequence SET dernier_numero=9')
        self.conn.commit()
        with self.assertRaises(FactureIntegrite):self.enregistrer(b2)

    def test_18_rollback_avant_numero_conserve_sequence(self):
        self.valider_lot()
        self.conn.executescript('''CREATE TRIGGER d6_test_fail BEFORE INSERT ON partenaires_factures_evenements
            BEGIN SELECT RAISE(ABORT,'echec simule de journal'); END;''')
        with self.assertRaises(Exception):self.enregistrer()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM partenaires_factures_officielles').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT dernier_numero FROM partenaires_factures_sequence').fetchone()[0],0)
        self.conn.execute('DROP TRIGGER d6_test_fail')
        self.assertEqual(self.enregistrer()['numero'],'PMSL-2025-000001')

    def test_19_autorisations_refusees_par_defaut(self):
        self.valider_lot()
        autre=FacturesPartenaires(self.conn)
        with self.assertRaises(AutorisationRefusee):
            autre.preparer_facture(self.f.bid,EMETTEUR,'2025-11-03','2025-11-10',acteur='direction')
        with self.assertRaises(AutorisationRefusee):
            self.d6.preparer_facture(self.f.bid,EMETTEUR,'2025-11-03','2025-11-10',acteur='observateur')

    def test_20_recette_compatibilite_d5_csv(self):
        self.valider_lot()
        csv=self.f.d5.preparer_csv(self.f.bid,acteur='direction')
        self.assertIn('DOCUMENT PREPARATOIRE',csv)
        self.assertNotIn('TVA A VERIFIER',csv)

    def test_21_modele_noedoc_pas_document_envoye(self):
        self.valider_lot();d=self.enregistrer()
        m=self.d6.modele_noedoc(d['IDfacture_partenaire'],acteur='direction')
        self.assertEqual(m['facture']['numero'],'PMSL-2025-000001')
        self.assertFalse(m['transmise'] or m['pdf_genere'])

    def test_22_concurrence_deux_connexions_un_gagnant(self):
        self.valider_lot()
        prep=self.apercu()['empreinte_preparation']
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'test.sqlite'
            d=sqlite3.connect(str(p));self.conn.backup(d);d.close()
            barrier=threading.Barrier(2)
            lock=threading.Lock()
            outcomes=[]
            def travail():
                co=sqlite3.connect(str(p),timeout=10)
                co.execute('PRAGMA foreign_keys=ON')
                moteur=FacturesPartenaires(co,autoriser=self.f.droit)
                barrier.wait(timeout=10)
                try:
                    moteur.enregistrer_facture(self.f.bid,EMETTEUR,'2025-11-03','2025-11-10',
                                               prep,acteur='direction')
                    result='ok'
                except FactureConflit:
                    result='refuse'
                except Exception as e:
                    result='erreur:'+repr(e)
                finally:
                    co.close()
                with lock:outcomes.append(result)
            t1=threading.Thread(target=travail);t2=threading.Thread(target=travail)
            t1.start();t2.start();t1.join(15);t2.join(15)
            self.assertFalse(t1.is_alive() or t2.is_alive())
            self.assertCountEqual(outcomes,['ok','refuse'])
            c=sqlite3.connect(str(p))
            self.assertEqual(c.execute('SELECT count(*) FROM partenaires_factures_officielles').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT dernier_numero FROM partenaires_factures_sequence').fetchone()[0],1)
            self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
            c.close()


if __name__ == '__main__':
    unittest.main()
