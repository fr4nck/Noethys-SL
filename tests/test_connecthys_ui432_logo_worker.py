# -*- coding: utf-8 -*-
"""#432 : le thread de synchro Connecthys ne cree plus de wx.Bitmap (GDI).

Le logo envoye a Connecthys doit rester identique au pixel pres (couleurs et
transparence) a l'ancien chemin wx.Image -> wx.Bitmap -> PNG. Logos fictifs,
aucune base, aucun reseau, aucune fenetre.
"""
import ast
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))

# La wx.App de la comparaison ne vit que dans un sous-processus : la suite
# CI partage un seul processus, qui ne doit pas garder d'application wx.
ENFANT = os.environ.get("UI432_LOGO_ENFANT") == "1"
wx = UTILS_Organisateur = None
if ENFANT:
    import wx
    from Utils import UTILS_Organisateur


def logo_png(alpha):
    image = wx.Image(300, 150)
    for x in range(300):
        for y in range(150):
            image.SetRGB(x, y, (x * 7) % 256, (y * 13) % 256, (x + y) % 256)
    if alpha:
        image.InitAlpha()
        for x in range(300):
            for y in range(150):
                image.SetAlpha(x, y, (x * 3 + y) % 256)
    with tempfile.TemporaryDirectory() as dossier:
        chemin = os.path.join(dossier, "logo.png")
        assert image.SaveFile(chemin, wx.BITMAP_TYPE_PNG)
        with open(chemin, "rb") as f:
            return f.read()


class FausseDB:
    ligne = None

    def ExecuterReq(self, req):
        return 1

    def ResultatReq(self):
        return [FausseDB.ligne]

    def Close(self):
        pass


@unittest.skipUnless(ENFANT, "execute dans le sous-processus de SousProcessusTests")
class LogoWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App(False)  # aucune fenetre

    def pixels(self, chemin):
        image = wx.Image(chemin, wx.BITMAP_TYPE_PNG)
        return (tuple(image.GetSize()), bytes(image.GetDataBuffer()),
                bytes(image.GetAlphaBuffer()) if image.HasAlpha() else None)

    def comparer(self, alpha):
        source = logo_png(alpha)
        FausseDB.ligne = (u"Organisateur fictif", u"", u"", u"", u"", u"", u"", u"",
                          u"", u"", u"", source, u"2026-10-27")
        with mock.patch.object(UTILS_Organisateur.GestionDB, "DB", FausseDB),                 tempfile.TemporaryDirectory() as dossier:
            ancien = UTILS_Organisateur.GetDonnees(tailleLogo=(200, 200))["logo"]
            nouveau = UTILS_Organisateur.GetDonnees(tailleLogo=(200, 200), logoBitmap=False)["logo"]
            self.assertIsInstance(ancien, wx.Bitmap)
            self.assertIsInstance(nouveau, wx.Image)
            a, b, r = (os.path.join(dossier, n) for n in ("a.png", "b.png", "r.png"))
            ancien.SaveFile(a, type=wx.BITMAP_TYPE_PNG)
            nouveau.SaveFile(b, type=wx.BITMAP_TYPE_PNG)
            # Reference : l'image recadree, sans passage par un bitmap GDI.
            reference = UTILS_Organisateur.RecadreImg(
                wx.Image(io.BytesIO(source), wx.BITMAP_TYPE_ANY), (200, 200))
            reference.SaveFile(r, wx.BITMAP_TYPE_PNG)
            taille_a, rgb_a, alpha_a = self.pixels(a)
            taille_b, rgb_b, alpha_b = self.pixels(b)
            self.assertTrue(self.pixels(b) == self.pixels(r), "logo envoye different de la source")
            self.assertEqual(taille_a, taille_b)
            self.assertTrue(alpha_a == alpha_b, "transparence modifiee")
            ecarts = 0
            for k in range(len(rgb_a)):
                if rgb_a[k] != rgb_b[k]:
                    opacite = 255 if alpha_a is None else alpha_a[k // 3]
                    # L'ancien aller-retour GDI premultiplie l'alpha : perte
                    # d'arrondi limitee aux pixels semi-transparents.
                    self.assertLess(opacite, 255, "pixel opaque modifie")
                    self.assertLessEqual(abs(rgb_a[k] * opacite - rgb_b[k] * opacite) / 255.0, 1.0)
                    ecarts += 1
            if alpha_a is None:
                self.assertEqual(ecarts, 0)

    def test_logo_opaque_identique(self):
        self.comparer(alpha=False)

    def test_logo_transparent_fidele_a_la_source(self):
        self.comparer(alpha=True)


class SousProcessusTests(unittest.TestCase):
    def test_comparaisons_de_logo_dans_un_processus_isole(self):
        try:
            import wx as _wx  # noqa: F401
        except Exception:
            self.skipTest("wx indisponible")
        p = subprocess.run([sys.executable, "-m", "unittest", "-v",
                            "tests.test_connecthys_ui432_logo_worker.LogoWorkerTests"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120,
                           env={**os.environ, "UI432_LOGO_ENFANT": "1"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Ran 2 tests", p.stderr)
        self.assertNotIn("skipped", p.stderr)


class ContratSourceTests(unittest.TestCase):
    def test_synchro_demande_un_logo_sans_bitmap(self):
        source = (ROOT / "noethys" / "Utils" / "UTILS_Portail_synchro.py").read_text(encoding="utf-8")
        appels = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Call)
                  and getattr(n.func, "attr", "") == "GetDonnees"
                  and getattr(n.func.value, "id", "") == "UTILS_Organisateur"]
        self.assertEqual(len(appels), 1)
        options = {k.arg: getattr(k.value, "value", None) for k in appels[0].keywords}
        self.assertIs(options.get("logoBitmap"), False)
        self.assertNotIn("ConvertToBitmap", source)
        self.assertNotIn("wx.Bitmap(", source)


if __name__ == "__main__":
    unittest.main()
