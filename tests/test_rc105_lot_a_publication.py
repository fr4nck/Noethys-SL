# -*- coding: utf-8 -*-
"""Lot A : publication atomique du NOD ; aucune base ni profil utilisateur."""
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

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
        source.write_bytes(b"SECOND")
        with self.assertRaises(FileExistsError):
            self.module._PublierArchiveSansRemplacement(source, destination)
        self.assertEqual(destination.read_bytes(), b"COMPLET")


if __name__ == "__main__":
    unittest.main()
