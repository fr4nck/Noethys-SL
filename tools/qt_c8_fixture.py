"""Base de démonstration Qt C8 — intégralement inventée et temporaire.

Aucun paramètre de chemin accepté; aucune lecture Config.json, aucun import wx.
Le contenu est régénéré à chaque ouverture et détruit à la fermeture.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from noethys_qt.activity_editor import NativeActivityEditorRepository
from noethys_qt.consumptions_core import ConsumptionRepository

MARKER = "NOETHYS_QT_C8_ONLY_FAKE_FIXTURE_20261027"
FIRST_DAY = dt.date(2026, 10, 1)
DAY_COUNT = 28
PERSON_COUNT = 4
EXPECTED_ROWS = DAY_COUNT * PERSON_COUNT


class C8FictiveDatabase:
    def __init__(self):
        self._temp = tempfile.TemporaryDirectory(prefix="noethys-qt-c8-fictif-")
        self._root = Path(self._temp.name).resolve()
        self.path = self._root / "C8_DEMONSTRATION_FICTIVE.sqlite"
        self._make_fixture()
        self.repository = ConsumptionRepository(NativeActivityEditorRepository(self.path))

    def close(self):
        self._temp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def _make_fixture(self):
        if self.path.exists() or self.path.parent.resolve() != self._root:
            raise RuntimeError("Chemin de la base temporaire non autorisé")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE c8_marker (token TEXT PRIMARY KEY);
                CREATE TABLE individus (
                    IDindividu INTEGER PRIMARY KEY, nom TEXT NOT NULL, prenom TEXT NOT NULL,
                    date_naiss TEXT, adresse_auto INTEGER, rue_resid TEXT, cp_resid TEXT,
                    ville_resid TEXT, tel_domicile TEXT, tel_mobile TEXT,
                    travail_tel TEXT, mail TEXT, travail_mail TEXT,
                    profession TEXT, employeur TEXT, etat TEXT
                );
                CREATE TABLE familles (IDfamille INTEGER PRIMARY KEY, etat TEXT);
                CREATE TABLE rattachements (
                    IDrattachement INTEGER PRIMARY KEY,
                    IDindividu INTEGER, IDfamille INTEGER, IDcategorie INTEGER, titulaire INTEGER
                );
                CREATE TABLE activites (
                    IDactivite INTEGER PRIMARY KEY, nom TEXT, abrege TEXT,
                    date_debut TEXT, date_fin TEXT
                );
                CREATE TABLE inscriptions (
                    IDinscription INTEGER PRIMARY KEY, IDindividu INTEGER, IDfamille INTEGER,
                    IDactivite INTEGER, IDgroupe INTEGER, IDcategorie_tarif INTEGER,
                    date_inscription TEXT, date_desinscription TEXT, statut TEXT
                );
                CREATE TABLE unites (IDunite INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE groupes (IDgroupe INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE evenements (IDevenement INTEGER PRIMARY KEY, nom TEXT);
                CREATE TABLE prestations (
                    IDprestation INTEGER PRIMARY KEY, montant TEXT,
                    IDfacture INTEGER, forfait_date_debut TEXT
                );
                CREATE TABLE ventilation (
                    IDventilation INTEGER PRIMARY KEY,
                    IDprestation INTEGER, montant TEXT
                );
                CREATE TABLE consommations (
                    IDconso INTEGER PRIMARY KEY,
                    IDindividu INTEGER, IDactivite INTEGER,
                    IDunite INTEGER, IDgroupe INTEGER,
                    IDprestation INTEGER, IDinscription INTEGER,
                    IDevenement INTEGER,
                    date TEXT NOT NULL, etat TEXT,
                    heure_debut TEXT, heure_fin TEXT,
                    verrouillage INTEGER, forfait INTEGER
                );
                INSERT INTO individus (IDindividu, nom, prenom, date_naiss, adresse_auto,
                                       rue_resid, cp_resid, ville_resid, mail) VALUES
                    (10, 'Exemple', 'Camille', '1986-04-12', NULL, '1 rue Fictive', '35000', 'Rennes', 'camille@example.invalid'),
                    (11, 'Fictif', 'Morgan', '1987-05-23', NULL, '2 rue Fictive', '35000', 'Rennes', 'morgan@example.invalid'),
                    (12, 'Démonstration', 'Alex', '2014-06-01', 10, NULL, NULL, NULL, NULL),
                    (13, 'Test', 'Sacha', '2015-03-07', 11, NULL, NULL, NULL, NULL);
                INSERT INTO familles VALUES (100, NULL), (101, NULL);
                INSERT INTO rattachements VALUES
                    (1, 10, 100, 1, 1),
                    (2, 12, 100, 2, 0),
                    (3, 11, 101, 1, 1),
                    (4, 13, 101, 2, 0);
                INSERT INTO activites VALUES
                    (1, 'Sport scolaire fictif', 'SPORT', '2026-09-01', '2027-08-31'),
                    (2, 'Loisirs et ateliers fictifs', 'ATEL', '2026-09-01', '2027-08-31');
                INSERT INTO inscriptions VALUES
                    (501, 10, 100, 1, 21, 1, '2026-09-02', NULL, 'ok'),
                    (502, 11, 101, 2, 22, 1, '2026-09-03', NULL, 'ok'),
                    (503, 12, 100, 1, 21, 1, '2026-09-04', NULL, 'ok'),
                    (504, 13, 101, 2, 22, 1, '2026-09-05', NULL, 'ok');
                INSERT INTO unites VALUES
                    (11, 'Matinée'), (12, 'Après-midi');
                INSERT INTO groupes VALUES
                    (21, 'Groupe A fictif'), (22, 'Groupe B fictif');
                INSERT INTO evenements VALUES
                    (41, 'Rencontre fictive'), (42, 'Atelier fictif');
                INSERT INTO prestations VALUES
                    (301, '12.005', NULL, NULL),
                    (302, '18.50', NULL, NULL),
                    (303, '0.00', NULL, NULL),
                    (304, '25.75', 990, NULL);
            """)
            db.execute("INSERT INTO c8_marker VALUES (?)", (MARKER,))
            states = (
                "reservation", "attente", "refus", "present", "absentj",
                "absenti", None, "code_experimental",
            )
            rows = []
            for day_index in range(DAY_COUNT):
                date = (FIRST_DAY + dt.timedelta(days=day_index)).isoformat()
                for person in range(PERSON_COUNT):
                    ident = day_index * PERSON_COUNT + person + 1
                    activity = 1 + person % 2
                    unit = 11 + person % 2
                    group = 21 + person % 2
                    event = 41 + person % 2 if day_index % 3 == 0 else None
                    state = states[(day_index + person) % len(states)]
                    rows.append((
                        ident, 10 + person, activity, unit, group,
                        301 + person, 501 + person, event, date, state,
                        "09:00" if person % 2 == 0 else "14:00",
                        "10:30" if person % 2 == 0 else "16:00",
                        1 if person == 3 and day_index == 7 else 0,
                        None,
                    ))
            db.executemany("""
                INSERT INTO consommations (
                    IDconso, IDindividu, IDactivite, IDunite, IDgroupe,
                    IDprestation, IDinscription, IDevenement, date, etat,
                    heure_debut, heure_fin, verrouillage, forfait
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)

    def dump(self):
        if self.path.is_symlink() or self.path.parent.resolve() != self._root:
            raise RuntimeError("Fichier temporaire non contrôlé")
        with closing(sqlite3.connect(
            "file:" + self.path.as_posix() + "?mode=ro", uri=True
        )) as db:
            marker = db.execute("SELECT token FROM c8_marker").fetchone()
            if marker != (MARKER,):
                raise RuntimeError("Le marqueur de base fictive est absent")
            return tuple(db.iterdump())
