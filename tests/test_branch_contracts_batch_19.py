import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOETHYS = ROOT / "noethys"
SOURCE_PATH = NOETHYS / "Dlg/DLG_Badgeage_interface.py"
AUDIT = ROOT / "scripts" / "audit_branch_assignment_gaps.py"
spec = importlib.util.spec_from_file_location("audit_branch_assignment_gaps", AUDIT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

TARGET = ("Dlg/DLG_Badgeage_interface.py", "VerificationConditionsAction", "listeReponses")


class TestBatch19BadgeageQuestionnaire(unittest.TestCase):
    def test_targeted_finding_disappears(self):
        remaining = [
            (item["file"], item["function"], item["name"])
            for item in audit.scan_file(SOURCE_PATH, NOETHYS)
            if (item["file"], item["function"], item["name"]) == TARGET
        ]
        self.assertEqual(remaining, [])

    def test_unsupported_or_missing_question_fails_closed_before_response_loop(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        block = source[source.index("# Recherche les réponses", source.index("def VerificationConditionsAction")):source.index("# Compare le filtre", source.index("def VerificationConditionsAction"))]
        self.assertIn('if IDquestion not in dictQuestions or dictQuestions[IDquestion]["type"] != "individu" :', block)
        self.assertIn("DB.Close()", block)
        self.assertIn("return False", block)
        self.assertLess(block.index("return False"), block.index("listeReponses = DB.ResultatReq()"))

    def test_supported_individual_question_keeps_historical_query(self):
        source = SOURCE_PATH.read_text(encoding="utf-8")
        self.assertIn("WHERE IDquestion=%d AND IDindividu=%d;", source)
        self.assertIn("listeReponses = DB.ResultatReq()", source)


if __name__ == "__main__":
    unittest.main()
