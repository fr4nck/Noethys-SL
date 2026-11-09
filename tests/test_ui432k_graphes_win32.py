# -*- coding: utf-8 -*-
"""UI-432K : vrai graphe Agg/PNG et VFS wx, une seule requete lente de 8 s."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
for chemin in (ROOT / "noethys", ROOT / "tests"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))


def scenario():
    import _garde_reseau
    import ctypes
    from ctypes import wintypes
    import time
    from unittest import mock
    import wx
    import GestionDB
    from Utils import UTILS_Etapes_ui, UTILS_Stats_modeles
    from Utils import UTILS_Stats_individus

    app = wx.App(False)
    main = wx.Frame(None, title="Noethys - Stats fictives", size=(970, 700))
    main.Show()
    main.Maximize(True)
    app.SetTopWindow(main)
    stats = wx.Dialog(main, title="Stats fictives", size=(540, 360))
    stats.Show()
    obj = UTILS_Stats_individus.Graphe_nombre_individus()
    base = UTILS_Stats_modeles.HTML([{
        "code": "individus", "pages": [{
            "code": "nombre", "objets": [obj],
        }],
    }])
    base.SetParametres({"mode": "presents", "listeActivites": [1],
                        "periode": {"date_debut": "2026-01-01",
                                    "date_fin": "2026-12-31"}})

    class BaseFictive:
        nomFichier = "SQL_FICTIVE"
        def Close(self):
            pass

    user32 = ctypes.windll.user32
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    for name in ("IsZoomed", "IsIconic", "IsHungAppWindow"):
        getattr(user32, name).argtypes = (wintypes.HWND,)

    def state():
        hwnd = main.GetHandle()
        return [bool(user32.IsZoomed(hwnd)), bool(user32.IsIconic(hwnd)),
                bool(user32.IsHungAppWindow(hwnd))]

    measures = {"pulses": [], "owners": [], "states": [], "errors": []}
    timer = wx.Timer()

    def pulse(event):
        measures["pulses"].append(time.monotonic())
        measures["states"].append(state())
        for wnd in wx.GetTopLevelWindows():
            if isinstance(wnd, UTILS_Etapes_ui.Attente) and wnd.IsShownOnScreen():
                measures["owners"].append(
                    user32.GetWindow(wnd.GetHandle(), 4) == stats.GetHandle())

    timer.Bind(wx.EVT_TIMER, pulse)

    def slow_data(*args, **kwargs):
        time.sleep(8.0)
        return {"labels": ["2025", "2026"], "valeurs": [7, 9],
                "indexPeriodeReference": 1}

    def run():
        try:
            measures["before"] = state()
            timer.Start(30)
            t0 = time.monotonic()
            with mock.patch.object(GestionDB, "DB", side_effect=lambda **k: BaseFictive()), \
                 mock.patch.object(UTILS_Stats_individus, "GetComparatifNombre",
                                   side_effect=slow_data):
                UTILS_Etapes_ui.Executer(
                    stats, base.MAJ_etapes(page="nombre", parent=stats),
                    titre="Stats fictives", texte="Calcul du graphe...")
            measures["duration_ms"] = int((time.monotonic() - t0) * 1000)
            measures["after"] = state()
            measures["image_ok"] = (obj.bitmap is not None
                and wx.FileSystem().OpenFile("memory:" + obj.nomImage) is not None)
            measures["html_ok"] = "memory:" in obj.GetObjetHTML()
        except BaseException as err:
            measures["errors"].append(type(err).__name__ + ": " + str(err))
        finally:
            timer.Stop()
            pulses = measures.pop("pulses")
            measures["pulse_count"] = len(pulses)
            measures["max_lag_ms"] = int(max(
                (t-b for b,t in zip(pulses,pulses[1:])), default=0)*1000)
            measures["network_attempts"] = len(_garde_reseau.TENTATIVES)
            stats.Destroy()
            main.Destroy()
            app.ExitMainLoop()

    wx.CallLater(160, run)
    app.MainLoop()
    print("UI432K_GRAPHE_WIN32 "+json.dumps(measures), flush=True)


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true",
                     "GUI native Windows uniquement avec environnement fictif")
class GraphesWin32Tests(unittest.TestCase):
    def test_une_requete_graphe_de_huit_secondes(self):
        p = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--scenario"],
            cwd=ROOT/"noethys", capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=40)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        line = next(z for z in p.stdout.splitlines()
                    if z.startswith("UI432K_GRAPHE_WIN32 "))
        data = json.loads(line.split(" ",1)[1])
        self.assertEqual(data["errors"], [], data)
        self.assertEqual(data["network_attempts"], 0)
        self.assertGreaterEqual(data["duration_ms"], 7500, data)
        self.assertEqual(data["before"], [True,False,False])
        self.assertEqual(data["after"], [True,False,False])
        self.assertTrue(data["image_ok"],data)
        self.assertTrue(data["html_ok"],data)
        self.assertTrue(data["states"], data)
        self.assertTrue(all(z==[True,False,False] for z in data["states"]),data)
        self.assertTrue(data["owners"],data)
        self.assertTrue(all(data["owners"]),data)
        self.assertGreater(data["pulse_count"], 15,data)
        self.assertLess(data["max_lag_ms"], 500,data)


if __name__ == "__main__":
    if "--scenario" in sys.argv:
        scenario()
    else:
        unittest.main()
