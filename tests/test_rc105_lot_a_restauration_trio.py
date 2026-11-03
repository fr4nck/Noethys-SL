# -*- coding: utf-8 -*-
"""Lot A : preuve de restauration complete, sans aucun appel MySQL."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools/verifier_sauvegarde_mysql_isolee.py"
SPEC = importlib.util.spec_from_file_location("verifier_nod_trio_rc105", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RestaurationTrioTests(unittest.TestCase):
    def test_noms_historiques_acceptes(self):
        for noms in (
            ["pelemele.sql", "pelemele_PHOTOS.sql", "pelemele_DOCUMENTS.sql"],
            ["noe437_synth_data", "noe437_synth_photos", "noe437_synth_documents"],
            ["DATA", "PHOTOS", "DOCUMENTS"],
        ):
            with self.subTest(noms=noms):
                self.assertIsNone(MODULE.ExigerTrioSauvegarde(noms))

    def test_archive_fournie_sans_photos_refusee(self):
        with self.assertRaisesRegex(RuntimeError, "trio DATA/PHOTOS/DOCUMENTS"):
            MODULE.ExigerTrioSauvegarde(["association", "association_DOCUMENTS"])

    def test_deux_dump_data_et_document_ne_constituent_pas_un_trio(self):
        for noms in (
            ["association", "association_documents", "autre_data"],
            ["DATA", "PHOTOS"],
            ["DATA", "PHOTOS", "DOCUMENTS", "AUTRE"],
            [],
        ):
            with self.subTest(noms=noms), self.assertRaises(RuntimeError):
                MODULE.ExigerTrioSauvegarde(noms)


if __name__ == "__main__":
    unittest.main()
