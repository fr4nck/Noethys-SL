# -*- coding: utf-8 -*-
"""Les événements souris précoces ne lisent pas hors du tampon Noedoc.

Le sous-processus protège la suite d'une régression native AlphaPixelData.
Profil temporaire et garde réseau ; aucune donnée réelle.
"""
import pathlib
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]


def verifier_tampons():
    sys.path.insert(0, str(REPO / "tests"))
    import _garde_reseau
    import faulthandler
    faulthandler.enable()
    import wx
    from Dlg.DLG_Noedoc import CanvasNoedoc
    app = wx.App(False)
    frame = wx.Frame(None)
    canvas = CanvasNoedoc(frame)
    def tampon(couleur, largeur=20, hauteur=20):
        bmp = wx.Bitmap(largeur, hauteur, 32)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(couleur))
        dc.Clear()
        dc.SelectObject(wx.NullBitmap)
        return bmp
    canvas._HTBitmap = tampon((17, 38, 59))
    canvas._ForegroundHTBitmap = None
    for xy in ((-1, 0), (0, -1), (20, 0), (0, 20), (289, 257)):
        assert canvas.GetHitTestColor(xy) == (0, 0, 0), xy
    assert canvas.GetHitTestColor((0, 0)) == (17, 38, 59)
    assert canvas.GetHitTestColor((19, 19)) == (17, 38, 59)
    canvas._ForegroundHTBitmap = tampon((72, 93, 114), 10, 10)
    assert canvas.GetHitTestColor((9, 9)) == (72, 93, 114)
    assert canvas.GetHitTestColor((10, 10)) == (0, 0, 0)
    canvas._HTBitmap = wx.NullBitmap
    canvas._ForegroundHTBitmap = None
    assert canvas.GetHitTestColor((0, 0)) == (0, 0, 0)
    frame.Destroy()
    assert not _garde_reseau.TENTATIVES
    print("TAMPONS_NOEDOC_OK", flush=True)


class NoedocTamponTests(unittest.TestCase):
    def test_evenement_precoce_et_selection_apres_dessin(self):
        result = subprocess.run(
            [sys.executable, str(pathlib.Path(__file__).resolve()), "--child"],
            cwd=str(REPO / "noethys"), capture_output=True, timeout=25,
        )
        sortie = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, sortie)
        self.assertIn("TAMPONS_NOEDOC_OK", sortie)


if __name__ == "__main__":
    if "--child" in sys.argv:
        verifier_tampons()
    else:
        unittest.main()
