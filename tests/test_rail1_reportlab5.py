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
    def test_plus_aucun_import_de_showboundaryvalue(self):
        for chemin in FICHIERS:
            with self.subTest(chemin=chemin):
                self.assertNotIn("ShowBoundaryValue", _noms_importes(chemin))

    def test_modules_importables_avec_reportlab_installe(self):
        if str(NOETHYS_DIR) not in sys.path:
            sys.path.insert(0, str(NOETHYS_DIR))
        try:
            import wx  # noqa: F401
        except ImportError:
            self.skipTest("wx absent")
        import importlib
        for nom in ("Utils.UTILS_Impression_rappel", "Utils.UTILS_Impression_recu",
                    "Utils.UTILS_Impression_cotisation"):
            with self.subTest(module=nom):
                importlib.import_module(nom)


if __name__ == "__main__":
    unittest.main()
