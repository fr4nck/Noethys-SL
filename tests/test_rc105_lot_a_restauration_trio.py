# -*- coding: utf-8 -*-
"""Lot A : DATA + DOCUMENTS sont prioritaires ; PHOTOS facultatif."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools/verifier_sauvegarde_mysql_isolee.py"
SPEC = importlib.util.spec_from_file_location("verifier_nod_perimetre_rc105", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RestaurationPerimetreTests(unittest.TestCase):
    def test_data_documents_suffisent_avec_ou_sans_photos(self):
        for noms in (
            ["association", "association_DOCUMENTS"],
            ["pelemele", "pelemele_PHOTOS", "pelemele_DOCUMENTS"],
            ["noe437_synth_data", "noe437_synth_documents"],
            ["DATA", "PHOTOS", "DOCUMENTS"],
            ["DATA", "PHOTOS", "DOCUMENTS", "AUTRE"],
        ):
            with self.subTest(noms=noms):
                retour = MODULE.QualifierPerimetreSauvegarde(noms)
                self.assertTrue(retour["perimetre_complet"])
                self.assertEqual(retour["categories_absentes"], [])

    def test_absence_de_photos_nest_pas_un_defaut(self):
        retour = MODULE.QualifierPerimetreSauvegarde(["DATA", "DOCUMENTS"])
        self.assertTrue(retour["perimetre_complet"])
        self.assertNotIn("PHOTOS", retour["categories_absentes"])

    def test_absence_de_data_ou_documents_est_signalee_sans_bloquer(self):
        for noms, attendues in (
            (["DATA", "PHOTOS"], ["DOCUMENTS"]),
            (["DATA"], ["DOCUMENTS"]),
            (["DOCUMENTS"], ["DATA"]),
            ([], ["DATA", "DOCUMENTS"]),
        ):
            with self.subTest(noms=noms):
                retour = MODULE.QualifierPerimetreSauvegarde(noms)
                self.assertFalse(retour["perimetre_complet"])
                self.assertEqual(retour["categories_absentes"], attendues)


if __name__ == "__main__":
    unittest.main()
