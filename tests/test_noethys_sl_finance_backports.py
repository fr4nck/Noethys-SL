# -*- coding: utf-8 -*-
"""Contrats des backports financiers de Noethys SL 0.1.0."""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lire(path):
    return (ROOT / path).read_text(encoding="utf-8")


def source_methode(path, class_name, method_name):
    source = lire(path)
    tree = ast.parse(source)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    return ast.get_source_segment(source, method)


class PrelevementLotContracts(unittest.TestCase):
    def test_label_supporte_une_date_absente(self):
        source = lire("noethys/Dlg/DLG_Saisie_prelevement_lot.py")
        self.assertIn("date = self.ctrl_date.GetDate()", source)
        self.assertIn('date = u""', source)


class FamilyTariffContracts(unittest.TestCase):
    def test_zero_family_tier_is_a_valid_recalculation_value(self):
        source = lire("noethys/Ctrl/CTRL_Grille.py")
        self.assertIn("montant_tarif_tmp = 0.0", source)

    def test_hourly_recalculation_resolves_each_remaining_consumption(self):
        source = lire("noethys/Ctrl/CTRL_Grille.py")
        self.assertIn("ligne_calcul_horaire = None", source)
        self.assertIn('consoTmp.IDprestation == IDprestation', source)
        self.assertIn('if "horaire" in methode_calcul and ligne_calcul_horaire == None', source)

    def test_hourly_tariff_does_not_leak_a_previous_row(self):
        source = lire("noethys/Ctrl/CTRL_Grille.py")
        self.assertGreaterEqual(source.count("montant_enfant_1 = None"), 2)
        self.assertGreaterEqual(source.count("montant_enfant_6 = None"), 2)


if __name__ == "__main__":
    unittest.main()
