# -*- coding: utf-8 -*-
"""Tests de contrat OCR-01, sans dépendance OCR, Qt, wx ni base de données."""
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "noethys" / "Utils" / "UTILS_OCR_contract.py"
spec = importlib.util.spec_from_file_location("ocr_contract", MODULE_PATH)
ocr = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = ocr
spec.loader.exec_module(ocr)


class TestOCRContract(unittest.TestCase):
    def sample(self, **changes):
        values = dict(
            key="responsable.nom", value="MARTIN", source_page=1,
            bbox=(0.1, 0.2, 0.6, 0.3), engine="trocr-fr",
            kind="handwritten", confidence=0.98,
        )
        values.update(changes)
        return ocr.OCRField(**values)

    def test_handwriting_always_needs_review(self):
        self.assertTrue(self.sample(confidence=1.0).requires_review)

    def test_unknown_confidence_allowed_but_review_required(self):
        self.assertTrue(self.sample(confidence=None).requires_review)

    def test_bad_page_bbox_and_confidence_rejected(self):
        for changes in (
            {"source_page": 0},
            {"bbox": (-0.1, 0.2, 0.3, 0.4)},
            {"bbox": (0.4, 0.2, 0.3, 0.4)},
            {"confidence": 1.1},
            {"confidence": -0.01},
            {"kind": "unknown"},
            {"state": "accepted"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.sample(**changes)

    def test_missing_provenance_rejected(self):
        with self.assertRaises(ValueError):
            ocr.OCRResult("not-a-hash", (self.sample(),), "model", "1")
        with self.assertRaises(ValueError):
            ocr.OCRResult("a" * 64, (self.sample(),), "", "1")

    def test_payload_is_read_only_and_serializable(self):
        import json
        result = ocr.OCRResult("a" * 64, (self.sample(),), "trocr-fr-v5", "0.1")
        data = result.to_review_payload()
        self.assertFalse(data["write_allowed"])
        self.assertTrue(data["fields"][0]["requires_review"])
        self.assertEqual(json.loads(json.dumps(data))["fields"][0]["value"], "MARTIN")
        data["fields"][0]["value"] = "CHANGED"
        self.assertEqual(result.fields[0].value, "MARTIN")


if __name__ == "__main__":
    unittest.main()
