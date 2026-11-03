# -*- coding: utf-8 -*-
"""Fiches famille ALSH / Club ados : sorties A4 distinctes et sans consentement fictif."""
import os
import re
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import patch
from Utils import UTILS_Accueil_familles_impression as F


def donnees():
    return {
        "IDfamille": 25, "regime": "CAF", "num_allocataire": "000-TEST",
        "responsables": [
            {"nom": "PARENT", "prenom": "Un", "adresse": "1 rue fictive",
             "cp": "35130", "ville": "Bais", "domicile": "02 00 00",
             "mobile": "06 00 00", "mail": "un@example.invalid",
             "employeur": "Entreprise fictive", "travail_tel": "01 00 00"},
            {"nom": "PARENT", "prenom": "Deux", "adresse": "1 rue fictive",
             "cp": "35130", "ville": "Bais", "mail": "deux@example.invalid"},
        ],
        "enfants": [
            {"nom": "ADO", "prenom": "Fictive", "sexe": "F",
             "date_naiss": "03/05/2011", "ecole": "Collège fictif",
             "classe": "Troisième"},
            {"nom": "ENFANT", "prenom": "Fictif", "sexe": "M",
             "date_naiss": "20/04/2017", "ecole": "École fictive",
             "classe": "CE2"},
        ],
    }


@unittest.skipIf(F.A4 is None, "ReportLab absent")
class ModeleFamille(unittest.TestCase):
    class Canvas:
        def __init__(self):
            self.txt = []
            self.crosses = []
        def drawString(self, x, y, txt):
            self.txt.append(txt)
            if txt == "X":
                self.crosses.append((x, y))
        def drawCentredString(self, x, y, txt):
            self.txt.append(txt)
        def drawRightString(self, x, y, txt):
            self.txt.append(txt)
        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    def test_deux_titres_distincts_et_sites(self):
        for modele, site, titre in (
            ("alsh","MOUTIERS","ACCUEIL DE LOISIRS PÊLE-MÊLE - FICHE FAMILLE"),
            ("ados","BAIS","Club ADOS PÊLE-MÊLE - FICHE FAMILLE"),
        ):
            with self.subTest(modele=modele):
                c = self.Canvas()
                F._page1(c, donnees(), modele, site, "2026-2027")
                self.assertIn(titre, c.txt)
                self.assertIn("2026-2027", c.txt)
        ca, cc = self.Canvas(), self.Canvas()
        F._page1(ca, donnees(), "alsh", "BAIS", "2026-2027")
        F._page1(cc, donnees(), "ados", "BAIS", "2026-2027")
        self.assertTrue(any("CAFPRO" in t for t in cc.txt))
        self.assertFalse(any("CAFPRO" in t for t in ca.txt))
        # Aucune case CAFPRO n'est cochée sur un document non signé.
        self.assertEqual(len(cc.crosses), 2)  # Bais et régime CAF, pas CAFPRO

    def test_fiche_commune_titre_cafpro_et_activites_par_enfant(self):
        donnees = self.donnees_unifiees()
        c = self.Canvas()
        F._page1(c, donnees, F.MODEL_FAMILLE, "", "2026-2027")
        self.assertIn("PÊLE-MÊLE - FICHE FAMILLE", c.txt)
        self.assertTrue(any("Club ados : Bais" in t for t in c.txt))
        self.assertTrue(any("CAFPRO" in t for t in c.txt))
        self.assertEqual(len(c.crosses), 1)  # regime CAF seulement

        p2 = self.Canvas()
        with patch.object(F, "_paragraphe", side_effect=(
                lambda _c, _t, _x, y, _w, *_a: y - 23)):
            F._page2(p2, donnees, F.MODEL_FAMILLE)
        self.assertIn("ENFANTS / ADOS À INSCRIRE", p2.txt)
        for valeur in ("ENFANT", "ADO", "ALSH MOUTIERS", "ALSH BAIS",
                       "CLUB ADOS BAIS", "Troisième"):
            self.assertTrue(any(valeur in t for t in p2.txt), valeur)

    @staticmethod
    def donnees_unifiees():
        d = donnees()
        d["enfants"] = [
            dict(d["enfants"][0], accueils=["ALSH BAIS", "CLUB ADOS BAIS"]),
            dict(d["enfants"][1], accueils=["ALSH MOUTIERS"]),
        ]
        return d

    def test_fiche_commune_est_un_seul_pdf_deux_pages(self):
        dossier = self.donnees_unifiees()
        avant = deepcopy(dossier)
        with tempfile.TemporaryDirectory() as d:
            fichier = os.path.join(d, "famille-unique.pdf")
            F.GenererPDF(fichier, dossier, modele=F.MODEL_FAMILLE,
                         annee="2026-2027")
            contenu = open(fichier, "rb").read()
            self.assertTrue(contenu.startswith(b"%PDF-"))
            self.assertEqual(len(re.findall(rb"/Type\\s*/Page\\b", contenu)), 2)
        self.assertEqual(dossier, avant)

    def test_fiche_commune_exige_un_accueil_par_enfant(self):
        with tempfile.TemporaryDirectory() as d:
            fichier = os.path.join(d, "famille-unique.pdf")
            for enfants in (
                donnees()["enfants"],  # aucune affectation
                [dict(donnees()["enfants"][0],
                      accueils=["ALSH BAIS", "ALSH MOUTIERS"])],
                [dict(donnees()["enfants"][0],
                      accueils=["CLUB ADOS PARIS"])],
            ):
                with self.subTest(enfants=enfants), self.assertRaises(ValueError):
                    F.GenererPDF(fichier, dict(donnees(), enfants=enfants),
                                 modele=F.MODEL_FAMILLE, annee="2026-2027")
            self.assertFalse(os.path.exists(fichier))

    def test_page2_titres_enfants_ou_ados(self):
        for modele, rubrique in (("alsh", "ENFANTS À INSCRIRE"),
                                 ("ados", "ADOS À INSCRIRE")):
            c = self.Canvas()
            with patch.object(F, "_paragraphe", side_effect=(
                    lambda _c, _t, _x, y, _w, *_a: y - 23)):
                F._page2(c, donnees(), modele)
            self.assertIn(rubrique, c.txt)
            self.assertIn("ADO", c.txt)
            self.assertIn("ENFANT", c.txt)
            self.assertEqual(len(F.ENGAGEMENTS), 8)

    def test_edition_deux_pages_et_source_inchangee(self):
        original = donnees()
        sauvegarde = deepcopy(original)
        with tempfile.TemporaryDirectory() as d:
            for modele, site in (("alsh","LA GUERCHE"),("ados","BAIS")):
                nom = os.path.join(d, "fiche-%s.pdf" % modele)
                resultat = F.GenererPDF(nom, original, modele, site, "2026-2027")
                self.assertEqual(resultat, nom)
                contenu = open(nom, "rb").read()
                self.assertTrue(contenu.startswith(b"%PDF-"))
                self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", contenu)), 2)
                self.assertGreater(len(contenu), 1000)
        self.assertEqual(original, sauvegarde)

    def test_pas_de_mauvais_modele_ni_site(self):
        with tempfile.TemporaryDirectory() as d:
            fichier = os.path.join(d, "fiche.pdf")
            for modele, site in (("alsh",""),("alsh","PARIS"),
                                 ("ados","MOUTIERS"),("enfant","BAIS")):
                with self.subTest(modele=modele,site=site), self.assertRaises(ValueError):
                    F.GenererPDF(fichier, donnees(), modele, site)
            self.assertFalse(os.path.exists(fichier))

    def test_pas_d_enfant_ou_plus_de_quatre_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = os.path.join(d, "fiche.pdf")
            x = donnees()
            x["enfants"] = []
            with self.assertRaises(ValueError):
                F.GenererPDF(chemin, x, "alsh", "BAIS")
            x["enfants"] = donnees()["enfants"] * 3
            with self.assertRaises(ValueError):
                F.GenererPDF(chemin, x, "alsh", "BAIS")
            self.assertFalse(os.path.exists(chemin))

    def test_nom_pdf_non_valide(self):
        for path in (None, "fiche.docx", ""):
            with self.subTest(path=path), self.assertRaises(ValueError):
                F.GenererPDF(path, donnees(), "ados", "BAIS")


if __name__ == "__main__":
    unittest.main()
