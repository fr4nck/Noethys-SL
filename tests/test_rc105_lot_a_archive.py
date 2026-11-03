# -*- coding: utf-8 -*-
"""Lot A : inspection de ZIP avec dumps fictifs, sans MySQL ni donnees PMSL."""
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_Archive_audit_RC105 as AUDIT
from Utils import UTILS_SQL_Integrite as SQL


class ArchivesTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(prefix="rc105-archive-a-")
        self.addCleanup(self.d.cleanup)
        self.base = Path(self.d.name)
        self.archive = self.base / "archive_de_test.nod"

    def sql(self, cat="DATA", manif=True):
        chemin = self.base / (cat + ".sql")
        contenu = (
            b"-- exemple fictif Noethys / aucune donnee reelle\n"
            + b"CREATE TABLE `exemple` (`id` integer);\n"
            + b"INSERT INTO `exemple` VALUES (1);\n"
            + b"-- Dump completed on 2026-01-01 00:00:00\n"
        )
        chemin.write_bytes(contenu)
        if manif:
            SQL.AjouterManifesteIntegriteSQL(chemin)
        return chemin.read_bytes()

    def creer(self, contenus=None):
        if contenus is None:
            contenus = {cat + ".sql": self.sql(cat) for cat in ("DATA", "PHOTOS", "DOCUMENTS")}
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for nom, contenu in contenus.items():
                zf.writestr(nom, contenu)
        return self.archive

    def test_trois_dumps_valides_lecture_seule(self):
        chemin = self.creer()
        empreinte_avant = hashlib.sha256(chemin.read_bytes()).digest()
        bilan = AUDIT.InspecterArchive(chemin)
        self.assertEqual(bilan["verdict"], "PASS", bilan["detail"])
        self.assertFalse(bilan["restauration_prouvee"])
        self.assertEqual(set(bilan["bases"]), {"DATA", "PHOTOS", "DOCUMENTS"})
        self.assertEqual(hashlib.sha256(chemin.read_bytes()).digest(), empreinte_avant)
        self.assertEqual(sorted(x.name for x in self.base.iterdir()),
                         ["DATA.sql", "DOCUMENTS.sql", "PHOTOS.sql", "archive_de_test.nod"])

    def test_noms_sql_prod_typiques_acceptes(self):
        self.creer({"pelemele.sql": self.sql(), "pelemele_PHOTOS.sql": self.sql("PHOTOS"),
                    "pelemele_DOCUMENTS.sql": self.sql("DOCUMENTS")})
        self.assertEqual(AUDIT.InspecterArchive(self.archive)["verdict"], "PASS")

    def test_dumps_anciens_non_certifies(self):
        self.creer({cat + ".sql": self.sql(cat, manif=False)
                    for cat in ("DATA", "PHOTOS", "DOCUMENTS")})
        retour = AUDIT.InspecterArchive(self.archive)
        self.assertEqual(retour["verdict"], "LEGACY")
        self.assertFalse(retour["restauration_prouvee"])

    def test_manifest_modifie_refuse(self):
        docs = self.sql("DOCUMENTS")
        contenu = {"DATA.sql": self.sql(), "PHOTOS.sql": self.sql("PHOTOS"),
                   "DOCUMENTS.sql": docs.replace(b"VALUES (1)", b"VALUES (2)")}
        self.creer(contenu)
        retour = AUDIT.InspecterArchive(self.archive)
        self.assertEqual(retour["verdict"], "FAIL")
        self.assertIn("empreinte SQL", retour["detail"])

    def test_manifeste_correct_sur_sql_tronque_ne_vaut_pas_sauvegarde(self):
        # L'empreinte V1 authentifie des octets, pas leur origine mysqldump.
        fichier = self.base / "DOCUMENTS.sql"
        fichier.write_bytes(b"CREATE TABLE `t` (id INT);\nINSERT INTO `t` VALUES (1);\n")
        SQL.AjouterManifesteIntegriteSQL(fichier)
        self.creer({"DATA.sql": self.sql(), "PHOTOS.sql": self.sql("PHOTOS"),
                    "DOCUMENTS.sql": fichier.read_bytes()})
        retour = AUDIT.InspecterArchive(self.archive)
        self.assertEqual(retour["verdict"], "FAIL", retour)
        self.assertIn("ligne finale mysqldump", retour["detail"])

    def test_document_manquant_refuse(self):
        self.creer({"DATA.sql": self.sql(), "PHOTOS.sql": self.sql("PHOTOS")})
        retour = AUDIT.InspecterArchive(self.archive)
        self.assertEqual(retour["verdict"], "FAIL")
        self.assertIn("DOCUMENTS", retour["detail"])

    def test_ancien_dump_tronque_refuse(self):
        fichiers = {cat + ".sql": self.sql(cat) for cat in ("DATA", "PHOTOS", "DOCUMENTS")}
        fichiers["DOCUMENTS.sql"] = b"CREATE TABLE `t` (id int);\n"
        self.creer(fichiers)
        self.assertEqual(AUDIT.InspecterArchive(self.archive)["verdict"], "FAIL")

    def test_doublons_et_traversee_refuses(self):
        contenu = {cat + ".sql": self.sql(cat) for cat in ("DATA", "PHOTOS", "DOCUMENTS")}
        for nom in ("../confidentiel.sql", "rep/../../secret", "DATA2.sql"):
            with self.subTest(nom=nom):
                self.creer(dict(contenu, **{nom: b"faux"}))
                self.assertEqual(AUDIT.InspecterArchive(self.archive)["verdict"], "FAIL")

    def test_annexe_non_sql_crc_corrompu_refusee(self):
        # Une archive NOD peut contenir des fichiers annexes au-dela des SQL.
        # Un SQL intact ne doit pas masquer la corruption d'une autre entree.
        self.creer()
        with zipfile.ZipFile(self.archive, "a") as zf:
            zf.writestr("annexe_fictive.bin", b"FICHIER FICTIF " * 64,
                        compress_type=zipfile.ZIP_STORED)
        premier = AUDIT.InspecterArchive(self.archive)
        self.assertEqual(premier["verdict"], "PASS", premier["detail"])
        with zipfile.ZipFile(self.archive) as zf:
            info = zf.getinfo("annexe_fictive.bin")
            debut = info.header_offset
        with open(self.archive, "r+b") as fichier:
            fichier.seek(debut + 26)
            nom_long = int.from_bytes(fichier.read(2), "little")
            extra_long = int.from_bytes(fichier.read(2), "little")
            fichier.seek(debut + 30 + nom_long + extra_long + 8)
            fichier.write(b"X")
        resultat = AUDIT.InspecterArchive(self.archive)
        self.assertEqual(resultat["verdict"], "FAIL", resultat)

    def test_archive_corrompue_refusee(self):
        self.archive.write_bytes(b"CECI N'EST PAS UN ZIP")
        self.assertEqual(AUDIT.InspecterArchive(self.archive)["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()
