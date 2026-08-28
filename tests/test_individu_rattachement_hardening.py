#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import types
import unittest
from pathlib import Path

from scripts import audit_branch_assignment_gaps


SOURCE = Path("noethys/Dlg/DLG_Individu.py")


def load_dialog_method(name, extra_globals=None):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    dialog = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Dialog"
    )
    method = next(
        node for node in dialog.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"_": lambda texte: texte}
    if extra_globals:
        namespace.update(extra_globals)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace[name]


class IndividuRattachementHardeningTests(unittest.TestCase):
    def test_unknown_category_and_three_holders_are_stable(self):
        resultats = iter([
            [(1, 10, 99, 0, 100)],
            [
                (1, 101, 10, 1, 1, "Alpha", "Ana"),
                (2, 102, 10, 1, 1, "Beta", "Ben"),
                (3, 103, 10, 1, 1, "Gamma", "Gus"),
            ],
        ])

        class FakeDB:
            def ExecuterReq(self, req):
                return True

            def ResultatReq(self):
                return next(resultats)

            def Close(self):
                return None

        method = load_dialog_method(
            "GetFamillesRattachees",
            {"GestionDB": types.SimpleNamespace(DB=FakeDB)},
        )
        self_obj = types.SimpleNamespace(IDindividu=999)
        resultat = method(self_obj)

        self.assertEqual(resultat[10]["IDcategorie"], 99)
        self.assertEqual(resultat[10]["nomCategorie"], "catégorie inconnue")
        self.assertEqual(
            resultat[10]["nomsTitulaires"],
            "Alpha Ana, Beta Ben et Gamma Gus",
        )

    def test_unknown_category_is_recorded_without_unbound_label(self):
        actions = []

        class FakeDB:
            def ReqInsert(self, table, donnees):
                return 123

            def Close(self):
                return None

        method = load_dialog_method(
            "RattacherIndividu",
            {
                "GestionDB": types.SimpleNamespace(DB=FakeDB),
                "UTILS_Historique": types.SimpleNamespace(
                    InsertActions=lambda values: actions.extend(values)
                ),
            },
        )
        self_obj = types.SimpleNamespace(IDindividu=999)

        self.assertTrue(method(self_obj, IDfamille=10, IDcategorie=99, titulaire=0))
        self.assertEqual(len(actions), 1)
        self.assertIn("catégorie inconnue", actions[0]["action"])

    def test_dialog_individu_has_no_branch_assignment_gap_left(self):
        findings = audit_branch_assignment_gaps.scan_file(
            SOURCE.resolve(), Path("noethys").resolve()
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
