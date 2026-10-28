# -*- coding: utf-8 -*-
"""OCR-02 : adaptateurs locaux facultatifs, sans UI, réseau ni écriture métier.

Entrée : une image de page déjà rasterisée. Sortie : OCRResult à relire.
Les moteurs et modèles doivent être provisionnés explicitement hors application.
"""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import threading

from .UTILS_OCR_contract import OCRField, OCRResult


MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 20_000_000
_TORCH_LOCK = threading.RLock()


class OCRUnavailableError(RuntimeError):
    """Dépendance ou modèle local absent/incompatible ; aucun repli réseau."""


class OCRExecutionError(RuntimeError):
    """Reconnaissance échouée ; aucun résultat partiel n'est rendu."""


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("%s doit être un entier de %s à %s" % (name, low, high))
    return value


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _page(path, source_page):
    _integer(source_page, "source_page", 1, 1_000_000)
    try:
        from PIL import Image
    except ImportError:
        raise OCRUnavailableError("Pillow local est nécessaire pour lire une image") from None
    # Une seule lecture : l'empreinte désigne exactement les octets décodés.
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_SOURCE_BYTES + 1)
    if not data or len(data) > MAX_SOURCE_BYTES:
        raise ValueError("Image vide ou supérieure à 32 Mio")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("PNG", "JPEG", "TIFF", "BMP", "PPM"):
                raise ValueError("Format image non pris en charge")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Fournir une seule page rasterisée, sans animation")
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("Image supérieure à 20 millions de pixels")
            # Pas de rotation EXIF implicite : les coordonnées restent celles du raster.
            # Aplatir la transparence sur blanc, plutôt que transformer l'encre en noir.
            rgba = image.convert("RGBA")
            rgb = Image.new("RGB", image.size, "white")
            rgb.paste(rgba, mask=rgba.getchannel("A"))
    except (OSError, Image.DecompressionBombError):
        raise ValueError("Image illisible ou démesurée") from None
    return rgb, hashlib.sha256(data).hexdigest()


def _crop(image, bbox, key, source_page):
    # Réutiliser les validations du contrat, y compris NaN et les limites [0, 1].
    field = OCRField(key, "", source_page, tuple(bbox), "trocr-fr-cpu", "handwritten")
    x0, y0, x1, y1 = field.bbox
    rect = (math.floor(x0 * image.width), math.floor(y0 * image.height),
            math.ceil(x1 * image.width), math.ceil(y1 * image.height))
    normalized = (rect[0] / image.width, rect[1] / image.height,
                  rect[2] / image.width, rect[3] / image.height)
    return image.crop(rect), normalized


class TesseractFrenchCPU:
    """Imprimé français, Tesseract 5 CPU, un champ proposé par mot détecté."""

    def __init__(self, executable, tessdata_dir, *, threads=2, timeout=60, psm=3):
        self.executable = Path(executable).resolve()
        self.tessdata_dir = Path(tessdata_dir).resolve()
        self.threads = _integer(threads, "threads", 1, 12)
        self.psm = _integer(psm, "psm", 3, 13)
        if self.psm in (5, 12):
            raise ValueError("Mode vertical/OSD hors périmètre de l'adaptateur français")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 600:
            raise ValueError("timeout doit appartenir à ]0, 600] secondes")
        self.timeout = timeout

    def _run(self, arguments, data=None):
        env = dict(os.environ, OMP_THREAD_LIMIT=str(self.threads),
                   OMP_NUM_THREADS=str(self.threads))
        try:
            result = subprocess.run(
                [str(self.executable)] + arguments, input=data,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                timeout=self.timeout, env=env, shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            raise OCRExecutionError("Tesseract indisponible ou délai dépassé") from None
        if result.returncode:
            # stderr peut contenir des données du document : ne pas les journaliser.
            raise OCRExecutionError("Tesseract a refusé la reconnaissance")
        return result.stdout

    def recognize_page(self, image_path, *, source_page=1, key_prefix="ocr"):
        if not isinstance(key_prefix, str) or not key_prefix.strip():
            raise ValueError("key_prefix est obligatoire")
        model = self.tessdata_dir / "fra.traineddata"
        if not self.executable.is_file() or not model.is_file():
            raise OCRUnavailableError("Fournir Tesseract 5 CPU et fra.traineddata locaux")
        image, source_hash = _page(image_path, source_page)
        version_output = self._run(["--version"]).decode("utf-8", errors="replace")
        version = re.search(r"^tesseract (5\.\S+)", version_output)
        if not version or "opencl" in version_output.lower():
            raise OCRUnavailableError("Une distribution Tesseract 5 CPU sans OpenCL est requise")
        model_hash = _sha256_file(model)
        raster = io.BytesIO()
        image.save(raster, format="PPM")
        tsv = self._run([
            "stdin", "stdout", "--tessdata-dir", str(self.tessdata_dir),
            "-l", "fra", "--oem", "1", "--psm", str(self.psm),
            "-c", "tessedit_create_tsv=1",
        ], raster.getvalue())
        if _sha256_file(model) != model_hash:
            raise OCRExecutionError("Le modèle français a changé pendant la reconnaissance")
        fields = self._fields(tsv, image.size, source_page, key_prefix)
        return OCRResult(source_hash, fields, "tesseract/fra@sha256:" + model_hash,
                         "tesseract " + version.group(1))

    @staticmethod
    def _fields(data, size, source_page, prefix):
        """Les boîtes TSV sont exprimées en pixels de la page, sans écrêtage."""
        try:
            rows = csv.DictReader(io.StringIO(data.decode("utf-8")), delimiter="\t")
            required = {"level", "page_num", "left", "top", "width", "height", "conf", "text"}
            if not required.issubset(rows.fieldnames or ()):
                raise ValueError("En-tête TSV incomplet")
            fields = []
            width, height = size
            for row in rows:
                if int(row["page_num"]) != 1:
                    raise ValueError("TSV multipage inattendu")
                if int(row["level"]) != 5:
                    continue
                text = row["text"].strip()
                if not text:
                    continue
                left, top, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
                confidence = float(row["conf"])
                if confidence == -1:
                    confidence = None
                elif not math.isfinite(confidence) or not 0 <= confidence <= 100:
                    raise ValueError("Confiance TSV invalide")
                else:
                    confidence /= 100
                fields.append(OCRField(
                    "%s.word.%s" % (prefix, len(fields) + 1), text, source_page,
                    (left / width, top / height, (left + w) / width, (top + h) / height),
                    "tesseract-fra-cpu", "printed", confidence,
                ))
            return tuple(fields)
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, csv.Error):
            raise OCRExecutionError("Sortie TSV Tesseract invalide") from None


def _snapshot(model_dir):
    """Empreinte du snapshot local complet, sans accepter un identifiant Hub."""
    directory = Path(model_dir).resolve()
    if not directory.is_dir():
        raise OCRUnavailableError("Fournir un répertoire TrOCR français local complet")
    required = ("ocr-model.json", "config.json", "preprocessor_config.json",
                "tokenizer_config.json", "model.safetensors")
    if not all((directory / name).is_file() for name in required):
        raise OCRUnavailableError("Snapshot TrOCR incomplet (safetensors et manifeste requis)")
    try:
        metadata = json.loads((directory / "ocr-model.json").read_text(encoding="utf-8"))
        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        if (metadata["language"] != "fr" or metadata["unit"] != "line"
                or not isinstance(metadata["model_id"], str) or not metadata["model_id"].strip()
                or config["model_type"] != "vision-encoder-decoder"
                or config["decoder"]["model_type"] != "trocr"):
            raise ValueError()
    except (OSError, ValueError, KeyError, TypeError):
        raise OCRUnavailableError("Manifeste français/ligne ou configuration TrOCR invalide") from None
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise OCRUnavailableError("Exporter le snapshot local sans liens symboliques")
        if path.is_file():
            digest.update(path.relative_to(directory).as_posix().encode("utf-8") + b"\0")
            digest.update(_sha256_file(path).encode("ascii") + b"\n")
    return directory, metadata["model_id"], digest.hexdigest()


class TrOCRFrenchCPU:
    """Une ligne manuscrite explicitement découpée, modèle français local.

    Une instance conserve un seul modèle en mémoire ; appels OCR sérialisés.
    La déclaration française du manifeste doit être qualifiée par l'opérateur.
    """

    def __init__(self, model_dir, *, threads=2, max_new_tokens=128):
        self.model_dir = model_dir
        self.threads = _integer(threads, "threads", 1, 12)
        self.max_new_tokens = _integer(max_new_tokens, "max_new_tokens", 1, 512)
        self._runtime = None

    def _load(self, torch, transformers):
        if self._runtime is None:
            directory, model_id, digest = _snapshot(self.model_dir)
            local = dict(local_files_only=True, token=False, trust_remote_code=False)
            try:
                processor = transformers.TrOCRProcessor.from_pretrained(str(directory), **local)
                model = transformers.VisionEncoderDecoderModel.from_pretrained(
                    str(directory), use_safetensors=True, **local,
                ).to(device="cpu", dtype=torch.float32).eval()
            except Exception:
                raise OCRUnavailableError("Chargement local TrOCR impossible ; aucun téléchargement tenté") from None
            if _snapshot(directory)[2] != digest:
                raise OCRExecutionError("Le snapshot TrOCR a changé pendant son chargement")
            provenance = "transformers %s; torch %s" % (transformers.__version__, torch.__version__)
            self._runtime = (processor, model, model_id + "@sha256:" + digest, provenance)
        return self._runtime

    def recognize_line(self, image_path, *, key, bbox, source_page=1):
        image, source_hash = _page(image_path, source_page)
        line, normalized = _crop(image, bbox, key, source_page)
        # Valider l'installation avant les imports facultatifs et sans accès au Hub.
        if self._runtime is None:
            _snapshot(self.model_dir)
        try:
            import torch
            import transformers
        except ImportError:
            raise OCRUnavailableError("Installer explicitement PyTorch CPU et Transformers pour TrOCR") from None
        with _TORCH_LOCK:
            previous_threads = torch.get_num_threads()
            try:
                torch.set_num_threads(self.threads)
                # Neutraliser aussi un éventuel périphérique PyTorch global CUDA.
                with torch.device("cpu"), torch.inference_mode():
                    processor, model, model_id, version = self._load(torch, transformers)
                    pixels = processor(images=line, return_tensors="pt").pixel_values
                    tokens = model.generate(
                        pixels.to(device="cpu", dtype=torch.float32),
                        max_new_tokens=self.max_new_tokens, num_beams=1, do_sample=False,
                    )
                    decoded = processor.batch_decode(tokens, skip_special_tokens=True)
                if len(decoded) != 1 or not isinstance(decoded[0], str):
                    raise OCRExecutionError("Décodage TrOCR invalide")
                text = decoded[0].strip()
            except (OCRUnavailableError, OCRExecutionError):
                raise
            except Exception:
                raise OCRExecutionError("Reconnaissance TrOCR échouée") from None
            finally:
                torch.set_num_threads(previous_threads)
        fields = (OCRField(key, text, source_page, normalized, "trocr-fr-cpu",
                           "handwritten", confidence=None),) if text else ()
        return OCRResult(source_hash, fields, model_id, version)
