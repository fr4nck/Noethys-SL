# -*- coding: utf-8 -*-
"""Contrats UI de stabilisation de Noethys SL 0.1.0."""
from __future__ import annotations

import ast
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def source_methode(path, class_name, method_name):
    source = (ROOT / path).read_text(encoding="utf-8")
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


class BoutonImageContractTests(unittest.TestCase):
    def test_le_bouton_reserve_la_place_du_bitmap_complet(self):
        src = source_methode(
            "noethys/Ctrl/CTRL_Bouton_image.py", "CTRL", "MAJ"
        )
        self.assertIn("best = self.GetBestSize()", src)
        self.assertIn("bmp.GetWidth() + 12", src)
        self.assertIn("bmp.GetHeight() + 8", src)
        self.assertIn("self.SetMinSize((largeur_min, hauteur_min))", src)
        self.assertIn("except (OSError, ValueError):", src)
        self.assertIn("bmp = wx.NullBitmap", src)


class StaticImageAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "noethys" / "Chemins.py"
        spec = importlib.util.spec_from_file_location("chemins_test_sl", path)
        cls.Chemins = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.Chemins)

    def test_les_trois_ressources_absentes_replient_sur_organisme(self):
        with tempfile.TemporaryDirectory() as temp:
            static = Path(temp) / "Static" / "Images" / "16x16"
            static.mkdir(parents=True)
            organisme = static / "Organisme.png"
            organisme.write_bytes(b"png")

            with mock.patch.object(self.Chemins, "REP_COURANT", temp):
                for nom in ("Collectivite.png", "Association.png", "Entreprise.png"):
                    chemin = self.Chemins.GetStaticPath("Images/16x16/" + nom)
                    self.assertEqual(os.path.normpath(chemin), os.path.normpath(str(organisme)))

    def test_une_ressource_existante_reste_prioritaire(self):
        with tempfile.TemporaryDirectory() as temp:
            static = Path(temp) / "Static" / "Images" / "16x16"
            static.mkdir(parents=True)
            association = static / "Association.png"
            association.write_bytes(b"png")
            (static / "Organisme.png").write_bytes(b"fallback")

            with mock.patch.object(self.Chemins, "REP_COURANT", temp):
                chemin = self.Chemins.GetStaticPath("Images/16x16/Association.png")
                self.assertEqual(os.path.normpath(chemin), os.path.normpath(str(association)))

    def test_aucun_repli_generique_pour_un_nom_inconnu(self):
        with tempfile.TemporaryDirectory() as temp:
            static = Path(temp) / "Static" / "Images" / "16x16"
            static.mkdir(parents=True)
            (static / "Organisme.png").write_bytes(b"fallback")

            with mock.patch.object(self.Chemins, "REP_COURANT", temp):
                chemin = self.Chemins.GetStaticPath("Images/16x16/Inconnue.png")
                self.assertTrue(chemin.endswith(os.path.normpath("Images/16x16/Inconnue.png")))




class LightStartupContractTests(unittest.TestCase):
    def test_noethys_desactive_le_dark_mode_natif_avant_les_controles(self):
        source = (ROOT / "noethys" / "Noethys.py").read_text(encoding="utf-8")
        self.assertIn('wx.SystemOptions.SetOption("msw.dark-mode", 0)', source)

    def test_noethys_ne_lit_plus_directement_un_ancien_theme_noir(self):
        source = (ROOT / "noethys" / "Noethys.py").read_text(encoding="utf-8")
        self.assertNotIn(
            'CUSTOMIZE.GetValeur("interface", "theme", "Vert")',
            source,
        )
        self.assertGreaterEqual(source.count("UTILS_Interface.GetTheme()"), 2)


if __name__ == "__main__":
    unittest.main()
