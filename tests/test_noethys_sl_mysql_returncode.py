# -*- coding: utf-8 -*-
"""Noe-032 : un mysqldump silencieusement echoue ne produit aucune sauvegarde.

Test local avec AST et sous-processus fictif ; aucun wx, MySQL, reseau ou
profil Noethys ne sont importes ni utilises.
"""
import ast
import os
import shutil
import tempfile
import types
import unittest
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Sauvegarde.py"


class _Dialog:
    def __init__(self, *args, **kwargs):
        pass

    def ShowModal(self):
        return 0

    def Destroy(self):
        return None

    def Update(self, *args, **kwargs):
        return True


def _charger_sauvegarde(dependances):
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    fonction = next(
        noeud for noeud in arbre.body
        if isinstance(noeud, ast.FunctionDef) and noeud.name == "Sauvegarde"
    )
    namespace = dict(dependances)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fonction], type_ignores=[])),
                 str(SOURCE), "exec"), namespace)
    return namespace["Sauvegarde"]



def _charger_restauration(dependances):
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    fonction = next(
        noeud for noeud in arbre.body
        if isinstance(noeud, ast.FunctionDef) and noeud.name == "Restauration"
    )
    namespace = dict(dependances)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fonction], type_ignores=[])),
                 str(SOURCE), "exec"), namespace)
    return namespace["Restauration"]


class BackupMySQLReturncodeTests(unittest.TestCase):
    def test_code_sortie_non_nul_sans_stdout_rejete_et_efface_le_zip(self):
        with tempfile.TemporaryDirectory(prefix="noethys-noe032-factice-") as root:
            rep = Path(root)
            journal = []
            errors = []

            class ProcessusFictif:
                returncode = 23

                def communicate(self):
                    return b"", None

            def popen(arguments, **kwargs):
                journal.append(arguments)
                return ProcessusFictif()

            class Message(_Dialog):
                def __init__(self, parent, message, *args, **kwargs):
                    super().__init__()
                    errors.append(message)

            wx = types.SimpleNamespace(
                ProgressDialog=_Dialog,
                MessageDialog=Message,
                PD_SMOOTH=0, PD_AUTO_HIDE=0, PD_APP_MODAL=0,
                OK=0, ICON_ERROR=0,
            )
            dep = {
                "wx": wx,
                "_": lambda s: s,
                "os": os,
                "shutil": shutil,
                "zipfile": zipfile,
                "subprocess": types.SimpleNamespace(Popen=popen, PIPE=-1, STDOUT=-2),
                "six": types.SimpleNamespace(PY2=False, PY3=True),
                "EXTENSIONS": {"decrypte": "nod", "crypte": "noc"},
                "UTILS_Fichiers": types.SimpleNamespace(
                    GetRepTemp=lambda fichier: str(rep / fichier)
                ),
                "UTILS_Customize": types.SimpleNamespace(
                    GetValeur=lambda *args, **kwargs: ""
                ),
                "GetRepertoireMySQL": lambda conn: str(rep) + os.sep,
                "CreationFichierLoginTemp": lambda **kwargs: None,
            }
            resultat = _charger_sauvegarde(dep)(
                listeFichiersReseau=["base_fictive"],
                nom="essai",
                dictConnexion={
                    "host": "127.0.0.1", "port": "3308",
                    "user": "fiction", "password": "fiction",
                },
            )

            self.assertIs(resultat, False)
            self.assertEqual(len(journal), 1)
            self.assertIn("--opt --single-transaction --skip-lock-tables", journal[0])
            self.assertTrue(errors)
            self.assertIn("23", errors[0])
            self.assertFalse((rep / "essai.nod").exists(), "ZIP partiel conserve")
            self.assertFalse((rep / "savetemp").exists(), "Secrets temporaires conserves")

    def test_code_sortie_non_nul_restauration_sans_stdout_rejetee(self):
        with tempfile.TemporaryDirectory(prefix="noethys-noe032-restore-") as root:
            rep = Path(root)
            archive = rep / "essai.nod"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("base_fictive.sql", "CREATE TABLE temoin (id INTEGER);")
            journal = []
            messages = []

            class ProcessusFictif:
                returncode = 19

                def communicate(self):
                    return b"", None

            def popen(arguments, **kwargs):
                journal.append(arguments)
                return ProcessusFictif()

            class Message(_Dialog):
                def __init__(self, parent, message, *args, **kwargs):
                    super().__init__()
                    messages.append(message)

                def ShowModal(self):
                    return 5103

            wx = types.SimpleNamespace(
                ProgressDialog=_Dialog, MessageDialog=Message,
                ID_YES=5103, YES_NO=0, CANCEL=0, NO_DEFAULT=0,
                ICON_EXCLAMATION=0, OK=0, ICON_ERROR=0,
                PD_SMOOTH=0, PD_AUTO_HIDE=0, PD_APP_MODAL=0,
            )
            dep = {
                "wx": wx, "_": lambda s: s, "os": os,
                "shutil": shutil, "zipfile": zipfile,
                "subprocess": types.SimpleNamespace(Popen=popen, PIPE=-1, STDOUT=-2),
                "six": types.SimpleNamespace(PY2=False, PY3=True),
                "UTILS_Fichiers": types.SimpleNamespace(
                    GetRepTemp=lambda fichier: str(rep / fichier)
                ),
                "GetListeFichiersReseau": lambda _conn: ["base_fictive"],
                "GetRepertoireMySQL": lambda _conn: str(rep) + os.sep,
                "CreationFichierLoginTemp": lambda **kwargs: None,
            }
            resultat = _charger_restauration(dep)(
                fichier=str(archive),
                listeFichiersReseau=["base_fictive.sql"],
                dictConnexion={
                    "host": "127.0.0.1", "port": "3308",
                    "user": "fiction", "password": "fiction",
                },
            )
            self.assertIs(resultat, False)
            self.assertEqual(len(journal), 1)
            self.assertIn("19", "\n".join(messages))
            self.assertFalse((rep / "restoretemp").exists())
            self.assertTrue(archive.exists(), "Archive source supprimee")



if __name__ == "__main__":
    unittest.main()
