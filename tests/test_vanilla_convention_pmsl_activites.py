# -*- coding: utf-8 -*-
"""Contrat du modèle PMSL fourni pour le champ activités."""
from __future__ import annotations

import sys as _sys_garde, pathlib as _pathlib_garde
_sys_garde.path.insert(0, str(_pathlib_garde.Path(__file__).resolve().parent))
import _garde_reseau  # noqa: E402,F401  aucune connexion à une base réseau (voir _garde_reseau)
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODELE = ROOT / "noethys" / "Static" / "ModelesConventionExemples" / "modele_convention_pmsl_associative.ndc"


class ModelePMSLActivitesContractTests(unittest.TestCase):
    def test_article_2_affiche_le_champ_activites(self):
        donnees = json.loads(MODELE.read_text(encoding="utf-8"))
        article = next(obj for obj in donnees["objets"] if obj.get("nom") == "Article 2 corps")
        self.assertIn("Activité(s) encadrée(s) : {CONVENTION_ACTIVITES}", article["texte"])
        self.assertIn("{CONVENTION_PLANNING_CRENEAUX}", article["texte"])


if __name__ == "__main__":
    unittest.main()
