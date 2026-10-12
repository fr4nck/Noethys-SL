# -*- coding: utf-8 -*-
"""Vanilla : defauts trouves par le passage de toutes les actions de menu (12/10/2026).

Recette : vraie MainFrame sur profil Portable fictif, chaque action de menu
ouverte puis fermee par la croix. Defauts Python 3 herites de l'amont :
- Parametrage > Organisateur : SetValue(None) sur un champ vide -> dialogue non ouvert ;
- Importer des familles/individus et import de badgeage : unicodecsv absent du paquet,
  repli Python 2 (itertools.izip) -> dialogues non ouverts ;
- Synthese des deductions : dict_keys.sort() -> aucune ligne affichee.
Base SQLite fictive temporaire ; configuration isolee par la garde reseau.
"""
import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401
import ast  # noqa: E402
import importlib  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402

RACINE = Path(__file__).resolve().parents[1] / "noethys"

try:
    import wx
    APP = wx.GetApp() or wx.App(False)
except ImportError:  # pragma: no cover
    wx = None


@unittest.skipIf(wx is None, "wxPython absent")
class OrganisateurChampsVidesTests(unittest.TestCase):
    def test_dialogue_s_ouvre_avec_champs_null(self):
        import GestionDB
        from Data import DATA_Tables as Tables
        from _fixtures_noethys_db import RedirectionGestionDB
        dossier = tempfile.TemporaryDirectory(prefix="noethys-vanilla-organisateur-")
        self.addCleanup(dossier.cleanup)
        chemin = os.path.join(dossier.name, "Fictif_DATA.dat")
        db = GestionDB.DB(nomFichier=chemin, suffixe=None, modeCreation=True)
        for table in Tables.DB_DATA:
            db.CreationTable(nomTable=table, dicoDB=Tables.DB_DATA)
        db.ExecuterReq("INSERT INTO organisateur (IDorganisateur, nom, rue, cp, ville) "
                       "VALUES (1, 'Association fictive', NULL, '35000', 'Rennes');")
        db.Commit()
        db.Close()
        with RedirectionGestionDB(chemin):
            from Dlg import DLG_Organisateur
            dlg = DLG_Organisateur.Dialog(None)
            try:
                self.assertEqual(dlg.ctrl_nom.GetValue(), "Association fictive")
                self.assertEqual(dlg.ctrl_rue.GetValue(), "")
                self.assertEqual(dlg.ctrl_site.GetValue(), "")
                self.assertEqual(dlg.ctrl_siret.GetValue(), "")
            finally:
                dlg.Destroy()


class CsvUnicodeTests(unittest.TestCase):
    def test_lecture_fichier_binaire_utf8_point_virgule(self):
        from Utils import UTILS_Csv_unicode
        dossier = tempfile.TemporaryDirectory(prefix="noethys-vanilla-csv-")
        self.addCleanup(dossier.cleanup)
        chemin = os.path.join(dossier.name, "familles.csv")
        with open(chemin, "wb") as flux:
            flux.write(u"NOM;PRENOM;NAISSANCE\r\nFICTIF;Léa;03/03/1985\r\nO'FICTION;Élise;\r\n".encode("utf-8"))
        with open(chemin, "rb") as flux:
            lignes = list(UTILS_Csv_unicode.reader(flux, encoding="utf8", delimiter=";"))
        self.assertEqual(lignes, [["NOM", "PRENOM", "NAISSANCE"], ["FICTIF", "Léa", "03/03/1985"],
                                  ["O'FICTION", "Élise", ""]])

    @unittest.skipIf(wx is None, "wxPython absent")
    def test_dialogues_d_import_s_importent_sans_unicodecsv(self):
        try:
            import unicodecsv  # noqa: F401
            self.skipTest("unicodecsv installe : repli non exerce")
        except ImportError:
            pass
        for nom in ("Dlg.DLG_Importation_individus", "Dlg.DLG_Badgeage_importation"):
            with self.subTest(module=nom):
                module = importlib.import_module(nom)
                self.assertTrue(hasattr(module.csv, "reader"))


class VuesDictionnaireTests(unittest.TestCase):
    def test_aucun_tri_sur_une_vue_de_dictionnaire(self):
        fautes = []
        for fichier in sorted(RACINE.rglob("*.py")):
            if "Outils" in fichier.parts or "ObjectListView" in fichier.parts:
                continue
            try:
                arbre = ast.parse(fichier.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for fonction in [n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)]:
                vues = {}
                for noeud in ast.walk(fonction):
                    if isinstance(noeud, ast.Assign) and len(noeud.targets) == 1:
                        cible = ast.unparse(noeud.targets[0])
                        appel = noeud.value
                        if (isinstance(appel, ast.Call) and isinstance(appel.func, ast.Attribute)
                                and appel.func.attr in ("keys", "values", "items") and not appel.args):
                            vues[cible] = noeud.lineno
                for noeud in ast.walk(fonction):
                    if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
                            and noeud.func.attr == "sort" and ast.unparse(noeud.func.value) in vues):
                        fautes.append("%s:%d" % (fichier.name, noeud.lineno))
        self.assertEqual(fautes, [])


if __name__ == "__main__":
    unittest.main()
