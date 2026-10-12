# -*- coding: utf-8 -*-
"""Noe-032 : analyse syntaxique des dumps SQL avant restauration.

Cas repris des tests historiques de master (test_noe_032_restore_flow) et dump
synthetique au format mysqldump 5.5. Aucun wx, MySQL, reseau ni profil.
"""
import importlib.util
import os
import random
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_SQL_Integrite.py"
_SPEC = importlib.util.spec_from_file_location("noe032_sql_analyse", SOURCE)
MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MODULE)
AnalyserDumpSQL = MODULE.AnalyserDumpSQL


def _blob_mysqldump(taille, graine):
    """Octets arbitraires echappes comme mysqldump (sans --hex-blob)."""
    alea = random.Random(graine)
    brut = bytes(alea.getrandbits(8) for _ in range(taille))
    echappements = {0: b"\\0", 10: b"\\n", 13: b"\\r", 26: b"\\Z", 34: b'\\"', 39: b"\\'", 92: b"\\\\"}
    return b"".join(echappements.get(octet, bytes([octet])) for octet in brut)


def _dump_mysqldump_synthetique():
    return (
        b"-- MySQL dump 10.13  Distrib 5.5.62, for Win64 (AMD64)\n"
        b"--\n-- Host: 127.0.0.1    Database: fictive_data\n"
        b"-- ------------------------------------------------------\n"
        b"/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;\n"
        b"/*!40101 SET NAMES utf8 */;\n"
        b"/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;\n\n"
        b"CREATE DATABASE /*!32312 IF NOT EXISTS*/ `fictive_data` /*!40100 DEFAULT CHARACTER SET utf8 */;\n\n"
        b"USE `fictive_data`;\n\n"
        b"DROP TABLE IF EXISTS `individus`;\n"
        b"/*!40101 SET @saved_cs_client     = @@character_set_client */;\n"
        b"CREATE TABLE `individus` (\n  `IDindividu` int(11) NOT NULL AUTO_INCREMENT,\n"
        b"  `nom` varchar(100) DEFAULT NULL,\n  PRIMARY KEY (`IDindividu`)\n"
        b") ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8;\n"
        b"LOCK TABLES `individus` WRITE;\n"
        b"/*!40000 ALTER TABLE `individus` DISABLE KEYS */;\n"
        b"INSERT INTO `individus` VALUES (1,'Fictif; -- pas un commentaire'),(2,'O\\'Fiction \\\\ test');\n"
        b"/*!40000 ALTER TABLE `individus` ENABLE KEYS */;\n"
        b"UNLOCK TABLES;\n\n"
        b"DROP TABLE IF EXISTS `documents`;\n"
        b"CREATE TABLE `documents` (`IDdocument` int(11) NOT NULL, `document` longblob);\n"
        b"LOCK TABLES `documents` WRITE;\n"
        b"INSERT INTO `documents` VALUES (1,'" + _blob_mysqldump(20000, 32) + b"');\n"
        b"UNLOCK TABLES;\n\n"
        b"--\n-- Temporary table structure for view `vue_fictive`\n--\n"
        b"/*!50001 DROP TABLE IF EXISTS `vue_fictive`*/;\n"
        b"/*!50001 CREATE TABLE `vue_fictive` (\n  `IDindividu` int(11)\n) ENGINE=MyISAM */;\n\n"
        b"/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;\n"
        b"DELIMITER ;;\n"
        b"/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_fictif` "
        b"BEFORE INSERT ON `individus` FOR EACH ROW SET NEW.`nom` = TRIM(NEW.`nom`) */;;\n"
        b"DELIMITER ;\n\n"
        b"/*!50001 DROP TABLE IF EXISTS `vue_fictive`*/;\n"
        b"/*!50001 CREATE ALGORITHM=UNDEFINED */\n"
        b"/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */\n"
        b"/*!50001 VIEW `vue_fictive` AS select `individus`.`IDindividu` AS `IDindividu` from `individus` */;\n"
        b"/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;\n\n"
        b"-- Dump completed on 2026-10-12 14:00:00\n"
    )


class AnalyseDumpSQLTests(unittest.TestCase):
    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory(prefix="noe032-analyse-")
        self.rep = Path(self._dossier.name)
        self.chemin = self.rep / "fictive_data.sql"

    def tearDown(self):
        self._dossier.cleanup()

    def _analyser(self, contenu):
        self.chemin.write_bytes(contenu)
        return AnalyserDumpSQL(str(self.chemin))

    def test_objets_de_premier_niveau_avec_delimiteurs_crlf(self):
        # Cas master : test_sql_analysis_tracks_only_top_level_objects_with_crlf_delimiters
        analyse, erreur = self._analyser(
            b"CREATE TABLE `base_table` (`id` INTEGER);\r\n"
            b"DELIMITER ;;\r\n"
            b"/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ "
            b"/*!50003 TRIGGER `sample_trigger` BEFORE INSERT ON `base_table` "
            b"FOR EACH ROW\r\nBEGIN\r\n"
            b"  SET @texte = 'CREATE TABLE `not_a_real_table` (id INTEGER)';\r\n"
            b"END */;;\r\n"
            b"DELIMITER ;\r\n"
            b"/*!50001 CREATE ALGORITHM=UNDEFINED */\r\n"
            b"/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */\r\n"
            b"/*!50001 VIEW `sample_view` AS SELECT `id` FROM `base_table` */;\r\n"
        )
        self.assertIsNone(erreur)
        self.assertFalse(analyse["avec_manifeste"])
        self.assertEqual(analyse["objets"]["tables"], {"base_table"})
        self.assertEqual(analyse["objets"]["vues"], {"sample_view"})
        self.assertEqual(analyse["objets"]["triggers"], {"sample_trigger"})

    def test_toutes_les_categories_d_objets(self):
        # Cas master : _sql_with_all_supported_objects
        analyse, erreur = self._analyser(
            b"CREATE TABLE `base_table` (`id` INTEGER);\n"
            b"CREATE VIEW `sample_view` AS SELECT `id` FROM `base_table`;\n"
            b"DELIMITER ;;\n"
            b"CREATE DEFINER=`root`@`localhost` TRIGGER `sample_trigger` "
            b"BEFORE INSERT ON `base_table` FOR EACH ROW SET NEW.`id` = NEW.`id`;;\n"
            b"CREATE PROCEDURE `sample_procedure`() BEGIN SELECT 1; END;;\n"
            b"CREATE FUNCTION `sample_function`() RETURNS INTEGER DETERMINISTIC RETURN 1;;\n"
            b"CREATE EVENT `sample_event` ON SCHEDULE EVERY 1 DAY "
            b"DO INSERT INTO `base_table` (`id`) VALUES (1);;\n"
            b"DELIMITER ;\n"
        )
        self.assertIsNone(erreur)
        objets = analyse["objets"]
        self.assertEqual(objets["tables"], {"base_table"})
        self.assertEqual(objets["vues"], {"sample_view"})
        self.assertEqual(objets["triggers"], {"sample_trigger"})
        self.assertEqual(objets["procedures"], {"sample_procedure"})
        self.assertEqual(objets["fonctions"], {"sample_function"})
        self.assertEqual(objets["evenements"], {"sample_event"})

    def test_dump_mysqldump_synthetique_complet_accepte(self):
        analyse, erreur = self._analyser(_dump_mysqldump_synthetique())
        self.assertIsNone(erreur)
        self.assertEqual(analyse["objets"]["tables"], {"individus", "documents"})
        self.assertEqual(analyse["objets"]["vues"], {"vue_fictive"})
        self.assertEqual(analyse["objets"]["triggers"], {"trg_fictif"})

    def test_dump_synthetique_avec_manifeste_analyse_sans_l_enveloppe(self):
        self.chemin.write_bytes(_dump_mysqldump_synthetique())
        MODULE.AjouterManifesteIntegriteSQL(str(self.chemin))
        analyse, erreur = AnalyserDumpSQL(str(self.chemin))
        self.assertIsNone(erreur)
        self.assertTrue(analyse["avec_manifeste"])
        self.assertEqual(analyse["objets"]["tables"], {"individus", "documents"})

    def test_manifeste_altere_refuse_avant_analyse(self):
        self.chemin.write_bytes(b"CREATE TABLE `t` (id INT);\n")
        MODULE.AjouterManifesteIntegriteSQL(str(self.chemin))
        contenu = self.chemin.read_bytes().replace(b"`t`", b"`u`")
        analyse, erreur = self._analyser(contenu)
        self.assertIsNone(analyse)
        self.assertIn("SHA-256", erreur)

    def test_ancien_dump_tronque_en_pleine_instruction_refuse(self):
        # Cas master : test_network_restore_rejects_legacy_sql_truncated_mid_statement
        analyse, erreur = self._analyser(b"CREATE TABLE `broken_table` (id INTEGER")
        self.assertIsNone(analyse)
        self.assertIn("incomplete", erreur)

    def test_ancien_dump_tronque_dans_un_blob_refuse(self):
        complet = _dump_mysqldump_synthetique()
        coupure = complet.index(b"INSERT INTO `documents`") + 5000
        analyse, erreur = self._analyser(complet[:coupure])
        self.assertIsNone(analyse)
        self.assertIn("non ferme", erreur)

    def test_troncatures_successives_jamais_acceptees_en_pleine_instruction(self):
        complet = _dump_mysqldump_synthetique()
        debut_blob = complet.index(b"INSERT INTO `documents`")
        for coupure in range(debut_blob + 1, debut_blob + 20000, 997):
            with self.subTest(coupure=coupure):
                analyse, erreur = self._analyser(complet[:coupure])
                self.assertIsNone(analyse)
                self.assertIsNotNone(erreur)

    def test_delimiteur_non_retabli_refuse(self):
        analyse, erreur = self._analyser(
            b"CREATE TABLE `t` (id INT);\nDELIMITER ;;\n"
            b"CREATE PROCEDURE `p`() BEGIN SELECT 1; END;;\n"
        )
        self.assertIsNone(analyse)
        self.assertIn("delimiteur", erreur)

    def test_commentaire_non_ferme_refuse(self):
        analyse, erreur = self._analyser(b"CREATE TABLE `t` (id INT);\n/*!40101 SET NAMES utf8 ")
        self.assertIsNone(analyse)
        self.assertIsNotNone(erreur)

    def test_dump_sans_objet_restaurable_refuse(self):
        # Cas master : test_network_restore_rejects_noop_sql_before_mysql
        analyse, erreur = self._analyser(b"SELECT 1;")
        self.assertIsNone(analyse)
        self.assertIn("aucun objet", erreur)

    def test_dump_vide_ou_blanc_refuse(self):
        for contenu in (b"", b"  \n\t\n"):
            with self.subTest(contenu=contenu):
                analyse, erreur = self._analyser(contenu)
                self.assertIsNone(analyse)
                self.assertIn("vide", erreur)

    def test_fichier_absent_refuse_sans_exception(self):
        analyse, erreur = AnalyserDumpSQL(str(self.rep / "absent.sql"))
        self.assertIsNone(analyse)
        self.assertIsNotNone(erreur)


if __name__ == "__main__":
    unittest.main()
