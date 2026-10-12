# -*- coding: utf-8 -*-
"""Non-régression : hauteur du tooltip individu (SuperToolTip) sous
wxPython 4.2.5.

CTRL_Composition.py (et 5 autres fichiers : CTRL_Droits.py, CTRL_Grille.py,
CTRL_Locations_tableau.py, DLG_Noedoc.py, DLG_Ouvertures.py) affichent un
tooltip individu via :

    self.tipFrame = STT.ToolTipWindow(self, self.tip)
    self.tipFrame.CalculateBestSize()

wx.lib.agw.supertooltip.ToolTipWindowBase.CalculateBestSize() fait :

    maxWidth, maxHeight = self.OnPaint(None)
    self.SetSize((maxWidth, maxHeight))

OnPaint() mélange division entière (//) et division réelle (/) selon les
options du tooltip : dès qu'un pied de page avec bitmap est défini
(SetFooterBitmap, ce que fait Noethys), le calcul de la hauteur totale
passe par une division réelle et devient un flottant. SetSize() reçoit
alors une hauteur flottante, ce qui tronque visuellement le tooltip sous
wxPython 4.2.5 (recette réelle : hauteur ~20px au lieu de la hauteur
réelle du message sur 8-10 lignes) au lieu de lever une erreur explicite.

Correctif : Utils/UTILS_Adaptations.py remplace
ToolTipWindowBase.CalculateBestSize() par une version qui force des
coordonnées entières, sans modifier wx.lib.agw.supertooltip (site-packages
non touché).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

from Utils import UTILS_Adaptations  # noqa: E402,F401  (charge le correctif à l'import)
import wx.lib.agw.supertooltip as STT  # noqa: E402


def _creer_tooltip_multiligne(parent, nombre_lignes=10):
    """ Reproduit exactement la configuration utilisée par CTRL_Composition.py
    (message multiligne + pied de page avec bitmap ET texte, le
    déclencheur du calcul en division réelle). """
    tip = STT.SuperToolTip(u"")
    message = u"\n".join(u"Ligne %d" % i for i in range(nombre_lignes))
    tip.SetMessage(message)
    tip.SetDrawFooterLine(True)
    tip.SetFooterBitmap(wx.Bitmap(16, 16))
    tip.SetFooterFont(wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_LIGHT))
    tip.SetFooter(u"Double-cliquez pour ouvrir sa fiche")
    return STT.ToolTipWindow(parent, tip)


class SuperToolTipHauteurTests(unittest.TestCase):
    def setUp(self):
        self.frame = wx.Frame(None)
        self.addCleanup(self.frame.Destroy)

    def test_onpaint_peut_renvoyer_une_hauteur_flottante(self):
        """Caractérise la cause racine, dans la bibliothèque wx.lib.agw
        (non modifiée ici) : ne doit pas disparaître si le correctif
        Noethys venait à être retiré par erreur -- sert de garde-fou pour
        que le prochain test reste pertinent."""
        tipFrame = _creer_tooltip_multiligne(self.frame)
        self.addCleanup(tipFrame.Destroy)
        _largeur, hauteur = tipFrame.OnPaint(None)
        self.assertIsInstance(hauteur, float)

    def test_calculatebestsize_utilise_des_coordonnees_entieres(self):
        """Le correctif (Utils/UTILS_Adaptations.py) doit garantir une
        taille entière, égale à la hauteur réelle calculée par OnPaint
        (tronquée à l'entier), et non une hauteur écrasée par
        wx.Window.SetSize() recevant un flottant."""
        tipFrame = _creer_tooltip_multiligne(self.frame)
        self.addCleanup(tipFrame.Destroy)
        largeur_attendue, hauteur_attendue = tipFrame.OnPaint(None)

        tipFrame.CalculateBestSize()

        taille = tipFrame.GetSize()
        self.assertEqual(taille.GetWidth(), int(largeur_attendue))
        self.assertEqual(taille.GetHeight(), int(hauteur_attendue))
        # Preuve directe de non-régression : la recette réelle observait une
        # hauteur tronquée à ~20px pour un message de 10 lignes + pied de
        # page ; la hauteur réelle attendue est nettement supérieure.
        self.assertGreater(taille.GetHeight(), 100)

    def test_tous_les_appelants_connus_chargent_le_correctif(self):
        """Vérifie, au niveau du code source, que les 7 sites d'appel de
        CalculateBestSize() connus dans le dépôt importent bien
        Utils.UTILS_Adaptations (qui charge le correctif à l'import), sans
        dupliquer le correctif localement dans chaque fichier."""
        fichiers = (
            "Ctrl/CTRL_Composition.py",
            "Ctrl/CTRL_Droits.py",
            "Ctrl/CTRL_Grille.py",
            "Ctrl/CTRL_Locations_tableau.py",
            "Dlg/DLG_Noedoc.py",
            "Dlg/DLG_Ouvertures.py",
        )
        for relatif in fichiers:
            source = (NOETHYS_DIR / relatif).read_text(encoding="utf-8")
            self.assertIn("CalculateBestSize", source, relatif)
            self.assertIn("from Utils import UTILS_Adaptations", source, relatif)


if __name__ == "__main__":
    unittest.main()
