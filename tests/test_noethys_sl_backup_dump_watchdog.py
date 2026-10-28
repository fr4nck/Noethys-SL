# -*- coding: utf-8 -*-
"""Regressions du gel mysqldump : AST, processus fictifs, aucun reseau."""
import ast
import os
import shlex
import shutil
import subprocess
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from tests._mysql_backup_test_support import moteur, horloge_repetable

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Sauvegarde.py"


class FauxDialogue:
    messages = []
    def __init__(self, *args, **kwargs):
        if len(args) > 1 and isinstance(args[1], str):
            FauxDialogue.messages.append(args[1])
    def Update(self, *args, **kwargs):
        return True
    def Destroy(self):
        pass
    def ShowModal(self):
        return 0


def isoler(dossier, lancer, horloge):
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    methode = next(n for n in arbre.body
                   if isinstance(n, ast.FunctionDef) and n.name == "Sauvegarde")
    env = {
        "_": lambda x: x, "os": os, "shutil": shutil, "zipfile": zipfile,
        "shlex": shlex, "tempfile": tempfile,
        "time": horloge_repetable(horloge),
        "subprocess": types.SimpleNamespace(
            Popen=lancer, DEVNULL=subprocess.DEVNULL,
            TimeoutExpired=subprocess.TimeoutExpired),
        "wx": types.SimpleNamespace(
            ProgressDialog=FauxDialogue, MessageDialog=FauxDialogue,
            PD_SMOOTH=0, PD_AUTO_HIDE=0, PD_APP_MODAL=0, OK=0, ICON_ERROR=0),
        "EXTENSIONS": {"decrypte": "nod", "crypte": "noc"},
        "UTILS_Fichiers": types.SimpleNamespace(
            GetRepTemp=lambda fichier: str(dossier / fichier)),
        "UTILS_Customize": types.SimpleNamespace(
            GetValeur=lambda *args, **kwargs: ""),
        "GetRepertoireMySQL": lambda connexion: str(dossier) + os.sep,
        "CreationFichierLoginTemp": lambda **kwargs: None,
        "UTILS_SQL_Integrite": types.SimpleNamespace(
            AnalyserDumpSQL=lambda *args, **kwargs: (None, None),
            AjouterManifesteIntegriteSQL=lambda *args, **kwargs: None),
        "UTILS_Envoi_email": types.SimpleNamespace(
            Message=lambda **kwargs: kwargs),
    }
    env["UTILS_MySQL_backup"] = moteur(env)
    exec(compile(ast.Module(body=[methode], type_ignores=[]), str(SOURCE), "exec"), env)
    return env["Sauvegarde"]


def essai(sauvegarde, repertoire=None):
    return sauvegarde(listeFichiersReseau=["base_fictive"], nom="testdump",
                      repertoire=repertoire, dictConnexion={
                          "host": "127.0.0.1", "port": "3308",
                          "user": "fictif", "password": "fictif"})


class TestsWatchdogDump(unittest.TestCase):
    def setUp(self):
        FauxDialogue.messages = []

    def test_arret_apres_dix_minutes_sans_octet_et_suppression_zip(self):
        with tempfile.TemporaryDirectory(prefix="noethys-dump-faux-") as root:
            dossier = Path(root)
            processus = []
            class Processus:
                returncode = None
                def __init__(self, argv, **kwargs):
                    self.argv = argv
                    self.sortie = kwargs["stdout"]
                    self.sortie.write(b"PARTIEL")
                    self.sortie.flush()
                def wait(self, timeout=None):
                    if self.returncode is None:
                        raise subprocess.TimeoutExpired(self.argv, timeout)
                    return self.returncode
                def poll(self):
                    return self.returncode
                def terminate(self):
                    self.returncode = -15
                def kill(self):
                    self.returncode = -9
            def lancer(argv, **kwargs):
                self.assertIs(kwargs["shell"], False)
                p = Processus(argv, **kwargs)
                processus.append(p)
                return p
            fn = isoler(dossier, lancer, iter((0.0, 1.0, 602.0)))
            self.assertFalse(essai(fn))
            self.assertEqual(processus[0].returncode, -15)
            self.assertTrue(any("10 minutes" in x for x in FauxDialogue.messages))
            self.assertFalse((dossier / "testdump.nod").exists())
            self.assertFalse((dossier / "savetemp").exists())

    def test_sortie_sql_directe_et_archive_complete(self):
        with tempfile.TemporaryDirectory(prefix="noethys-dump-complet-") as root:
            dossier = Path(root)
            destination = dossier / "destination"
            destination.mkdir()
            journal = []
            data = b"-- fiction\nCREATE TABLE t (id INT);\n"
            class Processus:
                returncode = 0
                def wait(self, timeout=None):
                    return self.returncode
                def poll(self):
                    return self.returncode
            def lancer(argv, **kwargs):
                journal.append((argv, kwargs))
                self.assertIs(kwargs["shell"], False)
                kwargs["stdout"].write(data)
                kwargs["stdout"].flush()
                return Processus()
            fn = isoler(dossier, lancer, iter((0.0,)))
            self.assertTrue(essai(fn, str(destination)))
            argv = journal[0][0]
            self.assertEqual(argv[1].split("=", 1)[0], "--defaults-file")
            self.assertEqual(argv[2:5], ["--opt", "--single-transaction", "--skip-lock-tables"])
            self.assertEqual(argv[-2:], ["--databases", "base_fictive"])
            with zipfile.ZipFile(destination / "testdump.nod") as archive:
                self.assertEqual(archive.read("base_fictive.sql"), data)
            self.assertFalse((dossier / "savetemp").exists())

    def test_progression_continuelle_permet_export_long(self):
        with tempfile.TemporaryDirectory(prefix="noethys-dump-croissance-") as root:
            dossier = Path(root)
            class Processus:
                returncode = None
                appels = 0
                def __init__(self, argv, **kwargs):
                    self.argv = argv
                    self.sortie = kwargs["stdout"]
                def wait(self, timeout=None):
                    self.appels += 1
                    if self.appels <= 3:
                        self.sortie.write(b"SQL" * 1024)
                        self.sortie.flush()
                        raise subprocess.TimeoutExpired(self.argv, timeout)
                    self.returncode = 0
                    return 0
                def poll(self):
                    return self.returncode
                def terminate(self):
                    raise AssertionError("pas de fin forcee")
                def kill(self):
                    raise AssertionError("pas de fin forcee")
            fn = isoler(dossier, lambda a, **k: Processus(a, **k),
                        iter((0.0, 500.0, 1000.0, 1500.0)))
            self.assertTrue(essai(fn))

    def test_limite_absolue_meme_avec_des_octets_produits(self):
        with tempfile.TemporaryDirectory(prefix="noethys-dump-limite-") as root:
            dossier = Path(root)
            class Processus:
                returncode = None
                def __init__(self, argv, **kwargs):
                    self.argv = argv
                    self.sortie = kwargs["stdout"]
                def wait(self, timeout=None):
                    if self.returncode is None:
                        self.sortie.write(b"SQL")
                        self.sortie.flush()
                        raise subprocess.TimeoutExpired(self.argv, timeout)
                    return self.returncode
                def poll(self):
                    return self.returncode
                def terminate(self):
                    self.returncode = -15
            fn = isoler(dossier, lambda a, **k: Processus(a, **k),
                        iter((0.0, 7201.0)))
            self.assertFalse(essai(fn))
            self.assertTrue(any("2 heures" in x for x in FauxDialogue.messages))
            self.assertFalse((dossier / "savetemp").exists())


if __name__ == "__main__":
    unittest.main()
