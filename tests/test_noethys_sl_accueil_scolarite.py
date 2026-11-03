# -*- coding: utf-8 -*-
"""Scolarite fiche enfant : SQLite fictif, aucune donnees PMSL."""
import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "noethys"))
from Utils import UTILS_Accueil_scolarite as S


class Base:
    isNetwork = False
    echec = 0

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        self.conn.executescript("""
            CREATE TABLE scolarite (
                IDscolarite INTEGER PRIMARY KEY, IDindividu INTEGER,
                date_debut TEXT, date_fin TEXT, IDecole INTEGER,
                IDclasse INTEGER, IDniveau INTEGER);
            CREATE TABLE ecoles (IDecole INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE classes (IDclasse INTEGER PRIMARY KEY, nom TEXT);
            CREATE TABLE niveaux_scolaires (
                IDniveau INTEGER PRIMARY KEY, nom TEXT, abrege TEXT);
            INSERT INTO ecoles VALUES (7, 'Ecole fictive');
            INSERT INTO classes VALUES (10, 'Classe A'),(11, 'Classe B');
            INSERT INTO niveaux_scolaires VALUES (2, 'Cours elementaire 1', 'CE1'),
                                               (3, 'Cours elementaire 2', 'CE2');
            INSERT INTO scolarite VALUES
                (1,10,'2025-09-01','2026-08-31',7,11,2),
                (2,10,'2026-09-01','2027-08-31',7,10,3);
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()


class LectureScolariteTests(unittest.TestCase):
    def setUp(self):
        self.db = Base()
        self.addCleanup(self.db.close)

    def lire(self, jour, enfant=10):
        return S.LireScolariteActuelle(enfant, jour, DB=self.db)

    def test_niveau_et_classe_du_dossier_existant(self):
        r = self.lire("2026-11-03")
        self.assertEqual(r, {"etat": "ok", "classe": "CE2 (Classe A)",
                             "niveau": "CE2", "ecole": "Ecole fictive"})

    def test_recherche_a_date_et_bornes_inclusives(self):
        self.assertEqual(self.lire(date(2026, 8, 31))["niveau"], "CE1")
        self.assertEqual(self.lire(date(2026, 9, 1))["niveau"], "CE2")
        self.assertEqual(self.lire(date(2027, 8, 31))["niveau"], "CE2")
        self.assertEqual(self.lire(date(2027, 9, 1))["etat"], "absent")

    def test_dossier_sans_scolarite_reste_vide(self):
        self.assertEqual(self.lire("2026-11-03", 99),
                         {"etat": "absent", "classe": "", "niveau": "", "ecole": ""})

    def test_deux_scolarites_simultanees_ne_sont_pas_choisies(self):
        self.db.conn.execute(
            "INSERT INTO scolarite VALUES (3,10,'2026-09-01','2027-08-31',7,11,2)")
        r = self.lire("2026-11-03")
        self.assertEqual(r["etat"], "a_verifier")
        self.assertIn("À vérifier", r["classe"])

    def test_etape_sans_niveau_ou_classe(self):
        self.db.conn.execute(
            "INSERT INTO scolarite VALUES (4,40,'2026-09-01',NULL,7,NULL,NULL)")
        r = self.lire("2026-11-03", 40)
        self.assertEqual(r["classe"], "")
        self.assertEqual(r["ecole"], "Ecole fictive")

    def test_aucune_modification_sql(self):
        reqs = []
        self.db.conn.set_trace_callback(reqs.append)
        avant = self.db.conn.total_changes
        self.lire("2026-11-03")
        self.assertEqual(self.db.conn.total_changes, avant)
        self.assertTrue(reqs)
        self.assertTrue(all(x.lstrip().upper().startswith("SELECT") for x in reqs))

    def test_identifiant_et_dates_invalides(self):
        for val in (None, 0, -1, True, "10"):
            with self.subTest(identifiant=val), self.assertRaises(ValueError):
                self.lire("2026-11-03", val)
        for jour in ("03/11/2026", "2026-02-30", 20261103, True):
            with self.subTest(date=jour), self.assertRaises(ValueError):
                self.lire(jour)


if __name__ == "__main__":
    unittest.main()
