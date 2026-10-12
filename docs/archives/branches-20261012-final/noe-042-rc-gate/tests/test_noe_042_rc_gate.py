# -*- coding: utf-8 -*-
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-candidate.yml"


class ReleaseCandidateGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_real_database_recipe_is_required_and_denied_by_default(self):
        self.assertIn("real_db_recipe:", self.text)
        self.assertIn('default: "NO"', self.text)
        self.assertIn('if [ "$REAL_DB_RECIPE" != "YES" ]; then', self.text)

    def test_release_is_draft_not_automatic_publication(self):
        self.assertIn("gh release create", self.text)
        self.assertIn("--draft", self.text)
        self.assertNotIn("gh release edit", self.text)
        self.assertNotIn("--draft=false", self.text)

    def test_existing_tag_cannot_be_overwritten(self):
        self.assertIn("git ls-remote --exit-code --tags origin", self.text)
        self.assertIn("existe déjà : refus d'écrasement", self.text)

    def test_rc_is_restricted_to_master(self):
        self.assertIn('if [ "$GITHUB_REF" != "refs/heads/master" ]; then', self.text)

    def test_portable_archive_is_smoke_tested(self):
        self.assertIn('NOETHYS_FROZEN_SMOKE = "1"', self.text)
        self.assertIn("WaitForExit(30000)", self.text)
        self.assertIn("Portable/README.txt", self.text)


if __name__ == "__main__":
    unittest.main()
