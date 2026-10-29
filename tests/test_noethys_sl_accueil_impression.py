# -*- coding: utf-8 -*-
"""#436 : impression A4 anonyme suivant la fiche enfant papier PMSL."""
import os
import re
import tempfile
import unittest
from Utils import UTILS_Accueil_impression as Impression

try:
    import reportlab
except ImportError:
    reportlab = None


class ContratPapier(unittest.TestCase):
    def test_rubriques_page_1_identiques_au_formulaire(self):
        self.assertEqual(Impression.SECTIONS_P1, (
            "IDENTITÉ", "RESPONSABLE LÉGAL n°1",
            "RESPONSABLE LÉGAL n°2", "ACCOMPAGNANTS",
            "VACCINATIONS", "MÉDECIN TRAITANT"))

    def test_rubriques_page_2_identiques(self):
        self.assertEqual(Impression.SECTIONS_P2,
                         ("MALADIES ET ALLERGIES", "AUTORISATIONS DIVERSES"))

    def test_quatre_autorisations_du_document(self):
        self.assertEqual(tuple(a for a,b in Impression.AUTORISATIONS_PAPIER),
            ("photos_site_imprimes", "maquillage", "piscine_baignade",
             "activites_physiques"))
        self.assertIn("pelemele.org", Impression.AUTORISATIONS_PAPIER[0][1])

    def test_destination_et_fiche_invalides_refusees(self):
        with self.assertRaises(ValueError):
            Impression.GenererPDF("fiche.txt", {})
        with self.assertRaises(ValueError):
            Impression.GenererPDF("fiche.pdf", None)


@unittest.skipIf(reportlab is None, "reportlab absent")
class EditionDeuxPages(unittest.TestCase):
    def test_creation_deux_pages_A4_donnees_fictives(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = os.path.join(tmp, "fiche-fictive.pdf")
            data = {
                "nom": "FICTIF", "prenom": "Enfant", "date_naiss": "2017-01-09",
                "alsh": "La Guerche", "annee": "2026-2027",
                "responsables": [{"identite": "Parent TEST"}],
                "vaccinations": "Dossier Noethys existant",
                "medecin": "Docteur FICTIF",
                "medical": ["FICHE MEDICALE FICTIVE"],
                "autorisations": {
                    "photos_site_imprimes": "non",
                    "maquillage": "oui",
                    "piscine_baignade": "non_renseigne",
                    "activites_physiques": "oui",
                },
            }
            self.assertEqual(Impression.GenererPDF(chemin, data), chemin)
            data = open(chemin, "rb").read()
            self.assertTrue(data.startswith(b"%PDF-"))
            self.assertGreater(len(data), 3500)
            self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", data)), 2)

    def test_sans_medical_ne_lit_pas_de_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "fiche.pdf")
            Impression.GenererPDF(out, {"nom": "FICTIF", "autorisations": {}})
            self.assertTrue(os.path.isfile(out))


if __name__ == "__main__":
    unittest.main()
