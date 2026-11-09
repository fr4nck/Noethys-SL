# -*- coding: utf-8 -*-
"""STATS-RESTORE : inventaire statique des 11 pages et 33 objets du dialogue."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIALOGUE = ROOT / "noethys" / "Dlg" / "DLG_Stats.py"
SOURCES = {
    "INDIVIDUS": ROOT / "noethys" / "Utils" / "UTILS_Stats_individus.py",
    "FAMILLES": ROOT / "noethys" / "Utils" / "UTILS_Stats_familles.py",
}


def champ(objet, nom):
    assert isinstance(objet, ast.Dict)
    for cle, valeur in zip(objet.keys, objet.values):
        if isinstance(cle, ast.Constant) and cle.value == nom:
            return valeur
    raise KeyError(nom)


class InventaireStatistiquesTests(unittest.TestCase):
    def test_11_pages_33_objets_referencent_classes_metier(self):
        arbre = ast.parse(DIALOGUE.read_text(encoding="utf-8"))
        dialogue = next(n for n in arbre.body
                        if isinstance(n, ast.ClassDef) and n.name == "Dialog")
        initialiseur = next(n for n in dialogue.body
                            if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        affectation = next(
            n for n in ast.walk(initialiseur)
            if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Attribute)
                and isinstance(t.value, ast.Name) and t.value.id == "self"
                and t.attr == "listeObjets" for t in n.targets))
        rubriques = affectation.value.elts
        codes_pages, codes_objets, categories = set(), set(), []
        classes = {}
        for domaine, chemin in SOURCES.items():
            source = ast.parse(chemin.read_text(encoding="utf-8"))
            classes[domaine] = {
                node.name: node for node in source.body if isinstance(node, ast.ClassDef)
            }
        for rubrique in rubriques:
            pages = champ(rubrique, "pages").elts
            for page in pages:
                code = champ(page, "code").value
                self.assertNotIn(code, codes_pages)
                codes_pages.add(code)
                for objet in champ(page, "objets").elts:
                    self.assertIsInstance(objet, ast.Call)
                    constructeur = objet.func
                    self.assertIsInstance(constructeur, ast.Attribute)
                    domaine = constructeur.value.id
                    nom = constructeur.attr
                    self.assertIn(domaine, classes)
                    self.assertIn(nom, classes[domaine])
                    classe = classes[domaine][nom]
                    self.assertTrue(any(
                        isinstance(n, ast.FunctionDef) and n.name == "MAJ"
                        for n in classe.body), nom)
                    bases = [b.attr for b in classe.bases if isinstance(b, ast.Attribute)]
                    self.assertEqual(len(bases), 1, nom)
                    categories.append(bases[0])
                    # Les codes sont definis sur les instances ; contrôler
                    # uniquement ici l'existence des classes et de leur MAJ.
                    codes_objets.add((domaine, nom))
        self.assertEqual(len(rubriques), 2)
        self.assertEqual(len(codes_pages), 11)
        self.assertEqual(len(categories), 33)
        self.assertEqual(categories.count("Tableau"), 16)
        self.assertEqual(categories.count("Graphe"), 15)
        self.assertEqual(categories.count("Texte"), 2)
        self.assertEqual(len(codes_objets), 33)


if __name__ == "__main__":
    unittest.main()
