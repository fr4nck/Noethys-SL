from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import sys
import unittest
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx
import wx.lib.agw.aui as aui

from Utils import UTILS_AUI_Apparence


class NoethysSLAuiRobustesseTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp()
        if cls.app is None:
            cls.app = wx.App(False)

    def setUp(self):
        self.frame = wx.Frame(None)
        self.addCleanup(self.frame.Destroy)

        self.mgr = UTILS_AUI_Apparence.NoethysSLAuiManager()
        self.mgr.SetManagedWindow(self.frame)
        self.addCleanup(self.mgr.UnInit)

    def test_capture_lost_ignore_un_guide_deja_detruit(self):
        self.mgr._action = aui.actionDragFloatingPane
        self.mgr.CreateGuideWindows()
        aui.ShowDockingGuides(self.mgr._guides, True)

        for guide in self.mgr._guides:
            guide.host.Destroy()

        wx.SafeYield()

        try:
            self.mgr.OnCaptureLost(wx.MouseCaptureLostEvent())
        finally:
            # Les hosts sont deja detruits : ne pas demander a AGW
            # de les detruire une seconde fois pendant le cleanup.
            self.mgr._guides = []

    def test_toolbar_minimisee_recoit_art_provider_noethys(self):
        noms = ("ephemeride", "messages", "effectifs")

        for nom in noms:
            self.mgr.AddPane(
                wx.Panel(self.frame),
                aui.AuiPaneInfo().Name(nom).Caption(nom).Left(),
            )

        self.mgr.Update()

        for nom in noms:
            with self.subTest(pane=nom):
                self.mgr.MinimizePane(self.mgr.GetPane(nom))

                pane_min = self.mgr.GetPane(nom + "_min")
                self.assertTrue(pane_min.IsOk())
                self.assertIsInstance(pane_min.window, aui.AuiToolBar)
                self.assertIsInstance(
                    pane_min.window.GetArtProvider(),
                    UTILS_AUI_Apparence.NoethysSLToolBarArt,
                )


if __name__ == "__main__":
    unittest.main()
