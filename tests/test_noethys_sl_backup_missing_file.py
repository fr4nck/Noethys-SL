# -*- coding: utf-8 -*-
"""Noe-032 : test historique master b0be3c7e, ZIP partiel sur fichier absent.

Sauvegarde chargee par AST sans importer wx, GestionDB ni profil utilisateur.
"""
import ast
import os
import shutil
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock


class _Dialog:
    def __init__(self, *args, **kwargs):
        pass

    def ShowModal(self):
        return 5103

    def Destroy(self):
        pass

    def Update(self, *args, **kwargs):
        return True


def _load_module(data_dir, temp_dir):
    source = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_Sauvegarde.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    fonction = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "Sauvegarde")
    wx = types.SimpleNamespace(MessageDialog=_Dialog, ProgressDialog=_Dialog, ID_YES=5103,
                               PD_SMOOTH=0, PD_AUTO_HIDE=0, PD_APP_MODAL=0, OK=0, ICON_ERROR=0)
    namespace = dict(wx=wx, zipfile=zipfile, os=os, shutil=shutil, _=lambda value: value,
                     EXTENSIONS={"decrypte": "nod", "crypte": "noc"},
                     UTILS_Fichiers=types.SimpleNamespace(
                         GetRepData=lambda fichier: str(data_dir / fichier),
                         GetRepTemp=lambda fichier: str(temp_dir / fichier)),
                     UTILS_Envoi_email=types.SimpleNamespace(Message=lambda **kwargs: kwargs))
    exec(compile(ast.Module(body=[fonction], type_ignores=[]), str(source), "exec"), namespace)
    return types.SimpleNamespace(**namespace)


class BackupMissingFileTests(unittest.TestCase):
    def test_missing_local_file_closes_zip_and_removes_partial_archive(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            data_dir = root / "data"
            temp_dir = root / "temp"
            data_dir.mkdir()
            temp_dir.mkdir()

            module = _load_module(data_dir, temp_dir)
            real_zip_file = module.zipfile.ZipFile
            opened = []

            class _TrackingZip(object):
                def __init__(self, *args, **kwargs):
                    self.inner = real_zip_file(*args, **kwargs)
                    self.closed = False
                    opened.append(self)

                def write(self, *args, **kwargs):
                    return self.inner.write(*args, **kwargs)

                def close(self):
                    self.closed = True
                    self.inner.close()

            with mock.patch.object(module.zipfile, "ZipFile", _TrackingZip):
                result = module.Sauvegarde(
                    listeFichiersLocaux=["missing_DATA.dat"],
                    nom="backup",
                )

            self.assertFalse(result)
            self.assertTrue(opened[0].closed)
            self.assertFalse((temp_dir / "backup.nod").exists())



    def test_missing_file_after_first_entry_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            data_dir, temp_dir, output_dir = root / "data", root / "temp", root / "output"
            for directory in (data_dir, temp_dir, output_dir):
                directory.mkdir()
            (data_dir / "demo_DATA.dat").write_bytes(b"fictif")
            destination = output_dir / "backup.nod"
            destination.write_bytes(b"ancienne sauvegarde fictive")
            module = _load_module(data_dir, temp_dir)
            module.Sauvegarde.__globals__["wx"].YES_NO = 0
            module.Sauvegarde.__globals__["wx"].NO_DEFAULT = 0
            module.Sauvegarde.__globals__["wx"].ICON_EXCLAMATION = 0
            result = module.Sauvegarde(
                listeFichiersLocaux=["demo_DATA.dat", "missing_DATA.dat"],
                nom="backup", repertoire=str(output_dir))
            self.assertFalse(result)
            self.assertFalse((temp_dir / "backup.nod").exists())
            self.assertEqual(destination.read_bytes(), b"ancienne sauvegarde fictive")

    def test_successful_local_backup_keeps_complete_archive(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            data_dir, temp_dir, output_dir = root / "data", root / "temp", root / "output"
            for directory in (data_dir, temp_dir, output_dir):
                directory.mkdir()
            (data_dir / "demo_DATA.dat").write_bytes(b"fictif")
            module = _load_module(data_dir, temp_dir)
            result = module.Sauvegarde(listeFichiersLocaux=["demo_DATA.dat"],
                                      nom="backup", repertoire=str(output_dir))
            self.assertTrue(result)
            with zipfile.ZipFile(output_dir / "backup.nod") as archive:
                self.assertEqual(archive.read("demo_DATA.dat"), b"fictif")
            self.assertFalse((temp_dir / "backup.nod").exists())


if __name__ == "__main__":
    unittest.main()
