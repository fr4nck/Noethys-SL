# -*- coding: utf-8 -*-
"""Contrat de progression du traitement automatique des réservations Connecthys."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Dlg" / "DLG_Saisie_portail_demande.py"


def method_source(class_name, method_name):
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    return ast.get_source_segment(source, method)


class ConnecthysReservationProgressTests(unittest.TestCase):
    def test_foreground_progress_is_repainted_without_yield(self):
        src = method_source("Dialog", "AfficherProgressionReservations")
        self.assertIn("self.ctrl_reponse.Update()", src)
        self.assertIn("self.panel_bandeau.Update()", src)
        self.assertNotIn("wx.Yield", src)
        self.assertNotIn("wx.SafeYield", src)

    def test_result_is_shown_before_grid_save(self):
        src = method_source("Traitement", "Traitement_reservations")
        show = src.index("AfficherProgressionReservations")
        save = src.index("self.Save_grille(ctrl_grille)")
        self.assertLess(show, save)
        self.assertIn("Enregistrement des consommations en cours", src)
        self.assertIn("Enregistrement des consommations terminé", src)


if __name__ == "__main__":
    unittest.main()
