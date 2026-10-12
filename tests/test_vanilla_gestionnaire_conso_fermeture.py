# -*- coding: utf-8 -*-
"""Vanilla P1 : fermer le Gestionnaire des consommations par la croix Windows.

OK et Annuler appellent _mgr.UnInit() avant EndModal ; la croix (EVT_CLOSE)
laissait l'AuiManager empile sur la fenetre detruite : assertion wx
« any pushed event handlers must have been removed », crash natif possible.
Scenario reel (ShowModal, EVT_CLOSE, Destroy) dans un sous-processus.
Base SQLite fictive temporaire, configuration isolee par la garde reseau.
"""
import os
import subprocess
import sys
import unittest

ENFANT = "--scenario-enfant"


def scenario_enfant():
    import tempfile
    import traceback
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(racine, "tests"))
    sys.path.insert(0, os.path.join(racine, "noethys"))
    import _garde_reseau  # noqa: F401
    os.chdir(os.path.join(racine, "noethys"))
    import wx
    app = wx.App(False)  # noqa: F841
    erreurs = []
    sys.excepthook = lambda t, v, tb: erreurs.append("".join(traceback.format_exception(t, v, tb)))
    wx.MessageDialog.ShowModal = lambda self: wx.ID_NO
    import GestionDB
    from Data import DATA_Tables as Tables
    from _fixtures_noethys_db import RedirectionGestionDB

    chemin = os.path.join(tempfile.mkdtemp(prefix="noethys-vanilla-gestionnaire-"), "Fictif_DATA.dat")
    db = GestionDB.DB(nomFichier=chemin, suffixe=None, modeCreation=True)
    for table in Tables.DB_DATA:
        db.CreationTable(nomTable=table, dicoDB=Tables.DB_DATA)
    db.ExecuterReq("INSERT INTO activites (IDactivite, nom, abrege, date_debut, date_fin) "
                   "VALUES (1, 'Accueil fictif', 'ACC', '2026-01-01', '2027-12-31');")
    db.ExecuterReq("INSERT INTO groupes (IDgroupe, IDactivite, nom, ordre) VALUES (1, 1, 'Groupe', 1);")
    db.ExecuterReq("INSERT INTO unites (IDunite, IDactivite, nom, abrege, type, ordre) "
                   "VALUES (1, 1, 'Journee', 'J', 'Unitaire', 1);")
    db.Commit()
    db.Close()

    with RedirectionGestionDB(chemin):
        from Dlg import DLG_Gestionnaire_conso
        for _ in range(3):
            dlg = DLG_Gestionnaire_conso.Dialog(None)

            def croix(d=dlg):
                evt = wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW, d.GetId())
                evt.SetEventObject(d)
                evt.SetCanVeto(True)
                d.GetEventHandler().ProcessEvent(evt)
            wx.CallLater(300, croix)
            dlg.ShowModal()
            dlg.Destroy()
            for _ in range(5):
                wx.Yield()
    sys.stdout.write("ERREURS_PYTHON=%d\n" % len(erreurs))
    for erreur in erreurs[:2]:
        sys.stdout.write(erreur[-1500:])
    sys.stdout.flush()
    os._exit(0)


@unittest.skipUnless(sys.platform.startswith("win"), "scenario Windows natif")
class GestionnaireConsoFermetureTests(unittest.TestCase):
    def test_croix_windows_sans_assertion_ni_crash(self):
        try:
            import wx  # noqa: F401
        except ImportError:
            self.skipTest("wxPython absent")
        proc = subprocess.run([sys.executable, os.path.abspath(__file__), ENFANT],
                              capture_output=True, text=True, timeout=600)
        sortie = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, "Fin anormale (code %s)\n%s" % (proc.returncode, sortie[-2000:]))
        self.assertIn("ERREURS_PYTHON=0", sortie, sortie[-2000:])


if __name__ == "__main__":
    if ENFANT in sys.argv:
        scenario_enfant()
    else:
        unittest.main()
