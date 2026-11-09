# -*- coding: utf-8 -*-
"""STATS-RESTORE : l'apercu doit conserver les ressources MemoryFS."""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] /
          "noethys" / "Dlg" / "DLG_Stats.py")


class ApercuRessourcesTests(unittest.TestCase):
    def test_preview_retient_le_modele_pendant_son_affichage(self):
        arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
        classe = next(x for x in arbre.body
                      if isinstance(x, ast.ClassDef) and x.name == "Dialog")
        imprimer = next(x for x in classe.body
                       if isinstance(x, ast.FunctionDef) and x.name == "Imprimer")
        proprietaires = [
            n for n in ast.walk(imprimer)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute)
                    and isinstance(t.value, ast.Name)
                    and t.value.id == "preview_window"
                    and t.attr == "_stats_html_owner"
                    for t in n.targets)
            and isinstance(n.value, ast.Attribute)
            and isinstance(n.value.value, ast.Name)
            and n.value.value.id == "self"
            and n.value.attr == "baseHTML"
        ]
        self.assertEqual(len(proprietaires), 1)


if __name__ == "__main__":
    unittest.main()
