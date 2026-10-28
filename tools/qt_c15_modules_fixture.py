"""C15 : extension temporaire et 100 % inventée des fixtures C8-C14.

Seul le fichier SQLite contrôlé de TemporaryDirectory reçoit les
CREATE/ALTER/INSERT de cette recette. Aucune base Noethys réelle n'est ouverte.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from tools.qt_c14_catalog_fixture import C14FictiveCatalogDatabase


class C15FictiveModulesDatabase(C14FictiveCatalogDatabase):
    def _make_fixture(self):
        super()._make_fixture()
        if (
            self.path.is_symlink()
            or self.path.parent.resolve() != self._root
            or self.path.name != "C8_DEMONSTRATION_FICTIVE.sqlite"
        ):
            raise RuntimeError("Extension C15 hors répertoire temporaire interdit")
        with closing(sqlite3.connect(self.path)) as db, db:
            if db.execute("SELECT token FROM c14_marker").fetchone() != (
                "C14_ADMIN_FAKE_ONLY",
            ):
                raise RuntimeError("Source C14 fictive non reconnue")
            db.executescript("""
                CREATE TABLE c15_marker (token TEXT PRIMARY KEY);
                ALTER TABLE unites_cotisations ADD COLUMN IDtype_cotisation INTEGER;
                ALTER TABLE unites_cotisations ADD COLUMN montant TEXT;
                ALTER TABLE unites_cotisations ADD COLUMN duree TEXT;
                ALTER TABLE unites_cotisations ADD COLUMN defaut INTEGER;

                ALTER TABLE unites ADD COLUMN IDactivite INTEGER;
                ALTER TABLE unites ADD COLUMN abrege TEXT;
                ALTER TABLE unites ADD COLUMN type TEXT;
                ALTER TABLE unites ADD COLUMN date_debut TEXT;
                ALTER TABLE unites ADD COLUMN date_fin TEXT;
                ALTER TABLE unites ADD COLUMN ordre INTEGER;
                ALTER TABLE unites ADD COLUMN autogen_active INTEGER;

                ALTER TABLE groupes ADD COLUMN IDactivite INTEGER;
                ALTER TABLE groupes ADD COLUMN ordre INTEGER;
                ALTER TABLE groupes ADD COLUMN abrege TEXT;
                ALTER TABLE groupes ADD COLUMN nbre_inscrits_max INTEGER;

                CREATE TABLE categories_tarifs (
                    IDcategorie_tarif INTEGER PRIMARY KEY,
                    IDactivite INTEGER, nom TEXT
                );
                CREATE TABLE attestations (
                    IDattestation INTEGER PRIMARY KEY,
                    numero TEXT, IDfamille INTEGER,
                    date_edition TEXT, IDutilisateur INTEGER,
                    date_debut TEXT, date_fin TEXT,
                    total TEXT, regle TEXT, solde TEXT
                );

                INSERT INTO c15_marker VALUES ('C15_MODULES_FICTIFS_ONLY');
                UPDATE unites_cotisations
                   SET IDtype_cotisation=1, montant='12.005',
                       duree='1 an', defaut=1
                 WHERE IDunite_cotisation=1;
                UPDATE unites_cotisations
                   SET IDtype_cotisation=2, montant='1000.0003',
                       duree='3 mois', defaut=0
                 WHERE IDunite_cotisation=2;
                UPDATE unites SET
                    IDactivite=1, abrege='MAT', type='Consommation',
                    date_debut='2026-09-01', date_fin='2027-08-31',
                    ordre=1, autogen_active=0
                 WHERE IDunite=11;
                UPDATE unites SET
                    IDactivite=2, abrege='APM', type='Consommation',
                    date_debut='2026-09-01', date_fin='2027-08-31',
                    ordre=2, autogen_active=1
                 WHERE IDunite=12;
                INSERT INTO unites VALUES
                    (13, 'Séance fictive', 1, 'SEAN', 'Consommation',
                     '2027-01-01', '2027-08-31', 3, 0);

                UPDATE groupes SET
                    IDactivite=1, ordre=1, abrege='A', nbre_inscrits_max=12
                 WHERE IDgroupe=21;
                UPDATE groupes SET
                    IDactivite=2, ordre=1, abrege='B', nbre_inscrits_max=16
                 WHERE IDgroupe=22;
                INSERT INTO groupes VALUES
                    (23, 'Groupe C fictif', 1, 2, 'C', NULL);

                INSERT INTO categories_tarifs VALUES
                    (1, 1, 'Tarif foyer fictif'),
                    (2, 2, 'Tarif quartier fictif'),
                    (3, 1, 'Tarif social fictif');

                INSERT INTO attestations VALUES
                    (7001, 'ATT-FAKE-001', 100, '2026-10-05', 1,
                     '2026-09-01', '2026-10-01',
                     '12.005', '0.000', '12.005'),
                    (7002, 'ATT-FAKE-002', 101, '2026-10-07', 2,
                     '2026-09-01', '2026-10-01',
                     '25.00', '25.00', '0.00'),
                    (7003, 'ATT-FAKE-003', 100, '2027-02-04', 1,
                     '2027-01-01', '2027-01-31',
                     '1000.0003', '5.00', '995.0003');

                INSERT INTO inscriptions (
                    IDinscription, IDindividu, IDfamille, IDactivite,
                    IDgroupe, IDcategorie_tarif, date_inscription,
                    date_desinscription, statut
                ) VALUES (
                    505, 13, 101, 2, 22, 2, '2026-10-02', NULL, 'attente'
                );
            """)
