# -*- coding: utf-8 -*-
"""STATS-RESTORE : wx.MemoryFSHandler reel sur Windows sans base ni profil."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODELES = ROOT / "noethys" / "Utils" / "UTILS_Stats_modeles.py"


def charger_graphe():
    arbre = ast.parse(MODELES.read_text(encoding="utf-8"))
    graphe = next(n for n in arbre.body if isinstance(n, ast.ClassDef)
                  and n.name == "Graphe")
    noms = ("MemoriseImage", "__del__", "GetObjetHTML")
    fonctions = [x for x in graphe.body if isinstance(x, ast.FunctionDef)
                 and x.name in noms]
    assert {x.name for x in fonctions} == set(noms)
    module = ast.Module(body=fonctions, type_ignores=[])
    ast.fix_missing_locations(module)
    espace = {}
    import wx
    espace["wx"] = wx
    exec(compile(module, str(MODELES), "exec"), espace)
    return espace


def scenario():
    # Aucun import de la base, de la configuration ou des donnees utilisateur.
    import gc
    import wx
    app = wx.App(False)
    wx.FileSystem.AddHandler(wx.MemoryFSHandler())
    fs = wx.FileSystem()
    fonctions = charger_graphe()

    class GrapheFictif:
        MemoriseImage = fonctions["MemoriseImage"]
        GetObjetHTML = fonctions["GetObjetHTML"]
        __del__ = fonctions["__del__"]

        def __init__(self, code):
            self.code = code
            self.bitmap = None
            self.stockImages = wx.MemoryFSHandler

        def ConvertMPLtoBMP(self, figure):
            return wx.Bitmap(16, 16)

    mesures = {"actualisations": 0, "fermetures": 0,
               "ouvertures_vfs": 0, "collisions": 0}
    graphes = []
    try:
        print("STATS_VFS_JALON ouverture", flush=True)
        for k in range(2):
            graphe = GrapheFictif("graphe_nombre_individus")
            graphe.MemoriseImage(None)
            graphes.append(graphe)
            assert "memory:" + graphe.nomImage in graphe.GetObjetHTML()
            fichier = fs.OpenFile("memory:" + graphe.nomImage)
            assert fichier is not None, "Image introuvable dans le VFS reel"
            fichier = None
            mesures["ouvertures_vfs"] += 1
        assert graphes[0].nomImage != graphes[1].nomImage
        nom_second = graphes[1].nomImage
        for index in range(100):
            graphes[0].MemoriseImage(None)
            mesures["actualisations"] += 1
            fichier = fs.OpenFile("memory:" + graphes[0].nomImage)
            assert fichier is not None, "Actualisation invalide"
            fichier = None
            mesures["ouvertures_vfs"] += 1
        assert fs.OpenFile("memory:" + nom_second) is not None, "Image d'un autre dialogue perdue"
        print("STATS_VFS_JALON apres_100_actualisations", flush=True)
        # Ne jamais appeler __del__() directement : Python le rappellerait
        # au relachement effectif de l'objet, avec risque de double finalisation
        # des objets natifs wx. Qualifier la destruction par perte de reference.
        premier, second = graphes
        nom_premier = premier.nomImage
        graphes.clear()
        del graphe  # ancienne variable de boucle maintenant "second"
        del premier
        gc.collect()
        assert fs.OpenFile("memory:" + nom_premier) is None, "Image non liberee"
        assert fs.OpenFile("memory:" + nom_second) is not None
        del second
        gc.collect()
        assert fs.OpenFile("memory:" + nom_second) is None
        print("STATS_VFS_JALON premier_doublet_libere", flush=True)
        for index in range(100):
            graphe = GrapheFictif("graphe_nombre_individus")
            graphe.MemoriseImage(None)
            nom = graphe.nomImage
            fichier = fs.OpenFile("memory:" + nom)
            assert fichier is not None, "Ressource absente a l'ouverture"
            fichier = None
            mesures["ouvertures_vfs"] += 1
            # CPython appelle le destructeur aussitot la derniere
            # reference relachee ; gc.collect() dans chaque iteration est
            # disproportionne et ne constitue pas une vraie fermeture.
            del graphe
            assert fs.OpenFile("memory:" + nom) is None, "Ressource persistante"
            mesures["fermetures"] += 1
            if (index + 1) % 20 == 0:
                print("STATS_VFS_JALON boucles_%d" % (index + 1), flush=True)
        gc.collect()
        mesures["pass"] = True
    finally:
        graphes.clear()
        gc.collect()
        print("STATS_VFS_JALON avant_fs_release", flush=True)
        fs = None
        gc.collect()
        print("STATS_VFS_JALON avant_app_destroy", flush=True)
        app.Destroy()
        print("STATS_VFS_JALON apres_app_destroy", flush=True)
    print("STATS_VFS_NATIVE " + json.dumps(mesures, sort_keys=True),
          flush=True)


@unittest.skipUnless(sys.platform == "win32" and (
    os.environ.get("GITHUB_ACTIONS") == "true"
    or os.environ.get("NOETHYS_STATS_NATIVE") == "1"),
    "Qualification VFS native uniquement sur Windows isole")
class MemoryFSWindowsTests(unittest.TestCase):
    def test_graphes_reels_recharges_et_liberes(self):
        try:
            execution = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--scenario"],
                cwd=ROOT, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=45)
        except subprocess.TimeoutExpired as exc:
            sortie = exc.stdout or b""
            erreur = exc.stderr or b""
            self.fail("VFS scenario sans fin : STDOUT=%r STDERR=%r" %
                      (sortie[-5000:], erreur[-5000:]))
        self.assertEqual(execution.returncode, 0,
                         execution.stdout + execution.stderr)
        ligne = next((l for l in execution.stdout.splitlines()
                      if l.startswith("STATS_VFS_NATIVE ")), None)
        self.assertIsNotNone(ligne, execution.stdout + execution.stderr)
        mesures = json.loads(ligne.split(" ", 1)[1])
        self.assertTrue(mesures["pass"])
        self.assertEqual(mesures["actualisations"], 100)
        self.assertEqual(mesures["fermetures"], 100)
        self.assertEqual(mesures["ouvertures_vfs"], 202)


if __name__ == "__main__":
    if "--scenario" in sys.argv:
        scenario()
    else:
        unittest.main()
