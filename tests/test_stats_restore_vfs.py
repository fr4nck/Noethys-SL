# -*- coding: utf-8 -*-
"""STATS-RESTORE : collisions MemoryFS sans charger wx ni les donnees PMSL."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Stats_modeles.py"


def memoriser():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    classe = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "Graphe")
    methode = next(x for x in classe.body if isinstance(x, ast.FunctionDef)
                   and x.name == "MemoriseImage")
    module = ast.Module(body=[methode], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"wx": SimpleNamespace(BITMAP_TYPE_PNG=42)}
    exec(compile(module, str(SOURCE), "exec"), ns)
    return ns["MemoriseImage"]


class FauxVFS:
    fichiers = {}

    def AddFile(self, nom, bitmap, genre):
        if nom in self.fichiers:
            raise ValueError("Memory VFS already contains file")
        self.fichiers[nom] = (bitmap, genre)

    def RemoveFile(self, nom):
        if nom not in self.fichiers:
            raise ValueError("Image absente")
        del self.fichiers[nom]


class MemoryFSTests(unittest.TestCase):
    def setUp(self):
        FauxVFS.fichiers = {}
        self.methode = memoriser()

    def nouveau(self, code):
        return SimpleNamespace(code=code, bitmap=None, stockImages=FauxVFS(),
                               ConvertMPLtoBMP=lambda figure: object())

    def test_ouverture_deux_dialogues_meme_code(self):
        premier = self.nouveau("graphe_nombre_individus")
        deuxieme = self.nouveau("graphe_nombre_individus")
        self.methode(premier, figure=object())
        self.methode(deuxieme, figure=object())
        self.assertNotEqual(premier.nomImage, deuxieme.nomImage)
        self.assertEqual(len(FauxVFS.fichiers), 2)

    def test_100_reactualisations_du_meme_objet(self):
        objet = self.nouveau("graphe_qf_tarifs")
        for _ in range(100):
            self.methode(objet, figure=object())
        self.assertEqual(len(FauxVFS.fichiers), 1)
        self.assertIn(objet.nomImage, FauxVFS.fichiers)

    def test_codes_differents_noms_differents(self):
        a = self.nouveau("graphe_qf_tarifs")
        b = self.nouveau("graphe_nombre_individus")
        self.methode(a)
        self.methode(b)
        self.assertNotEqual(a.nomImage, b.nomImage)


if __name__ == "__main__":
    unittest.main()
