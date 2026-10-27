# -*- coding: utf-8 -*-
"""UI-432: synchronisation manuelle simulee, sans base ni reseau reel."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def scenario(echec=False):
    sys.path.insert(0, str(ROOT / "tests"))
    import _garde_reseau
    import ctypes
    from ctypes import wintypes
    import socket
    import threading
    import time
    from unittest import mock
    import wx
    from Dlg import DLG_Portail_config
    from Utils import UTILS_Portail_synchro

    app = wx.App(False)
    frame = wx.Frame(None, title="UI432 - FICTIF", size=(950, 740))
    frame.Show()
    frame.Maximize(True)
    parent = wx.Dialog(frame, title="Connecthys - FICTIF")
    parent.Show()

    journal = []
    battements = []
    etats = []
    erreurs = []
    resultat = {}
    def ecrire(texte):
        assert wx.IsMainThread(), "Journal modifie hors wx"
        journal.append(texte)
    parent.EcritLog = ecrire

    timer = wx.Timer(frame)
    frame.Bind(wx.EVT_TIMER, lambda e: battements.append(time.monotonic()), timer)
    timer.Start(40)

    class SynchroFictive:
        appels = 0
        def __init__(self, dict_parametres=None, log=None):
            assert dict_parametres == {"factice": True}
            self.log = log
        def Synchro_totale(self, full_synchro=False):
            assert not wx.IsMainThread(), "Synchro bloquante sur wx"
            assert not full_synchro
            type(self).appels += 1
            for n in range(10):
                self.log.EcritLog("ETAPE_FICTIVE")
                self.log.SetGauge((n + 1) * 10)
                time.sleep(0.15)
            if echec:
                raise RuntimeError("PANNE_FICTIVE")
            return True

    sync = DLG_Portail_config.Synchro(parent, {"factice": True})

    def verifier_modal():
        dlg = getattr(sync, "dlgprogress", None)
        if dlg is not None:
            user32 = ctypes.windll.user32
            user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
            user32.GetWindow.restype = wintypes.HWND
            etats.append((dlg.IsModal(), not parent.IsEnabled(),
                          user32.GetWindow(dlg.GetHandle(), 4) == parent.GetHandle()))

    def terminer():
        timer.Stop()
        resultat.update(
            appels=SynchroFictive.appels,
            journal=len(journal),
            battements=len(battements),
            retard_ms=round(1000 * max((b - a for a, b in zip(battements, battements[1:])), default=0)),
            maximisee=frame.IsMaximized(),
            geometrie=tuple(frame.GetRect()) == avant,
            modal_ok=bool(etats) and all(all(x) for x in etats),
            aucune_connexion=not _garde_reseau.TENTATIVES,
            erreur=len(erreurs),
            terminee=sync._synchro_terminee,
            dialogue_detruit=sync.dlgprogress is None,
        )
        print("UI432_MANUAL " + json.dumps(resultat), flush=True)
        parent.Destroy()
        frame.Destroy()

    def demarrer():
        nonlocal avant
        avant = tuple(frame.GetRect())
        try:
            with mock.patch.object(socket.socket, "connect", side_effect=AssertionError("Reseau interdit")), \
                 mock.patch.object(UTILS_Portail_synchro, "Synchro", SynchroFictive):
                try:
                    reponse = sync.Start(full_synchro=False)
                except RuntimeError as err:
                    if not echec or str(err) != "PANNE_FICTIVE":
                        raise
                else:
                    assert not echec and reponse is True
        except BaseException as err:
            erreurs.append(str(err))
        wx.CallLater(150, terminer)

    avant = None
    wx.CallLater(300, demarrer)
    wx.CallLater(550, verifier_modal)
    app.MainLoop()
    assert not erreurs, erreurs
    assert resultat["appels"] == 1, resultat
    assert resultat["journal"] == 10, resultat
    assert resultat["modal_ok"], resultat
    assert resultat["retard_ms"] < 500, resultat
    assert resultat["maximisee"] and resultat["geometrie"], resultat
    assert resultat["terminee"] and resultat["dialogue_detruit"], resultat
    assert resultat["aucune_connexion"], resultat


class SynchroManuelleWindowsTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "wx Windows requis")
    def test_synchro_manuelle_reste_reactive_et_modale(self):
        self._scenario("--ok")

    @unittest.skipUnless(sys.platform == "win32", "wx Windows requis")
    def test_exception_worker_propagee_sans_rejouer(self):
        self._scenario("--erreur")

    def _scenario(self, choix):
        env = {**os.environ, "NOETHYS_SL_UI_DIAG": "0"}
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), choix],
                              cwd=ROOT / "noethys", env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        ligne = next((x for x in proc.stdout.splitlines() if x.startswith("UI432_MANUAL ")), None)
        self.assertIsNotNone(ligne, proc.stdout)
        mesures = json.loads(ligne.split(" ", 1)[1])
        print(ligne, flush=True)
        self.assertEqual(mesures["appels"], 1)
        self.assertLess(mesures["retard_ms"], 500)
        self.assertTrue(mesures["modal_ok"])


if __name__ == "__main__":
    if "--ok" in sys.argv or "--erreur" in sys.argv:
        scenario(echec="--erreur" in sys.argv)
    else:
        unittest.main()
