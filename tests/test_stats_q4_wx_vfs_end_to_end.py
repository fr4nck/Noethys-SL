# -*- coding: utf-8 -*-
"""Q4-C2 - Vrai Matplotlib -> vrai wx.Bitmap -> MemoryFS pour 15 graphes.

Seulement sur Windows GitHub Actions, en sous-processus pour detecter
un crash natif a la destruction. SQLite fictif et photos/PNG en memoire.
Ne cree ni installation ni HTML de l'application, n'ouvre aucune base PMSL.
"""
import ast
import gc
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys" / "Utils" / "UTILS_Stats_modeles.py"


def methodes_graphe_native(wx, six, Image):
    """Les 4 methodes du vrai modele Graphes, sans importer GestionDB."""
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    cls = next(c for c in arbre.body
               if isinstance(c, ast.ClassDef) and c.name == "Graphe")
    noms = (
        "MemoriseImage", "ConvertPNGtoBMP", "GetObjetHTML", "__del__",
    )
    defs = [x for x in cls.body
            if isinstance(x, ast.FunctionDef) and x.name in noms]
    if len(defs) != len(noms):
        raise AssertionError("Contrat Graphe/MemoryFS change")
    mod = ast.Module(body=defs, type_ignores=[])
    ast.fix_missing_locations(mod)
    env = {"wx": wx, "six": six, "Image": Image}
    exec(compile(mod, str(SOURCE), "exec"), env)
    return {nom: env[nom] for nom in noms}


def scenario():
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    import numpy as np
    import six
    import wx
    from PIL import Image
    from tests.test_stats_q4_matplotlib_agg import CASES, preparer

    gc.collect()
    app = wx.App(False)
    wx.FileSystem.AddHandler(wx.MemoryFSHandler())
    fs = wx.FileSystem()
    fonctions = methodes_graphe_native(wx, six, Image)
    graphes = []
    noms_images = []
    compteurs = {"graphes": 0, "vfs_ouverts": 0, "vfs_liberes": 0}
    print("Q4_C2_JALON demarrage", flush=True)

    try:
        assert wx.IsMainThread(), "wx natif n'est pas sur le thread principal"
        for groupe, nom_classe in CASES:
            namespace, db, parametres = preparer(groupe, None)
            try:
                namespace["matplotlib"] = matplotlib
                namespace["arange"] = np.arange
                modeles = namespace["MODELES"]
                if hasattr(modeles, "ConvertitCouleur2"):
                    modeles.ConvertitCouleur2 = lambda rgb: tuple(
                        n / 255.0 for n in rgb)

                GrapheNative = type(
                    "Q4Native_" + nom_classe,
                    (namespace[nom_classe],),
                    fonctions)
                obj = GrapheNative()
                obj.bitmap = None
                obj.stockImages = wx.MemoryFSHandler
                fig = plt.figure(figsize=(6, 4), dpi=100)
                try:
                    assert obj.MAJ(
                        figure=fig, DB=db, dictParametres=parametres) is fig
                    png = io.BytesIO()
                    fig.savefig(png, format="png")
                    assert png.getvalue().startswith(b"\x89PNG\r\n\x1a\n")
                    obj.MemoriseImage(png_data=png.getvalue())
                finally:
                    plt.close(fig)
                    fig = None

                assert obj.bitmap is not None and obj.bitmap.IsOk(), nom_classe
                nom = obj.nomImage
                assert nom not in noms_images, "Collision de nom MemoryFS"
                assert "memory:" + nom in obj.GetObjetHTML(), nom_classe
                item = fs.OpenFile("memory:" + nom)
                assert item is not None, "VFS illisible : " + nom_classe
                item = None
                graphes.append(obj)
                noms_images.append(nom)
                compteurs["graphes"] += 1
                compteurs["vfs_ouverts"] += 1
                obj = None
            finally:
                db.Close()

        assert len(graphes) == 15 and len(noms_images) == 15
        print("Q4_C2_JALON 15_graphes_enregistres", flush=True)

        # Destruction naturelle uniquement : ne JAMAIS appeler __del__
        # a la main (ancien crash natif Windows 0xC000041D).
        del obj
        graphes.clear()
        gc.collect()
        for nom in noms_images:
            introuvable = fs.OpenFile("memory:" + nom)
            assert introuvable is None, "Fuite MemoryFS : " + nom
            compteurs["vfs_liberes"] += 1
        print("Q4_C2_JALON 15_graphes_liberes", flush=True)
    finally:
        graphes.clear()
        gc.collect()
        fs = None
        gc.collect()
        print("Q4_C2_JALON avant_app_destroy", flush=True)
        app.Destroy()
        print("Q4_C2_JALON apres_app_destroy", flush=True)

    compteurs["pass"] = True
    print("Q4_C2_NATIVE " + json.dumps(compteurs, sort_keys=True),
          flush=True)


@unittest.skipUnless(
    sys.platform == "win32" and (
        os.environ.get("GITHUB_ACTIONS") == "true"
        or os.environ.get("NOETHYS_STATS_Q4_WX") == "1"),
    "wx/MemoryFS Q4-C2 : Windows CI isole uniquement")
class Q4WxMemoryFSNativeTest(unittest.TestCase):
    def test_15_graphes_et_sortie_normale_sous_processus(self):
        try:
            r = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--scenario"],
                cwd=ROOT, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=100)
        except subprocess.TimeoutExpired as e:
            self.fail("Sous-processus wx bloque : stdout=%r stderr=%r" %
                      (e.stdout, e.stderr))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ligne = next((line for line in r.stdout.splitlines()
                      if line.startswith("Q4_C2_NATIVE ")), None)
        self.assertIsNotNone(ligne, r.stdout + r.stderr)
        r_json = json.loads(ligne.split(" ", 1)[1])
        self.assertTrue(r_json["pass"])
        self.assertEqual(r_json["graphes"], 15)
        self.assertEqual(r_json["vfs_ouverts"], 15)
        self.assertEqual(r_json["vfs_liberes"], 15)


if __name__ == "__main__":
    if "--scenario" in sys.argv:
        scenario()
    else:
        unittest.main()
