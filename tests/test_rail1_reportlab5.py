# -*- coding: utf-8 -*-
"""ReportLab 5 a retiré reportlab.platypus.frames.ShowBoundaryValue.

Les modules d'impression des rappels, reçus, cotisations et relevés (tous
envoyables par email) l'importaient sans l'utiliser : sous ReportLab >= 5,
leur import échouait et le document ne pouvait plus être généré ni envoyé.
Même correctif que #409 (attestations fiscales).
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
FICHIERS = [
    "Utils/UTILS_Impression_rappel.py",
    "Utils/UTILS_Impression_recu.py",
    "Utils/UTILS_Impression_cotisation.py",
    "Dlg/DLG_Releve_prestations.py",
]


def _noms_importes(chemin):
    arbre = ast.parse((NOETHYS_DIR / chemin).read_text(encoding="utf-8"))
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom) and noeud.module == "reportlab.platypus.frames":
            noms.update(alias.name for alias in noeud.names)
    return noms


class ShowBoundaryValueTests(unittest.TestCase):
    def test_caracterisation_import_retire_de_reportlab_5(self):
        for chemin in FICHIERS:
            with self.subTest(chemin=chemin):
                self.assertIn("ShowBoundaryValue", _noms_importes(chemin))


if __name__ == "__main__":
    unittest.main()
