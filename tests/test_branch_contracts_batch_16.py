import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
AUDIT = ROOT / "scripts" / "audit_branch_assignment_gaps.py"
spec = importlib.util.spec_from_file_location("audit_branch_assignment_gaps", AUDIT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

TARGETS = {
    ("Utils/UTILS_Utilisateurs.py", "VerificationDroits", "condition"),
    ("Utils/UTILS_Utilisateurs.py", "VerificationDroits", "listeActivites"),
}

class TestBatch16Permissions(unittest.TestCase):
    def test_targeted_findings_disappear(self):
        path = NOETHYS / "Utils/UTILS_Utilisateurs.py"
        remaining = {
            (item["file"], item["function"], item["name"])
            for item in audit.scan_file(path, NOETHYS)
            if (item["file"], item["function"], item["name"]) in TARGETS
        }
        self.assertEqual(remaining, set())

    def test_restrictions_fail_closed_for_empty_or_unknown_modes(self):
        source = (NOETHYS / "Utils/UTILS_Utilisateurs.py").read_text(encoding="utf-8")
        self.assertIn('mode, listeID = code.split(":", 1)', source)
        self.assertIn('if listeID == ""', source)
        self.assertIn("except (TypeError, ValueError)", source)
        self.assertIn("listeActivites = []", source)
        self.assertIn("else : condition = None", source)
        self.assertIn("if condition != None", source)
        self.assertIn('elif mode == "activites"', source)

if __name__ == "__main__":
    unittest.main()
