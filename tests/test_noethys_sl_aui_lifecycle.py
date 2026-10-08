# -*- coding: utf-8 -*-
"""Non-régression du cycle de vie AUI spécifique à Noethys SL wx."""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import sys
import unittest
import warnings
from pathlib import Path

NOETHYS_DIR = Path(__file__).resolve().parents[1] / "noethys"
if str(NOETHYS_DIR) not in sys.path:
    sys.path.insert(0, str(NOETHYS_DIR))

import wx  # noqa: E402
import wx.lib.agw.aui as aui  # noqa: E402

_APP = wx.GetApp() or wx.App(False)

from Utils import UTILS_AUI_Apparence  # noqa: E402


class NoethysSLAuiManagerTests(unittest.TestCase):

    def setUp(self):
        self.frame = wx.Frame(None, size=(800, 600))
        self.mgr = UTILS_AUI_Apparence.NoethysSLAuiManager()
        self.mgr.SetManagedWindow(self.frame)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        try:
            self.mgr.UnInit()
        finally:
            self.frame.Destroy()

    def _add_pane(self, name, direction="left"):
        panel = wx.Panel(self.frame)
        info = aui.AuiPaneInfo().Name(name).Caption(name).MinimizeButton(True).MaximizeButton(True)
        if direction == "center":
            info.CenterPane()
        elif direction == "right":
            info.Right()
        else:
            info.Left()
        self.assertTrue(self.mgr.AddPane(panel, info))
        self.mgr.Update()
        return self.mgr.GetPane(name)

    def _automatic_toolbar_count(self, base_name):
        target = base_name + "_min"
        return sum(1 for pane in self.mgr.GetAllPanes() if pane.name == target)

    def _warnings_duplicate_min(self, captured):
        return [
            item for item in captured
            if "already exists in the manager" in str(item.message)
            and "_min" in str(item.message)
        ]

    def test_capture_lost_masque_tous_les_guides(self):
        self.mgr.CreateGuideWindows()
        aui.ShowDockingGuides(self.mgr._guides, True)
        self.assertTrue(any(guide.host.IsShown() for guide in self.mgr._guides))

        self.mgr._action = aui.actionDragFloatingPane
        self.mgr._action_window = object()
        self.mgr.OnCaptureLost(None)

        self.assertEqual(self.mgr._action, aui.actionNone)
        self.assertIsNone(self.mgr._action_window)
        self.assertTrue(all(not guide.host.IsShown() for guide in self.mgr._guides))

    def test_fin_normale_du_drag_masque_toujours_les_guides(self):
        pane = self._add_pane("drag_test")
        self.mgr.CreateGuideWindows()
        aui.ShowDockingGuides(self.mgr._guides, True)
        self.mgr._action_window = pane.window

        self.mgr.OnLeftUp_DragFloatingPane(wx.Point(5, 5))

        self.assertTrue(all(not guide.host.IsShown() for guide in self.mgr._guides))

    def test_loadperspective_ne_laisse_pas_de_toolbar_min_stale(self):
        ephemeride = self._add_pane("ephemeride")
        perspective_normale = self.mgr.SavePerspective()

        self.mgr.MinimizePane(ephemeride)
        self.assertTrue(self.mgr.GetPane("ephemeride_min").IsOk())

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            self.assertTrue(self.mgr.LoadPerspective(perspective_normale))
            ephemeride = self.mgr.GetPane("ephemeride")
            self.mgr.MinimizePane(ephemeride)

        self.assertFalse(self._warnings_duplicate_min(captured))
        self.assertEqual(self._automatic_toolbar_count("ephemeride"), 1)
        self.assertTrue(self.mgr.GetPane("ephemeride").IsMinimized())

    def test_restauration_agw_normale_puis_reminimisation_reste_propre(self):
        ephemeride = self._add_pane("ephemeride")
        self.mgr.MinimizePane(ephemeride)

        toolbar = self.mgr.GetPane("ephemeride_min")
        self.assertTrue(toolbar.IsOk())
        self.mgr.RestoreMinimizedPane(toolbar)

        self.assertFalse(self.mgr.GetPane("ephemeride").IsMinimized())
        self.assertFalse(self.mgr.GetPane("ephemeride_min").IsOk())

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            self.mgr.MinimizePane(self.mgr.GetPane("ephemeride"))

        self.assertFalse(self._warnings_duplicate_min(captured))
        self.assertEqual(self._automatic_toolbar_count("ephemeride"), 1)

    def test_maximizepane_preserve_invariant_minimized_toolbar(self):
        ephemeride = self._add_pane("ephemeride")
        messages = self._add_pane("messages", direction="right")

        self.mgr.MinimizePane(ephemeride)
        self.mgr.MaximizePane(messages)

        ephemeride = self.mgr.GetPane("ephemeride")
        self.assertTrue(ephemeride.IsMinimized())
        self.assertTrue(self.mgr.GetPane("ephemeride_min").IsOk())
        self.assertEqual(self._automatic_toolbar_count("ephemeride"), 1)

        self.mgr.RestorePane(messages)
        self.assertTrue(self.mgr.RestoreManagedMinimizedPane(ephemeride))

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            self.mgr.MinimizePane(self.mgr.GetPane("ephemeride"))

        self.assertFalse(self._warnings_duplicate_min(captured))
        self.assertTrue(self.mgr.GetPane("ephemeride").IsMinimized())
        self.assertEqual(self._automatic_toolbar_count("ephemeride"), 1)


if __name__ == "__main__":
    unittest.main()
