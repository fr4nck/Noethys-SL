# -*- coding: utf-8 -*-
"""Lot C : edition PDF familiale sure, sans base ni alteration du modele PMSL."""
import copy
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from Utils import UTILS_Accueil_familles_impression as F


def _famille():
    return {
        "IDfamille": 17, "regime": "CAF", "num_allocataire": "TEST",
        "responsables": [{"nom": "PARENT FICTIF", "prenom": "Une"}],
        "enfants": [
            {"IDindividu": 11, "nom": "ADO", "prenom": "Fictif",
             "date_naiss": "03/05/2011", "accueils": ["ALSH BAIS", "CLUB ADOS BAIS"]},
            {"IDindividu": 12, "nom": "ENFANT", "prenom": "Fictif",
             "date_naiss": "11/06/2018", "accueils": ["ALSH MOUTIERS"]},
        ],
    }


@unittest.skipIf(F.A4 is None, "ReportLab absent")
class FamillePDFTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(prefix="rc105-lot-c-")
        self.addCleanup(self.d.cleanup)
        self.pdf = Path(self.d.name) / "famille-unique.pdf"
        self.famille = _famille()

    def test_erreur_page2_ne_remplace_pas_l_ancien_pdf(self):
        ancien = b"%PDF-1.4\nancienne fiche de test\n%%EOF\n"
        self.pdf.write_bytes(ancien)
        with mock.patch.object(F, "_page2", side_effect=RuntimeError("panne de rendu simulee")):
            with self.assertRaisesRegex(RuntimeError, "panne de rendu"):
                F.GenererPDF(str(self.pdf), self.famille, modele="famille")
        self.assertEqual(self.pdf.read_bytes(), ancien)
        self.assertEqual(os.listdir(self.d.name), ["famille-unique.pdf"])

    def test_pdf_nouveau_entier_deux_pages_et_sans_temporaire(self):
        avant = copy.deepcopy(self.famille)
        self.assertEqual(F.GenererPDF(str(self.pdf), self.famille, modele="famille"),
                         str(self.pdf))
        octets = self.pdf.read_bytes()
        self.assertTrue(octets.startswith(b"%PDF-"))
        self.assertTrue(octets.rstrip().endswith(b"%%EOF"))
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", octets)), 2)
        self.assertEqual(os.listdir(self.d.name), ["famille-unique.pdf"])
        self.assertEqual(self.famille, avant)

    def test_reimpression_atomique_remplace_uniquement_apres_validation(self):
        self.pdf.write_bytes(b"%PDF-1.4\nancienne impression\n%%EOF\n")
        self.assertEqual(F.GenererPDF(str(self.pdf), self.famille, modele="famille"),
                         str(self.pdf))
        self.assertNotIn(b"ancienne impression", self.pdf.read_bytes())
        self.assertEqual(len(list(Path(self.d.name).glob("*.pdf"))), 1)

    def test_plus_de_quatre_enfants_refuses_sans_detruire_ancien_pdf(self):
        self.pdf.write_bytes(b"ancienne fiche")
        self.famille["enfants"] = self.famille["enfants"] * 3
        with self.assertRaisesRegex(ValueError, "4 lignes"):
            F.GenererPDF(str(self.pdf), self.famille, modele="famille")
        self.assertEqual(self.pdf.read_bytes(), b"ancienne fiche")
        self.assertEqual(os.listdir(self.d.name), ["famille-unique.pdf"])


if __name__ == "__main__":
    unittest.main()
