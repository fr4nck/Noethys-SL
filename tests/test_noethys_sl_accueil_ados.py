# -*- coding: utf-8 -*-
"""Lot C : Club ados, 2 pages sans données familiales ni duplication."""
import os
import re
import tempfile
import unittest
from Utils import UTILS_Accueil_impression as I
from Utils import UTILS_Accueil_autorisations as A
from Utils import UTILS_Fiche_accueil_enfant as F

try:
    import reportlab
except ImportError:
    reportlab = None


class ContratAdos(unittest.TestCase):
    def test_cinq_autorisations_dont_transport_independant(self):
        codes = tuple(c for c, _label in I.AUTORISATIONS_ADOS)
        self.assertEqual(codes, (
            "photos_site_imprimes", "maquillage", "piscine_baignade",
            "activites_physiques", "transport_ados"))
        self.assertIn("transport_ados", A.TYPES)
        self.assertIn("transport_ados", F.AUTORISATIONS)
        self.assertIn("depart_seul", A.TYPES)
        self.assertNotIn("transport_ados",
                         tuple(c for c, _label in I.AUTORISATIONS_PAPIER))

    def test_generateur_refuse_donnees_non_dict(self):
        with self.assertRaises(ValueError):
            I.GenererPDFAdos("ados.pdf", None)


@unittest.skipIf(reportlab is None, "reportlab absent")
class PDFAdos(unittest.TestCase):
    def donnees(self):
        return {
            "nom": "FICTIF", "prenom": "Ado", "sexe": "F",
            "date_naiss": "2011-05-10", "annee": "2026-2027",
            "classe": "Seconde fictive",
            "responsables": [
                {"identite": "Parent FICTIF", "adresse": "Rue Exemple",
                 "telephone": "06 00 00 00 00"}],
            "accompagnants": [
                {"nom": "CONTACT", "prenom": "Fictif", "lien": "Tante",
                 "telephone_court": "02 00 00 00 00"}],
            "vaccinations": "15/07/2025",
            "medecin": "Docteur Fictif",
            "pai": "Non renseigné",
            "allergies": "Non renseigné",
            "traitement": "Non renseigné",
            "medical": [],
            "autorisations": {
                "photos_site_imprimes": "oui", "maquillage": "non",
                "piscine_baignade": "oui", "activites_physiques": "oui",
                "transport_ados": "oui", "depart_seul": "non",
            },
        }

    class Capture:
        def __init__(self):
            self.txt = []
            self.centres = []
            self.crosses = []
        def drawString(self, x, y, txt):
            self.txt.append((x, y, txt))
            if txt == "X":
                self.crosses.append((x, y))
        def drawCentredString(self, x, y, txt):
            self.centres.append(txt)
        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    def test_page1_ados_et_contacts_sans_choix_depart_seul(self):
        c = self.Capture()
        donnees = dict(self.donnees(), modele="ados")
        I._page1(c, donnees)
        tous = [texte for _x, _y, texte in c.txt] + c.centres
        self.assertIn("FICHE ADOS", tous)
        self.assertIn("CONTACT", tous)
        self.assertTrue(any("changement de cette liste" in t for t in tous))
        self.assertFalse(any("quitter l'ALSH seul" in t for t in tous))
        self.assertFalse(any("ALSH fréquenté" in t for t in tous))

    def test_page2_transport_et_depart_seul_ne_se_confondent_pas(self):
        c = self.Capture()
        donnees = dict(self.donnees(), modele="ados",
                       autorisation_modele="Fiche Ados 2026-11")
        I._page2(c, donnees)
        textes = [s for _x, _y, s in c.txt] + c.centres
        self.assertIn("Transport", textes)
        self.assertTrue(any("repartir seul du Club ados" in t for t in textes))
        self.assertTrue(any("Fiche Ados 2026-11" in t for t in textes))
        # Les cinq cases de la grille plus le départ seul sont indépendants :
        # six choix oui/non parmi sept? 5 dans grille + 1 départ.
        self.assertEqual(len(c.crosses), 6)

    def test_depart_seul_non_renseigne_ne_coche_pas_la_case(self):
        donnees = dict(self.donnees(), modele="ados")
        donnees["autorisations"] = {}
        c = self.Capture()
        I._page2(c, donnees)
        self.assertEqual(c.crosses, [])

    def test_generer_pdf_deux_pages_et_ne_pas_modifier_source(self):
        donnees = self.donnees()
        original = dict(donnees)
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, "fiche-ados-fictive.pdf")
            self.assertEqual(I.GenererPDFAdos(chemin, donnees), chemin)
            contenu = open(chemin, "rb").read()
            self.assertTrue(contenu.startswith(b"%PDF-"))
            self.assertEqual(
                len(re.findall(rb"/Type\s*/Page\b", contenu)), 2)
        self.assertEqual(donnees, original)
        self.assertNotIn("modele", donnees)


if __name__ == "__main__":
    unittest.main()
