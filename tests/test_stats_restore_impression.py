# -*- coding: utf-8 -*-
"""STATS-RESTORE : choix d'impression et coches, sur objets fictifs."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def extraire(path, classe, methode, espace=None):
    code = (ROOT / path).read_text(encoding="utf-8")
    arbre = ast.parse(code)
    corps = next(item.body for item in arbre.body
                 if isinstance(item, ast.ClassDef) and item.name == classe)
    fonction = next(item for item in corps if isinstance(item, ast.FunctionDef)
                    and item.name == methode)
    module = ast.Module(body=[fonction], type_ignores=[])
    ast.fix_missing_locations(module)
    espace = dict(espace or {})
    exec(compile(module, path, "exec"), espace)
    return espace[methode]


class ImpressionSelectionTests(unittest.TestCase):
    def setUp(self):
        self.maj = extraire("noethys/Utils/UTILS_Stats_modeles.py",
                           "HTML", "GetHTML", {
                               "_": lambda texte: texte,
                               "DateEngFr": lambda texte: texte,
                               "ConvertitCouleur": lambda rvb: "000000",
                           })

    def faux_modele(self):
        appels = []
        pageA = SimpleNamespace(code="texte_a",
                                GetObjetHTML=lambda: "Texte A")
        pageB = SimpleNamespace(code="texte_b",
                                GetObjetHTML=lambda: "Texte B")
        modele = SimpleNamespace(
            dictParametres={"mode": "inscrits", "listeActivites": [1],
                            "dictActivites": {1: "Activite"}},
            liste_objets=[{"nom": "Individus", "code": "individus",
                           "pages": [
                               {"nom": "Page A", "code": "page_a", "objets": [pageA]},
                               {"nom": "Page B", "code": "page_b", "objets": [pageB]},
                           ]}],
            MAJ=lambda **kw: appels.append(kw["page"]),
        )
        return modele, appels

    def test_une_seule_page_est_calculee_et_imprimee(self):
        modele, appels = self.faux_modele()
        texte = self.maj(modele, mode="impression",
                         selectionsCodes=["individus", "page_b", "texte_b"])
        self.assertEqual(appels, ["page_b"])
        self.assertIn("Texte B", texte)
        self.assertNotIn("Texte A", texte)

    def test_toutes_les_pages_selectionnees_sont_calculees(self):
        modele, appels = self.faux_modele()
        texte = self.maj(modele, mode="impression",
                         selectionsCodes=["individus", "page_a", "texte_a",
                                          "page_b", "texte_b"])
        self.assertEqual(appels, ["page_a", "page_b"])
        self.assertIn("Texte A", texte)
        self.assertIn("Texte B", texte)


class CocheArborescenceTests(unittest.TestCase):
    def test_selection_tous_descend_jusqu_aux_objets(self):
        coche = extraire("noethys/Ctrl/CTRL_Stats_objets.py",
                         "CTRL_Objets", "Coche")
        enfants = {"root": ["rubrique"], "rubrique": ["page"],
                   "page": ["objet_a", "objet_b"],
                   "objet_a": [], "objet_b": []}
        controles = []
        faux = SimpleNamespace(
            root="root",
            GetFirstChild=lambda parent: (
                enfants[parent][0] if enfants[parent] else None, 0),
            GetChildrenCount=lambda parent, recursively=False:
                len(enfants[parent]),
            GetNextChild=lambda parent, position: (
                enfants[parent][position] if position < len(enfants[parent])
                else None, position),
            CheckItem=lambda item, etat: controles.append((item, etat)),
        )
        coche(faux, True)
        self.assertEqual(controles, [
            ("rubrique", True), ("page", True),
            ("objet_a", True), ("objet_b", True),
        ])


if __name__ == "__main__":
    unittest.main()
