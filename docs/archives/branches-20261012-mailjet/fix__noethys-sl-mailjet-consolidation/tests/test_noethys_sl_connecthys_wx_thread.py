# -*- coding: utf-8 -*-
"""Contrats de thread wx du panneau Connecthys Noethys SL."""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Ctrl" / "CTRL_Portail_serveur.py"


def source_methode(nom):
    source = SOURCE.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    panel = next(
        node for node in arbre.body
        if isinstance(node, ast.ClassDef) and node.name == "Panel"
    )
    methode = next(
        node for node in panel.body
        if isinstance(node, ast.FunctionDef) and node.name == nom
    )
    return ast.get_source_segment(source, methode)


class ConnecthysWxThreadContractTests(unittest.TestCase):
    def test_set_gauge_ne_lit_plus_les_widgets_depuis_le_worker(self):
        src = source_methode("SetGauge")
        self.assertIn("wx.CallAfter(self._AppliqueGauge, valeur)", src)
        self.assertNotIn("self.gauge.IsShown()", src)
        self.assertNotIn("self.Layout()", src)

    def test_set_image_construit_le_bitmap_dans_le_callback_ui(self):
        src = source_methode("SetImage")
        self.assertIn("wx.CallAfter(self._AppliqueImage, nomImage)", src)
        self.assertNotIn("wx.Bitmap(", src)

    def test_ecrit_log_ne_lit_plus_le_textctrl_depuis_le_worker(self):
        src = source_methode("EcritLog")
        self.assertIn("wx.CallAfter(self._AjouteLogPanel", src)
        self.assertNotIn("self.log.GetValue()", src)

    def test_callbacks_ui_portent_les_operations_wx(self):
        gauge = source_methode("_AppliqueGauge")
        image = source_methode("_AppliqueImage")
        log = source_methode("_AjouteLogPanel")
        self.assertIn("self.gauge.IsShown()", gauge)
        self.assertIn("self.gauge.SetValue(valeur)", gauge)
        self.assertIn("wx.Bitmap(", image)
        self.assertIn("self.log.GetValue()", log)

    def test_journal_fichier_ecrit_du_texte_utf8_sous_python3(self):
        src = source_methode("EcritLog")
        self.assertIn('open(nom_fichier, "a", encoding="utf-8")', src)
        self.assertIn("file_log.write(texte)", src)
        self.assertNotIn(".encode('UTF-8')", src)
        self.assertNotIn('.encode("UTF-8")', src)


if __name__ == "__main__":
    unittest.main()
