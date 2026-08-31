import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
AUDIT = ROOT / "scripts" / "audit_branch_assignment_gaps.py"
spec = importlib.util.spec_from_file_location("audit_branch_assignment_gaps", AUDIT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

TARGET = ("Utils/UTILS_Archivage.py", "Effacer_individus", "dlgAttente")

class TestBatch17Archivage(unittest.TestCase):
    def test_targeted_finding_disappears(self):
        path = NOETHYS / "Utils/UTILS_Archivage.py"
        remaining = {
            (item["file"], item["function"], item["name"])
            for item in audit.scan_file(path, NOETHYS)
            if (item["file"], item["function"], item["name"]) == TARGET
        }
        self.assertEqual(remaining, set())

    def test_busy_info_is_optional_for_explicit_individual_list(self):
        source = (NOETHYS / "Utils/UTILS_Archivage.py").read_text(encoding="utf-8")
        self.assertIn("dlgAttente = None", source)
        self.assertIn("if dlgAttente != None:", source)

if __name__ == "__main__":
    unittest.main()
