#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
import unittest
from pathlib import Path

from scripts import audit_branch_assignment_gaps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "noethys"
SOURCE_PATH = SOURCE_ROOT / "Dlg" / "DLG_Badgeage_grille.py"


def load_method(name):
    source = SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(
        item
        for node in tree.body if isinstance(node, ast.ClassDef)
        for item in node.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"_": lambda text: text, "UTILS_Dates": object()}
    exec(compile(module, str(SOURCE_PATH), "exec"), namespace)
    return namespace[name]


class EmptyEventCase:
    ouvert = True
    liste_evenements = []


class FakeGrid:
    dictUnites = {
        7: {
            "heure_debut": None,
            "heure_fin": None,
            "type": "Evenement",
        }
    }


class FakeBadgeage:
    def __init__(self):
        self.grille = FakeGrid()
        self.usage = "nomadhys"
        self.case = EmptyEventCase()

    def GetCase(self, IDunite=None, date=None):
        return self.case


class BadgeageEvenementContractTests(unittest.TestCase):
    def test_saisie_evenement_vide_retourne_une_erreur_metier(self):
        result = load_method("SaisieConso")(FakeBadgeage(), IDunite=7)
        self.assertIsInstance(result, str)
        self.assertIn("aucun événement", result.lower())

    def test_suppression_evenement_vide_retourne_une_erreur_metier(self):
        result = load_method("SupprimeConso")(FakeBadgeage(), IDunite=7)
        self.assertIsInstance(result, str)
        self.assertIn("aucun événement", result.lower())

    def test_saisie_conso_ne_laisse_plus_evenement_conditionnellement_indefini(self):
        findings = audit_branch_assignment_gaps.scan_file(SOURCE_PATH, SOURCE_ROOT)
        targeted = [
            finding for finding in findings
            if finding.get("function") == "SaisieConso" and finding.get("name") == "evenement"
        ]
        self.assertEqual(targeted, [], targeted)


if __name__ == "__main__":
    unittest.main()
