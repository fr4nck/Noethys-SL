#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Dlg" / "DLG_Compta_graphiques.py"


class FakeDB:
    def __init__(self):
        self.rows = [
            (1, "Catégorie A", 10.0),
            (2, "Catégorie B", 25.5),
        ]

    def ExecuterReq(self, req):
        self.req = req

    def ResultatReq(self):
        return list(self.rows)

    def Close(self):
        pass


class FakeCanvas:
    def draw(self):
        pass


class FakeFigureRef:
    def __init__(self):
        self.canvas = FakeCanvas()


class FakeAxis:
    def __init__(self):
        self.labels = None
        self.figure = FakeFigureRef()

    def pie(self, valeurs, labels, colors, autopct, shadow):
        self.valeurs = list(valeurs)
        self.labels = list(labels)
        return object(), [object() for _ in labels], [object() for _ in labels]

    def set_title(self, *args, **kwargs):
        return object()

    def set_aspect(self, value):
        pass

    def autoscale_view(self, value):
        pass


class FakeFigure:
    def __init__(self):
        self.axis = FakeAxis()

    def add_subplot(self, code):
        return self.axis


class FakeSelf:
    def __init__(self):
        self.dictParametres = {
            "date_debut": None,
            "date_fin": None,
            "IDanalytique": None,
            "nom": "Test",
        }
        self.afficher_valeurs = True
        self.figure = FakeFigure()

    def SendSizeEvent(self):
        pass


def get_graphe_repartition_categories_node():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    return next(
        node
        for classe in tree.body
        if isinstance(classe, ast.ClassDef) and classe.name == "CTRL_Graphique"
        for node in classe.body
        if isinstance(node, ast.FunctionDef) and node.name == "Graphe_repartition_categories"
    )


def load_graphe_repartition_categories():
    fonction = get_graphe_repartition_categories_node()
    module = ast.Module(body=[fonction], type_ignores=[])
    ast.fix_missing_locations(module)

    fake_matplotlib = types.SimpleNamespace(
        cm=types.SimpleNamespace(hsv=lambda value: value),
        pyplot=types.SimpleNamespace(setp=lambda *args, **kwargs: None),
    )
    namespace = {
        "GestionDB": types.SimpleNamespace(DB=FakeDB),
        "matplotlib": fake_matplotlib,
        "wx": types.SimpleNamespace(CallAfter=lambda callback: callback()),
        "SYMBOLE": "€",
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["Graphe_repartition_categories"]


class ComptaGraphiquesCategoryAmountContractTests(unittest.TestCase):
    def test_each_category_label_uses_its_own_aggregated_amount(self):
        fonction = load_graphe_repartition_categories()
        objet = FakeSelf()

        fonction(objet, typeCategorie="debit", typeDonnees="budgetaires")

        self.assertEqual(objet.figure.axis.valeurs, [10.0, 25.5])
        self.assertEqual(
            objet.figure.axis.labels,
            ["Catégorie A\n10.00 €", "Catégorie B\n25.50 €"],
        )

    def test_label_source_uses_current_category_amount(self):
        fonction = get_graphe_repartition_categories_node()
        label_updates = [
            node
            for node in ast.walk(fonction)
            if isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "label"
        ]
        self.assertEqual(len(label_updates), 1, label_updates)
        expression = label_updates[0].value

        stale_amount_reads = [
            node
            for node in ast.walk(expression)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "montant"
        ]
        self.assertEqual(stale_amount_reads, [])

        current_category_amount_reads = [
            node
            for node in ast.walk(expression)
            if isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "dictTemp"
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "montant"
        ]
        self.assertEqual(len(current_category_amount_reads), 1, current_category_amount_reads)


if __name__ == "__main__":
    unittest.main()
