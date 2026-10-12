# -*- coding: utf-8 -*-
"""Contrats statiques pour la navigation commune Repens."""

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NavigationUIContractTests(unittest.TestCase):
    def _read_aui(self):
        path = ROOT / "noethys/Utils/UTILS_Aui.py"
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        return text

    def test_common_book_navigation_is_semantic_and_cross_platform(self):
        text = self._read_aui()
        self.assertIn("def ConfigurerNavigation(book):", text)
        self.assertIn('("Notebook", "Choicebook", "Listbook", "Treebook", "Simplebook")', text)
        self.assertIn('GetCouleurRole("surface")', text)
        self.assertIn('GetCouleurRole("surface_container_low")', text)
        self.assertIn('GetCouleurRole("on_surface")', text)
        self.assertIn('("GetListView", "GetChoiceCtrl", "GetTreeCtrl")', text)

    def test_native_books_keep_platform_geometry_and_focus(self):
        text = self._read_aui()
        navigation = text.split("def ConfigurerNavigation(book):", 1)[1].split("def ConfigurerNotebook", 1)[0]
        self.assertIn("if est_aui:", navigation)
        self.assertIn("SetTabCtrlHeight", navigation)
        self.assertNotIn("SetMinSize", navigation)
        self.assertNotIn("SetSize", navigation)
        self.assertNotIn("SetWindowStyle", navigation)

    def test_historical_notebook_entry_point_delegates_to_common_navigation(self):
        text = self._read_aui()
        wrapper = text.split("def ConfigurerNotebook(notebook):", 1)[1].split("def _ConfigurerComposantsDuManager", 1)[0]
        self.assertIn("return ConfigurerNavigation(notebook)", wrapper)

    def test_aui_manager_discovers_standard_books_without_relaying_out_panes(self):
        text = self._read_aui()
        manager_components = text.split("def _ConfigurerComposantsDuManager(manager):", 1)[1].split("def _ConfigurerPoliceCaptions", 1)[0]
        self.assertIn("types_navigation = _TypesNavigationStandard(wx)", manager_components)
        self.assertIn("ConfigurerNavigation(fenetre)", manager_components)
        self.assertNotIn("DockSize", manager_components)
        self.assertNotIn("BestSize", manager_components)
        self.assertNotIn("MinSize", manager_components)


if __name__ == "__main__":
    unittest.main()
