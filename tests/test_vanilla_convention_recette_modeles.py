# -*- coding: utf-8 -*-
"""Rejoue les deux modeles .ndc de recette utilisateur commites dans
noethys/Static/ModelesConventionExemples/ (import reel + generation PDF
sur des donnees fictives) : si une modification du moteur les casse
silencieusement, ce test le detecte en CI. Ces fichiers sont ceux qu'un
vrai utilisateur importe depuis Paramétrage > Modèles de documents >
Convention -- voir docs/recette_conventions/README.md. Ils vivent sous
noethys/Static/ (et non docs/) car c'est le seul dossier de ressources
reellement embarque dans le portable/installateur Windows (packaging/
vanilla-noethys.spec) : une installation reelle contient donc ces
fichiers, sans acces au depot GitHub.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_DIR = TESTS_DIR.parent
NOETHYS_DIR = REPO_DIR / "noethys"
MODELES_DIR = NOETHYS_DIR / "Static" / "ModelesConventionExemples"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import wx  # noqa: E402

_APP = wx.App(False)

from _fixtures_noethys_db import (  # noqa: E402
    RedirectionGestionDB,
    creer_base_association_simple,
    creer_base_ecole_simple,
)
from Utils import UTILS_Export_documents  # noqa: E402
from Utils import UTILS_Impression_convention as UIC  # noqa: E402


def _lire_nombre_de_pages(chemin_pdf):
    contenu = Path(chemin_pdf).read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?!s)", contenu))


class RecetteModelesConventionTests(unittest.TestCase):
    def test_aucune_donnee_pmsl_dans_les_fichiers_commites(self):
        interdits = ("PMSL", "Providence", "SALMON", "ESTIER", "Groupama", "La Guerche", "Atout Sports")
        for nom in ("modele_convention_associative.ndc", "modele_convention_scolaire.ndc"):
            chemin = MODELES_DIR / nom
            contenu = chemin.read_text(encoding="utf-8")
            for texte in interdits:
                self.assertNotIn(texte, contenu, "%s trouvé dans %s" % (texte, chemin.name))

    def test_modele_reference_atout_sports_conserve_les_marqueurs_visuels(self):
        import json
        chemin = MODELES_DIR / "modele_convention_pmsl_associative.ndc"
        self.assertTrue(chemin.is_file())
        texte = chemin.read_text(encoding="utf-8")
        self.assertNotIn("TÃ", texte)
        data = json.loads(texte)
        objets = data["objets"]
        textes = [o.get("texte") for o in objets if isinstance(o.get("texte"), str)]
        self.assertFalse(
            any("\\n" in valeur for valeur in textes),
            "Le modèle de référence ne doit pas contenir de \\n littéral : utiliser de vrais retours ligne.",
        )
        noms = {o["nom"] for o in objets}
        self.assertIn("Logo organisateur", noms)
        logo = next(o for o in objets if o["nom"] == "Logo organisateur")
        self.assertEqual(logo.get("typeImage"), "fichier_png")
        self.assertGreater(len(logo.get("image") or ""), 1000)
        self.assertIn("Cadre coordonnées", noms)
        self.assertIn("Cadre titre", noms)
        self.assertIn("Cadres signatures", noms)
        structure = next(o for o in objets if o["nom"] == "Structure partie")
        self.assertNotIn("{FAMILLE_VILLE}", structure["texte"])
        self.assertNotIn("]]]]", structure["texte"])
        self.assertIn("Saut page 2", noms)
        bandeaux = [o for o in objets if o["nom"].startswith("Article ") and o["nom"].endswith("titre")]
        self.assertEqual(len(bandeaux), 6)
        self.assertTrue(all(o.get("couleurFond") == "(215, 215, 215)" for o in bandeaux))
        self.assertEqual(data["categorie"], "convention")

    def test_modele_associatif_s_importe_et_se_genere(self):
        chemin_ndc = MODELES_DIR / "modele_convention_associative.ndc"
        self.assertTrue(chemin_ndc.is_file())
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                IDmodele = UTILS_Export_documents.Importer(fichier=str(chemin_ndc))
                chemin_pdf = tempfile.mktemp(suffix=".pdf")
                try:
                    resultat = UIC.Impression(
                        IDfamille=1, IDmodele=IDmodele, date_debut="2026-09-01", date_fin="2026-09-30",
                        saison="2026-2027", listeIDindividus=[2, 3], nomDoc=chemin_pdf, afficherDoc=False,
                        overrides={
                            "{CONVENTION_REPRESENTANT_FONCTION}": "Président",
                            "{CONVENTION_LIEU_SIGNATURE}": "TESTVILLE",
                            "{CONVENTION_DATE_SIGNATURE}": "21/09/2026",
                        },
                    )
                    self.assertIsInstance(resultat, dict, "génération échouée : %r" % (resultat,))
                    self.assertTrue(os.path.isfile(chemin_pdf))
                    self.assertGreater(os.path.getsize(chemin_pdf), 0)
                    self.assertEqual(_lire_nombre_de_pages(chemin_pdf), 1)
                finally:
                    if os.path.isfile(chemin_pdf):
                        os.remove(chemin_pdf)

    def test_modele_reference_atout_sports_s_importe_et_genere_deux_pages(self):
        chemin_ndc = MODELES_DIR / "modele_convention_pmsl_associative.ndc"
        with creer_base_association_simple() as base:
            with RedirectionGestionDB(base.chemin):
                IDmodele = UTILS_Export_documents.Importer(fichier=str(chemin_ndc))
                chemin_pdf = tempfile.mktemp(suffix=".pdf")
                try:
                    resultat = UIC.Impression(
                        IDfamille=1, IDmodele=IDmodele,
                        date_debut="2026-09-01", date_fin="2026-09-30",
                        saison="2026-2027", listeIDindividus=[2, 3],
                        nomDoc=chemin_pdf, afficherDoc=False,
                        overrides={
                            "{CONVENTION_REPRESENTANT_FONCTION}": "Président",
                            "{CONVENTION_LIEU_SIGNATURE}": "TESTVILLE",
                            "{CONVENTION_DATE_SIGNATURE}": "21/09/2026",
                        },
                    )
                    self.assertIsInstance(resultat, dict)
                    self.assertEqual(_lire_nombre_de_pages(chemin_pdf), 2)
                finally:
                    if os.path.isfile(chemin_pdf):
                        os.remove(chemin_pdf)

    def test_modele_scolaire_s_importe_et_se_genere_multipage(self):
        chemin_ndc = MODELES_DIR / "modele_convention_scolaire.ndc"
        self.assertTrue(chemin_ndc.is_file())
        with creer_base_ecole_simple() as base:
            with RedirectionGestionDB(base.chemin):
                IDmodele = UTILS_Export_documents.Importer(fichier=str(chemin_ndc))
                chemin_pdf = tempfile.mktemp(suffix=".pdf")
                try:
                    resultat = UIC.Impression(
                        IDfamille=2, IDmodele=IDmodele, date_debut="2026-08-01", date_fin="2027-07-31",
                        listeIDindividus=[20, 21, 22], nomDoc=chemin_pdf, afficherDoc=False,
                        overrides={
                            "{CONVENTION_REPRESENTANT_FONCTION}": "Directrice",
                            "{CONVENTION_LIEU_SIGNATURE}": "TESTVILLE",
                            "{CONVENTION_DATE_SIGNATURE}": "21/09/2026",
                        },
                    )
                    self.assertIsInstance(resultat, dict, "génération échouée : %r" % (resultat,))
                    self.assertTrue(os.path.isfile(chemin_pdf))
                    self.assertGreaterEqual(_lire_nombre_de_pages(chemin_pdf), 2)
                finally:
                    if os.path.isfile(chemin_pdf):
                        os.remove(chemin_pdf)


if __name__ == "__main__":
    unittest.main()