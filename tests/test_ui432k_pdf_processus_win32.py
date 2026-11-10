# -*- coding: utf-8 -*-
"""UI-432K : vrai rendu Noedoc spawn dans un worker pendant wx modal Windows.

Sous-processus de test isole, base SQLite fictive, aucun envoi. Verifie
simultanement le PDF final, l'owner modal et la reactivite de la MainFrame.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "noethys", ROOT / "tests", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def scenario():
    import ctypes
    from ctypes import wintypes
    import time
    import wx
    import _garde_reseau
    from tests.test_vanilla_facture_prestation_sans_activite import (
        _creer_base_facture_avec_prestation_sans_activite, _dict_options_minimal)
    from _fixtures_noethys_db import RedirectionGestionDB
    from Utils import (UTILS_Facturation, UTILS_Impression_facture,
                       UTILS_PDF_processus, UTILS_PDF_securise, UTILS_Etapes_ui)

    os.environ["NOETHYS_SL_PDF_TEST_ISOLE"] = "1"
    app = wx.App(False)
    base, modele = _creer_base_facture_avec_prestation_sans_activite()
    dossier = tempfile.TemporaryDirectory(prefix="ui432k-pdf-window-")
    try:
        options = _dict_options_minimal(modele)
        with RedirectionGestionDB(base.chemin):
            facture = UTILS_Facturation.Facturation()
            donnees = facture.GetDonneesImpression(
                listeFactures=[1], dictOptions=options, parent=None)
        if donnees is False:
            raise AssertionError("Donnees fictives indisponibles")
        comptes = donnees[0]
        precedent = str(Path(dossier.name) / "ancien.pdf")
        resultat = str(Path(dossier.name) / "isole.pdf")
        with RedirectionGestionDB(base.chemin):
            UTILS_Impression_facture.Impression(
                comptes, options, IDmodele=modele,
                ouverture=False, nomFichier=precedent)
        comptes, options = UTILS_PDF_processus.Preparer(comptes, options)
        main = wx.Frame(None, title="Noethys PDF fictif", size=(980, 750))
        main.Show()
        main.Maximize(True)
        app.SetTopWindow(main)
        dialogue = wx.Dialog(main, title="Facturation fictive", size=(530, 320))
        dialogue.Show()

        native = ctypes.windll.user32
        native.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
        native.GetWindow.restype = wintypes.HWND
        for nom in ("IsZoomed", "IsIconic", "IsHungAppWindow"):
            getattr(native, nom).argtypes = (wintypes.HWND,)

        def etat():
            hwnd = main.GetHandle()
            return [bool(native.IsZoomed(hwnd)), bool(native.IsIconic(hwnd)),
                    bool(native.IsHungAppWindow(hwnd))]

        mesure = {"erreurs": [], "pulses": [], "etats": [], "owners": []}
        timer = wx.Timer()

        def tick(event):
            mesure["pulses"].append(time.monotonic())
            mesure["etats"].append(etat())
            for wnd in wx.GetTopLevelWindows():
                if isinstance(wnd, UTILS_Etapes_ui.Attente) and wnd.IsShownOnScreen():
                    mesure["owners"].append(
                        native.GetWindow(wnd.GetHandle(), 4) == dialogue.GetHandle())

        timer.Bind(wx.EVT_TIMER, tick)

        def etapes():
            def calcul():
                return UTILS_PDF_securise.Generer(
                    resultat, lambda provisoire: UTILS_PDF_processus.Generer(
                        comptes, options, modele, provisoire, base.chemin,
                        delai=60, donnees_pretes=True))
            document = yield UTILS_Etapes_ui.TravailFond(
                calcul, etape="factures.generation_pdf")
            mesure["rendu_ok"] = document == resultat
            yield "factures.generation_pdf"

        def run():
            try:
                mesure["avant"] = etat()
                timer.Start(30)
                debut = time.monotonic()
                UTILS_Etapes_ui.Executer(
                    dialogue, etapes(), titre="PDF isole",
                    texte="Creation d'une facture fictive")
                mesure["duree_ms"] = int((time.monotonic() - debut) * 1000)
                mesure["apres"] = etat()
                original, pdf = Path(precedent).read_bytes(), Path(resultat).read_bytes()
                mesure["pdf_ok"] = (pdf.startswith(b"%PDF-") and
                                   b"%%EOF" in pdf[-2048:])
                mesure["taille_equivalente"] = (
                    abs(len(original) - len(pdf)) < max(2000, int(len(original)*0.10)))
            except BaseException as erreur:
                mesure["erreurs"].append(type(erreur).__name__)
            finally:
                timer.Stop()
                dates = mesure.pop("pulses")
                mesure["battements"] = len(dates)
                mesure["retard_max_ms"] = int(max(
                    (b-a for a,b in zip(dates, dates[1:])), default=0) * 1000)
                mesure["reseau"] = len(_garde_reseau.TENTATIVES)
                dialogue.Destroy()
                main.Destroy()
                app.ExitMainLoop()

        wx.CallLater(200, run)
        app.MainLoop()
        print("UI432K_PDF_WIN32 " + json.dumps(mesure), flush=True)
    finally:
        dossier.cleanup()
        base.fermer()
        app.Destroy()


@unittest.skipUnless(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true",
                     "Recette wx native Windows uniquement sur runner isole")
class PDFProcessusWindowsTests(unittest.TestCase):
    def test_un_rendu_noedoc_processus_et_mainframe_reactive(self):
        p = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--scenario"],
            cwd=ROOT / "noethys", capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        result = next(l for l in p.stdout.splitlines()
                      if l.startswith("UI432K_PDF_WIN32 "))
        data = json.loads(result.split(" ", 1)[1])
        self.assertEqual(data["erreurs"], [], data)
        self.assertEqual(data["reseau"], 0, data)
        self.assertTrue(data["rendu_ok"], data)
        self.assertTrue(data["pdf_ok"], data)
        self.assertTrue(data["taille_equivalente"], data)
        self.assertEqual(data["avant"], [True, False, False])
        self.assertEqual(data["apres"], [True, False, False])
        self.assertTrue(data["etats"], data)
        self.assertTrue(all(s == [True, False, False] for s in data["etats"]), data)
        self.assertTrue(data["owners"], data)
        self.assertTrue(all(data["owners"]), data)
        self.assertGreater(data["battements"], 5, data)
        self.assertLess(data["retard_max_ms"], 500, data)


if __name__ == "__main__":
    if "--scenario" in sys.argv:
        scenario()
    else:
        unittest.main()
