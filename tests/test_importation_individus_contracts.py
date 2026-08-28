#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import unittest
from pathlib import Path

from scripts import audit_branch_assignment_gaps


SOURCE = Path("noethys/Dlg/DLG_Importation_individus.py")


class ImportationIndividusContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_all_declared_column_formats_have_a_converter(self):
        declared_formats = set()
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Dict):
                continue
            pairs = zip(node.keys, node.values)
            for key, value in pairs:
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "format"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    declared_formats.add(value.value)

        converter_map = None
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "dictConverters" for target in node.targets):
                continue
            if isinstance(node.value, ast.Dict):
                converter_map = {
                    key.value: value.id
                    for key, value in zip(node.value.keys, node.value.values)
                    if isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and isinstance(value, ast.Name)
                }
                break

        self.assertIsNotNone(converter_map)
        self.assertTrue(declared_formats <= set(converter_map))
        self.assertEqual(converter_map["codepostal"], "Formate_cp")

    def test_csv_separator_is_initialized_before_dialog_result(self):
        position_initialisation = self.source.index("        separation = None")
        position_dialogue = self.source.index("        dlg = wx.SingleChoiceDialog", position_initialisation)
        self.assertLess(position_initialisation, position_dialogue)

    def test_importation_individus_has_no_branch_assignment_gap_left(self):
        findings = audit_branch_assignment_gaps.scan_file(
            SOURCE.resolve(), Path("noethys").resolve()
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
