#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import types
import unittest
from pathlib import Path


SOURCE = Path("noethys/Dlg/DLG_Noedoc.py")


def load_deplacer_objet():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fonction = next(
        node for classe in ast.walk(tree)
        if isinstance(classe, ast.ClassDef)
        for node in classe.body
        if isinstance(node, ast.FunctionDef) and node.name == "DeplacerObjet"
    )
    module = ast.Module(body=[fonction], type_ignores=[])
    ast.fix_missing_locations(module)

    namespace = {"numpy": __import__("numpy")}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["DeplacerObjet"]


class FakeObjet:
    def __init__(self, xy):
        self._xy = xy
        self.verrouillageX = False
        self.verrouillageY = False
        self.categorie = "texte"

    def GetXY(self):
        return self._xy

    def Move(self, delta):
        self._xy = self._xy + delta

    def CalcBoundingBox(self):
        pass


class FakeCtrlPosition:
    def SetX(self, x):
        pass

    def SetY(self, y):
        pass


class FakeCtrlProprietes:
    def __init__(self):
        self.ctrl_position = FakeCtrlPosition()

    def SetObjet(self, objet):
        pass


class FakeCanvas:
    def Draw(self, refresh):
        pass


class FakeSelf:
    def MemoriserEtat(self):
        pass

    def __init__(self):
        self.dictSelection = None
        self.ctrl_proprietes = FakeCtrlProprietes()
        self.canvas = FakeCanvas()


class NoedocDeplacerObjetContractTests(unittest.TestCase):
    def setUp(self):
        self.fonction = load_deplacer_objet()
        self.numpy = __import__("numpy")

    def test_deplacement_avec_sens_reconnu(self):
        objet = FakeObjet(self.numpy.array([0, 0]))
        self.fonction(FakeSelf(), objet, sens="haut")
        self.assertEqual(list(objet.GetXY()), [0, 1])

    def test_deplacement_avec_nouvelle_position(self):
        objet = FakeObjet(self.numpy.array([0, 0]))
        self.fonction(FakeSelf(), objet, newPosition=self.numpy.array([5, 5]))
        self.assertEqual(list(objet.GetXY()), [5, 5])

    def test_contrat_ambigu_sans_sens_ni_position_leve_une_erreur_explicite(self):
        objet = FakeObjet(self.numpy.array([0, 0]))
        with self.assertRaises(ValueError):
            self.fonction(FakeSelf(), objet)

    def test_sens_non_reconnu_leve_une_erreur_explicite(self):
        objet = FakeObjet(self.numpy.array([0, 0]))
        with self.assertRaises(ValueError):
            self.fonction(FakeSelf(), objet, sens="diagonale")


if __name__ == "__main__":
    unittest.main()
