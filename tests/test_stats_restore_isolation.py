# -*- coding: utf-8 -*-
"""STATS-RESTORE : isolation des caches statistiques, donnees fictives uniquement."""
import ast
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_familles.py"


def charge_membres():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fonction = next(n for n in arbre.body if isinstance(n, ast.FunctionDef)
                    and n.name == "GetDictMembres")
    module = ast.Module(body=[fonction], type_ignores=[])
    ast.fix_missing_locations(module)
    modeles_source = SOURCE.parent / "UTILS_Stats_modeles.py"
    arbre_modeles = ast.parse(modeles_source.read_text(encoding="utf-8"))
    helpers = [x for x in arbre_modeles.body
               if isinstance(x, ast.FunctionDef)
               and x.name in ("LireCacheStats", "EcrireCacheStats")]
    namespace_helpers = {}
    compile_helpers = ast.Module(body=helpers, type_ignores=[])
    ast.fix_missing_locations(compile_helpers)
    exec(compile(compile_helpers, str(modeles_source), "exec"),
         namespace_helpers)
    modele = SimpleNamespace(
        GetDatesPeriode=lambda p: (
            datetime.date(2026, 1, 1), datetime.date(2026, 12, 31)),
        GetConditionActivites=lambda p: "(" + ",".join(str(n) for n in
                                                   p["listeActivites"]) + ")")
    modele.LireCacheStats = namespace_helpers["LireCacheStats"]
    modele.EcrireCacheStats = namespace_helpers["EcrireCacheStats"]
    espace = {
        "MODELES": modele,
        "DICT_MEMBRES": {"dictParametres": {}, "dictResultats": {}}
    }
    exec(compile(module, str(SOURCE), "exec"), espace)
    return espace["GetDictMembres"]


class DBFictive:
    def __init__(self, lignes):
        self.lignes = lignes
        self.requetes = []

    def ExecuterReq(self, req):
        self.requetes.append(req)

    def ResultatReq(self):
        return list(self.lignes)


class IsolationDesStatistiquesTests(unittest.TestCase):
    def test_deux_connexions_differentes_ne_partagent_pas_resultats(self):
        get_membres = charge_membres()
        params = {"mode": "presents", "listeActivites": [1]}
        premiere = DBFictive([(10, 100)])
        deuxieme = DBFictive([(20, 200), (20, 201)])
        self.assertEqual(get_membres(premiere, params), {1: 1})
        self.assertEqual(get_membres(deuxieme, params), {2: 1})
        self.assertEqual(len(deuxieme.requetes), 1)

    def test_mutation_de_parametres_invalide_cache(self):
        get_membres = charge_membres()
        params = {"mode": "presents", "listeActivites": [1]}
        db = DBFictive([(10, 100)])
        self.assertEqual(get_membres(db, params), {1: 1})
        self.assertEqual(len(db.requetes), 1)
        params["listeActivites"].append(2)
        db.lignes = [(20, 200), (20, 201)]
        self.assertEqual(get_membres(db, params), {2: 1})
        self.assertEqual(len(db.requetes), 2)


if __name__ == "__main__":
    unittest.main()
