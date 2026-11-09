# -*- coding: utf-8 -*-
"""UI-432J - recette HWND d'une attente Stats cooperative avec chiffres fictifs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "tests", ROOT / "noethys"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def scenario():
    import _garde_reseau  # noqa: F401 : aucun reseau/base utilisateur
    import ctypes
    from ctypes import wintypes
    import time
    import wx
    from Utils import UTILS_Etapes_ui as etapes

    app = wx.App(False)
    principale = wx.Frame(None, title="Noethys fictif", size=(930, 700))
    principale.Show()
    principale.Maximize(True)
    app.SetTopWindow(principale)
    stats = wx.Dialog(principale, title="Statistiques fictives",
                      style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
    stats.SetSize((550, 350))
    user32 = ctypes.windll.user32
    user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetWindow.restype = wintypes.HWND
    user32.IsZoomed.argtypes = (wintypes.HWND,)
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.IsHungAppWindow.argtypes = (wintypes.HWND,)

    battements = []
    proprietaires = []
    erreurs = []
    mesures = {}
    minuterie = wx.Timer()

    def etat():
        hwnd = principale.GetHandle()
        return (bool(user32.IsZoomed(hwnd)), bool(user32.IsIconic(hwnd)),
                bool(user32.IsHungAppWindow(hwnd)))

    def battement(evt):
        battements.append(time.monotonic())
        candidats = [fenetre for fenetre in wx.GetTopLevelWindows()
                     if isinstance(fenetre, etapes.Attente) and fenetre.IsShownOnScreen()]
        for fenetre in candidats:
            proprietaires.append(
                user32.GetWindow(fenetre.GetHandle(), 4) == stats.GetHandle())

    minuterie.Bind(wx.EVT_TIMER, battement)

    def generer():
        for numero in range(5):
            # Calcul synthétique lent : aucune requete ou document reel.
            time.sleep(0.065)
            yield "statistiques.objet"

    def lancer():
        try:
            mesures["avant"] = etat()
            minuterie.Start(25)
            etapes.Executer(stats, generer(), titre="Statistiques",
                            texte="Actualisation de donnees fictives")
        except BaseException as erreur:
            erreurs.append(type(erreur).__name__ + ": " + str(erreur))
        finally:
            minuterie.Stop()
            mesures["apres"] = etat()
            mesures["nombre_battements"] = len(battements)
            mesures["retard_max_ms"] = int(max(
                (b - a for a, b in zip(battements, battements[1:])), default=0) * 1000)
            mesures["proprietaires"] = proprietaires
            stats.EndModal(wx.ID_OK)

    wx.CallLater(250, lancer)
    stats.ShowModal()
    stats.Destroy()
    principale.Destroy()
    app.Destroy()
    mesures["erreurs"] = erreurs
    mesures["reseau"] = len(_garde_reseau.TENTATIVES)
    print("UI432_STATS_WIN32 " + json.dumps(mesures), flush=True)


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true",
                     "Recette de fenetres uniquement sur runner Windows isole")
class StatistiquesWin32Tests(unittest.TestCase):
    def test_owner_et_fenetre_maximisee_sous_calcul_lent(self):
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--scenario"],
                           cwd=ROOT / "noethys", capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        ligne = next(texte for texte in p.stdout.splitlines()
                     if texte.startswith("UI432_STATS_WIN32 "))
        resultat = json.loads(ligne.split(" ", 1)[1])
        self.assertEqual(resultat["erreurs"], [])
        self.assertEqual(resultat["reseau"], 0)
        self.assertEqual(resultat["avant"], [True, False, False])
        self.assertEqual(resultat["apres"], [True, False, False])
        self.assertTrue(resultat["proprietaires"], resultat)
        self.assertTrue(all(resultat["proprietaires"]), resultat)
        self.assertGreater(resultat["nombre_battements"], 7, resultat)
        self.assertLess(resultat["retard_max_ms"], 500, resultat)


if __name__ == "__main__":
    if "--scenario" in sys.argv:
        scenario()
    else:
        unittest.main()
