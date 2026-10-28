"""C18 — prolongement TEMPORAIRE et intégralement fictif de la fixture C16.

Aucune lecture de sauvegarde .nod, de config réseau ou de profil utilisateur.
Les DDL/DML sont confinés au répertoire temporaire marqué C8 à C16.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from noethys_qt.c18_sensitive_guard import C18_MARKER
from tools.qt_c16_fixture import C16FictivePlanningDatabase


class C18FictiveRegistryDatabase(C16FictivePlanningDatabase):
    def _make_fixture(self):
        super()._make_fixture()
        if (
            self.path.is_symlink()
            or self.path.parent.resolve() != self._root
            or self.path.name != "C8_DEMONSTRATION_FICTIVE.sqlite"
        ):
            raise RuntimeError("C18 : DDL hors fixture éphémère interdit")
        with closing(sqlite3.connect(self.path)) as db, db:
            if db.execute("SELECT token FROM c16_marker").fetchone() != (
                "C16_ALL_FAKE_NOETHYS_ONLY",
            ):
                raise RuntimeError("C18 : marqueur C16 fictif non reconnu")
            db.executescript("""
                CREATE TABLE c18_marker (token TEXT PRIMARY KEY);
                CREATE TABLE ecoles (
                    IDecole INTEGER PRIMARY KEY, nom TEXT, rue TEXT,
                    cp TEXT, ville TEXT, tel TEXT, fax TEXT, mail TEXT,
                    secteurs TEXT
                );
                CREATE TABLE classes (
                    IDclasse INTEGER PRIMARY KEY, IDecole INTEGER,
                    nom TEXT, date_debut TEXT, date_fin TEXT, niveaux TEXT
                );
                CREATE TABLE niveaux_scolaires (
                    IDniveau INTEGER PRIMARY KEY, ordre INTEGER,
                    nom TEXT, abrege TEXT
                );
                CREATE TABLE scolarite (
                    IDscolarite INTEGER PRIMARY KEY, IDindividu INTEGER,
                    date_debut TEXT, date_fin TEXT, IDecole INTEGER,
                    IDclasse INTEGER, IDniveau INTEGER
                );
                CREATE TABLE produits_categories (
                    IDcategorie INTEGER PRIMARY KEY, nom TEXT, observations TEXT
                );
                ALTER TABLE produits ADD COLUMN IDcategorie INTEGER;
                ALTER TABLE produits ADD COLUMN quantite INTEGER;
                ALTER TABLE produits ADD COLUMN montant TEXT;
                ALTER TABLE produits ADD COLUMN activation_partage INTEGER;
                CREATE TABLE types_pieces (
                    IDtype_piece INTEGER PRIMARY KEY, nom TEXT, public TEXT,
                    duree_validite TEXT, valide_rattachement INTEGER
                );
                CREATE TABLE pieces (
                    IDpiece INTEGER PRIMARY KEY, IDtype_piece INTEGER,
                    IDindividu INTEGER, IDfamille INTEGER,
                    date_debut TEXT, date_fin TEXT, titre TEXT
                );

                INSERT INTO ecoles VALUES
                    (201, 'École fictive des Ajoncs', NULL, '35000',
                     'Ville inventée', NULL, NULL, NULL, '1,3'),
                    (202, 'École fictive du Bois', NULL, '35100',
                     'Commune imaginaire', NULL, NULL, NULL, '2'),
                    (203, 'École fictive du Port', NULL, '35200',
                     'Lieu inexistant', NULL, NULL, NULL, '');
                INSERT INTO niveaux_scolaires VALUES
                    (301, 1, 'Petite section fictive', 'PS'),
                    (302, 2, 'CP fictif', 'CP'),
                    (303, 3, 'CE1 fictif', 'CE1');
                INSERT INTO classes VALUES
                    (401, 201, 'Classe A inventée', '2026-09-01', '2027-08-31', '301,302'),
                    (402, 202, 'Classe B inventée', '2026-09-01', '2027-08-31', '303'),
                    (403, 203, 'Classe C inventée', '2027-09-01', '2028-08-31', '302');
                INSERT INTO scolarite VALUES
                    (5011, 10, '2026-09-01', '2027-08-31', 201, 401, 301),
                    (5012, 11, '2026-09-01', '2027-08-31', 202, 402, 303),
                    (5013, 12, '2027-09-01', '2028-08-31', 203, 403, 302),
                    (5014, 13, '2026-09-01', '2027-08-31', 201, 401, 302);

                INSERT INTO produits_categories VALUES
                    (71, 'Sport fictif', NULL),
                    (72, 'Loisirs fictifs', NULL),
                    (73, 'Équipement fictif', NULL);
                UPDATE produits
                   SET IDcategorie=71, quantite=17, montant='12.005',
                       activation_partage=1
                 WHERE IDproduit=1;
                UPDATE produits
                   SET IDcategorie=72, quantite=3, montant='1000.0003',
                       activation_partage=0
                 WHERE IDproduit=2;
                INSERT INTO produits (
                    IDproduit, nom, IDcategorie, quantite,
                    montant, activation_partage
                ) VALUES (3, 'Produit fictif supplémentaire', 73, 0, '0.00', 1);

                INSERT INTO types_pieces VALUES
                    (801, 'Justificatif fictif', 'individu', '1 an', 0),
                    (802, 'Autorisation fictive', 'famille', '6 mois', 1),
                    (803, 'Pièce fictive complémentaire', 'individu', NULL, 0);
                INSERT INTO pieces VALUES
                    (9011, 801, 10, NULL, '2026-09-01', '2027-08-31',
                     'Document individuel inventé'),
                    (9012, 802, NULL, 100, '2026-10-01', '2027-04-01',
                     'Document famille inventé'),
                    (9013, 803, 11, 101, '2027-01-01', '2028-01-01',
                     'Autre pièce fictive'),
                    (9014, 801, 13, 100, '2026-09-01', '2027-08-31',
                     'Pièce liée à deux clés fictives');
            """)
            db.execute(
                "INSERT INTO c18_marker(token) VALUES (?)", (C18_MARKER,)
            )
