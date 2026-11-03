# -*- coding: utf-8 -*-
"""Lot A : publication atomique du NOD ; aucune base ni profil utilisateur."""
import os
from pathlib import Path
import tempfile
import types
import unittest
import zipfile
from unittest import mock

from tests.test_noethys_sl_mysql_returncode import _charger_manifeste

from tests._mysql_backup_test_support import moteur


class PublicationArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rc105-a-publication-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.module = moteur()

    def test_windows_exfat_nutilise_pas_de_lien_physique(self):
        source = self.directory / "staging.nod"
        destination = self.directory / "complete.nod"
        source.write_bytes(b"ZIP FICTIF")
        def rename_no_replace(src, dst):
            if Path(dst).exists():
                raise FileExistsError(str(dst))
            os.rename(src, dst)
        faux_os = types.SimpleNamespace(
            name="nt", rename=mock.Mock(side_effect=rename_no_replace),
            link=mock.Mock(side_effect=AssertionError("hardlink interdit")))
        with mock.patch.object(self.module, "os", faux_os):
            self.module._PublierArchiveSansRemplacement(source, destination)
        self.assertEqual(destination.read_bytes(), b"ZIP FICTIF")
        self.assertFalse(source.exists())
        faux_os.rename.assert_called_once_with(source, destination)
        faux_os.link.assert_not_called()

    def test_windows_collision_conserve_lancienne_archive(self):
        source = self.directory / "staging.nod"
        destination = self.directory / "complete.nod"
        source.write_bytes(b"NOUVELLE")
        destination.write_bytes(b"ANCIENNE")
        def rename_no_replace(src, dst):
            if Path(dst).exists():
                raise FileExistsError(str(dst))
            os.rename(src, dst)
        faux_os = types.SimpleNamespace(name="nt", rename=rename_no_replace,
                                        link=mock.Mock(side_effect=AssertionError("interdit")))
        with mock.patch.object(self.module, "os", faux_os):
            with self.assertRaises(FileExistsError):
                self.module._PublierArchiveSansRemplacement(source, destination)
        self.assertEqual(destination.read_bytes(), b"ANCIENNE")
        self.assertEqual(source.read_bytes(), b"NOUVELLE")

    def test_rapport_json_non_inscriptible_ne_fait_pas_echouer_larchive(self):
        # L'archive SQL publiee est l'objet metier ; le diagnostic est un
        # accessoire. Aucune connexion MySQL, aucun profil.
        chemin = self.directory / "data_documents.nod"
        def export_fictif(_prog, _login, fichier, _base, **kwargs):
            payload = (
                b"CREATE TABLE `temoin` (`id` INT);\n"
                b"INSERT INTO `temoin` VALUES (437);\n"
                b"-- Dump completed on 2026-01-01 00:00:00\n"
            )
            Path(fichier).write_bytes(payload)
            return {"erreur": None, "octets": len(payload), "code_retour": 0}
        def ouvrir(chemin_fichier, *args, **kwargs):
            if os.fspath(chemin_fichier).endswith(".diagnostic.json"):
                raise PermissionError("diagnostic fictivement interdit")
            return open(chemin_fichier, *args, **kwargs)
        with mock.patch.object(self.module, "ExporterSQL", side_effect=export_fictif):
            with mock.patch.object(self.module, "open", side_effect=ouvrir, create=True):
                bilan = self.module.CreerArchive(
                    "mysqldump-fictif", "client-fictif.cnf",
                    ["demo_data", "demo_documents"], chemin, _charger_manifeste())
        self.assertTrue(bilan["succes"], bilan)
        self.assertTrue(bilan["rapport_indisponible"])
        self.assertFalse(chemin.with_suffix(".nod.diagnostic.json").exists())
        with zipfile.ZipFile(chemin) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.namelist(), ["demo_data.sql", "demo_documents.sql"])

    def test_posix_conserve_le_lien_non_remplacant(self):
        lien = mock.Mock()
        faux_os = types.SimpleNamespace(
            name="posix", link=lien,
            rename=mock.Mock(side_effect=AssertionError("rename interdit")))
        with mock.patch.object(self.module, "os", faux_os):
            self.module._PublierArchiveSansRemplacement("source.nod", "dest.nod")
        lien.assert_called_once_with("source.nod", "dest.nod")
        faux_os.rename.assert_not_called()

    def test_publication_reelle_sur_volume_local_sans_ecrasement(self):
        source = self.directory / "staging.nod"
        destination = self.directory / "complete.nod"
        source.write_bytes(b"COMPLET")
        self.module._PublierArchiveSansRemplacement(source, destination)
        self.assertEqual(destination.read_bytes(), b"COMPLET")
        # Sous POSIX, le premier lien partage le meme inode : nettoyer la
        # source publiee avant de creer un nouveau temporaire independant.
        source.unlink(missing_ok=True)
        source.write_bytes(b"SECOND")
        with self.assertRaises(FileExistsError):
            self.module._PublierArchiveSansRemplacement(source, destination)
        self.assertEqual(destination.read_bytes(), b"COMPLET")


if __name__ == "__main__":
    unittest.main()
