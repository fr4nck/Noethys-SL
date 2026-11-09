# -*- coding: utf-8 -*-
"""Q3 : isoler les fermetures wx natives; aucun fichier ni reseau utilisateur."""
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Un sous-processus lance sur un fichier ne conserve pas toujours le paquet tests.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def scenario(mode):
    import wx
    mesures = {"mode": mode, "etapes": []}

    def signaler(etape):
        mesures["etapes"].append(etape)
        print("STATS_WX_SHUTDOWN " + json.dumps(mesures), flush=True)

    app = wx.App(False)
    signaler("app-creee")
    fs = None
    graphe = None
    bitmap = None
    if mode != "app":
        wx.FileSystem.AddHandler(wx.MemoryFSHandler())
        fs = wx.FileSystem()
        signaler("handler-cree")
    if mode == "bitmap":
        bitmap = wx.Bitmap(16, 16)
        wx.MemoryFSHandler.AddFile("test-q3-natif", bitmap, wx.BITMAP_TYPE_PNG)
        signaler("image-ajoutee")
        ouvert = fs.OpenFile("memory:test-q3-natif")
        assert ouvert is not None, "image VFS inaccessible"
        ouvert = None
        wx.MemoryFSHandler.RemoveFile("test-q3-natif")
        bitmap = None
        signaler("image-liberee")
    if mode in ("graphe", "graphe_fermeture"):
        from tests.test_stats_restore_vfs_win32 import charger_graphe
        methodes = charger_graphe()

        class G:
            MemoriseImage = methodes["MemoriseImage"]
            __del__ = methodes["__del__"]

            def __init__(self):
                self.bitmap = None
                self.code = "q3-shutdown"
                self.stockImages = wx.MemoryFSHandler()

            def ConvertMPLtoBMP(self, figure):
                return wx.Bitmap(16, 16)

        graphe = G()
        for index in range(5):
            graphe.MemoriseImage(None)
        signaler("5-actualisations")
        if mode == "graphe_fermeture":
            graphe.__del__()
            graphe = None
            gc.collect()
            signaler("graphe-libere")
    if mode in ("handler", "bitmap", "graphe_fermeture"):
        fs = None
        gc.collect()
        signaler("filesystem-libere")
    app.Destroy()
    signaler("app-detruite")
    if mode != "graphe":
        app = None
        gc.collect()
        signaler("app-reference-liberee")
    signaler("sortie-normale")


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true",
                     "Sous-processus wx natif reserve au runner Windows isole")
class FermetureNativeTests(unittest.TestCase):
    def verifier_mode(self, mode):
        child = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child", mode],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=40)
        self.assertEqual(child.returncode, 0,
                         "MODE %s RC %s\nSTDOUT:\n%s\nSTDERR:\n%s" % (
                             mode, child.returncode, child.stdout, child.stderr))
        self.assertIn('"sortie-normale"', child.stdout)

    def test_fenetre_basique(self):
        self.verifier_mode("app")

    def test_handler_vfs_sans_images(self):
        self.verifier_mode("handler")

    def test_bitmap_vfs_puis_liberation(self):
        self.verifier_mode("bitmap")

    def test_graphe_vfs_avec_liberation(self):
        self.verifier_mode("graphe_fermeture")

    def test_graphe_sans_liberation_expresse(self):
        self.verifier_mode("graphe")


if __name__ == "__main__":
    if "--child" in sys.argv:
        scenario(sys.argv[-1])
    else:
        unittest.main()
