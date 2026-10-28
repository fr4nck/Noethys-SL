# -*- coding: utf-8 -*-
"""Publication ponctuelle : uniquement les assets du candidat RC10.1 qualifié."""
from pathlib import Path
import unittest
from tests.test_noethys_sl_workflow_publication_rc101 import LireWorkflow, Evaluer, Contexte

RACINE = Path(__file__).resolve().parents[1]
SHA = "cfeccd499927319583b263b5361d9abbedeb6963"


class PublicationExacteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = LireWorkflow((RACINE / ".github/workflows/noethys-sl-rc101-publish-verified.yml").read_text(encoding="utf-8"))
        cls.job = cls.workflow["jobs"]["publier"]

    def test_sha_et_runs_exacts(self):
        self.assertEqual(self.job["env"]["BUILD_SHA"], SHA)
        self.assertEqual(self.job["env"]["BUILD_RUN"], "40762579762")
        self.assertEqual(self.job["env"]["FAST_RUN"], "40762579606")
        recuperer = next(s for s in self.job["steps"] if s.get("uses", "").startswith("actions/download-artifact@"))
        self.assertEqual(str(recuperer["with"]["run-id"]), self.job["env"]["BUILD_RUN"])
        self.assertEqual(recuperer["with"]["name"], "Noethys-SL-0.1.0-rc.10.1-Windows-candidat")
        controles = "\n".join(s.get("run", "") for s in self.job["steps"])
        self.assertIn('test "$etat" = "success"', controles)
        self.assertIn('test "$source" = "$BUILD_SHA"', controles)

    def test_autorisation_exacte_et_refus_des_autres_evenements(self):
        message = "release: publier RC10.1 validee cfeccd49"
        for event, ref, msg, resultat in (
            ("push", "refs/heads/wx", message, True),
            ("push", "refs/heads/main", message, False),
            ("push", "refs/heads/wx", "docs", False),
            ("workflow_dispatch", "refs/heads/wx", message, False),
            ("pull_request", "refs/heads/wx", message, False),
        ):
            contexte = Contexte(event, ref=ref, message=msg)
            contexte["github"]["repository"] = "fr4nck/Noethys-SL"
            self.assertEqual(Evaluer(self.job["if"], contexte), resultat)

    def test_empreintes_et_refus_de_remplacer_tag_ou_release(self):
        texte = "\n".join(s.get("run", "") for s in self.job["steps"])
        self.assertIn("sha256sum -c SHA256SUMS.txt", texte)
        self.assertIn("git/ref/tags/$TAG", texte)
        self.assertIn('gh release view "$TAG"', texte)
        self.assertNotIn("--clobber", texte)
        self.assertNotIn("--force", texte)
        self.assertIn('--target "$BUILD_SHA"', texte)
        self.assertIn("--prerelease", texte)

    def test_permissions_et_declencheur_limites(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(self.job["permissions"], {"actions": "read", "contents": "write"})
        self.assertEqual(self.workflow["on"]["push"]["branches"], ["wx"])
        self.assertEqual(self.job["env"]["TAG"], "noethys-sl-0.1.0-rc.10.1")


if __name__ == "__main__":
    unittest.main()
