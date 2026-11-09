# -*- coding: utf-8 -*-
"""STATS-RESTORE : test SQLite reel sur tables de recette purement synthetiques."""
import datetime
import sqlite3
import unittest
from types import SimpleNamespace

from tests.test_stats_restore_qf_historique import fonction


class SQLiteStatsDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()
        self.queries = []
        self.cursor.executescript("""
            CREATE TABLE familles(IDfamille INTEGER PRIMARY KEY);
            CREATE TABLE comptes_payeurs(IDcompte_payeur INTEGER PRIMARY KEY,
                                       IDfamille INTEGER);
            CREATE TABLE consommations(IDcompte_payeur INTEGER, date TEXT,
                                       etat TEXT, IDactivite INTEGER);
            CREATE TABLE inscriptions(IDcompte_payeur INTEGER, statut TEXT,
                                      IDactivite INTEGER);
            CREATE TABLE quotients(IDfamille INTEGER, IDquotient INTEGER,
                                   date_debut TEXT, date_fin TEXT,
                                   quotient NUMERIC, IDtype_quotient INTEGER);
            CREATE TABLE tarifs_lignes(IDligne INTEGER, IDactivite INTEGER,
                                       qf_min INTEGER, qf_max INTEGER);
        """)
        self.cursor.executemany("INSERT INTO familles VALUES (?)",
                                [(1,), (2,), (3,), (4,), (5,)])
        self.cursor.executemany("INSERT INTO comptes_payeurs VALUES (?,?)",
                                [(11, 1), (12, 2), (13, 3), (14, 4), (15, 5)])
        self.cursor.executemany("INSERT INTO consommations VALUES (?,?,?,?)", [
            (11, "2026-03-01", "reservation", 1),
            (11, "2026-04-01", "present", 2),  # Unicite familiale
            (12, "2026-04-01", "present", 1),
            (13, "2026-04-01", "present", 1),
            (14, "2026-04-01", "present", 1),
            (15, "2025-03-01", "present", 1),  # Hors periode
        ])
        self.cursor.executemany("INSERT INTO inscriptions VALUES (?,?,?)", [
            (11, "ok", 1), (12, "ok", 1), (13, "ok", 2),
            (14, "ok", 1), (15, "annule", 1),
        ])
        self.cursor.executemany("INSERT INTO quotients VALUES (?,?,?,?,?,?)", [
            (1, 10, "2025-01-01", "2025-12-31", 999, 1),
            (1, 11, "2026-01-01", "2099-12-31", 150, 1),
            (2, 20, "2026-01-01", "2099-12-31", 650, 1),
            (2, 21, "2026-01-01", "2099-12-31", 1200, 2),
            (4, 40, "2026-01-01", "2099-12-31", 0, None),
            (5, 50, "2026-01-01", "2099-12-31", 300, 1),
        ])
        self.cursor.executemany("INSERT INTO tarifs_lignes VALUES (?,?,?,?)", [
            (1, 1, 0, 299), (2, 1, 300, 699),
            (3, 2, 0, 699), (4, 2, 700, 999999),
        ])

    def ExecuterReq(self, sql):
        self.queries.append(sql)
        self.cursor.execute(sql)

    def ResultatReq(self):
        return self.cursor.fetchall()

    def Close(self):
        self.conn.close()


class QFSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteStatsDB()
        self.modele = SimpleNamespace(
            GetConditionActivites=lambda p: "(1,2)",
            GetDatesPeriode=lambda p: (
                datetime.date(2026, 1, 1), datetime.date(2026, 12, 31)),
            GetDateExtremeActivites=lambda db, **kw:
                datetime.date(2026, 1, 1) if kw["typeDate"] == "date_debut"
                else datetime.date(2026, 12, 31),
        )
        self.calcul = fonction("GetDictQuotients", {
            "MODELES": self.modele,
            "_QuotientsAlaDate": fonction("_QuotientsAlaDate"),
            "_TranchesTarifsExclusives": fonction("_TranchesTarifsExclusives")})

    def tearDown(self):
        self.db.Close()

    def verifier_resultat(self, resultat):
        tranches = resultat["dictTranchesTarifs"]
        self.assertEqual(tranches[(0, 299)], 2)
        self.assertEqual(tranches["a_verifier"], 1)
        self.assertEqual(tranches["pasqf"], 1)
        self.assertEqual(sum(tranches.values()), 4)
        self.assertEqual(sum(resultat["dictTranchesDefaut"].values()), 4)

    def test_presents_uniques_periode_et_types_conflictuels(self):
        params = {"mode": "presents", "listeActivites": [1, 2]}
        resultat = self.calcul(self.db, params)
        self.verifier_resultat(resultat)
        self.assertEqual(resultat["date_reference"],
                         datetime.date(2026, 12, 31))
        self.assertEqual(len(self.db.queries), 2)
        self.assertIs(self.calcul(self.db, params), resultat)
        self.assertEqual(len(self.db.queries), 2)

    def test_inscrits_exclut_annulations(self):
        params = {"mode": "inscrits", "listeActivites": [1, 2]}
        resultat = self.calcul(self.db, params)
        self.verifier_resultat(resultat)
        self.assertEqual(resultat["date_reference"], datetime.date.today())
        self.assertIn("inscriptions.statut='ok'", self.db.queries[0])


if __name__ == "__main__":
    unittest.main()
