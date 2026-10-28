# -*- coding: utf-8 -*-
"""MySQL 5.7 jetable : BLOB binaire >24 Mio, archive et restauration complète.

    NOETHYS_TEST_MYSQL437_RUNTIME=<racine contenant mysql-5.7.44-winx64 et mysql-data>

Le serveur doit être explicitement démarré sur 127.0.0.1:3407. Son datadir est
vérifié AVANT le premier CREATE/DROP. Aucun profil Noethys n'est lu.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from tests._mysql_backup_test_support import moteur


def integrite():
    chemin = Path(__file__).resolve().parents[1] / "noethys/Utils/UTILS_SQL_Integrite.py"
    spec = importlib.util.spec_from_file_location("integrite_mysql437", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(os.environ.get("NOETHYS_TEST_MYSQL437_RUNTIME"), "recette MySQL 437 volontaire")
class BackupMySQL437ReelTests(unittest.TestCase):
    def test_blob_binaire_depasse_24_mio_et_archive_restaurable(self):
        runtime = Path(os.environ["NOETHYS_TEST_MYSQL437_RUNTIME"]).resolve()
        binary = runtime / "mysql-5.7.44-winx64/bin"
        commande = [str(binary / "mysql.exe"), "--no-defaults", "--host=127.0.0.1",
                    "--port=3407", "--user=root", "--max-allowed-packet=1G", "-N", "-B"]
        def sql(requete=None, fichier=None):
            if fichier:
                with open(fichier, "rb") as f:
                    return subprocess.run(commande, stdin=f, capture_output=True, check=True, timeout=120).stdout
            return subprocess.run(commande + ["-e", requete], capture_output=True, check=True, timeout=30).stdout
        # Garde indépendante des données du test, avant toute écriture SQL.
        retour = sql("SELECT @@port, @@datadir, @@version;").decode().strip().split("\t")
        self.assertEqual(retour[0], "3407")
        self.assertTrue(retour[2].startswith("5.7."))
        datadir = Path(retour[1].replace("\\\\", "\\")).resolve()
        self.assertEqual(datadir, (runtime / "mysql-data").resolve())
        bases = ["noe437_synth_data", "noe437_synth_documents"]
        existantes = sql("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME IN "
                         "('noe437_synth_data','noe437_synth_documents');")
        self.assertEqual(existantes, b"", "Ne jamais réutiliser une base existante")
        try:
            sql("CREATE DATABASE noe437_synth_data; CREATE TABLE noe437_synth_data.temoin (id INT); "
                "INSERT INTO noe437_synth_data.temoin VALUES (437); "
                "CREATE DATABASE noe437_synth_documents; "
                "CREATE TABLE noe437_synth_documents.documents (id INT, document LONGBLOB); "
                "INSERT INTO noe437_synth_documents.documents VALUES "
                "(1, REPEAT(UNHEX('0001275C80FF'), 4543829));")
            attendu = sql("SELECT COUNT(*), MAX(OCTET_LENGTH(document)), MIN(SHA2(document,256)) "
                          "FROM noe437_synth_documents.documents;")
            self.assertGreater(int(attendu.split(b"\t")[1]), 24 * 1024 * 1024)
            with tempfile.TemporaryDirectory(prefix="noe437-vrai-") as rep:
                rep = Path(rep)
                login = rep / "client.cnf"
                login.write_text("[client]\nhost=127.0.0.1\nport=3407\nuser=root\n", encoding="utf-8")
                # Contre-épreuve : limite historique réelle, pas une simulation.
                with open(rep / "historique.sql", "wb") as sortie:
                    ancien = subprocess.run([str(binary / "mysqldump.exe"),
                        "--defaults-file=" + str(login), "--opt", "--single-transaction",
                        "--skip-lock-tables", "--databases", bases[1]],
                        stdout=sortie, stderr=subprocess.PIPE, timeout=60)
                self.assertNotEqual(ancien.returncode, 0, "La contre-épreuve doit échouer")
                self.assertIn(b"2020", ancien.stderr)
                archive = rep / "complete.nod"
                bilan = moteur().CreerArchive(binary / "mysqldump.exe", login, bases,
                                               archive, integrite())
                self.assertTrue(bilan["succes"], bilan)
                self.assertTrue(all(e["fin_mysqldump"] for e in bilan["exports"]))
                with zipfile.ZipFile(archive) as z:
                    self.assertIsNone(z.testzip())
                    self.assertEqual(z.namelist(), [b + ".sql" for b in bases])
                    for base in bases:
                        z.extract(base + ".sql", rep)
                # Retirer les sources du serveur jetable prouve une restauration,
                # et non une relecture accidentelle de tables restées en place.
                sql("DROP DATABASE noe437_synth_data; DROP DATABASE noe437_synth_documents;")
                for base in bases:
                    sql(fichier=rep / (base + ".sql"))
                obtenu = sql("SELECT COUNT(*), MAX(OCTET_LENGTH(document)), MIN(SHA2(document,256)) "
                             "FROM noe437_synth_documents.documents;")
                self.assertEqual(obtenu, attendu)
                self.assertEqual(sql("SELECT id FROM noe437_synth_data.temoin;").strip(), b"437")
                preuve = {"mysql": retour[2], "historique_code": ancien.returncode,
                          "blob_octets": int(attendu.split(b"\t")[1]), "archive_crc": "OK",
                          "fin_dumps": True, "restauration_sha256_identique": True,
                          "bases": bases, "reseau": "127.0.0.1:3407 uniquement"}
                (runtime / "preuve-recette-synthetique.json").write_text(
                    json.dumps(preuve, indent=2), encoding="utf-8")
        finally:
            for base in bases:
                sql("DROP DATABASE IF EXISTS `%s`;" % base)


if __name__ == "__main__":
    unittest.main()
