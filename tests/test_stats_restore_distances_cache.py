# -*- coding: utf-8 -*-
"""STATS-RESTORE : cache de distances valide sans aucun appel reseau reel."""
import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest import mock
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_individus.py"


def charger():
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    f = next(x for x in arbre.body if isinstance(x, ast.FunctionDef)
             and x.name == "GetDistancesVilles")
    module = ast.Module(body=[f], type_ignores=[])
    ast.fix_missing_locations(module)
    espace = {"DICT_DISTANCES_VILLES": {"dictParametres": {}, "dictDistances": {}}}
    exec(compile(module, str(SOURCE), "exec"), espace)
    return espace["GetDistancesVilles"]


class CacheDistancesTests(unittest.TestCase):
    def test_une_origine_ou_destination_differente_invalide_cache(self):
        appels = []
        utils = ModuleType("Utils")
        service = ModuleType("UTILS_Distances_villes")

        def service_fictif(origine, destinations):
            appels.append((origine, tuple(destinations)))
            return {"numero_appel": len(appels)}

        service.GetDistances = service_fictif
        utils.UTILS_Distances_villes = service
        calcul = charger()
        params = {"mode": "presents", "listeActivites": [1]}
        with mock.patch.dict(sys.modules, {"Utils": utils}):
            self.assertEqual(calcul(params, ("35000", "Rennes"),
                                    [("35300", "Fougeres")]), {"numero_appel": 1})
            self.assertEqual(calcul(params, ("35000", "Rennes"),
                                    [("35300", "Fougeres")]), {"numero_appel": 1})
            self.assertEqual(calcul(params, ("35000", "Rennes"),
                                    [("35400", "Saint-Malo")]), {"numero_appel": 2})
            self.assertEqual(calcul(params, ("35200", "Rennes"),
                                    [("35400", "Saint-Malo")]), {"numero_appel": 3})
            params["listeActivites"].append(2)
            self.assertEqual(calcul(params, ("35200", "Rennes"),
                                    [("35400", "Saint-Malo")]), {"numero_appel": 4})
        self.assertEqual(len(appels), 4)


if __name__ == "__main__":
    unittest.main()
