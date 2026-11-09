# -*- coding: utf-8 -*-
"""STATS-RESTORE : bornes QF exclusives et mode inscrits, sans base reelle."""
import ast
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_familles.py"


def charger(nom, espace=None):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    obj = next(x for x in tree.body
               if isinstance(x, ast.FunctionDef) and x.name == nom)
    mod = ast.Module(body=[obj], type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = dict(espace or {})
    exec(compile(mod, str(SOURCE), "exec"), ns)
    return ns[nom]


class FakeDB:
    def __init__(self):
        self.queries = []
        self.liste = []
        self.resultats = [
            # Requete familles/quotients : deux familles avec QF et une sans.
            [(1, 101, "2026-01-01", "2026-12-31", 150),
             (2, 102, "2026-01-01", "2026-12-31", 5200),
             (3, None, None, None, None)],
            [(1, 0, 299), (2, 0, 699), (3, 300, 699),
             (4, 700, 999), (5, 1000, 5000), (6, 1000, 999999)],
        ]

    def ExecuterReq(self, query):
        self.queries.append(query)

    def ResultatReq(self):
        return self.resultats[len(self.queries) - 1]


class QuotientsTests(unittest.TestCase):
    def test_partition_barèmes_imbriques(self):
        partition = charger("_TranchesTarifsExclusives")
        self.assertEqual(partition([
            (0, 299), (0, 699), (300, 699), (700, 999),
            (1000, 5000), (1000, 999999),
        ]), [(0, 299), (300, 699), (700, 999),
             (1000, 5000), (5001, 999999)])

    def test_trous_et_doublons(self):
        partition = charger("_TranchesTarifsExclusives")
        self.assertEqual(partition([(0, 99), (0, 99), (200, 299)]),
                         [(0, 99), (200, 299)])

    def verifier_mode(self, mode):
        params = {"mode": mode, "listeActivites": [3],
                  "periode": {"date_debut": datetime.date(2026, 1, 1),
                              "date_fin": datetime.date(2026, 12, 31)}}
        dates = (datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))
        modeles = SimpleNamespace(
            GetConditionActivites=lambda p: "(3)",
            GetDatesPeriode=lambda p: dates,
            GetDateExtremeActivites=lambda *a, **k:
                dates[0] if k["typeDate"] == "date_debut" else dates[1])
        cache = {"dictParametres": {}, "dictResultats": {}}
        env = {"MODELES": modeles, "datetime": datetime,
               "DICT_QUOTIENTS": cache,
               "_TranchesTarifsExclusives": charger("_TranchesTarifsExclusives"),
               "_QuotientsAlaDate": charger("_QuotientsAlaDate", {"datetime": datetime})}
        fn = charger("GetDictQuotients", env)
        db = FakeDB()
        resultat = fn(db, params)
        tranches = resultat["dictTranchesTarifs"]
        self.assertEqual(tranches[(0, 299)], 1)
        self.assertEqual(tranches[(5001, 999999)], 1)
        self.assertEqual(tranches["pasqf"], 1)
        self.assertEqual(sum(tranches.values()), 3)
        self.assertEqual(len(db.queries), 2)
        if mode == "inscrits":
            self.assertIn("LEFT JOIN inscriptions", db.queries[0])
            self.assertIn("statut='ok'", db.queries[0])
        else:
            self.assertIn("LEFT JOIN consommations", db.queries[0])
            self.assertIn("consommations.etat", db.queries[0])

    def test_presents(self):
        self.verifier_mode("presents")

    def test_inscrits(self):
        self.verifier_mode("inscrits")


if __name__ == "__main__":
    unittest.main()
