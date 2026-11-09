# -*- coding: utf-8 -*-
"""Portes statiques de publication de la preversion Windows RC10.56."""
import unittest
from pathlib import Path
from tests.test_noethys_sl_workflow_publication_rc105 import LireWorkflow, Evaluer, Contexte

RACINE = Path(__file__).resolve().parents[1]
WORKFLOW = RACINE / ".github/workflows/noethys-sl-rc1056-windows.yml"


class PublicationRC1056Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texte = WORKFLOW.read_text(encoding="utf-8")
        cls.jobs = LireWorkflow(cls.texte)["jobs"]

    def test_candidat_ne_publie_pas(self):
        c = Contexte("push", message="[candidate rc1056]")
        self.assertTrue(Evaluer(self.jobs["build"]["if"], c))
        self.assertFalse(Evaluer(self.jobs["publish"]["if"], c))

    def test_publication_explicite_exige_build_et_tests_exhaustifs(self):
        c = Contexte("push", message="[publish rc1056]")
        self.assertTrue(Evaluer(self.jobs["build"]["if"], c))
        self.assertTrue(Evaluer(self.jobs["publish"]["if"], c))
        gate = next(e for e in self.jobs["build"]["steps"]
                    if "contrats critiques du candidat" in e.get("name", ""))
        self.assertTrue(Evaluer(gate["if"], c))
        self.assertFalse(Evaluer(gate["if"], Contexte("push", message="[candidate rc1056]")))
        self.assertFalse(Evaluer(self.jobs["publish"]["if"],
                                Contexte("push", ref="refs/heads/main",
                                        message="[publish rc1056]")))
        self.assertFalse(Evaluer(self.jobs["publish"]["if"], Contexte("push", message="doc")))

    def test_publication_seulement_apres_le_build_et_controle_empreintes(self):
        self.assertEqual(self.jobs["publish"]["needs"], "build")
        self.assertEqual(self.jobs["publish"]["permissions"], {"contents": "write"})
        self.assertEqual(self.jobs["build"]["permissions"], {"contents": "read"})
        self.assertIn("SHA256SUMS.txt", self.texte)
        self.assertIn("gh release create", self.texte)
        self.assertIn("noethys-sl-0.1.0-rc.10.56", self.texte)


if __name__ == "__main__":
    unittest.main()
