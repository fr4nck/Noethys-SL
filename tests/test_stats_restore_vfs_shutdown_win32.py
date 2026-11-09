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



def scenario_deux(mode):
    """Comparer instances de gestionnaire et classe statique avec deux graphes."""
    import gc
    import wx
    from tests.test_stats_restore_vfs_win32 import charger_graphe
    methods = charger_graphe()
    app = wx.App(False)
    wx.FileSystem.AddHandler(wx.MemoryFSHandler())

    class G:
        MemoriseImage = methods["MemoriseImage"]
        __del__ = methods["__del__"]

        def __init__(self, code):
            self.bitmap = None
            self.code = code
            self.stockImages = (
                wx.MemoryFSHandler if mode == "deux_classe"
                else wx.MemoryFSHandler())

        def ConvertMPLtoBMP(self, _figure):
            return wx.Bitmap(16, 16)

    def existe(nom):
        lecteur = wx.FileSystem()
        present = lecteur.OpenFile("memory:" + nom) is not None
        lecteur = None
        return present

    premier = G("meme_code")
    second = G("meme_code")
    premier.MemoriseImage(None)
    second.MemoriseImage(None)
    cle1, cle2 = premier.nomImage, second.nomImage
    assert cle1 != cle2
    assert existe(cle1) and existe(cle2)
    print("STATS_VFS_DUO deux_images", mode, flush=True)
    premier = None
    gc.collect()
    print("STATS_VFS_DUO premier_libere", mode, flush=True)
    assert not existe(cle1), "Premier graphique non libere"
    assert existe(cle2), "Second graphique supprime par la liberation du premier"
    second = None
    gc.collect()
    assert not existe(cle2), "Second graphique non libere"
    print("STATS_VFS_DUO deux_libres", mode, flush=True)
    app.Destroy()
    app = None
    gc.collect()
    print("STATS_VFS_DUO sortie_normale", mode, flush=True)

def scenario(mode):
    import wx
    if mode in ("deux_instances", "deux_classe"):
        return scenario_deux(mode)
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
    if mode in ("graphe", "graphe_fermeture", "graphe_gc"):
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
        if mode == "graphe_gc":
            graphe = None
            gc.collect()
            signaler("graphe-gc-naturel")
        if mode == "graphe_fermeture":
            graphe.__del__()
            graphe = None
            gc.collect()
            signaler("graphe-libere")
    if mode in ("handler", "bitmap", "graphe_fermeture", "graphe_gc"):
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
        self.assertTrue('"sortie-normale"' in child.stdout or "STATS_VFS_DUO sortie_normale" in child.stdout,
                        child.stdout)

    def test_fenetre_basique(self):
        self.verifier_mode("app")

    def test_deux_graphes_avec_instances(self):
        self.verifier_mode("deux_instances")

    def test_deux_graphes_avec_classe_statique(self):
        self.verifier_mode("deux_classe")

    def test_handler_vfs_sans_images(self):
        self.verifier_mode("handler")

    def test_bitmap_vfs_puis_liberation(self):
        self.verifier_mode("bitmap")

    def test_graphe_vfs_avec_liberation(self):
        self.verifier_mode("graphe_fermeture")

    def test_graphe_libere_naturellement(self):
        self.verifier_mode("graphe_gc")

    def test_graphe_sans_liberation_expresse(self):
        self.verifier_mode("graphe")


if __name__ == "__main__":
    if "--child" in sys.argv:
        scenario(sys.argv[-1])
    else:
        unittest.main()
