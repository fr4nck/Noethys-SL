# -*- coding: utf-8 -*-
"""UI-432K : un seul calcul de huit secondes, vraie boucle graphique Windows."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "tests", ROOT / "noethys"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def scenario():
    import _garde_reseau  # noqa: F401
    import ctypes
    from ctypes import wintypes
    import time
    import wx
    from Utils import UTILS_Etapes_ui

    app = wx.App(False)
    frame = wx.Frame(None, title="MainFrame Stats fictive", size=(940, 720))
    frame.Show()
    frame.Maximize(True)
    app.SetTopWindow(frame)
    stats = wx.Dialog(frame, title="Statistiques fictives", size=(550, 330))
    stats.Show()
    user32 = ctypes.windll.user32
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    for nom in ("IsZoomed", "IsIconic", "IsHungAppWindow"):
        getattr(user32, nom).argtypes = (wintypes.HWND,)

    def etat():
        hwnd = frame.GetHandle()
        return [bool(user32.IsZoomed(hwnd)), bool(user32.IsIconic(hwnd)),
                bool(user32.IsHungAppWindow(hwnd))]

    mesures = {"etats": [], "owners": [], "battements": [], "erreurs": []}
    minuterie = wx.Timer()

    def battement(evt):
        mesures["battements"].append(time.monotonic())
        mesures["etats"].append(etat())
        for dlg in wx.GetTopLevelWindows():
            if isinstance(dlg, UTILS_Etapes_ui.Attente) and dlg.IsShownOnScreen():
                mesures["owners"].append(
                    user32.GetWindow(dlg.GetHandle(), 4) == stats.GetHandle())

    minuterie.Bind(wx.EVT_TIMER, battement)

    def etapes():
        # Une seule operation lente : aucun autre objet ne peut rendre la main.
        resultat = yield UTILS_Etapes_ui.TravailFond(
            lambda: time.sleep(8.0) or "calcule")
        mesures["resultat_ok"] = resultat == "calcule"
        yield "statistiques.objet"

    def lancer():
        try:
            mesures["avant"] = etat()
            minuterie.Start(30)
            debut = time.monotonic()
            UTILS_Etapes_ui.Executer(stats, etapes(), titre="Stats",
                                     texte="Calcul fictif en cours")
            mesures["duree_ms"] = int((time.monotonic() - debut) * 1000)
            mesures["apres"] = etat()
        except BaseException as exc:
            mesures["erreurs"].append(type(exc).__name__ + ": " + str(exc))
        finally:
            minuterie.Stop()
            dates = mesures.pop("battements")
            mesures["nombre_battements"] = len(dates)
            mesures["retard_max_ms"] = int(max(
                (b - a for a, b in zip(dates, dates[1:])), default=0) * 1000)
            mesures["reseau"] = len(_garde_reseau.TENTATIVES)
            stats.Destroy()
            frame.Destroy()
            app.ExitMainLoop()

    wx.CallLater(180, lancer)
    app.MainLoop()
    print("UI432K_STATS_WIN32 " + json.dumps(mesures), flush=True)


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true",
                     "Banc GUI uniquement sur runner Windows isole")
class StatsUnitaireWin32Tests(unittest.TestCase):
    def test_un_objet_huit_secondes_et_gui_reactive(self):
        essai = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--scenario"],
            cwd=ROOT / "noethys", capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=35)
        self.assertEqual(essai.returncode, 0, essai.stdout + essai.stderr)
        line = next(x for x in essai.stdout.splitlines()
                    if x.startswith("UI432K_STATS_WIN32 "))
        resultat = json.loads(line.split(" ", 1)[1])
        self.assertEqual(resultat["erreurs"], [], resultat)
        self.assertEqual(resultat["reseau"], 0)
        self.assertTrue(resultat["resultat_ok"], resultat)
        self.assertGreaterEqual(resultat["duree_ms"], 7500, resultat)
        self.assertEqual(resultat["avant"], [True, False, False])
        self.assertEqual(resultat["apres"], [True, False, False])
        self.assertTrue(resultat["etats"], resultat)
        self.assertTrue(all(s == [True, False, False] for s in resultat["etats"]),
                        resultat)
        self.assertTrue(resultat["owners"], resultat)
        self.assertTrue(all(resultat["owners"]), resultat)
        self.assertGreater(resultat["nombre_battements"], 15, resultat)
        self.assertLess(resultat["retard_max_ms"], 500, resultat)


if __name__ == "__main__":
    if "--scenario" in sys.argv:
        scenario()
    else:
        unittest.main()
