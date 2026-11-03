# -*- coding: utf-8 -*-
"""Synthetic, non-personal tests for the ALSH meal preflight."""
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_lot_c_alsh.py"
spec = importlib.util.spec_from_file_location("audit_lot_c_alsh", SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditLotCAlshTests(unittest.TestCase):
    def sauver(self, sql):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        chemin = Path(dossier.name) / "test.nod"
        with zipfile.ZipFile(chemin, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("mad_data.sql", sql)
        return chemin

    def test_sauvegarde_sans_parametrage_signalee(self):
        sql = b"CREATE TABLE `consommations` (x int);\nINSERT INTO `consommations` VALUES (1),(2);\nCREATE TABLE `modeles_commandes` (x int);\n"
        r = audit.AuditerSauvegarde(self.sauver(sql))
        self.assertEqual(r["tables"]["consommations"], {"schema": True, "lignes": 2})
        self.assertEqual(r["configuration_fournisseur"], "SCHEMA_INCOMPLET")

    def test_zero_modeles_est_absent_et_non_pas_pret(self):
        tables = ["restaurateurs", "modeles_commandes", "modeles_commandes_colonnes"]
        sql = b"".join(("CREATE TABLE `%s` (x int);\n" % x).encode() for x in tables)
        self.assertEqual(audit.AuditerSauvegarde(self.sauver(sql))["configuration_fournisseur"], "CONFIGURATION_ABSENTE")

    def test_presence_de_questions_ne_signifie_pas_pret(self):
        sql = b"""CREATE TABLE `questionnaire_questions` (x int);
CREATE TABLE `questionnaire_choix` (x int);
INSERT INTO `questionnaire_questions` VALUES (1);
INSERT INTO `questionnaire_choix` VALUES (2),(3),(4),(5);
"""
        r = audit.AuditerSauvegarde(self.sauver(sql))
        self.assertEqual(r["configuration_questionnaire"], "A_QUALIFIER")
        self.assertIn("ne prouve pas", r["remarque"])

    def test_sql_echappe_parentheses_et_texte_prive_jamais_restitues(self):
        secret = "contact@famille-fictive.invalid"
        sql = ("CREATE TABLE `consommations` (x text);\n"
               "INSERT INTO `consommations` VALUES ('%s (test)'),('l\\'ami'),(CONCAT('a','b'));\n" % secret).encode()
        r = audit.AuditerSauvegarde(self.sauver(sql))
        self.assertEqual(r["tables"]["consommations"]["lignes"], 3)
        self.assertNotIn(secret, json.dumps(r))
        self.assertNotIn("CONCAT", json.dumps(r))

    def test_insert_avec_colonnes_et_quotes_doublees(self):
        sql = b"""CREATE TABLE `unites` (x text);
INSERT INTO `unites` (`x`) VALUES ('O''Hara'),('A,(B)');
"""
        self.assertEqual(audit.AuditerSauvegarde(self.sauver(sql))["tables"]["unites"]["lignes"], 2)

    def test_sql_non_termine_bloque(self):
        sql = b"CREATE TABLE `unites` (x int);\nINSERT INTO `unites` VALUES (1),(2)"
        with self.assertRaises(audit.AuditLotCInvalide):
            audit.AuditerSauvegarde(self.sauver(sql))

    def test_archive_manquante_refusee(self):
        with self.assertRaises(audit.AuditLotCInvalide):
            audit.AuditerSauvegarde("/faux/chemin.nod")

    def test_pas_d_ecriture_dans_archive(self):
        chemin = self.sauver(b"CREATE TABLE `unites` (x int);")
        avant = chemin.read_bytes()
        audit.AuditerSauvegarde(chemin)
        self.assertEqual(chemin.read_bytes(), avant)


if __name__ == "__main__":
    unittest.main()
