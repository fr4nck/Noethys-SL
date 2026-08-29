#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import unittest
from pathlib import Path

from scripts import audit_branch_assignment_gaps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "noethys"
SOURCE_PATH = SOURCE_ROOT / "Ctrl" / "CTRL_Composition.py"


def load_positions_helper():
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "GetPositionsLiensFiliation"
    ]
    if len(functions) != 1:
        raise AssertionError(functions)
    module = ast.Module(body=functions, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace["GetPositionsLiensFiliation"]


class CompositionFiliationLayoutTests(unittest.TestCase):
    def test_historical_positions_one_to_five_are_preserved(self):
        positions = load_positions_helper()
        expected = {
            1: [100],
            2: [98, 102],
            3: [96, 100, 104],
            4: [94, 98, 102, 106],
            5: [92, 96, 100, 104, 108],
        }
        for count, values in expected.items():
            with self.subTest(count=count):
                self.assertEqual(positions(100, count), values)

    def test_ten_filiation_groups_are_supported(self):
        positions = load_positions_helper()
        self.assertEqual(
            positions(100, 10),
            [82, 86, 90, 94, 98, 102, 106, 110, 114, 118],
        )

    def test_zero_groups_returns_no_position(self):
        positions = load_positions_helper()
        self.assertEqual(positions(100, 0), [])

    def test_positions_remain_regular_and_centered(self):
        positions = load_positions_helper()
        for count in (1, 2, 5, 10, 17):
            values = positions(240, count)
            self.assertEqual(len(values), count)
            if count > 1:
                self.assertEqual(
                    [b - a for a, b in zip(values, values[1:])],
                    [4] * (count - 1),
                )
            self.assertEqual(values[0] + values[-1], 480)

    def test_draw_liens_poscentrale_branch_gap_is_gone(self):
        findings = audit_branch_assignment_gaps.scan_file(SOURCE_PATH, SOURCE_ROOT)
        targeted = [
            item for item in findings
            if item.get("function") == "DrawLiens"
            and item.get("name") == "posCentrale"
        ]
        self.assertEqual(targeted, [], targeted)


if __name__ == "__main__":
    unittest.main()
