"""C16 — données fictives pour planning, tarifs, états et badgeage.

Tous les DDL/DML ci-dessous n'ont lieu QUE dans le sqlite temporaire
créé par C8, contrôlé par chemin et marqueurs successifs jusqu'à C15.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from tools.qt_c15_modules_fixture import C15FictiveModulesDatabase


class C16FictivePlanningDatabase(C15FictiveModulesDatabase):
    def _make_fixture(self):
        super()._make_fixture()
        if (
            self.path.is_symlink()
            or self.path.parent.resolve() != self._root
            or self.path.name != "C8_DEMONSTRATION_FICTIVE.sqlite"
        ):
            raise RuntimeError("C16 : chemin hors fixture temporaire")
        with closing(sqlite3.connect(self.path)) as db, db:
            if db.execute("SELECT token FROM c15_marker").fetchone() != (
                "C15_MODULES_FICTIFS_ONLY",
            ):
                raise RuntimeError("C16 : marqueur de la fixture C15 absent")
            db.executescript("""
                CREATE TABLE c16_marker (token TEXT PRIMARY KEY);
                ALTER TABLE evenements ADD COLUMN IDactivite INTEGER;
                ALTER TABLE evenements ADD COLUMN IDunite INTEGER;
                ALTER TABLE evenements ADD COLUMN IDgroupe INTEGER;
                ALTER TABLE evenements ADD COLUMN date TEXT;
                ALTER TABLE evenements ADD COLUMN description TEXT;
                ALTER TABLE evenements ADD COLUMN capacite_max INTEGER;
                ALTER TABLE evenements ADD COLUMN heure_debut TEXT;
                ALTER TABLE evenements ADD COLUMN heure_fin TEXT;
                ALTER TABLE evenements ADD COLUMN montant TEXT;

                CREATE TABLE ouvertures (
                    IDouverture INTEGER PRIMARY KEY,
                    IDactivite INTEGER, IDunite INTEGER,
                    IDgroupe INTEGER, date TEXT
                );
                CREATE TABLE tarifs (
                    IDtarif INTEGER PRIMARY KEY, IDactivite INTEGER,
                    date_debut TEXT, date_fin TEXT, methode TEXT,
                    type TEXT, categories_tarifs TEXT, IDevenement INTEGER
                );
                CREATE TABLE tarifs_lignes (
                    IDligne INTEGER PRIMARY KEY, IDactivite INTEGER,
                    IDtarif INTEGER, num_ligne INTEGER, code TEXT,
                    qf_min TEXT, qf_max TEXT, montant_unique TEXT,
                    montant_min TEXT, montant_max TEXT, ajustement TEXT
                );
                CREATE TABLE badgeage_journal (
                    IDaction INTEGER PRIMARY KEY, date TEXT,
                    heure TEXT, IDindividu INTEGER, individu TEXT,
                    action TEXT, resultat TEXT
                );

                INSERT INTO c16_marker VALUES ('C16_ALL_FAKE_NOETHYS_ONLY');
                UPDATE evenements SET IDactivite=1, IDunite=11,
                    IDgroupe=21, date='2026-10-05',
                    description='Texte factice', capacite_max=16,
                    heure_debut='09:00', heure_fin='11:00', montant='12.005'
                  WHERE IDevenement=41;
                UPDATE evenements SET IDactivite=2, IDunite=12,
                    IDgroupe=22, date='2026-10-10',
                    description='Démonstration', capacite_max=20,
                    heure_debut='14:00', heure_fin='15:30', montant='0.00'
                  WHERE IDevenement=42;
                INSERT INTO evenements (
                    IDevenement, nom, IDactivite, IDunite, IDgroupe,
                    date, description, capacite_max, heure_debut,
                    heure_fin, montant
                ) VALUES (
                    43, 'Événement 2027 fictif', 1, 13, 23,
                    '2027-01-10', '100 % inventé', NULL,
                    '13:15', '15:00', '1000.0003'
                );

                INSERT INTO ouvertures VALUES
                    (601, 1, 11, 21, '2026-10-05'),
                    (602, 2, 12, 22, '2026-10-10'),
                    (603, 1, 13, 23, '2027-01-10');

                INSERT INTO tarifs VALUES
                    (801, 1, '2026-09-01', '2026-12-31',
                     'montant', 'activite', '[1,3]', NULL),
                    (802, 2, '2026-09-01', '2027-08-31',
                     'forfait', 'activite', '[2]', 42),
                    (803, 1, '2027-01-01', '2027-08-31',
                     'qf', 'evenement', '[1]', 43);

                INSERT INTO tarifs_lignes VALUES
                    (901, 1, 801, 1, 'unique', '0', '1000',
                     '12.005', '0', '100', '0.005'),
                    (902, 2, 802, 1, 'forfait', NULL, NULL,
                     '19.90', NULL, NULL, '0.00'),
                    (903, 1, 803, 1, 'qf', '0', '9999',
                     '1000.0003', NULL, NULL, '-0.0003');

                INSERT INTO badgeage_journal VALUES
                    (1001, '2026-10-02', '09:02', 10,
                     'Exemple Camille fictif', 'Pointage fictif OK', '1'),
                    (1002, '2026-10-02', '09:03', 11,
                     'Fictif Morgan exemple', 'Pointage fictif annulé', '0'),
                    (1003, '2027-01-10', '13:15', NULL,
                     'Personne anonyme simulée', 'Entrée fictive', NULL);

                INSERT INTO consommations (
                    IDconso, IDindividu, IDactivite, IDunite,
                    IDgroupe, IDprestation, IDinscription,
                    IDevenement, date, etat, heure_debut,
                    heure_fin, verrouillage, forfait
                ) VALUES
                    (9001, 12, 1, 13, 23, NULL, 503, 43,
                     '2027-01-10', 'present', '13:15', '15:00', 0, NULL),
                    (9002, 11, 2, 12, 22, NULL, 502, NULL,
                     '2027-01-11', 'etat_inconnu_c16', NULL, NULL, 0, NULL),
                    (9003, 11, 2, 12, 22, NULL, 502, NULL,
                     '2027-01-12', NULL, NULL, NULL, 0, NULL);
            """)
