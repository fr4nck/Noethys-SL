# -*- coding: utf-8 -*-
"""Contrat structurel minimal de la gestion des modèles Convention."""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOGUE = ROOT / "noethys" / "Dlg" / "DLG_Generation_convention.py"


class GestionModelesConventionUIContractTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = DIALOGUE.read_text(encoding="utf-8")
        cls.arbre = ast.parse(cls.source)
        cls.methodes = {
            node.name
            for node in ast.walk(cls.arbre)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def test_actions_de_gestion_sont_accessibles(self):
        for nom in (
            "OnBoutonModeles",
            "OnModifierModele",
            "OnDupliquerModele",
            "OnRenommerModele",
            "OnDefinirModeleDefaut",
            "OnSupprimerModele",
            "OnInstallerModelesExemples",
        ):
            self.assertIn(nom, self.methodes)

    def test_installation_initiale_reste_idempotente(self):
        self.assertIn("UTILS_Convention_modeles.AssurerModelesDisponibles()", self.source)
        self.assertIn('categorie="convention"', self.source)

    def test_fallback_premier_modele_est_conserve(self):
        self.assertIn("self.ctrl_modele.GetID() is None and self.ctrl_modele.GetCount() > 0", self.source)
        self.assertIn("self.ctrl_modele.SetSelection(0)", self.source)

    def test_editeur_reste_noedoc(self):
        self.assertIn("from Dlg import DLG_Noedoc", self.source)
        self.assertIn("DLG_Noedoc.Dialog(", self.source)


if __name__ == "__main__":
    unittest.main()
