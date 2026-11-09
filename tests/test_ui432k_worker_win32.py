# -*- coding: utf-8 -*-
"""UI-432K : vraie boucle wx/Win32 pendant une lecture fictive unique de 8 s."""
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
    from Utils import UTILS_Facturation, UTILS_Travail_long

    app = wx.App(False)
    frame = wx.Frame(None, title="Fenetre test UI432K", size=(950, 710))
    frame.Show()
    frame.Maximize(True)
    app.SetTopWindow(frame)
    owner = wx.Dialog(frame, title="Facture fictive", size=(370, 230))
    owner.Show()

    user32 = ctypes.windll.user32
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    for nom in ("IsZoomed", "IsIconic", "IsHungAppWindow"):
        getattr(user32, nom).argtypes = (wintypes.HWND,)

    def etat():
        handle = frame.GetHandle()
        return [bool(user32.IsZoomed(handle)), bool(user32.IsIconic(handle)),
                bool(user32.IsHungAppWindow(handle))]

    mesures = {"battements": [], "etats_pendant": [], "proprietaires": [],
               "erreurs": [], "reseau": 0}
    timer = wx.Timer()

    def battement(evt):
        mesures["battements"].append(time.monotonic())
        mesures["etats_pendant"].append(etat())
        for w in wx.GetTopLevelWindows():
            if (isinstance(w, UTILS_Travail_long.DialogueLecture)
                    and w.IsShownOnScreen()):
                mesures["proprietaires"].append(
                    user32.GetWindow(w.GetHandle(), 4) == owner.GetHandle())

    timer.Bind(wx.EVT_TIMER, battement)

    def lancer():
        try:
            fac = UTILS_Facturation.Facturation.__new__(
                UTILS_Facturation.Facturation)
            fac._source_db = "BASE_FICTIVE_INACCESSIBLE"

            def calcul(*args, **kwargs):
                time.sleep(8.0)  # une seule operation, sans SQL reel
                return ("termine",)

            fac._GetDonneesImpression_core = calcul
            mesures["avant"] = etat()
            timer.Start(35)
            debut = time.monotonic()
            resultat = fac.GetDonneesImpression([42], {}, parent=owner)
            mesures["duree_ms"] = int((time.monotonic() - debut) * 1000)
            mesures["resultat_ok"] = resultat == ("termine",)
            mesures["apres"] = etat()
        except BaseException as err:
            mesures["erreurs"].append(type(err).__name__ + ": " + str(err))
        finally:
            timer.Stop()
            instants = mesures.pop("battements")
            mesures["nombre_battements"] = len(instants)
            mesures["retard_max_ms"] = int(max(
                (b - a for a, b in zip(instants, instants[1:])), default=0) * 1000)
            mesures["reseau"] = len(_garde_reseau.TENTATIVES)
            owner.Destroy()
            frame.Destroy()
            app.ExitMainLoop()

    wx.CallLater(180, lancer)
    app.MainLoop()
    print("UI432K_WORKER_WIN32 " + json.dumps(mesures), flush=True)


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true",
                     "Recette HWND reservee au runner Windows isole")
class WorkerWin32Tests(unittest.TestCase):
    def test_lecture_unique_longue_et_mainframe_reactive(self):
        p = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--scenario"],
            cwd=ROOT / "noethys", capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=35)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        ligne = next(x for x in p.stdout.splitlines()
                     if x.startswith("UI432K_WORKER_WIN32 "))
        resultat = json.loads(ligne.split(" ", 1)[1])
        self.assertEqual(resultat["erreurs"], [], resultat)
        self.assertEqual(resultat["reseau"], 0)
        self.assertTrue(resultat["resultat_ok"], resultat)
        self.assertGreaterEqual(resultat["duree_ms"], 7500, resultat)
        self.assertEqual(resultat["avant"], [True, False, False])
        self.assertEqual(resultat["apres"], [True, False, False])
        self.assertTrue(resultat["etats_pendant"], resultat)
        self.assertTrue(all(x == [True, False, False]
                            for x in resultat["etats_pendant"]), resultat)
        self.assertTrue(resultat["proprietaires"], resultat)
        self.assertTrue(all(resultat["proprietaires"]), resultat)
        self.assertGreater(resultat["nombre_battements"], 15, resultat)
        self.assertLess(resultat["retard_max_ms"], 500, resultat)


if __name__ == "__main__":
    if "--scenario" in sys.argv:
        scenario()
    else:
        unittest.main()
