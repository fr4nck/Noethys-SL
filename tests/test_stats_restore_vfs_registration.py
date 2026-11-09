# -*- coding: utf-8 -*-
"""STATS-RESTORE : un seul gestionnaire MemoryFS par processus."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_modeles.py"


def extraire_init(espace):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    classe = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HTML")
    meth = next(n for n in classe.body if isinstance(n, ast.FunctionDef)
                and n.name == "__init__")
    module = ast.Module(body=[meth], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), espace)
    return espace["__init__"]


class MemoryFSRegistrationTests(unittest.TestCase):
    def test_deux_fenetres_un_seul_handler_global(self):
        compteurs = []
        class MemoryFSHandler:
            pass
        class HTML:
            pass
        wx = SimpleNamespace(MemoryFSHandler=MemoryFSHandler,
                             FileSystem=SimpleNamespace(
                                 AddHandler=lambda x: compteurs.append(x)))
        initialiser = extraire_init({"wx": wx, "HTML": HTML})
        un = SimpleNamespace()
        deux = SimpleNamespace()
        initialiser(un, liste_objets=[1])
        initialiser(deux, liste_objets=[2])
        self.assertEqual(len(compteurs), 1)
        self.assertEqual(un.liste_objets, [1])
        self.assertEqual(deux.liste_objets, [2])
        self.assertIsInstance(un.stockImages, MemoryFSHandler)
        self.assertIsInstance(deux.stockImages, MemoryFSHandler)


if __name__ == "__main__":
    unittest.main()
