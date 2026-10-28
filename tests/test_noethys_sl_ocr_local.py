# -*- coding: utf-8 -*-
"""Recette OCR-02 sur documents fictifs, réseau interdit, moteurs simulés.

Le raster, son empreinte, le découpage et le contrat de sortie sont réels.
Ces tests ne qualifient ni les poids OCR ni la précision de reconnaissance.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from noethys.Utils import UTILS_OCR_local as ocr


PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None
HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
TSV = (HEADER + "1\t1\t0\t0\t0\t0\t0\t0\t100\t50\t-1\t\n"
       "5\t1\t1\t1\t1\t1\t10\t5\t30\t10\t96.5\tÉlève\n"
       "5\t1\t1\t1\t1\t2\t50\t5\t40\t10\t-1\tfrançais\n").encode("utf-8")


class IsolationTests(unittest.TestCase):
    def test_import_without_ocr_toolkits_or_database(self):
        script = """
import sys
class Block:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PIL', 'torch', 'transformers', 'wx',
                                      'PySide6', 'PyQt6', 'GestionDB'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
from noethys.Utils import UTILS_OCR_local
"""
        result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))

    def test_resource_options_rejected(self):
        for options in ({"threads": 0}, {"threads": True}, {"threads": 13},
                        {"timeout": float("nan")}, {"timeout": 0}, {"psm": 12}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                ocr.TesseractFrenchCPU("absent", "absent", **options)
        for options in ({"max_new_tokens": 0}, {"max_new_tokens": 513}, {"threads": 2.5}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                ocr.TrOCRFrenchCPU("absent", **options)

    def test_missing_pillow_is_explicit(self):
        with mock.patch.dict(sys.modules, {"PIL": None}):
            with self.assertRaises(ocr.OCRUnavailableError):
                ocr._page("absent.png", 1)


@unittest.skipUnless(PIL_AVAILABLE, "Pillow requis pour la recette image (présent en CI Windows)")
class LocalOCRTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.Image = Image
        self.temp = tempfile.TemporaryDirectory(prefix="noethys-ocr-fictif-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory / "page française.png"
        image = Image.new("RGB", (100, 50), "white")
        image.putpixel((25, 10), (0, 0, 0))
        image.save(self.source)
        self.initial_source = self.source.read_bytes()
        for target in ("socket.socket.connect", "socket.create_connection"):
            patcher = mock.patch(target, side_effect=AssertionError("Réseau interdit dans la recette OCR"))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.executable = self.directory / "Tesseract CPU.exe"
        self.executable.write_bytes(b"fake executable, never launched")
        self.tessdata = self.directory / "tessdata"
        self.tessdata.mkdir()
        (self.tessdata / "fra.traineddata").write_bytes(b"fake french weights")
        self.adapter = ocr.TesseractFrenchCPU(self.executable, self.tessdata)

    def tearDown(self):
        self.assertEqual(self.source.read_bytes(), self.initial_source)

    def tesseract(self, output=TSV, version=b"tesseract 5.5.0\n Found AVX2\n", failure=None):
        def run(command, **kwargs):
            if command[-1] == "--version":
                return subprocess.CompletedProcess(command, 0, version, b"")
            if failure:
                raise failure
            return subprocess.CompletedProcess(command, 0, output, b"")
        return mock.patch.object(ocr.subprocess, "run", side_effect=run)

    def test_printed_french_image_to_review_payload(self):
        with self.tesseract() as run:
            result = self.adapter.recognize_page(self.source, source_page=3, key_prefix="page3")
        self.assertEqual([f.value for f in result.fields], ["Élève", "français"])
        self.assertEqual(result.fields[0].bbox, (0.1, 0.1, 0.4, 0.3))
        self.assertEqual(result.fields[0].source_page, 3)
        self.assertEqual(result.fields[0].key, "page3.word.1")
        self.assertEqual(result.fields[0].confidence, 0.965)
        self.assertIsNone(result.fields[1].confidence)
        self.assertEqual(result.source_sha256, hashlib.sha256(self.initial_source).hexdigest())
        self.assertEqual(result.model_id, "tesseract/fra@sha256:" + hashlib.sha256(b"fake french weights").hexdigest())
        self.assertEqual(result.engine_version, "tesseract 5.5.0")
        payload = json.loads(json.dumps(result.to_review_payload()))
        self.assertFalse(payload["write_allowed"])
        self.assertTrue(all(f["requires_review"] for f in payload["fields"]))
        command, kwargs = run.call_args
        self.assertIn("fra", command[0])
        self.assertEqual(command[0][1:3], ["stdin", "stdout"])
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], 60)
        self.assertEqual(kwargs["env"]["OMP_THREAD_LIMIT"], "2")
        with self.Image.open(io.BytesIO(kwargs["input"])) as raster:
            self.assertEqual(raster.size, (100, 50))
            self.assertEqual(raster.getpixel((25, 10)), (0, 0, 0))

    def test_blank_printed_page_has_no_invented_field(self):
        with self.tesseract(output=HEADER.encode()):
            self.assertEqual(self.adapter.recognize_page(self.source).fields, ())

    def test_malformed_tsv_fails_without_partial_results(self):
        for data in (b"", b"text\nsecret\n", TSV.replace(b"96.5", b"nan"),
                     TSV.replace(b"96.5", b"101"), TSV.replace(b"96.5", b"-2"),
                     TSV.replace(b"\t10\t5\t30\t10", b"\t90\t5\t30\t10"),
                     TSV.replace(b"5\t1\t1", b"5\t2\t1"), TSV + b"\xff"):
            with self.subTest(data=data), self.tesseract(output=data):
                with self.assertRaises(ocr.OCRExecutionError):
                    self.adapter.recognize_page(self.source)

    def test_timeout_and_engine_failure_are_redacted(self):
        with self.tesseract(failure=subprocess.TimeoutExpired("secret document", 60)):
            with self.assertRaises(ocr.OCRExecutionError) as error:
                self.adapter.recognize_page(self.source)
        self.assertNotIn("secret", str(error.exception))
        with mock.patch.object(ocr.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"secret")):
            with self.assertRaises(ocr.OCRExecutionError) as error:
                self.adapter.recognize_page(self.source)
        self.assertNotIn("secret", str(error.exception))

    def test_missing_french_weights_does_not_launch_engine(self):
        (self.tessdata / "fra.traineddata").unlink()
        with mock.patch.object(ocr.subprocess, "run") as run:
            with self.assertRaises(ocr.OCRUnavailableError):
                self.adapter.recognize_page(self.source)
            run.assert_not_called()

    def test_old_or_opencl_build_does_not_start_recognition(self):
        for version in (b"tesseract 4.1.0", b"tesseract 5.0.0\nOpenCL"):
            with self.subTest(version=version), self.tesseract(version=version) as run:
                with self.assertRaises(ocr.OCRUnavailableError):
                    self.adapter.recognize_page(self.source)
                self.assertEqual(run.call_count, 1)

    def test_model_changed_during_recognition_is_rejected(self):
        with self.tesseract(), mock.patch.object(ocr, "_sha256_file", side_effect=["a" * 64, "b" * 64]):
            with self.assertRaises(ocr.OCRExecutionError):
                self.adapter.recognize_page(self.source)

    def test_source_limits_page_and_bad_images(self):
        for page in (0, 1.5, True):
            with self.subTest(page=page), self.assertRaises(ValueError):
                self.adapter.recognize_page(self.source, source_page=page)
        with mock.patch.object(ocr, "MAX_SOURCE_BYTES", 4), self.assertRaises(ValueError):
            self.adapter.recognize_page(self.source)
        with mock.patch.object(ocr, "MAX_PIXELS", 4), self.assertRaises(ValueError):
            self.adapter.recognize_page(self.source)
        bad = self.directory / "invalid.png"
        bad.write_bytes(b"not an image")
        with self.assertRaises(ValueError):
            self.adapter.recognize_page(bad)
        self.Image.new("RGB", (10, 10)).save(bad, format="TIFF", save_all=True,
                                             append_images=[self.Image.new("RGB", (10, 10))])
        with self.assertRaises(ValueError):
            self.adapter.recognize_page(bad)

    def test_transparency_is_flattened_on_white(self):
        transparent = self.directory / "transparent.png"
        self.Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(transparent)
        image, digest = ocr._page(transparent, 1)
        self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(digest, hashlib.sha256(transparent.read_bytes()).hexdigest())

    def snapshot(self):
        directory = self.directory / "trocr français"
        directory.mkdir()
        for name, value in {
            "ocr-model.json": {"model_id": "fixture-fr-revision1", "language": "fr", "unit": "line"},
            "config.json": {"model_type": "vision-encoder-decoder", "decoder": {"model_type": "trocr"}},
            "preprocessor_config.json": {}, "tokenizer_config.json": {}, "tokenizer.json": {},
        }.items():
            (directory / name).write_text(json.dumps(value), encoding="utf-8")
        (directory / "model.safetensors").write_bytes(b"fake weights, never deserialized")
        return directory

    @contextlib.contextmanager
    def trocr(self, text="Je soussigné Élise", fail=False):
        pixels = mock.Mock()
        pixels.to.return_value = pixels
        processor = mock.Mock(return_value=types.SimpleNamespace(pixel_values=pixels))
        processor.batch_decode.return_value = [text]
        model = mock.Mock()
        model.to.return_value = model
        model.eval.return_value = model
        model.generate.return_value = [[1, 2]]
        if fail:
            model.generate.side_effect = RuntimeError("secret document")
        torch = types.SimpleNamespace(__version__="fixture", float32="float32", get_num_threads=lambda: 8,
                                      set_num_threads=mock.Mock(), inference_mode=contextlib.nullcontext,
                                      device=mock.Mock(side_effect=lambda value: contextlib.nullcontext()))
        transformers = types.SimpleNamespace(
            __version__="fixture", TrOCRProcessor=mock.Mock(), VisionEncoderDecoderModel=mock.Mock())
        transformers.TrOCRProcessor.from_pretrained.return_value = processor
        transformers.VisionEncoderDecoderModel.from_pretrained.return_value = model
        with mock.patch.dict(sys.modules, {"torch": torch, "transformers": transformers}):
            yield torch, transformers, processor, model, pixels

    def test_handwritten_french_crop_cpu_and_local_only_loading(self):
        directory = self.snapshot()
        adapter = ocr.TrOCRFrenchCPU(directory)
        with self.trocr() as (torch, transformers, processor, model, pixels):
            result = adapter.recognize_line(self.source, key="autorisation", bbox=(.251, .201, .799, .599), source_page=2)
            # Même modèle résident : aucune seconde lecture/initialisation des poids.
            adapter.recognize_line(self.source, key="signature", bbox=(0, 0, 1, 1))
        self.assertEqual(result.fields[0].value, "Je soussigné Élise")
        self.assertEqual(result.fields[0].bbox, (.25, .2, .8, .6))
        self.assertEqual(result.fields[0].source_page, 2)
        self.assertEqual(result.fields[0].kind, "handwritten")
        self.assertIsNone(result.fields[0].confidence)
        self.assertFalse(result.to_review_payload()["write_allowed"])
        self.assertTrue(result.fields[0].requires_review)
        self.assertEqual(result.source_sha256, hashlib.sha256(self.initial_source).hexdigest())
        self.assertIn("fixture-fr-revision1@sha256:", result.model_id)
        self.assertEqual(processor.call_args_list[0].kwargs["images"].size, (55, 20))
        self.assertEqual(processor.call_args_list[0].kwargs["images"].getpixel((0, 0)), (0, 0, 0))
        for loader in (transformers.TrOCRProcessor, transformers.VisionEncoderDecoderModel):
            loader.from_pretrained.assert_called_once()
            self.assertEqual(loader.from_pretrained.call_args.args, (str(directory.resolve()),))
            options = loader.from_pretrained.call_args.kwargs
            self.assertTrue(options["local_files_only"])
            self.assertFalse(options["trust_remote_code"])
            self.assertFalse(options["token"])
        self.assertTrue(transformers.VisionEncoderDecoderModel.from_pretrained.call_args.kwargs["use_safetensors"])
        model.to.assert_called_once_with(device="cpu", dtype="float32")
        torch.device.assert_has_calls([mock.call("cpu"), mock.call("cpu")])
        pixels.to.assert_called_with(device="cpu", dtype="float32")
        self.assertEqual(model.generate.call_args.kwargs, {"max_new_tokens": 128, "num_beams": 1, "do_sample": False})
        self.assertEqual(torch.set_num_threads.call_args_list, [mock.call(2), mock.call(8)] * 2)

    def test_empty_handwriting_does_not_invent_a_value(self):
        with self.trocr(text="  "):
            result = ocr.TrOCRFrenchCPU(self.snapshot()).recognize_line(self.source, key="ligne", bbox=(0, 0, 1, 1))
        self.assertEqual(result.fields, ())

    def test_trocr_error_restores_thread_limit_and_redacts_data(self):
        with self.trocr(fail=True) as (torch, *_):
            with self.assertRaises(ocr.OCRExecutionError) as error:
                ocr.TrOCRFrenchCPU(self.snapshot()).recognize_line(self.source, key="ligne", bbox=(0, 0, 1, 1))
        self.assertNotIn("secret", str(error.exception))
        self.assertEqual(torch.set_num_threads.call_args_list, [mock.call(2), mock.call(8)])

    def test_invalid_crop_is_rejected_before_model_load(self):
        with self.trocr() as (_, transformers, *_):
            for bbox in ((0, 0, 0, 1), (-.1, 0, 1, 1), (0, 0, float("nan"), 1)):
                with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                    ocr.TrOCRFrenchCPU("absent").recognize_line(self.source, key="ligne", bbox=bbox)
            transformers.TrOCRProcessor.from_pretrained.assert_not_called()

    def test_missing_model_or_hub_id_never_calls_loader(self):
        with self.trocr() as (_, transformers, *_):
            for path in (self.directory / "absent", "owner/model-on-hub"):
                with self.subTest(path=path), self.assertRaises(ocr.OCRUnavailableError):
                    ocr.TrOCRFrenchCPU(path).recognize_line(self.source, key="ligne", bbox=(0, 0, 1, 1))
            transformers.TrOCRProcessor.from_pretrained.assert_not_called()

    def test_manifest_language_and_unsafe_weights_are_rejected(self):
        directory = self.snapshot()
        manifest = directory / "ocr-model.json"
        manifest.write_text('{"model_id":"english-model","language":"en","unit":"line"}', encoding="utf-8")
        with self.assertRaises(ocr.OCRUnavailableError):
            ocr._snapshot(directory)
        manifest.write_text('{"model_id":"french-model","language":"fr","unit":"line"}', encoding="utf-8")
        (directory / "model.safetensors").rename(directory / "pytorch_model.bin")
        with self.assertRaises(ocr.OCRUnavailableError):
            ocr._snapshot(directory)

    def test_incomplete_snapshot_never_falls_back_to_network(self):
        directory = self.snapshot()
        with self.trocr() as (_, transformers, *_):
            transformers.TrOCRProcessor.from_pretrained.side_effect = OSError("missing tokenizer secret")
            with self.assertRaises(ocr.OCRUnavailableError) as error:
                ocr.TrOCRFrenchCPU(directory).recognize_line(self.source, key="ligne", bbox=(0, 0, 1, 1))
            self.assertNotIn("secret", str(error.exception))
            transformers.TrOCRProcessor.from_pretrained.assert_called_once()

    def test_missing_optional_dependencies_are_explicit(self):
        with mock.patch.dict(sys.modules, {"torch": None, "transformers": None}):
            with self.assertRaises(ocr.OCRUnavailableError):
                ocr.TrOCRFrenchCPU(self.snapshot()).recognize_line(self.source, key="ligne", bbox=(0, 0, 1, 1))

    def test_snapshot_fingerprint_changes_with_tokenizer(self):
        directory = self.snapshot()
        initial = ocr._snapshot(directory)[2]
        (directory / "tokenizer.json").write_text('{"changed":true}', encoding="utf-8")
        self.assertNotEqual(ocr._snapshot(directory)[2], initial)


if __name__ == "__main__":
    unittest.main()
