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
                    "depart_seul": "non_renseigne",
                },
            }
            self.assertEqual(Impression.GenererPDF(chemin, data), chemin)
            with open(chemin, "rb") as fichier:
                data = fichier.read()
            self.assertTrue(data.startswith(b"%PDF-"))
            self.assertGreater(len(data), 3500)
            self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", data)), 2)

    def test_coordonnees_et_accompagnants_apparaissent_dans_les_cases(self):
        class FauxCanvas:
            def __init__(self):
                self.textes = []
            def drawString(self, x, y, texte):
                self.textes.append((x, y, texte))
            def __getattr__(self, nom):
                return lambda *args, **kwargs: None

        c = FauxCanvas()
        Impression._page1(c, {
            "nom": "ENFANT", "prenom": "Fictif", "sexe": "F",
            "alsh": "Moutiers", "classe": "GS (Classe Fictive)",
            "vaccinations": "15/07/2025 (2 vaccins enregistrés)",
            "responsables": [
                {"identite": "PARENT Premier", "adresse": "5 rue Fictive",
                 "telephone": "Mobile : 06 00 11"},
                {"identite": "PARENT Deuxieme", "adresse": "2 place Exemple",
                 "telephone": "Domicile : 02 00 22"},
            ],
            "accompagnants": [
                {"nom": "TANTE", "prenom": "Exemple",
                 "lien": "tante", "telephone_court": "06 00 33"},
                {"nom": "VOISIN", "prenom": "Exemple",
                 "lien": "voisin", "telephone_court": "06 00 44"},
            ],
        })
        valeurs = [texte for _x, _y, texte in c.textes]
        for attendu in ("Moutiers", "GS (Classe Fictive)", "F",
                        "15/07/2025", "2 vaccins enregistrés",
                        "PARENT Premier", "5 rue Fictive", "06 00 11",
                        "PARENT Deuxieme", "2 place Exemple", "02 00 22",
                        "TANTE", "Exemple", "tante", "06 00 33",
                        "VOISIN", "voisin", "06 00 44"):
            self.assertTrue(any(attendu in texte for texte in valeurs),
                            msg=attendu)
        # Les personnes figurent dans les cellules et non dans le titre.
        self.assertTrue(any(texte == "TANTE" for _x, _y, texte in c.textes))
        # Les cinq lignes sont tracees, et non uniquement les trois premieres.
        class Mesure:
            def __init__(self):
                self.traits = []
            def line(self, x1, y1, x2, y2):
                self.traits.append((x1, y1, x2, y2))
            def __getattr__(self, _nom):
                return lambda *args, **kwargs: None
        c2 = Mesure()
        Impression._page1(c2, {"accompagnants": []})
        self.assertEqual(sum(
            1 for x1, y1, x2, y2 in c2.traits
            if x1 == x2 and abs(y1 - y2) >= 90), 3)

    def test_depart_seul_oui_non_non_renseigne_et_conflit_sur_page1(self):
        class FauxCanvas:
            def __init__(self):
                self.textes = []
                self.cases = []
            def drawString(self, x, y, txt):
                self.textes.append((x, y, txt))
            def rect(self, x, y, w, h, **kwargs):
                if w == 9 and h == 9:
                    self.cases.append((x, y))
            def __getattr__(self, nom):
                return lambda *args, **kwargs: None

        attentes = {
            "oui": [393],
            "non": [453],
            "non_renseigne": [],
            "expire": [],
            "a_verifier": [],
        }
        for statut, x_attendus in attentes.items():
            with self.subTest(statut=statut):
                c = FauxCanvas()
                Impression._page1(c, {
                    "accompagnants": [],
                    "autorisations": {"depart_seul": statut},
                })
                self.assertTrue(any("quitter l'ALSH seul" in texte
                                    for _x, _y, texte in c.textes))
                cases_cochees = [int(x) for x, _y, txt in c.textes if txt == "X"]
                self.assertEqual(cases_cochees, x_attendus)
                if statut in ("oui", "non", "non_renseigne"):
                    self.assertEqual(len(c.cases), 2)
                else:
                    self.assertEqual(len(c.cases), 0)
                    self.assertTrue(any(txt == "À vérifier"
                                        for _x, _y, txt in c.textes))

    def test_depart_seul_n_empeche_pas_cinq_accompagnants_et_vaccination(self):
        class FauxCanvas:
            def __init__(self):
                self.textes = []
            def drawString(self, x, y, txt):
                self.textes.append(txt)
            def __getattr__(self, nom):
                return lambda *args, **kwargs: None
        c = FauxCanvas()
        Impression._page1(c, {
            "vaccinations": "15/07/2025",
            "accompagnants": [
                {"nom": "NOM%d" % i, "prenom": "Test",
                 "lien": "Parent", "telephone_court": "000"}
                for i in range(5)],
            "autorisations": {"depart_seul": "oui"},
        })
        self.assertTrue(any("NOM4" in t for t in c.textes))
        self.assertTrue(any("15/07/2025" in t for t in c.textes))
        self.assertTrue(any("quitter l'ALSH seul" in t for t in c.textes))

    def test_page2_affiche_pai_allergies_traitements_et_consignes(self):
        class FauxCanvas:
            def __init__(self):
                self.textes = []
            def drawString(self, x, y, texte):
                self.textes.append(texte)
            def __getattr__(self, nom):
                return lambda *args, **kwargs: None

        c = FauxCanvas()
        Impression._page2(c, {
            "autorisation_modele": "Fiche Enfant 2026-11",
            "pai": "PAI mentionné : Asthme fictif",
            "allergies": "Allergie aux arachides",
            "traitement": "Traitement fictif",
            "medical": ["Asthme fictif - consigne fictive"],
        })
        for mot in ("PAI mentionné", "Allergie aux arachides",
                    "Traitement fictif", "consigne fictive",
                    "Fiche Enfant 2026-11"):
            self.assertTrue(any(mot in texte for texte in c.textes), msg=mot)

    def test_sans_medical_ne_lit_pas_de_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "fiche.pdf")
            Impression.GenererPDF(out, {"nom": "FICTIF", "autorisations": {}})
            self.assertTrue(os.path.isfile(out))


if __name__ == "__main__":
    unittest.main()
