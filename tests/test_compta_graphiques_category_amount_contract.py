#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import types
import unittest
from pathlib import Path

from scripts import audit_branch_assignment_gaps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "noethys"
SOURCE = SOURCE_ROOT / "Dlg" / "DLG_Compta_graphiques.py"


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


def load_graphe_repartition_categories():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fonction = next(
        node
        for classe in tree.body
        if isinstance(classe, ast.ClassDef) and classe.name == "CTRL_Graphique"
        for node in classe.body
        if isinstance(node, ast.FunctionDef) and node.name == "Graphe_repartition_categories"
    )
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

    def test_stale_sql_amount_branch_gap_is_gone(self):
        findings = audit_branch_assignment_gaps.scan_file(SOURCE, SOURCE_ROOT)
        targeted = [
            item for item in findings
            if item.get("function") == "Graphe_repartition_categories"
            and item.get("name") == "montant"
        ]
        self.assertEqual(targeted, [], targeted)


if __name__ == "__main__":
    unittest.main()
