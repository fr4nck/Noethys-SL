# -*- coding: utf-8 -*-
"""Régression Windows : le client MySQL lancé en fond n'ouvre pas de console."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
from tests._mysql_backup_test_support import moteur


class ProcessusSansConsoleTests(unittest.TestCase):
    def test_flag_windows_et_sorties_redirectees(self):
        m = moteur()
        m.os = types.SimpleNamespace(name="nt", fspath=os.fspath, path=os.path, SEEK_END=os.SEEK_END)
        captures = []
        def lancer(args, **kwargs):
            captures.append(kwargs)
            return types.SimpleNamespace(returncode=0, wait=lambda timeout=None: 0, poll=lambda: 0)
        with tempfile.TemporaryDirectory() as rep, mock.patch.object(m.subprocess, "Popen", lancer):
            resultat = m.ExporterSQL("client-fictif", "login-fictif", Path(rep) / "dump.sql", "fictif")
        self.assertIsNone(resultat["erreur"])
        self.assertEqual(captures[0]["creationflags"], 0x08000000)
        self.assertIs(captures[0]["shell"], False)
        self.assertNotEqual(captures[0]["stdout"], subprocess.PIPE)

    def test_aucun_flag_windows_sur_autre_plateforme(self):
        m = moteur()
        m.os = types.SimpleNamespace(name="posix", fspath=os.fspath, path=os.path, SEEK_END=os.SEEK_END)
        captures = []
        def lancer(args, **kwargs):
            captures.append(kwargs)
            return types.SimpleNamespace(returncode=0, wait=lambda timeout=None: 0, poll=lambda: 0)
        with tempfile.TemporaryDirectory() as rep, mock.patch.object(m.subprocess, "Popen", lancer):
            m.ExporterSQL("client-fictif", "login-fictif", Path(rep) / "dump.sql", "fictif")
        self.assertEqual(captures[0]["creationflags"], 0)

    @unittest.skipUnless(os.name == "nt", "API console Windows")
    def test_vrai_enfant_windows_sans_console(self):
        m = moteur()
        vrai_popen = subprocess.Popen
        def lancer(args, **kwargs):
            code = "import ctypes,json; k=ctypes.windll.kernel32; print(json.dumps({'console':bool(k.GetConsoleWindow()),'codepage':k.GetConsoleCP()}))"
            return vrai_popen([sys.executable, "-c", code], **kwargs)
        with tempfile.TemporaryDirectory() as rep, mock.patch.object(m.subprocess, "Popen", lancer):
            fichier = Path(rep) / "sortie.json"
            resultat = m.ExporterSQL("client-fictif", "login-fictif", fichier, "fictif")
            self.assertIsNone(resultat["erreur"])
            self.assertFalse(json.loads(fichier.read_text())["console"], "Un client de fond ne doit pas avoir de fenêtre console")


if __name__ == "__main__":
    unittest.main()
