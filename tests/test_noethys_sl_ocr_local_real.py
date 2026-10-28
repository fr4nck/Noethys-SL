# -*- coding: utf-8 -*-
"""Recette facultative de moteurs reels, assets provisionnes explicitement.

NOETHYS_OCR_ASSETS doit designer le dossier local tesseract/, tessdata/, trocr-fr/.
Aucun telechargement ou benchmark ; les deux images sont synthetiques.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from noethys.Utils import UTILS_OCR_local as ocr


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ocr"
EVIDENCE = []


class RealLocalOCRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("NOETHYS_OCR_ASSETS")
        if not value:
            raise unittest.SkipTest("Recette reelle sur demande : NOETHYS_OCR_ASSETS absent")
        cls.assets = Path(value).resolve()
        cls.samples = {item["file"]: item for item in json.loads((FIXTURES / "samples.json").read_text(encoding="utf-8"))}

    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.dict(os.environ, {
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
        }))
        self.network = []
        for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
            self.network.append(self.stack.enter_context(mock.patch(target, side_effect=AssertionError("Recette OCR hors ligne"))))

    def sample(self, name):
        path = FIXTURES / name
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), self.samples[name]["sha256"])
        return path

    def check_result(self, name, result):
        expected = self.samples[name]["expected"]
        actual = " ".join(field.value for field in result.fields)
        payload = result.to_review_payload()
        EVIDENCE.append({"sample": name, "expected": expected, "actual": actual,
                         "exact_match": actual == expected, "result": payload})
        self.assertFalse(payload["write_allowed"])
        self.assertTrue(result.fields)
        self.assertTrue(all(field.requires_review for field in result.fields))
        self.assertEqual(result.source_sha256, self.samples[name]["sha256"])
        for guard in self.network:
            guard.assert_not_called()
        self.assertEqual(actual, expected)
        self.sample(name)  # Source inchangee apres inference.

    def test_printed_french_real_tesseract(self):
        adapter = ocr.TesseractFrenchCPU(self.assets / "tesseract/tesseract.exe", self.assets / "tessdata", psm=7)
        result = adapter.recognize_page(self.sample("printed_fr.png"), source_page=1)
        self.assertIn("tesseract/fra@sha256:", result.model_id)
        self.check_result("printed_fr.png", result)

    def test_synthetic_cursive_real_trocr_cpu(self):
        import torch
        self.assertIsNone(torch.version.cuda, "La recette requiert un runtime PyTorch CPU")
        before = torch.get_num_threads()
        adapter = ocr.TrOCRFrenchCPU(self.assets / "trocr-fr", threads=2, max_new_tokens=64)
        result = adapter.recognize_line(self.sample("cursive_fr.png"), key="document.ligne.1", bbox=(0, 0, 1, 1))
        self.assertEqual(torch.get_num_threads(), before)
        self.assertTrue(all(parameter.device.type == "cpu" for parameter in adapter._runtime[1].parameters()))
        self.assertIsNone(result.fields[0].confidence)
        self.check_result("cursive_fr.png", result)

    def test_missing_model_fails_offline(self):
        with tempfile.TemporaryDirectory(prefix="ocr-missing-") as directory:
            adapter = ocr.TrOCRFrenchCPU(Path(directory) / "absent")
            with self.assertRaises(ocr.OCRUnavailableError):
                adapter.recognize_line(self.sample("cursive_fr.png"), key="ligne", bbox=(0, 0, 1, 1))
        for guard in self.network:
            guard.assert_not_called()
        EVIDENCE.append({"case": "missing-model", "expected_local_error": True, "network_attempts": 0})

    def test_incomplete_tokenizer_fails_offline_before_weights(self):
        import transformers
        with tempfile.TemporaryDirectory(prefix="ocr-tokenizer-") as directory:
            snapshot = Path(directory)
            for name in ("config.json", "preprocessor_config.json", "tokenizer_config.json", "ocr-model.json"):
                shutil.copyfile(self.assets / "trocr-fr" / name, snapshot / name)
            # Marqueur non chargeable : seul le vrai processeur doit etre invoque.
            (snapshot / "model.safetensors").write_bytes(b"never deserialize")
            with mock.patch.object(transformers.VisionEncoderDecoderModel, "from_pretrained") as loader:
                adapter = ocr.TrOCRFrenchCPU(snapshot)
                with self.assertRaises(ocr.OCRUnavailableError):
                    adapter.recognize_line(self.sample("cursive_fr.png"), key="ligne", bbox=(0, 0, 1, 1))
                loader.assert_not_called()
        for guard in self.network:
            guard.assert_not_called()
        EVIDENCE.append({"case": "incomplete-tokenizer", "expected_local_error": True, "network_attempts": 0})


if __name__ == "__main__":
    unittest.main()
