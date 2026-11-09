# -*- coding: utf-8 -*-
"""STATS-RESTORE : pas de cache valide apres erreur et mutation de parametres."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_modeles.py"


class ObjetFictif:
    def __init__(self, erreurs=0, categorie="texte"):
        self.visible = True
        self.categorie = categorie
        self.dictParametres = {}
        self.erreurs = erreurs
        self.appels = 0
        self.images = []

    def MAJ(self, DB, dictParametres, figure=None):
        self.appels += 1
        self.dictParametres = dictParametres
        if self.appels <= self.erreurs:
            raise RuntimeError("Calcul fictif interrompu")
        return figure

    def MemoriseImage(self, figure):
        self.images.append(figure)


def preparer(objet):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    html = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "HTML")
    names = [x.name for x in html.body if isinstance(x, ast.FunctionDef)]
    methode = "MAJ_etapes" if "MAJ_etapes" in names else "MAJ"
    fn = next(x for x in html.body if isinstance(x, ast.FunctionDef)
              and x.name == methode)
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    base = mock.Mock()
    pyplot = SimpleNamespace(figure=mock.Mock(return_value=object()),
                             close=mock.Mock())
    espace = {
        "GestionDB": SimpleNamespace(DB=lambda: base),
        "matplotlib": SimpleNamespace(pyplot=pyplot),
    }
    exec(compile(module, str(SOURCE), "exec"), espace)
    modele = SimpleNamespace(
        dictParametres={"listeActivites": [7], "mode": "presents"},
        liste_objets=[{"code": "individus", "pages": [
            {"code": "age", "objets": [objet]}]}])
    def executer():
        result = espace[methode](modele, page="age")
        if methode == "MAJ_etapes":
            list(result)
    return executer, modele, base, pyplot


class CachesStatistiquesTests(unittest.TestCase):
    def test_exception_rend_objet_recalculable(self):
        objet = ObjetFictif(erreurs=1)
        executer, _, base, _ = preparer(objet)
        with self.assertRaisesRegex(RuntimeError, "interrompu"):
            executer()
        self.assertEqual(objet.dictParametres, {})
        executer()
        self.assertEqual(objet.appels, 2)
        self.assertEqual(base.Close.call_count, 2)

    def test_mutation_parametres_force_nouveau_calcul(self):
        objet = ObjetFictif()
        executer, modele, _, _ = preparer(objet)
        executer()
        self.assertEqual(objet.appels, 1)
        self.assertIsNot(objet.dictParametres, modele.dictParametres)
        modele.dictParametres["listeActivites"].append(8)
        executer()
        self.assertEqual(objet.appels, 2)
        self.assertEqual(objet.dictParametres["listeActivites"], [7, 8])

    def test_figures_fermees_apres_conversion(self):
        objet = ObjetFictif(categorie="graphe")
        executer, _, base, pyplot = preparer(objet)
        executer()
        self.assertEqual(len(objet.images), 1)
        pyplot.close.assert_called_once()
        base.Close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
