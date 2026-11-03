# -*- coding: utf-8 -*-
"""Lot A : qualifier le perimetre sans empecher les restaurations partielles."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools/verifier_sauvegarde_mysql_isolee.py"
SPEC = importlib.util.spec_from_file_location("verifier_nod_perimetre_rc105", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RestaurationPerimetreTests(unittest.TestCase):
    def test_trio_historique_signale_complet(self):
        for noms in (
            ["pelemele", "pelemele_PHOTOS", "pelemele_DOCUMENTS"],
            ["noe437_synth_data", "noe437_synth_photos", "noe437_synth_documents"],
            ["DATA", "PHOTOS", "DOCUMENTS"],
        ):
            with self.subTest(noms=noms):
                resultat = MODULE.QualifierPerimetreSauvegarde(noms)
                self.assertTrue(resultat["perimetre_complet"])
                self.assertEqual(resultat["categories_absentes"], [])

    def test_archive_sans_photos_ne_bloque_pas(self):
        retour = MODULE.QualifierPerimetreSauvegarde(
            ["association", "association_DOCUMENTS"])
        self.assertFalse(retour["perimetre_complet"])
        self.assertEqual(retour["categories_absentes"], ["PHOTOS"])

    def test_autres_configurations_restent_valides(self):
        for noms, attendues in (
            (["DATA", "PHOTOS"], ["DOCUMENTS"]),
            (["DATA"], ["PHOTOS", "DOCUMENTS"]),
            (["DATA", "PHOTOS", "DOCUMENTS", "AUTRE"], []),
            ([], ["DATA", "PHOTOS", "DOCUMENTS"]),
        ):
            with self.subTest(noms=noms):
                retour = MODULE.QualifierPerimetreSauvegarde(noms)
                self.assertFalse(retour["perimetre_complet"])
                self.assertEqual(retour["categories_absentes"], attendues)


if __name__ == "__main__":
    unittest.main()
