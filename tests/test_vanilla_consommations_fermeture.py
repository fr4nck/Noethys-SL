# -*- coding: utf-8 -*-
"""Vanilla P1 : crash natif de la liste detaillee des consommations.

Scenario de l'audit Vanilla : liste chargee, defilement, saisie dans la
recherche (arme le wx.Timer de la barre), fermeture par la croix puis
reouverture immediate, en boucle. Avant le nettoyage de cycle de vie de la
PR #359, ce scenario tue le processus (violation d'acces native) ; il est
donc execute dans un sous-processus dont le code de sortie fait foi.

Base SQLite fictive temporaire, configuration isolee par la garde reseau.
Variable facultative NOETHYS_RECETTE_DLG_CONSO : chemin d'une autre version
du module (contre-epreuve manuelle sur une version anterieure).
"""
import os
import subprocess
import sys
import unittest

ENFANT = "--scenario-enfant"
CYCLES = 12
NB_CONSOMMATIONS = 3000


def scenario_enfant():
    import importlib.util
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
    import GestionDB
    from Data import DATA_Tables as Tables
    from _fixtures_noethys_db import RedirectionGestionDB

    chemin = os.path.join(tempfile.mkdtemp(prefix="noethys-vanilla-conso-"), "Fictif_DATA.dat")
    db = GestionDB.DB(nomFichier=chemin, suffixe=None, modeCreation=True)
    for table in ("activites", "groupes", "unites", "individus", "consommations", "inscriptions",
                  "evenements", "prestations"):
        db.CreationTable(nomTable=table, dicoDB=Tables.DB_DATA)
    db.ExecuterReq("INSERT INTO activites (IDactivite, nom, abrege) VALUES (1, 'Accueil fictif', 'ACC');")
    db.ExecuterReq("INSERT INTO groupes (IDgroupe, IDactivite, nom, ordre) VALUES (1, 1, 'Groupe', 1);")
    db.ExecuterReq("INSERT INTO unites (IDunite, IDactivite, nom, abrege, type, ordre) VALUES (1, 1, 'Journee', 'J', 'Unitaire', 1);")
    for i in range(1, 101):
        db.ExecuterReq("INSERT INTO individus (IDindividu, nom, prenom) VALUES (%d, 'FICTIF', 'Enfant%d');" % (i, i))
    lignes = ["(%d, %d, 1, '2026-%02d-%02d', 1, 1, 'reservation', '2026-01-01', 1)"
              % (n + 1, n % 100 + 1, n % 12 + 1, n % 28 + 1) for n in range(NB_CONSOMMATIONS)]
    for k in range(0, len(lignes), 500):
        db.ExecuterReq("INSERT INTO consommations (IDconso, IDindividu, IDactivite, date, IDunite, IDgroupe, "
                       "etat, date_saisie, quantite) VALUES %s;" % ",".join(lignes[k:k + 500]))
    db.Commit()
    db.Close()

    with RedirectionGestionDB(chemin):
        alternatif = os.environ.get("NOETHYS_RECETTE_DLG_CONSO")
        if alternatif:
            spec = importlib.util.spec_from_file_location("Dlg.DLG_Liste_consommations", alternatif)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            from Dlg import DLG_Liste_consommations as module
        cadre = wx.Frame(None)
        cadre.Show()
        for cycle in range(CYCLES):
            dlg = module.Dialog(cadre)

            def fermer(d=dlg, cycle=cycle):
                try:
                    liste = d.ctrl_consommations
                    liste.EnsureVisible(liste.GetItemCount() - 1)
                    liste.ScrollLines(50)
                    d.ctrl_recherche.barreRecherche.SetValue("Enfant1%d" % cycle)
                except RuntimeError:
                    pass
                evt = wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW, d.GetId())
                evt.SetEventObject(d)
                wx.PostEvent(d, evt)
            wx.CallLater(30, fermer)
            dlg.ShowModal()
            dlg.Destroy()
            if cycle % 2:
                wx.Yield()
        for _ in range(20):
            wx.Yield()
        cadre.Destroy()
    sys.stdout.write("ERREURS_PYTHON=%d\n" % len(erreurs))
    for erreur in erreurs[:3]:
        sys.stdout.write(erreur)
    sys.stdout.flush()
    os._exit(0)


@unittest.skipUnless(sys.platform.startswith("win"), "scenario de crash natif Windows")
class ListeConsommationsFermetureTests(unittest.TestCase):
    def test_fermer_rouvrir_pendant_recherche_sans_crash(self):
        try:
            import wx  # noqa: F401
        except ImportError:
            self.skipTest("wxPython absent")
        proc = subprocess.run([sys.executable, os.path.abspath(__file__), ENFANT],
                              capture_output=True, text=True, timeout=600)
        sortie = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0,
                         "Processus termine anormalement (code %s, crash natif probable)\n%s"
                         % (proc.returncode, sortie[-2000:]))
        self.assertIn("ERREURS_PYTHON=0", sortie, sortie[-2000:])


class BarresRechercheTemporiseesTests(unittest.TestCase):
    """Cause racine : timer de recherche encore arme apres destruction (contre-epreuve
    faite : le seul arret a la destruction suffit a l'ancienne version du dialogue)."""

    def test_toute_barre_temporisee_s_arrete_a_la_destruction(self):
        import ast
        from pathlib import Path
        racine = Path(__file__).resolve().parents[1] / "noethys"
        temporisees = []
        for fichier in sorted(racine.rglob("*.py")):
            arbre = ast.parse(fichier.read_text(encoding="utf-8", errors="replace"))
            for classe in ast.walk(arbre):
                if isinstance(classe, ast.ClassDef) and classe.name == "BarreRecherche":
                    source = ast.unparse(classe)
                    if "wx.Timer" in source or "CallLater" in source:
                        temporisees.append(fichier.relative_to(racine.parent).as_posix())
                        self.assertIn("EVT_WINDOW_DESTROY", source, fichier.name)
        self.assertEqual(sorted(temporisees), [
            "noethys/Ctrl/CTRL_ObjectListView.py", "noethys/Ol/OL_Individus.py", "noethys/Ol/OL_Villes.py"])


if __name__ == "__main__":
    if ENFANT in sys.argv:
        scenario_enfant()
    else:
        unittest.main()
