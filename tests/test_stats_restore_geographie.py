# -*- coding: utf-8 -*-
"""STATS-RESTORE : statistiques geographiques sans GetTitulaires ou reseau."""
import ast
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_individus.py"


def charger():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fn = next(n for n in arbre.body if isinstance(n, ast.FunctionDef)
              and n.name == "GetDictVilles")
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    modele = SimpleNamespace(
        GetDatesPeriode=lambda p: (
            datetime.date(2026, 1, 1), datetime.date(2026, 12, 31)),
        GetConditionActivites=lambda p: "(1,2)",
        LireCacheStats=lambda DB, name, params: (False, None),
        EcrireCacheStats=lambda DB, name, params, val: val)
    appels_distances = []
    def distances(params, origine, destinations):
        appels_distances.append((origine, destinations))
        return {}
    espace = {
        "MODELES": modele,
        "GetDistancesVilles": distances,
        "DICT_VILLES": {"dictParametres": {}, "dictResultats": {}}
    }
    exec(compile(module, str(SOURCE), "exec"), espace)
    return espace["GetDictVilles"], appels_distances, fn


class FauxDB:
    def __init__(self):
        self.queries = []
        self.reponses = [
            [(1, "A", "AA", "", "35000", "Rennes"),
             (2, "B", "BB", "", "35000", "Rennes"),
             (3, "C", "CC", "", "35300", "Fougeres")],
            [(1, None), (2, None)],
            [("35000", "Rennes")],
        ]
    def ExecuterReq(self, sql):
        self.queries.append(sql)
    def ResultatReq(self):
        return self.reponses[len(self.queries)-1]


class GeographieTests(unittest.TestCase):
    def test_pas_de_lecture_titulaires_inutile(self):
        _, _, fn = charger()
        self.assertNotIn("GetTitulaires", ast.unparse(fn))
        self.assertNotIn("UTILS_Titulaires", ast.unparse(fn))

    def test_villes_de_residence_sans_depassement_du_perimetre(self):
        lire, distances, _ = charger()
        params = {"mode": "presents", "listeActivites": [1, 2]}
        db = FauxDB()
        resultats = lire(db, params)
        self.assertEqual(resultats, {
            ("35000", "Rennes"): {"nbreIndividus": 2,
                                   "distance": "", "distance_metres": 0}
        })
        self.assertEqual(len(db.queries), 3)
        self.assertEqual(distances, [(("35000", "Rennes"),
                                      [("35000", "Rennes")])])


if __name__ == "__main__":
    unittest.main()
