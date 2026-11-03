"""C19 — registre comptable et administratif 100 % fictif.

Toutes les opérations DDL/DML sont réservées à C8FictiveDatabase et à son
TemporaryDirectory, après vérification des marqueurs C16/C18. Jamais de .nod,
profil, réseau, utilisateur Noethys ou import depuis la production.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from noethys_qt.c19_sensitive_guard import C19_MARKER
from tools.qt_c18_fixture import C18FictiveRegistryDatabase


class C19FictiveRegistryDatabase(C18FictiveRegistryDatabase):
    def _make_fixture(self):
        super()._make_fixture()
        if (
            self.path.is_symlink()
            or self.path.parent.is_symlink()
            or self.path.parent.resolve() != self._root
            or self.path.name != "C8_DEMONSTRATION_FICTIVE.sqlite"
            or not self.path.parent.name.startswith("noethys-qt-c8-fictif-")
        ):
            raise RuntimeError("C19 : extension hors base temporaire fictive")
        with closing(sqlite3.connect(self.path)) as db, db:
            if (
                db.execute("SELECT token FROM c18_marker").fetchone()
                != ("C18_ONLY_FICTIVE_DOCUMENTS_AND_SCHOOL",)
                or db.execute("SELECT token FROM c16_marker").fetchone()
                != ("C16_ALL_FAKE_NOETHYS_ONLY",)
            ):
                raise RuntimeError("C19 : chaîne de marqueurs C16/C18 invalide")
            db.executescript("""
                CREATE TABLE c19_marker (token TEXT PRIMARY KEY);
                CREATE TABLE compta_exercices (
                    IDexercice INTEGER PRIMARY KEY,
                    nom TEXT, date_debut TEXT, date_fin TEXT, defaut INTEGER
                );
                CREATE TABLE compta_analytiques (
                    IDanalytique INTEGER PRIMARY KEY,
                    nom TEXT, abrege TEXT, defaut INTEGER
                );
                CREATE TABLE compta_categories (
                    IDcategorie INTEGER PRIMARY KEY,
                    type TEXT, nom TEXT, abrege TEXT, journal TEXT,
                    IDcompte INTEGER
                );
                CREATE TABLE compta_comptes_comptables (
                    IDcompte INTEGER PRIMARY KEY, numero TEXT, nom TEXT
                );
                CREATE TABLE compta_budgets (
                    IDbudget INTEGER PRIMARY KEY, IDexercice INTEGER,
                    nom TEXT, observations TEXT, analytiques TEXT,
                    date_debut TEXT, date_fin TEXT
                );
                CREATE TABLE compta_categories_budget (
                    IDcategorie_budget INTEGER PRIMARY KEY,
                    IDbudget INTEGER, type TEXT,
                    IDcategorie INTEGER, valeur TEXT
                );
                CREATE TABLE banques (
                    IDbanque INTEGER PRIMARY KEY, nom TEXT, cp_resid TEXT,
                    ville_resid TEXT
                );
                CREATE TABLE regimes (
                    IDregime INTEGER PRIMARY KEY, nom TEXT
                );
                CREATE TABLE caisses (
                    IDcaisse INTEGER PRIMARY KEY, nom TEXT, IDregime INTEGER
                );
                CREATE TABLE secteurs (
                    IDsecteur INTEGER PRIMARY KEY, nom TEXT
                );

                ALTER TABLE modes_reglements ADD COLUMN type_comptable TEXT;
                ALTER TABLE modes_reglements ADD COLUMN numero_piece TEXT;
                ALTER TABLE modes_reglements ADD COLUMN frais_gestion TEXT;
                ALTER TABLE modes_reglements ADD COLUMN frais_montant TEXT;
                ALTER TABLE modes_reglements ADD COLUMN frais_pourcentage TEXT;
                ALTER TABLE modes_reglements ADD COLUMN code_compta TEXT;
                ALTER TABLE comptes_bancaires ADD COLUMN defaut INTEGER;
                ALTER TABLE comptes_bancaires ADD COLUMN raison TEXT;
                ALTER TABLE comptes_bancaires ADD COLUMN iban TEXT;
                ALTER TABLE comptes_bancaires ADD COLUMN bic TEXT;
                ALTER TABLE comptes_bancaires ADD COLUMN numero TEXT;

                INSERT INTO compta_exercices VALUES
                    (11, 'Exercice 2026 inventé', '2026-01-01', '2026-12-31', 1),
                    (12, 'Exercice 2027 fictif', '2027-01-01', '2027-12-31', 0),
                    (13, 'Exercice hors délai fictif', '2025-01-01', '2025-12-31', 0);
                INSERT INTO compta_analytiques VALUES
                    (21, 'Pôle sportif fictif', 'SPORT', 1),
                    (22, 'Ateliers inventés', 'ATELIER', 0),
                    (23, 'Administratif démo', 'ADMIN', 0);
                INSERT INTO compta_comptes_comptables VALUES
                    (31, '706100', 'Prestation imaginaire'),
                    (32, '606300', 'Fournitures fictives'),
                    (33, '411000', 'Tiers simulés');
                INSERT INTO compta_categories VALUES
                    (41, 'credit', 'Produits inventés', 'PRO', 'VT', 31),
                    (42, 'debit', 'Achats fictifs', 'ACH', 'AC', 32),
                    (43, 'credit', 'Recette test', 'REC', 'VT', 33);
                INSERT INTO compta_budgets VALUES
                    (101, 11, 'Budget sports fictif', NULL, '[21]',
                     '2026-01-01', '2026-12-31'),
                    (102, 12, 'Budget culture inventé', NULL, '[22]',
                     '2027-01-01', '2027-12-31'),
                    (103, 11, 'Budget transversal fictif', NULL, '[21,22]',
                     '2026-06-01', '2026-12-31');
                INSERT INTO compta_categories_budget VALUES
                    (201, 101, 'credit', 41, '1200.005'),
                    (202, 101, 'debit', 42, '800 + {NBRE_UNITE_11}'),
                    (203, 102, 'credit', 43, '1000.0003'),
                    (204, 103, 'debit', 42, '250.00');
                INSERT INTO banques VALUES
                    (301, 'Banque démo du Soleil', '99000', 'Ville fictive'),
                    (302, 'Établissement inventé', '99100', 'Ville inventée'),
                    (303, 'Banque laboratoire', '99200', 'Commune imaginaire');
                INSERT INTO regimes VALUES
                    (401, 'Régime inventé général'),
                    (402, 'Régime spécial fictif');
                INSERT INTO caisses VALUES
                    (501, 'Caisse expérimentale A', 401),
                    (502, 'Caisse expérimentale B', 402),
                    (503, 'Caisse sans rattachement fictif', 999);
                INSERT INTO secteurs VALUES
                    (601, 'Secteur fictif Nord'),
                    (602, 'Secteur fictif Sud'),
                    (603, 'Secteur expérimental Est');

                UPDATE modes_reglements SET
                    type_comptable='banque',
                    numero_piece='NUM', frais_gestion='FIXE',
                    frais_montant='12.005',
                    frais_pourcentage='0.0000', code_compta='CB'
                 WHERE IDmode=1;
                UPDATE modes_reglements SET
                    type_comptable='caisse',
                    numero_piece='ALPHA', frais_gestion='PRORATA',
                    frais_montant='0.00',
                    frais_pourcentage='1.0003', code_compta='CHQ'
                 WHERE IDmode=2;
                UPDATE comptes_bancaires SET
                    defaut=1, raison='Association fictive A',
                    iban='DEMO_SECRET_IBAN_A_NE_PAS_AFFICHER',
                    bic='DEMO_SECRET_BIC_A_NE_PAS_AFFICHER',
                    numero='DEMO_SECRET_NUM_A_NE_PAS_AFFICHER'
                 WHERE IDcompte=1;
                UPDATE comptes_bancaires SET
                    defaut=0, raison='Association fictive B',
                    iban='DEMO_SECRET_IBAN_B_NE_PAS_AFFICHER',
                    bic='DEMO_SECRET_BIC_B_NE_PAS_AFFICHER',
                    numero='DEMO_SECRET_NUM_B_NE_PAS_AFFICHER'
                 WHERE IDcompte=2;
            """)
            db.execute("INSERT INTO c19_marker(token) VALUES (?)", (C19_MARKER,))
