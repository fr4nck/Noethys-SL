# -*- coding: utf-8 -*-
"""Verification de manifeste avant toute creation de base ou import, sans reseau."""
import ast
import importlib.util
import os
import shutil
import tempfile
import types
import unittest
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Sauvegarde.py"
HELPER = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_SQL_Integrite.py"


def _charger_manifeste():
    spec = importlib.util.spec_from_file_location("sql_manifest_integrite", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Dialogue:
    def __init__(self, *args, **kwargs):
        pass

    def ShowModal(self):
        return 5103

    def Update(self, *args, **kwargs):
        return True

    def Destroy(self):
        return None


class RestaurationManifesteTests(unittest.TestCase):
    def _executer(self, archive, rep, processus_interdit, base_interdite):
        wx = types.SimpleNamespace(
            MessageDialog=_Dialogue, ProgressDialog=_Dialogue,
            ID_YES=5103, YES_NO=0, CANCEL=0, NO_DEFAULT=0,
            ICON_EXCLAMATION=0, ICON_ERROR=0, OK=0,
            PD_SMOOTH=0, PD_AUTO_HIDE=0, PD_APP_MODAL=0,
        )

        class Processus:
            returncode = 0

            def communicate(self):
                return b"", None

        def popen(*args, **kwargs):
            if processus_interdit:
                raise AssertionError("mysql execute avant verification SQL")
            return Processus()

        def db(*args, **kwargs):
            if base_interdite:
                raise AssertionError("base creee avant verification SQL")
            return types.SimpleNamespace(Close=lambda: None)

        deps = {
            "zipfile": zipfile, "os": os, "shutil": shutil,
            "wx": wx, "_": lambda texte: texte,
            "six": types.SimpleNamespace(PY2=False),
            "subprocess": types.SimpleNamespace(Popen=popen, PIPE=-1, STDOUT=-2),
            "GestionDB": types.SimpleNamespace(DB=db),
            "UTILS_SQL_Integrite": _charger_manifeste(),
            "UTILS_Fichiers": types.SimpleNamespace(GetRepTemp=lambda fichier: str(rep / fichier)),
            "GetListeFichiersReseau": lambda _connection: ([] if base_interdite else ["base_fictive"]),
            "GetRepertoireMySQL": lambda _connection: str(rep) + os.sep,
            "CreationFichierLoginTemp": lambda **kwargs: None,
        }
        arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
        fonction = next(noeud for noeud in arbre.body
                        if isinstance(noeud, ast.FunctionDef) and noeud.name == "Restauration")
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fonction], type_ignores=[])),
                     str(SOURCE), "exec"), deps)
        return deps["Restauration"](
            fichier=str(archive), listeFichiersReseau=["base_fictive.sql"],
            dictConnexion={"port": "3308", "host": "127.0.0.1", "user": "faux", "password": "faux"},
        )

    def test_manifeste_invalide_refuse_avant_sql(self):
        with tempfile.TemporaryDirectory(prefix="noe032-manifest-invalide-") as dossier:
            rep = Path(dossier)
            archive = rep / "temoin.nod"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("base_fictive.sql", b"-- NOETHYS-SQL-MANIFEST-V1 " + b"a" * 32 + b"\nCREATE TABLE faux (id INT);\n")
            resultat = self._executer(archive, rep, processus_interdit=True, base_interdite=True)
            self.assertIs(resultat, False)
            self.assertTrue(archive.exists())
            self.assertFalse((rep / "restoretemp").exists())

    def test_ancien_dump_tronque_refuse_avant_sql(self):
        with tempfile.TemporaryDirectory(prefix="noe032-analyse-tronque-") as dossier:
            rep = Path(dossier)
            archive = rep / "tronque.nod"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("base_fictive.sql", b"CREATE TABLE fictive (id INT);\nINSERT INTO fictive VALUES (1),(")
            resultat = self._executer(archive, rep, processus_interdit=True, base_interdite=True)
            self.assertIs(resultat, False)
            self.assertTrue(archive.exists())
            self.assertFalse((rep / "restoretemp").exists())

    def test_dump_sans_objet_restaurable_refuse_avant_sql(self):
        with tempfile.TemporaryDirectory(prefix="noe032-analyse-noop-") as dossier:
            rep = Path(dossier)
            archive = rep / "noop.nod"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("base_fictive.sql", b"-- vide\nSELECT 1;\n")
            resultat = self._executer(archive, rep, processus_interdit=True, base_interdite=True)
            self.assertIs(resultat, False)
            self.assertFalse((rep / "restoretemp").exists())

    def test_ancien_dump_sans_manifeste_reste_lisible(self):
        with tempfile.TemporaryDirectory(prefix="noe032-manifest-ancien-") as dossier:
            rep = Path(dossier)
            archive = rep / "ancien.nod"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("base_fictive.sql", b"CREATE TABLE fictive (id INT);\n")
            resultat = self._executer(archive, rep, processus_interdit=False, base_interdite=False)
            self.assertEqual(resultat, ["base_fictive"])
            self.assertFalse((rep / "restoretemp").exists())


    def test_sauvegarde_reseau_produit_un_manifeste_valide(self):
        with tempfile.TemporaryDirectory(prefix="noe032-save-manifest-") as dossier:
            rep = Path(dossier)
            sortie = rep / "sortie"
            sortie.mkdir()

            class Processus:
                returncode = 0

                def communicate(self):
                    return b"", None

            def popen(commande, **kwargs):
                import re
                chemin = re.search(r'>\s*"([^"]+)"', commande).group(1)
                Path(chemin).write_bytes(b"CREATE TABLE test_synth (id INT);\n")
                return Processus()

            wx = types.SimpleNamespace(
                MessageDialog=_Dialogue, ProgressDialog=_Dialogue,
                OK=0, ICON_ERROR=0, PD_SMOOTH=0, PD_AUTO_HIDE=0, PD_APP_MODAL=0,
            )
            deps = {
                "zipfile": zipfile, "os": os, "shutil": shutil,
                "wx": wx, "_": lambda texte: texte,
                "six": types.SimpleNamespace(PY2=False, PY3=True),
                "subprocess": types.SimpleNamespace(Popen=popen, PIPE=-1, STDOUT=-2),
                "UTILS_SQL_Integrite": _charger_manifeste(),
                "UTILS_Customize": types.SimpleNamespace(GetValeur=lambda *args, **kwargs: ""),
                "UTILS_Envoi_email": types.SimpleNamespace(Message=lambda **kwargs: kwargs),
                "UTILS_Fichiers": types.SimpleNamespace(GetRepTemp=lambda fichier: str(rep / fichier)),
                "GetRepertoireMySQL": lambda _connection: str(rep) + os.sep,
                "CreationFichierLoginTemp": lambda **kwargs: None,
                "EXTENSIONS": {"decrypte": "nod", "crypte": "noc"},
            }
            arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
            fonction = next(noeud for noeud in arbre.body
                            if isinstance(noeud, ast.FunctionDef) and noeud.name == "Sauvegarde")
            exec(compile(ast.fix_missing_locations(ast.Module(body=[fonction], type_ignores=[])),
                         str(SOURCE), "exec"), deps)
            resultat = deps["Sauvegarde"](
                listeFichiersReseau=["base_fictive"], nom="essai", repertoire=str(sortie),
                dictConnexion={"port": "3308", "host": "127.0.0.1", "user": "faux", "password": "faux"},
            )
            self.assertTrue(resultat)
            archive = sortie / "essai.nod"
            self.assertTrue(archive.exists())
            with zipfile.ZipFile(archive, "r") as z:
                sql = z.read("base_fictive.sql")
            self.assertTrue(sql.startswith(b"-- NOETHYS-SQL-MANIFEST-V1 "))
            fichier_sql = rep / "resultat.sql"
            fichier_sql.write_bytes(sql)
            self.assertEqual(_charger_manifeste().VerifierIntegriteSQL(fichier_sql), (True, None))
            self.assertFalse((rep / "savetemp").exists())



if __name__ == "__main__":
    unittest.main()
