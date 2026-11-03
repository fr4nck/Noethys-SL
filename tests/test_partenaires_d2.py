# -*- coding: utf-8 -*-
"""Recette D2 avec SQLite memoire : aucune connexion reseau/Noethys implicite.

Cas fictifs : ecole et club, versions signees et avenants, droits, tarifs,
immuabilite, reprise et separation totale d'avec la facturation historique.
"""
import sqlite3
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'noethys'))
from Utils.UTILS_Partenaires_D1 import AnnuairePartenaires, AutorisationRefusee
from Utils.UTILS_Partenaires_D2 import (
    RegistreConventions, ConventionInvalide, ConventionConflit,
    ConventionIntegrite,
)

D1 = ROOT / 'noethys/Data/Migrations/partenaires_d1_sqlite.sql'
D2 = ROOT / 'noethys/Data/Migrations/partenaires_d2_sqlite.sql'
MYSQL = ROOT / 'noethys/Data/Migrations/partenaires_d2_mysql57.sql'


class D2Tests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('CREATE TABLE familles (IDfamille INTEGER PRIMARY KEY, nom TEXT)')
        self.db.execute('CREATE TABLE compta_tiers (IDtiers INTEGER PRIMARY KEY, nom TEXT)')
        self.db.execute('CREATE TABLE prestations (IDprestation INTEGER PRIMARY KEY, montant TEXT)')
        self.db.execute('CREATE TABLE factures (IDfacture INTEGER PRIMARY KEY, montant TEXT)')
        self.db.execute('CREATE TABLE consommations (IDconso INTEGER PRIMARY KEY, etat TEXT)')
        self.db.execute("INSERT INTO familles VALUES (1, 'ne pas modifier')")
        self.db.execute("INSERT INTO factures VALUES (1, '99.99')")
        self.db.commit()
        self.avant = self.historique()
        self.db.executescript(D1.read_text(encoding='utf-8'))
        self.db.executescript(D2.read_text(encoding='utf-8'))
        self.autoriser = lambda a, action: a == 'direction'
        self.d1 = AnnuairePartenaires(self.db, autoriser=self.autoriser)
        self.reg = RegistreConventions(self.db, autoriser=self.autoriser)
        self.ecole = self.d1.creer_structure(
            {'categorie': 'ecole', 'raison_sociale': 'Ecole Exemple',
             'adresse_ligne1': '1 rue des Tests', 'code_postal': '35000',
             'commune': 'Ville-Test'}, acteur='direction')
        self.club = self.d1.creer_structure(
            {'categorie': 'association', 'raison_sociale': 'Club Exemple'},
            acteur='direction')

    def tearDown(self):
        self.db.close()

    def historique(self):
        return {t: self.db.execute('SELECT * FROM ' + t).fetchall() for t in
                ('familles', 'compta_tiers', 'prestations', 'factures', 'consommations')}

    def tables(self):
        return {x[0] for x in self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

    def convention(self, *, partenaire=None, type_convention='scolaire',
                   ref='TEST-2026', debut='2026-09-01', fin='2027-06-30'):
        if partenaire is None:
            partenaire = self.ecole
        return self.reg.creer_convention(partenaire, ref, 'Encadrement sportif',
             type_convention, debut, fin, acteur='direction')

    def version(self, IDconvention, *, effet='2026-09-01', mode='payante',
                clauses='Article 1 : missions et obligations des parties.',
                modele='noedoc', reference='Modele-scolaire'):
        return self.reg.ouvrir_version(IDconvention, effet, clauses, modele,
                                      reference, mode, acteur='direction')

    def tarif(self, montant='20.00', *, categorie='scolaires', libelle='Education physique',
              debut='2026-09-01', fin='2027-06-30', unite='heure'):
        return dict(categorie=categorie, libelle=libelle, montant=montant,
                    date_debut=debut, date_fin=fin, unite=unite)

    def signer(self, IDversion, empreinte='a' * 64):
        return self.reg.signer_version(IDversion, '2026-08-24', 'Directrice Test',
            empreinte, acteur='direction')

    def signee(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif()], acteur='direction')
        digest = self.signer(vid)
        return cid, vid, digest

    def test_migration_n_ajoute_que_quatre_tables_sans_alterer_historique(self):
        self.assertTrue({'partenaires_conventions', 'partenaires_conventions_versions',
            'partenaires_conventions_tarifs', 'partenaires_conventions_evenements'} <= self.tables())
        self.assertEqual(self.historique(), self.avant)
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_migration_rejouee_echoue_et_pas_de_drop(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.db.executescript(D2.read_text(encoding='utf-8'))
        self.assertNotIn('DROP TABLE', D2.read_text(encoding='utf-8').upper())

    def test_models_ecole_association_et_isolation_nom(self):
        school = self.convention()
        club = self.convention(partenaire=self.club, type_convention='associative', ref='TEST-2026')
        self.assertNotEqual(school, club)
        self.assertEqual(len(self.reg.lister_conventions(self.ecole, acteur='direction')), 1)
        self.assertEqual(len(self.reg.lister_conventions(self.club, acteur='direction')), 1)
        with self.assertRaises(ConventionInvalide):
            self.convention(partenaire=self.club)
        with self.assertRaises(ConventionInvalide):
            self.convention(type_convention='associative')

    def test_meme_reference_refusee_pour_meme_partenaire(self):
        self.convention()
        with self.assertRaises(ConventionConflit):
            self.convention()

    def test_dates_debut_fin_invalides(self):
        for date_debut, date_fin in [('2026-09-31','2027-06-30'),
                                      ('2027-09-01','2026-06-30'),
                                      ('01/09/2026','2027-06-30')]:
            with self.subTest(date_debut=date_debut), self.assertRaises(ConventionInvalide):
                self.convention(debut=date_debut, fin=date_fin)

    def test_brouillon_unique_et_numero_version_initial(self):
        cid = self.convention()
        vid = self.version(cid)
        with self.assertRaises(ConventionConflit):
            self.version(cid)
        lu = self.reg.obtenir_version(vid, acteur='direction')
        self.assertEqual((lu['version']['nature'], lu['version']['numero_version']), ('initiale', 1))
        self.assertEqual(lu['version']['statut'], 'brouillon')

    def test_version_hors_periode_refusee(self):
        cid = self.convention()
        for effet in ('2026-08-31', '2027-07-01'):
            with self.subTest(effet=effet), self.assertRaises(ConventionInvalide):
                self.version(cid, effet=effet)

    def test_validation_champs_brouillon_et_support(self):
        cid = self.convention()
        for modele, reference, mode in [('pdf', 'x', 'payante'),
                                         ('word', '', 'payante'),
                                         ('noedoc', 'x', 'auto')]:
            with self.subTest(modele=modele, reference=reference, mode=mode):
                with self.assertRaises(ConventionInvalide):
                    self.version(cid, modele=modele, reference=reference, mode=mode)
        self.assertEqual(self.db.execute(
            'SELECT COUNT(*) FROM partenaires_conventions_versions').fetchone()[0], 0)

    def test_tarifs_adultes_et_enfants_simultanes(self):
        cid = self.convention(partenaire=self.club, type_convention='associative')
        vid = self.version(cid, reference='Modele-associatif')
        tarifs = [self.tarif('36,50', categorie='adultes', libelle='Fitness'),
                  self.tarif('24.00', categorie='enfants', libelle='Badminton')]
        self.assertEqual(self.reg.remplacer_tarifs(vid, tarifs, acteur='direction'), 2)
        ligne = self.reg.obtenir_version(vid, acteur='direction')['tarifs']
        self.assertEqual(sorted(x['montant'] for x in ligne), ['24.00', '36.50'])
        self.assertTrue(all(isinstance(x['montant'], str) for x in ligne))

    def test_tarif_refuse_float_3_decimales_et_quantite_negative(self):
        cid = self.convention()
        vid = self.version(cid)
        for montant in (1.5, '1.234', '-5.00', 'NaN', 'Infinity'):
            with self.subTest(montant=montant), self.assertRaises(ConventionInvalide):
                self.reg.remplacer_tarifs(vid, [self.tarif(montant)], acteur='direction')
        self.assertEqual(self.reg.obtenir_version(vid, acteur='direction')['tarifs'], [])

    def test_chevauchement_meme_prestation_refuse(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif('20')], acteur='direction')
        with self.assertRaises(ConventionConflit):
            self.reg.remplacer_tarifs(vid, [self.tarif('20', fin='2026-12-31'),
                self.tarif('22', debut='2026-12-31')], acteur='direction')
        lignes = self.reg.obtenir_version(vid, acteur='direction')['tarifs']
        self.assertEqual([x['montant'] for x in lignes], ['20.00'])

    def test_tarifs_successifs_non_chevauchants_autorises(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif('20', fin='2026-12-31'),
            self.tarif('22', debut='2027-01-01')], acteur='direction')
        self.assertEqual(len(self.reg.obtenir_version(vid, acteur='direction')['tarifs']), 2)

    def test_brouillon_modification_et_remplacement_tarifs(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.modifier_brouillon(vid, {'clauses':'Nouvelles clauses'}, acteur='direction')
        self.reg.remplacer_tarifs(vid, [self.tarif('20')], acteur='direction')
        self.reg.remplacer_tarifs(vid, [self.tarif('22')], acteur='direction')
        donnees = self.reg.obtenir_version(vid, acteur='direction')
        self.assertEqual(donnees['version']['clauses'], 'Nouvelles clauses')
        self.assertEqual(donnees['tarifs'][0]['montant'], '22.00')

    def test_signature_exige_texte_taux_et_document(self):
        cid = self.convention()
        vid = self.version(cid, clauses='')
        with self.assertRaises(ConventionInvalide):
            self.signer(vid)
        self.reg.modifier_brouillon(vid, {'clauses':'Article 1'}, acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.signer(vid)
        self.reg.remplacer_tarifs(vid, [self.tarif('20')], acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.signer(vid, empreinte='absent')
        self.assertEqual(self.reg.obtenir_version(vid, acteur='direction')['version']['statut'], 'brouillon')

    def test_gratuite_explicite_sans_tarif_et_tarifs_interdits(self):
        cid = self.convention()
        vid = self.version(cid, mode='gratuite')
        with self.assertRaises(ConventionInvalide):
            self.reg.remplacer_tarifs(vid, [self.tarif('0')], acteur='direction')
        self.signer(vid)
        applicables = self.reg.tarifs_applicables(cid, '2026-09-05', acteur='direction')
        self.assertEqual(applicables['mode_facturation'], 'gratuite')
        self.assertEqual(applicables['tarifs'], [])

    def test_brouillon_n_est_pas_applicable_a_facturation(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif('20')], acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.reg.tarifs_applicables(cid, '2026-09-05', acteur='direction')

    def test_version_signee_immutable_et_tarifs_preserves(self):
        cid, vid, sha = self.signee()
        with self.assertRaises(ConventionInvalide):
            self.reg.modifier_brouillon(vid, {'clauses':'malveillant'}, acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.reg.remplacer_tarifs(vid, [], acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.signer(vid)
        donnees = self.reg.obtenir_version(vid, acteur='direction')
        self.assertEqual(donnees['version']['empreinte_contenu'], sha)
        self.assertEqual(donnees['tarifs'][0]['montant'], '20.00')

    def test_signature_avec_empreinte_document_et_sha_snapshot(self):
        _cid, vid, sha = self.signee()
        self.assertEqual(len(sha), 64)
        self.assertNotEqual(sha, 'a' * 64)
        version = self.reg.obtenir_version(vid, acteur='direction')['version']
        self.assertEqual(version['empreinte_document_signe'], 'a' * 64)
        self.assertEqual(version['date_signature'], '2026-08-24')

    def test_tampering_tarif_signe_est_detecte(self):
        _cid, vid, _sha = self.signee()
        self.db.execute("UPDATE partenaires_conventions_tarifs SET montant='30.00' WHERE IDversion=?", (vid,))
        self.db.commit()
        with self.assertRaises(ConventionIntegrite):
            self.reg.obtenir_version(vid, acteur='direction')

    def test_tampering_clause_signee_est_detecte(self):
        _cid, vid, _sha = self.signee()
        self.db.execute("UPDATE partenaires_conventions_versions SET clauses='autre' WHERE IDversion=?", (vid,))
        self.db.commit()
        with self.assertRaises(ConventionIntegrite):
            self.reg.lister_versions(1, acteur='direction')

    def test_avenant_effet_futur_ne_change_pas_les_anciens_tarifs(self):
        cid, v1, _sha = self.signee()
        v2 = self.version(cid, effet='2027-01-01', reference='Modele-nouvelle-version')
        self.reg.remplacer_tarifs(v2, [self.tarif('24', debut='2027-01-01')], acteur='direction')
        pendant_brouillon = self.reg.tarifs_applicables(cid, '2027-02-01', acteur='direction')
        self.assertEqual((pendant_brouillon['IDversion'], pendant_brouillon['tarifs'][0]['montant']), (v1, '20.00'))
        self.signer(v2, empreinte='b'*64)
        ancien = self.reg.tarifs_applicables(cid, '2026-12-03', acteur='direction')
        nouveau = self.reg.tarifs_applicables(cid, '2027-02-03', acteur='direction')
        self.assertEqual((ancien['IDversion'], ancien['tarifs'][0]['montant']), (v1, '20.00'))
        self.assertEqual((nouveau['IDversion'], nouveau['tarifs'][0]['montant']), (v2, '24.00'))
        self.assertEqual([x['version']['nature'] for x in self.reg.lister_versions(cid, acteur='direction')],
                         ['initiale','avenant'])

    def test_avenant_retour_arriere_interdit(self):
        cid, _vid, _sha = self.signee()
        with self.assertRaises(ConventionConflit):
            self.version(cid, effet='2026-09-01')
        self.assertEqual(len(self.reg.lister_versions(cid, acteur='direction')), 1)

    def test_avenant_oblige_ses_propres_tarifs(self):
        cid, _vid, _sha = self.signee()
        v2 = self.version(cid, effet='2027-01-01')
        with self.assertRaises(ConventionInvalide):
            self.signer(v2)
        self.assertEqual(self.reg.obtenir_version(v2, acteur='direction')['version']['statut'], 'brouillon')

    def test_aucun_tarif_sans_categorie_applicable(self):
        cid, _vid, _sha = self.signee()
        with self.assertRaises(ConventionInvalide):
            self.reg.tarifs_applicables(cid, '2026-09-15', acteur='direction', categorie='adultes')

    def test_tarifs_en_dehors_de_l_validite_refuses(self):
        cid = self.convention()
        vid = self.version(cid)
        for debut, fin in [('2026-08-31','2026-12-31'), ('2026-09-01','2027-07-01'),
                           ('2026-10-01','2026-09-30')]:
            with self.subTest(debut=debut), self.assertRaises(ConventionInvalide):
                self.reg.remplacer_tarifs(vid, [self.tarif(debut=debut, fin=fin)], acteur='direction')

    def test_contenu_signe_stable_apres_changement_de_fiche_partenaire(self):
        cid, vid, sha = self.signee()
        self.d1.modifier_structure(self.ecole, {'raison_sociale':'Nouveau nom'}, acteur='direction')
        export = self.reg.preparer_export(vid, acteur='direction')
        self.assertEqual(export['identite_partenaire'], 'Ecole Exemple')
        self.assertEqual(export['instantane_sha256'], sha)
        self.assertEqual(export['champs_compatibles']['{CONVENTION_ADRESSE_STRUCTURE}'],
                         '1 rue des Tests, 35000 Ville-Test')

    def test_export_n_invente_pas_de_planning_ni_representant(self):
        _cid, vid, _sha = self.signee()
        d = self.reg.preparer_export(vid, acteur='direction')
        self.assertEqual(d['etat'], 'signee')
        self.assertEqual(d['champs_compatibles']['{CONVENTION_LIEU_INTERVENTION}'], '')
        self.assertEqual(d['champs_compatibles']['{CONVENTION_REPRESENTANT_NOM_COMPLET}'], '')

    def test_export_brouillon_et_tarif_ambigu_sans_invention(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif('20', fin='2026-12-31'),
            self.tarif('22', debut='2027-01-01')], acteur='direction')
        export = self.reg.preparer_export(vid, acteur='direction')
        self.assertEqual(export['etat'], 'brouillon')
        self.assertEqual(export['champs_compatibles']['{CONVENTION_TARIF_HORAIRE}'], '')
        self.assertIsNone(export['document_signe_sha256'])

    def test_cloturer_refuse_brouillon_puis_archive_sans_detruire(self):
        cid = self.convention()
        v1 = self.version(cid)
        with self.assertRaises(ConventionConflit):
            self.reg.cloturer_convention(cid, acteur='direction')
        self.reg.remplacer_tarifs(v1, [self.tarif()], acteur='direction')
        self.signer(v1)
        self.reg.cloturer_convention(cid, acteur='direction')
        self.assertEqual(self.reg.lister_conventions(self.ecole, acteur='direction'), [])
        self.assertEqual(len(self.reg.lister_conventions(self.ecole, acteur='direction',
                                                        inclure_cloturees=True)), 1)
        with self.assertRaises(ConventionInvalide):
            self.version(cid, effet='2027-01-01')
        self.assertEqual(self.reg.obtenir_version(v1, acteur='direction')['version']['statut'], 'signee')

    def test_aucun_acces_sans_politique_meme_en_lecture(self):
        cid, v1, _sha = self.signee()
        refuse = RegistreConventions(self.db)
        appels = [lambda: refuse.lister_conventions(self.ecole, acteur='direction'),
                  lambda: refuse.obtenir_version(v1, acteur='direction'),
                  lambda: refuse.preparer_export(v1, acteur='direction'),
                  lambda: refuse.tarifs_applicables(cid, '2026-09-10', acteur='direction'),
                  lambda: refuse.cloturer_convention(cid, acteur='direction')]
        for appel in appels:
            with self.subTest(appel=appel), self.assertRaises(AutorisationRefusee):
                appel()

    def test_lecture_autorisee_ecriture_refusee_selon_action(self):
        cid, vid, _sha = self.signee()
        r = RegistreConventions(self.db,
            autoriser=lambda acteur, action: acteur == 'lecture' and
            action in {'lister_conventions', 'obtenir_version'})
        self.assertEqual(r.obtenir_version(vid, acteur='lecture')['version']['statut'], 'signee')
        with self.assertRaises(AutorisationRefusee):
            r.cloturer_convention(cid, acteur='lecture')
        self.assertEqual(self.historique(), self.avant)

    def test_audit_sans_texte_de_clauses_ni_contacts(self):
        cid, vid, _sha = self.signee()
        evts = self.reg.lister_evenements(acteur='direction')
        self.assertGreaterEqual(len(evts), 4)
        logs = ' '.join(str(e) for e in evts)
        self.assertNotIn('Article 1 : missions', logs)
        self.assertNotIn('Directrice Test', logs)
        self.assertNotIn('20.00', logs)
        self.assertTrue(any(e['action']=='signature_declaree' for e in evts))

    def test_restriction_fk_sans_suppression_en_cascade(self):
        _cid, vid, _sha = self.signee()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('DELETE FROM partenaires_conventions_versions WHERE IDversion=?', (vid,))
        self.db.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('DELETE FROM partenaires_structures WHERE IDpartenaire=?', (self.ecole,))
        self.db.rollback()

    def test_refuse_transaction_sqlite_empruntee(self):
        cid = self.convention()
        self.db.execute('BEGIN')
        with self.assertRaises(ConventionConflit):
            self.version(cid)
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()

    def test_refuse_foreign_keys_desactives(self):
        x = sqlite3.connect(':memory:')
        try:
            with self.assertRaises(ConventionInvalide):
                RegistreConventions(x, autoriser=self.autoriser)
        finally:
            x.close()

    def test_mysql_schemas_statiques_sans_destruction(self):
        sql = MYSQL.read_text(encoding='utf-8').upper()
        self.assertIn('DECIMAL(12,2)', sql)
        self.assertIn('ENGINE=INNODB', sql)
        self.assertIn('ON DELETE RESTRICT', sql)
        self.assertNotIn('DROP TABLE', sql)
        self.assertNotIn('ALTER TABLE', sql)
        self.assertEqual(sql.count('CREATE TABLE PARTENAIRES_'), 4)



    # Contre-tests D2 supplementaires, sans fixtures de production.
    def test_date_effet_changee_ne_laisse_pas_ancien_tarif_incoherent(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif()], acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.reg.modifier_brouillon(vid, {'date_effet':'2027-01-01'}, acteur='direction')
        self.assertEqual(self.reg.obtenir_version(vid, acteur='direction')['version']['date_effet'],
                         '2026-09-01')

    def test_switch_gratuite_refuse_tant_que_tarifs_existent(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif()], acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.reg.modifier_brouillon(vid, {'mode_facturation':'gratuite'}, acteur='direction')
        self.assertEqual(self.reg.obtenir_version(vid, acteur='direction')['version']['mode_facturation'],
                         'payante')

    def test_taux_unique_partiel_n_est_pas_exporte_comme_tarif_general(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif('20', fin='2026-12-31')], acteur='direction')
        champs = self.reg.preparer_export(vid, acteur='direction')['champs_compatibles']
        self.assertEqual(champs['{CONVENTION_TARIF_HORAIRE}'], '')

    def test_montant_zero_une_convention_payante_ne_peut_etre_signee(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif('0.00')], acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.signer(vid)

    def test_rollback_si_insert_tarif_echoue_en_milieu_de_l_operation(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif('20')], acteur='direction')
        original = self.reg._inserer
        compte = [0]
        def tomber(table, champs):
            if table == 'partenaires_conventions_tarifs':
                compte[0] += 1
                if compte[0] == 2:
                    raise RuntimeError('panne fictive')
            return original(table, champs)
        self.reg._inserer = tomber
        try:
            with self.assertRaisesRegex(RuntimeError, 'panne fictive'):
                self.reg.remplacer_tarifs(vid, [self.tarif('20', fin='2026-12-31'),
                  self.tarif('22', debut='2027-01-01')], acteur='direction')
        finally:
            self.reg._inserer = original
        self.assertEqual([x['montant'] for x in self.reg.obtenir_version(vid, acteur='direction')['tarifs']],
                         ['20.00'])

    def test_integrite_snapshot_partenaire_modifie_directement(self):
        cid, vid, digest = self.signee()
        self.db.execute("UPDATE partenaires_conventions_versions SET partenaire_snapshot='{}' WHERE IDversion=?",
                        (vid,))
        self.db.commit()
        with self.assertRaises(ConventionIntegrite):
            self.reg.preparer_export(vid, acteur='direction')

    def test_pas_de_tarif_hors_date_couverte_meme_version_signee(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif('20', fin='2026-12-31')], acteur='direction')
        self.signer(vid)
        with self.assertRaises(ConventionInvalide):
            self.reg.tarifs_applicables(cid, '2027-02-01', acteur='direction')

    def test_au_moins_une_facturation_valide_parce_que_taux_explicitement_signe(self):
        cid, vid, digest = self.signee()
        r = self.reg.tarifs_applicables(cid, '2026-09-12', acteur='direction', categorie='scolaires')
        self.assertEqual(r['IDversion'], vid)
        self.assertEqual(r['tarifs'][0]['montant'], '20.00')
        self.assertEqual(self.historique(), self.avant)


    def test_d2_exige_explicitement_schema_d1_precedent(self):
        autre = sqlite3.connect(':memory:')
        autre.execute('PRAGMA foreign_keys=ON')
        try:
            with self.assertRaises(sqlite3.OperationalError):
                autre.executescript(D2.read_text(encoding='utf-8'))
            self.assertNotIn('partenaires_conventions', {x[0] for x in autre.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")})
        finally:
            autre.close()

    def test_sauvegarde_restauration_sqlite_fictive_preserve_signature(self):
        import tempfile
        cid, vid, digest = self.signee()
        with tempfile.TemporaryDirectory(prefix='convention-d2-fictif-') as dossier:
            destination = Path(dossier) / 'copie_test.sqlite'
            sauvegarde = sqlite3.connect(str(destination))
            try:
                self.db.backup(sauvegarde)
            finally:
                sauvegarde.close()
            rouverte = sqlite3.connect(str(destination))
            try:
                rouverte.execute('PRAGMA foreign_keys=ON')
                lecture = RegistreConventions(rouverte, autoriser=self.autoriser)
                copie = lecture.obtenir_version(vid, acteur='direction')
                self.assertEqual(copie['version']['empreinte_contenu'], digest)
                self.assertEqual(lecture.tarifs_applicables(cid, '2026-12-02', acteur='direction')
                                 ['tarifs'][0]['montant'], '20.00')
                self.assertEqual(rouverte.execute('PRAGMA foreign_key_check').fetchall(), [])
            finally:
                rouverte.close()

    def test_changement_categorie_partenaire_bloque_avenant_incompatible(self):
        cid, vid, _sha = self.signee()
        self.d1.modifier_structure(self.ecole, {'categorie':'association'}, acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.version(cid, effet='2027-01-01')
        self.assertEqual(self.reg.obtenir_version(vid, acteur='direction')['version']['statut'], 'signee')

    def test_changement_categorie_partenaire_bloque_signature_brouillon(self):
        cid = self.convention()
        vid = self.version(cid)
        self.reg.remplacer_tarifs(vid, [self.tarif()], acteur='direction')
        self.d1.modifier_structure(self.ecole, {'categorie':'association'}, acteur='direction')
        with self.assertRaises(ConventionInvalide):
            self.signer(vid)
        self.assertEqual(self.reg.obtenir_version(vid, acteur='direction')['version']['statut'], 'brouillon')

    def test_convention_meme_annee_utilise_saison_simple(self):
        cid = self.convention(fin='2026-12-31')
        vid = self.version(cid)
        self.assertEqual(self.reg.preparer_export(vid, acteur='direction')
                         ['champs_compatibles']['{CONVENTION_SAISON}'], '2026')

if __name__ == '__main__':
    unittest.main()
