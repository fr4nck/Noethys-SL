# -*- coding: utf-8 -*-
"""Recette D1 hors production : uniquement SQLite en memoire, sans wx/reseau."""
import sqlite3
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'noethys'))
from Utils.UTILS_Partenaires_D1 import (  # noqa: E402
    AnnuairePartenaires, AutorisationRefusee, ConflitPartenaire,
    Introuvable, PartenairesErreur,
)

SCHEMA_SQLITE = RACINE / 'noethys/Data/Migrations/partenaires_d1_sqlite.sql'
SCHEMA_MYSQL = RACINE / 'noethys/Data/Migrations/partenaires_d1_mysql57.sql'


class AnnuaireD1Tests(unittest.TestCase):
    def setUp(self):
        self.connexion = sqlite3.connect(':memory:')
        self.connexion.execute('PRAGMA foreign_keys=ON')
        # Sentinelles historiques : la migration D1 ne doit pas les toucher.
        self.connexion.execute('CREATE TABLE familles (IDfamille INTEGER PRIMARY KEY, memo TEXT)')
        self.connexion.execute('CREATE TABLE compta_tiers (IDtiers INTEGER PRIMARY KEY, nom TEXT)')
        self.connexion.execute('INSERT INTO familles VALUES (10, ?)', ('ne pas modifier',))
        self.connexion.execute('INSERT INTO compta_tiers VALUES (30, ?)', ('ancien tiers',))
        self.connexion.commit()
        self.tables_avant = set(self.tables())
        self.connexion.executescript(SCHEMA_SQLITE.read_text(encoding='utf-8'))
        self.annuaire = AnnuairePartenaires(
            self.connexion, autoriser=lambda acteur, action: acteur == 'direction',
            reference_existe=lambda nature, ident: (nature, ident) in {
                ('famille', 10), ('famille', 20), ('compte_payeur', 40), ('tiers_comptable', 30),
            },
        )

    def tearDown(self):
        self.connexion.close()

    def tables(self):
        return [row[0] for row in self.connexion.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]

    def structure(self, nom='Ecole La Providence', categorie='ecole'):
        return self.annuaire.creer_structure(
            {'raison_sociale': nom, 'categorie': categorie}, acteur='direction')

    def test_migration_cree_uniquement_quatre_tables_nouvelles(self):
        ajouts = set(self.tables()) - self.tables_avant
        self.assertEqual(ajouts, {'partenaires_structures', 'partenaires_contacts',
                                   'partenaires_liens_noethys', 'partenaires_evenements'})
        self.assertEqual(self.connexion.execute('SELECT memo FROM familles').fetchone()[0], 'ne pas modifier')
        self.assertEqual(self.connexion.execute('SELECT nom FROM compta_tiers').fetchone()[0], 'ancien tiers')

    def test_reexecution_migration_echoue_explicitement(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.connexion.executescript(SCHEMA_SQLITE.read_text(encoding='utf-8'))

    def test_deux_structures_de_meme_nom_restent_distinctes(self):
        a = self.structure()
        b = self.structure()
        self.assertNotEqual(a, b)
        fiches = self.annuaire.lister_structures(acteur="direction", categorie='ecole')
        self.assertEqual([x['IDpartenaire'] for x in fiches], [a, b])

    def test_plusieurs_types_partenaire_et_filtrage(self):
        self.structure(categorie='ecole')
        self.structure('Atout Sports Moutiers', categorie='association')
        self.assertEqual(len(self.annuaire.lister_structures(acteur="direction", categorie='association')), 1)
        self.assertEqual(len(self.annuaire.lister_structures(acteur="direction")), 2)

    def test_noms_et_categories_invalides_refuses(self):
        for champs in ({'raison_sociale': '', 'categorie': 'ecole'},
                       {'raison_sociale': 'A', 'categorie': 'entreprise'},
                       {'raison_sociale': 'A', 'categorie': 'ecole', 'IDfamille': 10},
                       {'raison_sociale': 'A', 'categorie': 'ecole', 'siret': 'abc'}):
            with self.subTest(champs=champs), self.assertRaises(PartenairesErreur):
                self.annuaire.creer_structure(champs, acteur='direction')
        self.assertEqual(self.annuaire.lister_structures(acteur="direction"), [])

    def test_pas_de_droits_par_defaut(self):
        muet = AnnuairePartenaires(self.connexion)
        with self.assertRaises(AutorisationRefusee):
            muet.creer_structure({'raison_sociale': 'A', 'categorie': 'autre'}, acteur='direction')
        with self.assertRaises(AutorisationRefusee):
            self.annuaire.creer_structure({'raison_sociale': 'A', 'categorie': 'autre'}, acteur='inconnu')
        self.assertEqual(self.annuaire.lister_evenements(acteur="direction"), [])

    def test_lecture_refusee_sans_autorisation(self):
        partenaire = self.structure()
        avec_garde = AnnuairePartenaires(self.connexion)
        with self.assertRaises(AutorisationRefusee):
            avec_garde.lister_structures(acteur='direction')
        with self.assertRaises(AutorisationRefusee):
            self.annuaire.lister_contacts(partenaire, acteur='inconnu')
        with self.assertRaises(AutorisationRefusee):
            self.annuaire.lister_liens(partenaire, acteur='inconnu')
        with self.assertRaises(AutorisationRefusee):
            self.annuaire.lister_evenements(acteur='inconnu')

    def test_contacts_multiples_et_principal_unique(self):
        partenaire = self.structure()
        a = self.annuaire.creer_contact(partenaire, {'nom': 'Martin', 'principal': True}, acteur='direction')
        b = self.annuaire.creer_contact(partenaire, {'nom': 'Bernard', 'fonction': 'secretariat'}, acteur='direction')
        self.assertNotEqual(a, b)
        self.assertEqual(len(self.annuaire.lister_contacts(partenaire, acteur="direction")), 2)
        evenements_avant = len(self.annuaire.lister_evenements(acteur="direction"))
        with self.assertRaises(ConflitPartenaire):
            self.annuaire.modifier_contact(b, {'principal': True}, acteur='direction')
        self.assertEqual(len(self.annuaire.lister_evenements(acteur="direction")), evenements_avant)
        self.annuaire.archiver_contact(a, acteur='direction')
        self.annuaire.modifier_contact(b, {'principal': True}, acteur='direction')
        self.assertEqual(len(self.annuaire.lister_contacts(partenaire, acteur="direction")), 1)
        self.assertEqual(len(self.annuaire.lister_contacts(partenaire, acteur="direction", inclure_archives=True)), 2)

    def test_reference_externe_explicite_et_non_automatique(self):
        partenaire = self.structure()
        self.assertEqual(self.annuaire.lister_liens(partenaire, acteur="direction"), [])
        with self.assertRaises(PartenairesErreur):
            self.annuaire.lier_reference(partenaire, 'famille', 999, acteur='direction')
        sans_verification = AnnuairePartenaires(self.connexion, autoriser=lambda a, op: True)
        with self.assertRaises(PartenairesErreur):
            sans_verification.lier_reference(partenaire, 'famille', 10, acteur='direction')
        ident = self.annuaire.lier_reference(partenaire, 'famille', 10, acteur='direction')
        self.assertEqual(self.annuaire.lister_liens(partenaire, acteur="direction")[0]['IDlien'], ident)

    def test_liaison_idempotente_et_pas_de_doublon_devenements(self):
        partenaire = self.structure()
        lien = self.annuaire.lier_reference(partenaire, 'famille', 10, acteur='direction')
        compteur = len(self.annuaire.lister_evenements(acteur="direction"))
        self.assertEqual(self.annuaire.lier_reference(partenaire, 'famille', 10, acteur='direction'), lien)
        self.assertEqual(len(self.annuaire.lister_evenements(acteur="direction")), compteur)

    def test_reference_unique_entre_partenaires(self):
        a, b = self.structure(), self.structure()
        self.annuaire.lier_reference(a, 'famille', 10, acteur='direction')
        with self.assertRaises(ConflitPartenaire):
            self.annuaire.lier_reference(b, 'famille', 10, acteur='direction')
        self.assertEqual(self.annuaire.lister_liens(b, acteur="direction"), [])

    def test_une_reference_active_par_type_et_partenaire(self):
        a = self.structure()
        self.annuaire.lier_reference(a, 'famille', 10, acteur='direction')
        with self.assertRaises(ConflitPartenaire):
            self.annuaire.lier_reference(a, 'famille', 20, acteur='direction')
        self.annuaire.lier_reference(a, 'tiers_comptable', 30, acteur='direction')
        self.assertEqual(len(self.annuaire.lister_liens(a, acteur="direction")), 2)

    def test_revocation_permet_reassociation_historique_conserve(self):
        a, b = self.structure(), self.structure()
        lien = self.annuaire.lier_reference(a, 'famille', 10, acteur='direction')
        self.annuaire.delier_reference(lien, acteur='direction')
        self.annuaire.delier_reference(lien, acteur='direction')
        nouveau = self.annuaire.lier_reference(b, 'famille', 10, acteur='direction')
        self.assertNotEqual(lien, nouveau)
        self.assertEqual(self.annuaire.lister_liens(a, acteur="direction"), [])
        self.assertEqual(len(self.annuaire.lister_liens(a, acteur="direction", inclure_revoques=True)), 1)
        self.assertIsNotNone(self.annuaire.lister_liens(a, acteur="direction", inclure_revoques=True)[0]['date_fin'])
        evenements = self.annuaire.lister_evenements(acteur="direction", nature='lien', IDobjet=lien)
        self.assertEqual([e['action'] for e in evenements], ['creation', 'revocation'])

    def test_archivage_structure_protege_references(self):
        a = self.structure()
        lien = self.annuaire.lier_reference(a, 'famille', 10, acteur='direction')
        with self.assertRaises(ConflitPartenaire):
            self.annuaire.archiver_structure(a, acteur='direction')
        self.annuaire.delier_reference(lien, acteur='direction')
        self.annuaire.archiver_structure(a, acteur='direction')
        self.assertEqual(self.annuaire.lister_structures(acteur="direction"), [])
        self.assertEqual(len(self.annuaire.lister_structures(acteur="direction", inclure_archivees=True)), 1)
        with self.assertRaises(Introuvable):
            self.annuaire.creer_contact(a, {'nom': 'Martin'}, acteur='direction')

    def test_historique_de_modification_sans_valeurs_privees(self):
        a = self.structure()
        self.annuaire.modifier_structure(a, {'email_general': 'test@example.org'}, acteur='direction')
        events = self.annuaire.lister_evenements(acteur="direction", nature='structure', IDobjet=a)
        self.assertEqual([x['action'] for x in events], ['creation', 'modification'])
        self.assertEqual(events[-1]['champs'], 'email_general')
        self.assertNotIn('test@example.org', str(events))

    def test_pas_de_sql_injection_par_le_nom(self):
        nom = "ecole'); DROP TABLE familles; --"
        p = self.structure(nom)
        self.assertEqual(self.annuaire.lister_structures(acteur="direction")[0]['raison_sociale'], nom)
        self.assertEqual(self.connexion.execute('SELECT COUNT(*) FROM familles').fetchone()[0], 1)
        self.assertEqual(p, 1)

    def test_controle_rejet_identifiants_booleens_et_types(self):
        a = self.structure()
        for ident in (True, 0, -1, '1'):
            with self.subTest(ident=ident), self.assertRaises(PartenairesErreur):
                self.annuaire.lister_liens(ident, acteur="direction")
        with self.assertRaises(PartenairesErreur):
            self.annuaire.lier_reference(a, 'famille', True, acteur='direction')
        with self.assertRaises(PartenairesErreur):
            self.annuaire.creer_contact(a, {'nom': 'X', 'principal': 1}, acteur='direction')

    def test_le_sql_mysql57_contient_les_gardes_et_ne_migre_pas_les_tables_historiques(self):
        sql = SCHEMA_MYSQL.read_text(encoding='utf-8')
        self.assertEqual(sql.count('CREATE TABLE '), 4)
        self.assertIn('ENGINE=InnoDB', sql)
        self.assertIn('uq_partenaires_liens_reference_active', sql)
        self.assertIn('uq_partenaires_liens_partenaire_actif', sql)
        self.assertNotIn('ALTER TABLE familles', sql)
        self.assertNotIn('IF NOT EXISTS', '\n'.join(line for line in sql.splitlines() if line.strip().startswith('CREATE')))


if __name__ == '__main__':
    unittest.main()
