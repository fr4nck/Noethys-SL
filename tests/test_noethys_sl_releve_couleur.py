# -*- coding: utf-8 -*-
"""RC6 recette 14/10/2026 : TypeError wxPython 4.2.5 sur des valeurs flottantes.

DLG_Releve_prestations : ColourSelect/SetColour recevaient (0.8, 0.8, 1) ou
(204.0, 204.0, 255.0) ; la couleur affichée reste (204, 204, 255).
Aucune fenêtre n'est créée ni affichée (wx.App sans cadre).
"""
import ast
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

def _fonction_source(chemin, nom):
    source = chemin.read_text(encoding="utf-8")
    arbre = ast.parse(source)
    noeud = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == nom)
    espace = {}
    exec(compile(ast.Module(body=[noeud], type_ignores=[]), str(chemin), "exec"), espace)
    return espace[nom]


class RelevePrestationsCouleurTests(unittest.TestCase):
    CHEMIN = NOETHYS_DIR / "Dlg" / "DLG_Releve_prestations.py"

    def test_conversion_pdf_vers_wx_entiere(self):
        convertir = _fonction_source(self.CHEMIN, "ConvertCouleurPDFpourWX")
        self.assertEqual(convertir((0.8, 0.8, 1)), (204, 204, 255))
        self.assertEqual(convertir((0, 0, 0)), (0, 0, 0))
        self.assertTrue(all(isinstance(c, int) for c in convertir((0.5, 1, 0.2))))

    def test_aller_retour_pdf_inchange(self):
        vers_pdf = _fonction_source(self.CHEMIN, "ConvertCouleurWXpourPDF")
        vers_wx = _fonction_source(self.CHEMIN, "ConvertCouleurPDFpourWX")
        self.assertEqual(vers_pdf(vers_wx((0.8, 0.8, 1))), (0.8, 0.8, 1.0))

    def test_colourselect_initialise_avec_couleur_wx(self):
        source = self.CHEMIN.read_text(encoding="utf-8")
        self.assertIn('csel.ColourSelect(self, -1, u"", ConvertCouleurPDFpourWX(COULEUR_FOND_TITRE)', source)

    @unittest.skipIf(wx is None, "wxPython requis")
    def test_wx_colour_accepte_la_couleur_convertie(self):
        convertir = _fonction_source(self.CHEMIN, "ConvertCouleurPDFpourWX")
        self.assertEqual(wx.Colour(convertir((0.8, 0.8, 1))).Get(False), (204, 204, 255))
        self.assertEqual(wx.Colour(*convertir((0.8, 0.8, 1))).Get(False), (204, 204, 255))
        # Défauts reproduits : ColourSelect.__init__ fait wx.Colour(*couleur) -> TypeError ;
        # SetColour fait wx.Colour(couleur) -> aucune erreur mais couleur fausse.
        with self.assertRaises(TypeError):
            wx.Colour(*(0.8, 0.8, 1))
        self.assertNotEqual(wx.Colour((204.0, 204.0, 255.0)).Get(False), (204, 204, 255))


if __name__ == "__main__":
    unittest.main()
