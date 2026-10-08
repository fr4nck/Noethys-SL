# -*- coding: utf-8 -*-
"""La fermeture de l'accueil Windows ne rappelle pas un bandeau détruit.

Le test utilise un processus séparé : une violation native wx ne doit pas
abattre la suite. Profil temporaire, aucun fichier ouvert ni accès réseau.
"""
import pathlib
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]


def fermer_accueil():
    sys.path.insert(0, str(REPO / "tests"))
    import _garde_reseau
    import faulthandler
    faulthandler.enable()
    import wx
    import Noethys
    Noethys.CUSTOMIZE = Noethys.UTILS_Customize.Customize()
    app = wx.App(False)
    frame = Noethys.MainFrame(None)
    app.SetTopWindow(frame)
    frame.Initialisation()
    frame.Show()
    assert frame.ctrl_ephemeride.ctrl_ticker.timer.IsRunning()
    wx.CallLater(1200, frame.Close)
    app.MainLoop()
    assert not _garde_reseau.TENTATIVES
    print("FERMETURE_OK_RESEAU_ZERO", flush=True)


class FermetureWindowsTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Régression native wx sous Windows")
    def test_accueil_avec_bandeau_se_ferme_sans_violation_native(self):
        result = subprocess.run(
            [sys.executable, str(pathlib.Path(__file__).resolve()), "--child"],
            cwd=str(REPO / "noethys"), capture_output=True, timeout=25,
        )
        sortie = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, sortie)
        self.assertIn("FERMETURE_OK_RESEAU_ZERO", sortie)


if __name__ == "__main__":
    if "--child" in sys.argv:
        fermer_accueil()
    else:
        unittest.main()
