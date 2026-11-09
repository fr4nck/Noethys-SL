# -*- coding: utf-8 -*-
"""UI-432K : un rendu PDF temporaire n'est publie qu'apres succes."""
import os
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "noethys") not in sys.path:
    sys.path.insert(0, str(ROOT / "noethys"))
from Utils import UTILS_PDF_securise  # noqa: E402

PDF_FICTIF = b"%PDF-1.4\n" + b"%PDF fictif de recette\n" + b"%%EOF\n"


class EcritureAtomiquePDFTests(unittest.TestCase):
    def test_pdf_complet_rendu_et_valide(self):
        with tempfile.TemporaryDirectory(prefix="ui432k-pdf-") as rep:
            cible = os.path.join(rep, "Facture fictive.pdf")
            chemins = []
            def rendre(chemin):
                chemins.append(chemin)
                Path(chemin).write_bytes(PDF_FICTIF)
            self.assertEqual(UTILS_PDF_securise.Generer(cible, rendre), cible)
            self.assertEqual(Path(cible).read_bytes(), PDF_FICTIF)
            self.assertNotEqual(chemins[0], cible)
            self.assertEqual(sorted(os.listdir(rep)), ["Facture fictive.pdf"])

    def test_exception_de_rendu_ne_detruit_pas_original(self):
        with tempfile.TemporaryDirectory(prefix="ui432k-pdf-") as rep:
            cible = Path(rep) / "Facture.pdf"
            cible.write_bytes(PDF_FICTIF)
            def rendre(chemin):
                Path(chemin).write_bytes(b"%PDF-1.4\nINCOMPLET")
                raise RuntimeError("Rendu interrompu")
            with self.assertRaisesRegex(RuntimeError, "Rendu interrompu"):
                UTILS_PDF_securise.Generer(str(cible), rendre)
            self.assertEqual(cible.read_bytes(), PDF_FICTIF)
            self.assertEqual(os.listdir(rep), ["Facture.pdf"])

    def test_signature_pdf_invalide_refusee_sans_pdf_final(self):
        with tempfile.TemporaryDirectory(prefix="ui432k-pdf-") as rep:
            cible = str(Path(rep) / "Incomplet.pdf")
            with self.assertRaisesRegex(ValueError, "PDF incomplet"):
                UTILS_PDF_securise.Generer(
                    cible, lambda f: Path(f).write_bytes(b"NON PDF INVALIDE" * 10))
            self.assertEqual(os.listdir(rep), [])

    def test_pdf_sans_fin_de_fichier_refuse(self):
        with tempfile.TemporaryDirectory(prefix="ui432k-pdf-") as rep:
            cible = str(Path(rep) / "SansFin.pdf")
            with self.assertRaisesRegex(ValueError, "PDF incomplet"):
                UTILS_PDF_securise.Generer(
                    cible, lambda f: Path(f).write_bytes(
                        b"%PDF-1.4\n" + b"données fictives " * 12))
            self.assertEqual(os.listdir(rep), [])

    def test_pdf_existant_ne_change_qu_apres_succes(self):
        with tempfile.TemporaryDirectory(prefix="ui432k-pdf-") as rep:
            cible = Path(rep) / "Facture.pdf"
            cible.write_bytes(b"ANCIEN CONTENU FICTIF")
            UTILS_PDF_securise.Generer(
                str(cible), lambda f: Path(f).write_bytes(PDF_FICTIF))
            self.assertEqual(cible.read_bytes(), PDF_FICTIF)
            self.assertEqual(os.listdir(rep), ["Facture.pdf"])


if __name__ == "__main__":
    unittest.main()
