"""C14 : tables administratives inventées dans la fixture temporaire C13.

Ne charge AUCUNE sauvegarde Noethys, aucun fichier familial et aucun profil.
Les écritures sont limitées à la création volontaire de cette base de tests.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from tools.qt_c13_finance_fixture import C13FictiveFinanceDatabase


class C14FictiveCatalogDatabase(C13FictiveFinanceDatabase):
    def _make_fixture(self):
        super()._make_fixture()
        if (
            self.path.is_symlink()
            or self.path.parent.resolve() != self._root
            or self.path.name != "C8_DEMONSTRATION_FICTIVE.sqlite"
        ):
            raise RuntimeError("Dossier C14 non autorisé")
        with closing(sqlite3.connect(self.path)) as db, db:
            if db.execute("SELECT token FROM c13_marker").fetchone() != (
                "C13_FINANCE_FICTIVE_ONLY",
            ):
                raise RuntimeError("Source C13 fictive non reconnue")
            db.executescript("""
                CREATE TABLE c14_marker (token TEXT PRIMARY KEY);
                CREATE TABLE types_cotisations (
                    IDtype_cotisation INTEGER PRIMARY KEY, nom TEXT, type TEXT, defaut INTEGER
                );
                CREATE TABLE unites_cotisations (
                    IDunite_cotisation INTEGER PRIMARY KEY, nom TEXT
                );
                CREATE TABLE cotisations (
                    IDcotisation INTEGER PRIMARY KEY, IDfamille INTEGER, IDindividu INTEGER,
                    IDtype_cotisation INTEGER, IDunite_cotisation INTEGER,
                    date_saisie TEXT, date_debut TEXT, date_fin TEXT, numero TEXT
                );
                CREATE TABLE contrats (
                    IDcontrat INTEGER PRIMARY KEY, IDinscription INTEGER,
                    IDindividu INTEGER, date_debut TEXT, date_fin TEXT, type TEXT
                );
                CREATE TABLE types_quotients (
                    IDtype_quotient INTEGER PRIMARY KEY, nom TEXT
                );
                CREATE TABLE quotients (
                    IDquotient INTEGER PRIMARY KEY, IDfamille INTEGER,
                    date_debut TEXT, date_fin TEXT, quotient TEXT, revenu TEXT,
                    IDtype_quotient INTEGER
                );
                CREATE TABLE produits (
                    IDproduit INTEGER PRIMARY KEY, nom TEXT
                );
                CREATE TABLE locations (
                    IDlocation INTEGER PRIMARY KEY, IDfamille INTEGER,
                    IDproduit INTEGER, date_debut TEXT, date_fin TEXT, quantite INTEGER
                );
                CREATE TABLE locations_demandes (
                    IDdemande INTEGER PRIMARY KEY, date TEXT, IDfamille INTEGER,
                    statut TEXT, categories TEXT, produits TEXT
                );
                CREATE TABLE commandes (
                    IDcommande INTEGER PRIMARY KEY, nom TEXT,
                    date_debut TEXT, date_fin TEXT, IDmodele INTEGER
                );
                CREATE TABLE devis (
                    IDdevis INTEGER PRIMARY KEY, numero TEXT, IDfamille INTEGER,
                    date_edition TEXT, date_debut TEXT, date_fin TEXT,
                    total TEXT, regle TEXT, solde TEXT
                );

                INSERT INTO c14_marker VALUES ('C14_ADMIN_FAKE_ONLY');
                INSERT INTO types_cotisations VALUES
                    (1, 'Adhésion fictive', 'famille', 1),
                    (2, 'Carte atelier fictive', 'individu', 0);
                INSERT INTO unites_cotisations VALUES (1, 'Année fictive'), (2, 'Trimestre fictif');
                INSERT INTO cotisations VALUES
                    (1001, 100, NULL, 1, 1, '2026-10-01', '2026-09-01', '2027-08-31', 'CARTE-100'),
                    (1002, 101, 11, 2, 2, '2026-10-02', '2026-10-01', '2026-12-31', 'CARTE-101'),
                    (1003, 100, 12, 2, 2, '2027-01-04', '2027-01-01', '2027-03-31', 'CARTE-2027');
                INSERT INTO contrats VALUES
                    (2001, 501, 10, '2026-09-02', '2027-08-31', 'loisirs'),
                    (2002, 502, 11, '2026-09-03', '2027-08-31', 'periscolaire'),
                    (2003, 503, 12, '2027-02-01', '2027-05-31', 'sport'),
                    (2004, 999, 13, '2026-12-01', '2027-05-31', 'orphelin');
                INSERT INTO types_quotients VALUES (1, 'QF fictif'), (2, 'Autre QF fictif');
                INSERT INTO quotients VALUES
                    (3001, 100, '2026-01-01', '2026-12-31', '12.005', '1000.0003', 1),
                    (3002, 101, '2026-01-01', '2026-12-31', '987.50', '19000.00', 1),
                    (3003, 100, '2027-01-01', '2027-12-31', '13.0003', '1099.99', 2);
                INSERT INTO produits VALUES
                    (1, 'Ballon fictif %_ !'), (2, 'Matériel sportif fictif');
                INSERT INTO locations VALUES
                    (4001, 100, 1, '2026-10-05', '2026-10-06', 2),
                    (4002, 101, 2, '2026-10-08', '2026-10-09', 1),
                    (4003, 100, 2, '2027-03-01', '2027-03-02', 4);
                INSERT INTO locations_demandes VALUES
                    (4101, '2026-10-01', 100, 'attente', '[1]', '[1]'),
                    (4102, '2026-10-02', 101, 'acceptee', '[2]', '[2]');
                INSERT INTO commandes VALUES
                    (5001, 'Commande repas fictive', '2026-10-01', '2026-10-31', 0),
                    (5002, 'Commande activités fictive', '2027-01-01', '2027-01-31', 7);
                INSERT INTO devis VALUES
                    (6001, 'DEV-FAKE-01', 100, '2026-10-02', '2026-10-01',
                     '2026-12-31', '12.005', '0.00', '12.005'),
                    (6002, 'DEV-FAKE-02', 101, '2026-10-03', '2026-10-01',
                     '2026-12-31', '25.00', '20.00', '5.00'),
                    (6003, 'DEV-FAKE-03', 100, '2027-01-03', '2027-01-01',
                     '2027-05-31', '1000.0003', '0', '1000.0003');
            """)
