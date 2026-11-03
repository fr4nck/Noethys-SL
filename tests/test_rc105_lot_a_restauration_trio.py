# -*- coding: utf-8 -*-
"""Lot A : DATA + DOCUMENTS sont prioritaires ; PHOTOS facultatif."""
import importlib.util
from pathlib import Path
import tempfile
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


class ValidationSQLHistoriqueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rc105-sql-historique-")
        self.addCleanup(self.tmp.cleanup)
        self.sql = Path(self.tmp.name) / "ancienne.sql"

    def test_dump_historique_sans_manifeste_est_restaurable_sur_banc(self):
        self.sql.write_bytes(
            b"CREATE TABLE `temoin` (`id` INT);\n"
            b"INSERT INTO `temoin` VALUES (437);\n"
            b"-- Dump completed on 2026-01-01 00:00:00\n")
        self.assertEqual(MODULE.QualifierDumpSQL(self.sql), "HISTORIQUE_VERIFIE")

    def test_dump_historique_tronque_est_refuse(self):
        self.sql.write_bytes(b"CREATE TABLE `temoin` (`id` INT);\n")
        with self.assertRaisesRegex(RuntimeError, "non restaurable"):
            MODULE.QualifierDumpSQL(self.sql)

    def test_dump_avec_manifeste_valide_est_restaurable_sur_banc(self):
        self.sql.write_bytes(
            b"CREATE TABLE `temoin` (`id` INT);\n"
            b"-- Dump completed on 2026-01-01 00:00:00\n")
        MODULE.integrite.AjouterManifesteIntegriteSQL(self.sql)
        self.assertEqual(MODULE.QualifierDumpSQL(self.sql), "MANIFESTE_V1_VERIFIE")

    def test_manifeste_corrompu_est_refuse(self):
        self.sql.write_bytes(
            b"CREATE TABLE `temoin` (`id` INT);\n"
            b"-- Dump completed on 2026-01-01 00:00:00\n")
        MODULE.integrite.AjouterManifesteIntegriteSQL(self.sql)
        self.sql.write_bytes(self.sql.read_bytes().replace(b"temoin", b"temoiN"))
        with self.assertRaisesRegex(RuntimeError, "non restaurable"):
            MODULE.QualifierDumpSQL(self.sql)

    def test_manifeste_forge_sur_sql_sans_fin_refuse(self):
        self.sql.write_bytes(b"CREATE TABLE `temoin` (`id` INT);\n")
        MODULE.integrite.AjouterManifesteIntegriteSQL(self.sql)
        with self.assertRaisesRegex(RuntimeError, "marqueur de fin"):
            MODULE.QualifierDumpSQL(self.sql)


if __name__ == "__main__":
    unittest.main()
