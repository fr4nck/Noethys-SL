# -*- coding: utf-8 -*-
"""RC6 recette 14/10/2026 : TypeError wxPython 4.2.5 sur des valeurs flottantes.

UTILS_Printer : wx.Pen(wx.BLACK, 0.25, wx.SOLID) à l'aperçu d'une liste ;
largeur 0 = trait le plus fin, valeur historique (int(0.25)) des wx antérieurs.
Aucune fenêtre n'est créée ni affichée (wx.App sans cadre).
"""
import re
import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(NOETHYS_DIR))

try:
    import wx
    _APP = wx.App(False)
except ImportError:
    wx = None

PEN_FLOTTANT = re.compile(r"wx\.Pen\([^()]*,\s*\d*\.\d+\s*[,)]")



class PrinterPenTests(unittest.TestCase):
    def test_aucun_stylo_a_largeur_flottante(self):
        source = (NOETHYS_DIR / "Utils" / "UTILS_Printer.py").read_text(encoding="utf-8")
        self.assertEqual(PEN_FLOTTANT.findall(source), [])
        self.assertEqual(source.count("wx.Pen(wx.BLACK, 0, wx.SOLID)"), 6)

    @unittest.skipIf(wx is None, "wxPython requis")
    def test_stylo_fin_constructible_et_largeur_historique(self):
        stylo = wx.Pen(wx.BLACK, 0, wx.SOLID)
        self.assertTrue(stylo.IsOk())
        self.assertEqual(stylo.GetWidth(), 0)
        with self.assertRaises(TypeError):  # le défaut reproduit
            wx.Pen(wx.BLACK, 0.25, wx.SOLID)


if __name__ == "__main__":
    unittest.main()
