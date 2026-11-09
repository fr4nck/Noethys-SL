# -*- coding: utf-8 -*-
"""STATS-RESTORE : validite des QF, conflits, dates, sans donnees PMSL."""
import ast
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_familles.py"


def fonction(nom, espace=None):
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    f = next(x for x in arbre.body if isinstance(x, ast.FunctionDef) and x.name == nom)
    module = ast.Module(body=[f], type_ignores=[])
    ast.fix_missing_locations(module)
    env = {"datetime": datetime}
    env.update(espace or {})
    exec(compile(module, str(SOURCE), "exec"), env)
    return env[nom]


class FauxDB:
    def __init__(self, resultats):
        self.resultats = resultats
        self.requetes = []

    def ExecuterReq(self, sql):
        self.requetes.append(sql)

    def ResultatReq(self):
        return self.resultats[(len(self.requetes)-1) % len(self.resultats)]


class QFHistoriqueTests(unittest.TestCase):
    def test_seul_quotient_actif_retenu_peu_importe_lordre(self):
        choisir = fonction("_QuotientsAlaDate")
        donnees = [(7, 10, "2025-01-01", "2025-12-31", 500, 1),
                   (7, 20, "2026-01-01", "2027-01-09", 680, 1)]
        self.assertEqual(choisir(donnees, "2026-12-31"), {7: 680})
        self.assertEqual(choisir(list(reversed(donnees)), "2026-12-31"),
                         {7: 680})

    def test_qf_contradictorires_et_zero(self):
        choisir = fonction("_QuotientsAlaDate")
        donnees = [
            (1, 10, "2026-01-01", "2026-09-09", 499, 1),
            (1, 11, "2026-09-10", "2027-01-09", 650, 1),
            (2, 20, "2026-01-01", "2027-01-09", 900, 1),
            (2, 21, "2026-01-01", "2027-01-09", 1200, 2),
            (3, None, None, None, None, None),
            (4, 40, "2026-01-01", "2027-01-09", 0, None),
            (5, 50, "2026-01-01", "2026-12-31", None, 1),
        ]
        self.assertEqual(choisir(donnees, "2026-12-31"),
                         {1: 650, 2: "a_verifier", 3: None,
                          4: 0, 5: "a_verifier"})

    def test_mauvaise_date_ne_devient_pas_sans_qf(self):
        choisir = fonction("_QuotientsAlaDate")
        self.assertEqual(choisir([
            (6, 1, None, "2026-12-31", 700, 1),
            (7, 2, "2027-01-01", "2027-12-31", 700, 1),
        ], "2026-12-31"), {6: "a_verifier", 7: None})

    def test_ordre_labels(self):
        tri = fonction("TrierQF")
        self.assertEqual(tri(["autre", (700, 999), "pasqf",
                              (0, 299), "a_verifier"]),
                         [(0, 299), (700, 999), "pasqf",
                          "a_verifier", "autre"])

    def test_repartition_dedoublonnee_et_cache_borne_connexion(self):
        date_fin = datetime.date(2026, 12, 31)
        m = SimpleNamespace(GetDatesPeriode=lambda p: (
            datetime.date(2026, 1, 1), date_fin),
            GetConditionActivites=lambda p: "(5)")
        get_qf = fonction("GetDictQuotients", {
            "MODELES": m,
            "_QuotientsAlaDate": fonction("_QuotientsAlaDate"),
            "_TranchesTarifsExclusives": fonction("_TranchesTarifsExclusives")})
        db = FauxDB([
            [(1, 10, "2026-01-01", "2027-01-09", 550, 3),
             (2, 20, "2026-01-01", "2027-01-09", 1100, 2),
             (2, 21, "2026-01-01", "2027-01-09", 1800, 3),
             (3, None, None, None, None, None)],
            [(1, 0, 699), (2, 700, 999), (3, 1000, 999999)]
        ])
        p = {"mode": "presents", "listeActivites": [5],
             "periode": {"date_debut": datetime.date(2026, 1, 1),
                         "date_fin": date_fin}}
        resultat = get_qf(db, p)
        self.assertEqual(resultat["dictTranchesTarifs"][(0, 699)], 1)
        self.assertEqual(resultat["dictTranchesTarifs"]["a_verifier"], 1)
        self.assertEqual(resultat["dictTranchesTarifs"]["pasqf"], 1)
        self.assertEqual(sum(resultat["dictTranchesTarifs"].values()), 3)
        self.assertEqual(resultat["date_reference"], date_fin)
        self.assertIn("quotients.IDtype_quotient", db.requetes[0])
        self.assertIn("consommations.date", db.requetes[0])
        self.assertIs(get_qf(db, p), resultat)
        self.assertEqual(len(db.requetes), 2)
        p["listeActivites"] = [6]
        get_qf(db, p)
        self.assertEqual(len(db.requetes), 4)


if __name__ == "__main__":
    unittest.main()
