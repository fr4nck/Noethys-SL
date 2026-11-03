# -*- coding: utf-8 -*-
"""Integration C3 : utilisations de C1/C2 depuis l'application, data fictive."""
import csv
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'noethys'/'Utils'))
import UTILS_ALSH_C3_Session as c3
import test_alsh_communes_c2 as fixtures

ADMIN = {'IDutilisateur':42, 'actif':1, 'profil':'administrateur', 'droits':None}
CATEGORIE = c3.CATEGORIE_DROITS


def lecteur(droits):
    return {'IDutilisateur':17, 'actif':1, 'profil':'perso:17', 'droits':droits}


class ContratsDroitsC3(unittest.TestCase):
    def test_01_aucun_acces_anonyme(self):
        for x in (None, {}, {'IDutilisateur':7, 'actif':1},
                  {'IDutilisateur':7, 'actif':0, 'profil':'administrateur'},
                  {'IDutilisateur':True, 'actif':1, 'profil':'administrateur'}):
            with self.subTest(x=x), self.assertRaises(c3.ALSHAcces):
                c3.DroitsSituation(x)

    def test_02_admin_bonne_identite(self):
        d = c3.DroitsSituation(ADMIN)
        self.assertTrue(d.autoriser('noethys:42','frequentation_export_nominatif'))
        self.assertFalse(d.autoriser('noethys:43','frequentation_export_nominatif'))
        self.assertFalse(d.autoriser('noethys:42','action_inconnue'))

    def test_03_non_admin_refuse_tant_que_droits_non_explicitement_autorises(self):
        d = c3.DroitsSituation(lecteur({}))
        for action in c3.DROITS_ACTIONS:
            self.assertFalse(d.autoriser('noethys:17', action))

    def test_04_export_nom_exige_un_droit_different_de_lecture(self):
        d = c3.DroitsSituation(lecteur({(CATEGORIE,'consulter'):'autorisation'}))
        self.assertTrue(d.autoriser('noethys:17','frequentation_lire_nominatif'))
        self.assertFalse(d.autoriser('noethys:17','frequentation_export_nominatif'))
        self.assertFalse(d.autoriser('noethys:17','communes_parametrer'))
        self.assertTrue(d.autoriser('noethys:17','frequentation_export_anonyme'))

    def test_05_droits_interdits_meme_avec_permission_partielle(self):
        d = c3.DroitsSituation(lecteur({(CATEGORIE,'consulter'):'interdiction'}))
        self.assertFalse(d.autoriser('noethys:17','frequentation_lire_nominatif'))

    def test_06_chaine_autorisation_exacte_de_Noethys(self):
        d = c3.DroitsSituation(lecteur({(CATEGORIE,'modifier'):'autorisation',
                                      (CATEGORIE,'consulter'):'autorisation',
                                      (CATEGORIE,'exporter'):'autorisation'}))
        self.assertTrue(d.autoriser('noethys:17','communes_parametrer'))
        self.assertTrue(d.autoriser('noethys:17','frequentation_export_nominatif'))


class MoteurEtVueC3(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AdresseAutomatiqueTests()
        self.fixture.setUp()
        self.cn = self.fixture.cn
        self.s = c3.SituationC3(self.cn, ADMIN)

    def tearDown(self):
        self.fixture.tearDown()

    def test_07_profils_communes_unites_lus_dans_la_base(self):
        self.assertEqual(self.s.profils(), ['ALSH'])
        self.assertEqual(len(self.s.communes()), 3)
        self.assertEqual(self.s.perimetres()[0]['IDgroupe'], 201)
        self.assertEqual(len(self.s.unites([101])),4)

    def test_08_calcul_automatique_avec_3_communes(self):
        self.fixture.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        self.fixture.move('2026-09-01','3 rue Haute','35002','COMMUNE C')
        for day in ('2026-02-15','2026-05-10','2026-10-14'):
            self.fixture.conso(day)
        r=self.s.recalculer('2026-01-01','2026-12-31','ALSH')
        self.assertEqual(r['journees_global'],'3')
        self.assertFalse(r['liquidable'])
        self.assertEqual({x['code_insee']:x['journees'] for x in r['communes']},
                         {'00001':'1','00002':'1','00003':'1'})

    def test_09_vue_generale_anonyme_meme_pour_admin(self):
        self.fixture.conso('2026-03-01')
        r=self.s.recalculer('2026-01-01','2026-12-31','ALSH')
        vue=self.s.vue(r)
        self.assertEqual(vue['enfants'],[])
        self.assertEqual(vue['lignes'],[])
        self.assertEqual(vue['communes'][0]['enfants_distincts'],1)

    def test_10_vue_nom_par_une_seule_commune(self):
        self.fixture.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        self.fixture.conso('2026-03-01')
        self.fixture.conso('2026-05-01')
        r=self.s.recalculer('2026-01-01','2026-12-31','ALSH')
        vu=self.s.vue(r,'00001')
        self.assertEqual(len(vu['enfants']),1)
        self.assertEqual(len(vu['lignes']),1)
        self.assertIn('1 rue des Chenes',vu['enfants'][0]['adresse_complete'])
        self.assertNotIn('2 rue Neuve',str(vu))
        self.assertEqual(self.s.vue(r,'00002')['enfants'][0]['adresse_complete'].split(',')[0],
                         '2 rue Neuve')

    def test_11_deux_exports_csv_audit_distincts(self):
        self.fixture.conso('2026-03-01')
        r=self.s.recalculer('2026-01-01','2026-12-31','ALSH')
        before=self.cn.execute('SELECT COUNT(*) FROM alsh_communes_exports').fetchone()[0]
        a=self.s.csv(r,'recap','00001')
        b=self.s.csv(r,'detail','00001')
        self.assertTrue(a.startswith('\ufeff'))
        self.assertTrue(b.startswith('\ufeff'))
        self.assertIn('Enfant',a)  # fictitious first name in fixtures
        self.assertEqual(self.cn.execute('SELECT COUNT(*) FROM alsh_communes_exports').fetchone()[0],before+2)

    def test_12_export_autre_commune_ne_divulgue_pas_la_premiere(self):
        self.fixture.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        self.fixture.conso('2026-02-01')
        self.fixture.conso('2026-05-01')
        r=self.s.recalculer('2026-01-01','2026-12-31','ALSH')
        text=self.s.csv(r,'detail','00002')
        self.assertIn('2 rue Neuve',text)
        self.assertNotIn('1 rue des Chenes',text)
        self.assertNotIn('00001',text)

    def test_13_anonyme_sans_detail_enfant(self):
        self.fixture.conso('2026-03-01')
        r=self.s.recalculer('2026-01-01','2026-12-31','ALSH')
        text=self.s.csv(r,'anonyme')
        self.assertIn('00001',text)
        self.assertNotIn('Enfant;Exemple',text)
        self.assertNotIn('1 rue',text)

    def test_14_anomalie_bloque_exports_nominatifs(self):
        self.fixture.conso('2025-12-31')
        r=self.s.recalculer('2025-12-01','2026-02-01','ALSH')
        self.assertGreater(self.s.vue(r)['anomalies'],0)
        with self.assertRaises(c3.ALSHErreur):
            self.s.csv(r,'detail','00001')

    def test_15_sans_privilege_export_interdit(self):
        self.fixture.conso('2026-03-01')
        s=c3.SituationC3(self.cn,lecteur({(CATEGORIE,'consulter'):'autorisation'}))
        r=s.recalculer('2026-01-01','2026-12-31','ALSH')
        with self.assertRaises(c3.ALSHAcces):
            s.csv(r,'detail','00001')

    def test_16_correction_manuelle_de_date_avec_preuve(self):
        self.fixture.move('2026-04-01','2 rue Neuve','35001','COMMUNE B')
        observations=self.s.observations(1)
        current=observations[-1]['IDobservation']
        self.assertTrue(self.s.confirmer_demenagement(current,'2026-03-28','Certificat fictif'))
        self.assertEqual(self.s.observations(1)[-1]['date_effet'],'2026-03-28')
        with self.assertRaises(c3.ALSHErreur):
            self.s.confirmer_demenagement(current,'2026-03-20','Meme preuve')

    def test_17_configuration_nouveau_profil_et_commune_tracee(self):
        self.assertTrue(self.s.ajouter_correspondance('35003','COMMUNE D','00004','COMMUNE D'))
        self.assertEqual(len(self.s.communes()),4)
        new=self.s.creer_profil('ALSH-2027',[[101,201]],
                 {301:'J',302:'M',303:'A',304:'exclu'},fixtures.TARIFFS)
        self.assertGreater(new,0)
        self.assertEqual(self.s.profils(),['ALSH','ALSH-2027'])

    def test_18_ne_modifie_aucune_facture(self):
        self.fixture.conso('2026-03-01')
        before=self.cn.execute('SELECT * FROM factures').fetchall()
        self.s.recalculer('2026-01-01','2026-12-31','ALSH')
        self.s.csv(self.s.recalculer('2026-01-01','2026-12-31','ALSH'), 'detail','00001')
        self.assertEqual(self.cn.execute('SELECT * FROM factures').fetchall(),before)

    def test_19_refus_export_cross_communautes(self):
        self.fixture.conso('2026-03-01')
        r=self.s.recalculer('2026-01-01','2026-12-31','ALSH')
        for code in (None, 'A', '000010', 'AB-01'):
            with self.subTest(code=code), self.assertRaises(c3.ALSHErreur):
                self.s.csv(r,'recap',code)

    def test_20_aucun_etat_nominal_en_cas_d_erreur(self):
        with self.assertRaises(c3.ALSHErreur):
            self.s.vue({'etat':'FACTURE'},'00001')


class FichiersC3(unittest.TestCase):
    def test_21_csv_exige_bom_et_creation_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'liste.csv'
            c3.enregistrer_csv_nouveau(dest,'\ufeffColonne;Valeur\r\n')
            self.assertTrue(dest.read_text(encoding='utf-8').startswith('\ufeff'))
            with self.assertRaises(FileExistsError):
                c3.enregistrer_csv_nouveau(dest,'\ufeffNouvelle valeur')
            self.assertEqual(dest.read_bytes(), '\ufeffColonne;Valeur\r\n'.encode('utf-8'))

    def test_22_pas_de_fichier_cree_sur_entree_invalide(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'liste.csv'
            with self.assertRaises(c3.ALSHErreur):
                c3.enregistrer_csv_nouveau(dest,'=1+1')
            self.assertFalse(dest.exists())

if __name__=='__main__': unittest.main()
