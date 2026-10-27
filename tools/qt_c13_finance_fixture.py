"""Extension financière C13 de la base C8 : 100 % inventée et temporaire.

Ne jamais importer une base Noethys réelle. Les INSERT/ALTER sont autorisés
uniquement dans la fixture SQLite créée dans TemporaryDirectory par C8.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from tools.qt_c8_fixture import C8FictiveDatabase, MARKER


class C13FictiveFinanceDatabase(C8FictiveDatabase):
    def _make_fixture(self):
        super()._make_fixture()
        if (
            self.path.is_symlink()
            or self.path.parent.resolve() != self._root
            or self.path.name != "C8_DEMONSTRATION_FICTIVE.sqlite"
        ):
            raise RuntimeError("La source financière fictive est inconnue.")
        with closing(sqlite3.connect(self.path)) as db, db:
            if db.execute("SELECT token FROM c8_marker").fetchone() != (MARKER,):
                raise RuntimeError("Marqueur C8 absent, extension financière interdite")
            db.executescript("""
                CREATE TABLE c13_marker (token TEXT PRIMARY KEY);
                CREATE TABLE comptes_payeurs (
                    IDcompte_payeur INTEGER PRIMARY KEY,
                    IDfamille INTEGER NOT NULL
                );
                CREATE TABLE factures (
                    IDfacture INTEGER PRIMARY KEY, IDcompte_payeur INTEGER,
                    numero INTEGER, date_edition TEXT, date_echeance TEXT,
                    total TEXT, regle TEXT, solde TEXT, etat TEXT
                );
                CREATE TABLE modes_reglements (
                    IDmode INTEGER PRIMARY KEY, label TEXT
                );
                CREATE TABLE reglements (
                    IDreglement INTEGER PRIMARY KEY, IDcompte_payeur INTEGER,
                    date TEXT, IDmode INTEGER, numero_piece TEXT,
                    montant TEXT, IDdepot INTEGER
                );
                CREATE TABLE comptes_bancaires (
                    IDcompte INTEGER PRIMARY KEY, nom TEXT
                );
                CREATE TABLE compta_operations (
                    IDoperation INTEGER PRIMARY KEY, date TEXT, type TEXT,
                    libelle TEXT, montant TEXT, IDcompte_bancaire INTEGER,
                    IDreleve INTEGER, num_piece TEXT
                );
                CREATE TABLE depots (
                    IDdepot INTEGER PRIMARY KEY, date TEXT, nom TEXT,
                    IDcompte INTEGER, verrouillage INTEGER
                );
                ALTER TABLE prestations ADD COLUMN IDcompte_payeur INTEGER;
                ALTER TABLE prestations ADD COLUMN IDindividu INTEGER;
                ALTER TABLE prestations ADD COLUMN date TEXT;
                ALTER TABLE prestations ADD COLUMN label TEXT;
                ALTER TABLE ventilation ADD COLUMN IDreglement INTEGER;
                INSERT INTO c13_marker VALUES ('C13_FINANCE_FICTIVE_ONLY');
                INSERT INTO comptes_payeurs VALUES (201, 100), (202, 101);
                INSERT INTO factures VALUES
                    (501, 201, 101, '2026-10-02', '2026-10-17', '19.995',
                     '9.99', '10.005', 'editee'),
                    (502, 202, 102, '2026-10-06', '2026-10-21', '18.50',
                     '18.50', '0.00', 'editee'),
                    (503, 201, 103, '2027-02-03', '2027-02-20', '0.00',
                     '0.00', '0.00', 'annulee'),
                    (990, 202, 990, '2026-10-03', '2026-10-19', '25.75',
                     '2.00', '23.75', NULL);
                INSERT INTO modes_reglements VALUES
                    (1, 'Carte fictive'), (2, 'Chèque fictif');
                INSERT INTO reglements VALUES
                    (401, 201, '2026-10-03', 1, 'CARTE-FAKE-1', '10.005', 1),
                    (402, 202, '2026-10-04', 2, 'CHEQUE-FAKE-2', '18.50', 2),
                    (403, 201, '2026-10-05', 2, 'CHEQUE-FAKE-3', '0.00', NULL),
                    (404, 202, '2027-01-07', 1, 'CARTE-FAKE-4', '1000.0003', 2);
                INSERT INTO comptes_bancaires VALUES
                    (1, 'Banque A fictive'), (2, 'Banque B fictive');
                INSERT INTO compta_operations VALUES
                    (801, '2026-10-07', 'debit', 'Achat fictif', '12.005', 1, NULL, 'P-FAKE-1'),
                    (802, '2026-10-08', 'credit', 'Recette fictive', '18.50', 1, 71, 'P-FAKE-2'),
                    (803, '2027-01-02', 'debit', 'Test année suivante', '0.10', 2, NULL, NULL);
                INSERT INTO depots VALUES
                    (1, '2026-10-03', 'Dépôt fictif A', 1, 0),
                    (2, '2026-10-04', 'Dépôt fictif B', 2, 1);
            """)
            db.executemany("""
                UPDATE prestations
                   SET IDcompte_payeur=?, IDindividu=?, date=?, label=?,
                       IDfacture=?
                 WHERE IDprestation=?
            """, (
                (201, 10, "2026-10-02", "Prestation fictive A", 501, 301),
                (202, 11, "2026-10-06", "Prestation fictive B", 502, 302),
                (201, 12, "2026-10-02", "Prestation sans facture", None, 303),
                (202, 13, "2026-10-03", "Prestation fictive C", 990, 304),
            ))
            db.executemany("""
                INSERT INTO prestations (
                    IDprestation, montant, IDfacture, forfait_date_debut,
                    IDcompte_payeur, IDindividu, date, label
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
            """, (
                (305, "-1.005", 501, 201, 12, "2026-10-02", "Correction fictive"),
                (306, "1000.0003", 990, 202, 13, "2027-01-05", "Donnée haute précision"),
            ))
            db.executemany("""
                INSERT INTO ventilation (
                    IDventilation, IDprestation, montant, IDreglement
                ) VALUES (?, ?, ?, ?)
            """, (
                (701, 301, "9.99", 401),
                (702, 305, "0.005", 401),
                (703, 302, "18.50", 402),
                (704, 304, "1.15", 404),
                (705, 304, "0.00", 999),
            ))
