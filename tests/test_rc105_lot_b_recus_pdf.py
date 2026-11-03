# -*- coding: utf-8 -*-
"""Lot B : un reçu absent, vide ou tronque n'est jamais annonce comme envoye.

Tous les PDF sont fictifs ; aucun destinataire reel, aucun SMTP, aucune base.
"""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_Documents_Controle_RC105 as CONTROLE

try:
    from Utils import UTILS_Envoi_email as ENVOI
    IMPORT_OK = True
except ImportError:
    IMPORT_OK = False


class ControlePDFTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rc105-recus-b-")
        self.addCleanup(self.temp.cleanup)
        self.chemin = Path(self.temp.name, "RECU.pdf")

    def test_fichier_absent_ou_chemin_invalide(self):
        for chemin in (None, False, "", self.chemin):
            with self.subTest(chemin=repr(chemin)):
                self.assertFalse(CONTROLE.PDFPretPourEnvoi(chemin))

    def test_pdf_vide_refuse(self):
        self.chemin.write_bytes(b"")
        self.assertFalse(CONTROLE.PDFPretPourEnvoi(self.chemin))

    def test_fausse_extension_refusee(self):
        self.chemin.write_bytes(b"CE N'EST PAS UN PDF\n%%EOF\n")
        self.assertFalse(CONTROLE.PDFPretPourEnvoi(self.chemin))

    def test_pdf_tronque_refuse(self):
        self.chemin.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\n")
        self.assertFalse(CONTROLE.PDFPretPourEnvoi(self.chemin))

    def test_pdf_fictif_complet_accepte_sans_mutation(self):
        self.chemin.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
        original = hashlib.sha256(self.chemin.read_bytes()).digest()
        self.assertTrue(CONTROLE.PDFPretPourEnvoi(self.chemin))
        self.assertEqual(original, hashlib.sha256(self.chemin.read_bytes()).digest())

    def test_pdf_avec_fin_mauvaise_refuse(self):
        self.chemin.write_bytes(b"%PDF-1.4\n%%EOF\nINJECTION APRES FIN")
        self.assertFalse(CONTROLE.PDFPretPourEnvoi(self.chemin))


@unittest.skipUnless(IMPORT_OK, "wx et dependances Noethys necessaires")
class ParcoursRecuTests(ControlePDFTests):
    def test_recu_physiquement_tronque_n_ouvre_jamais_messagerie(self):
        self.chemin.write_bytes(b"%PDF-1.4\n1 0 obj\n")
        with mock.patch("Dlg.DLG_Mailer.Dialog", side_effect=AssertionError("envoi interdit")):
            res = ENVOI.EnvoiEmailFamille(
                IDfamille=12, nomDoc=str(self.chemin),
                categorie="recu_reglement",
                listeAdresses=["test@example.org"], visible=False,
                CreationPDF=lambda nomDoc, afficherDoc: {"identifiant": "fictif"})
        self.assertFalse(res)
        self.assertFalse(self.chemin.exists(), "Un PDF incomplet doit etre purge")

    def test_generation_pdf_echouee_purge_fichier_partiel(self):
        self.chemin.write_bytes(b"%PDF-1.4\nPARTIEL")
        with mock.patch("Dlg.DLG_Mailer.Dialog", side_effect=AssertionError("envoi interdit")):
            res = ENVOI.EnvoiEmailFamille(
                IDfamille=12, nomDoc=str(self.chemin),
                categorie="recu_reglement",
                listeAdresses=["test@example.org"], visible=False,
                CreationPDF=lambda nomDoc, afficherDoc: False)
        self.assertFalse(res)
        self.assertFalse(self.chemin.exists())

    def test_parcours_direct_reglement_applique_meme_prevol(self):
        chemin = (ROOT / "noethys" / "Dlg" / "DLG_Saisie_reglement.py")
        src = chemin.read_text(encoding="utf8")
        self.assertIn("UTILS_Documents_Controle_RC105.PDFPretPourEnvoi(nomDoc)", src)


if __name__ == "__main__":
    unittest.main()
