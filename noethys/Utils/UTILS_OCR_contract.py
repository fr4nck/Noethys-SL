# -*- coding: utf-8 -*-
"""OCR-01: contrat d'extraction documentaire, sans toolkit, base ou réseau.

Ce module n'effectue aucune reconnaissance. Un moteur OCR externe pourra
produire des propositions; leur application métier est hors de ce contrat.
"""
from dataclasses import dataclass
from typing import Optional, Tuple


_ALLOWED_KINDS = frozenset(("printed", "handwritten", "checkbox"))
_ALLOWED_STATES = frozenset(("proposed", "review_required", "rejected"))


@dataclass(frozen=True)
class OCRField:
    key: str
    value: str
    source_page: int
    bbox: Tuple[float, float, float, float]
    engine: str
    kind: str
    confidence: Optional[float] = None
    state: str = "review_required"

    def __post_init__(self):
        if not self.key or not self.engine or not self.kind in _ALLOWED_KINDS:
            raise ValueError("OCR field key, engine and kind are required")
        if self.source_page < 1:
            raise ValueError("Page numbers are 1-based")
        if len(self.bbox) != 4 or not all(isinstance(v, (int, float)) for v in self.bbox):
            raise ValueError("bbox must contain four coordinates")
        x0, y0, x1, y1 = self.bbox
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("bbox must be ordered and normalized to [0, 1]")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must belong to [0, 1]")
        if self.state not in _ALLOWED_STATES:
            raise ValueError("Unknown review state")

    @property
    def requires_review(self):
        # Une confiance élevée n'autorise jamais l'écriture automatique.
        return True


@dataclass(frozen=True)
class OCRResult:
    source_sha256: str
    fields: Tuple[OCRField, ...]
    model_id: str
    engine_version: str

    def __post_init__(self):
        import re
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ValueError("A lowercase SHA-256 fingerprint is required")
        if not self.model_id or not self.engine_version:
            raise ValueError("OCR provenance is required")
        if not isinstance(self.fields, tuple) or not all(isinstance(f, OCRField) for f in self.fields):
            raise ValueError("fields must be a tuple of OCRField")

    def to_review_payload(self):
        """Copie sérialisable pour l'interface de contrôle, jamais pour la DB."""
        return {
            "source_sha256": self.source_sha256,
            "model_id": self.model_id,
            "engine_version": self.engine_version,
            "write_allowed": False,
            "fields": [
                {
                    "key": f.key, "value": f.value, "source_page": f.source_page,
                    "bbox": list(f.bbox), "engine": f.engine, "kind": f.kind,
                    "confidence": f.confidence, "state": f.state,
                    "requires_review": True,
                }
                for f in self.fields
            ],
        }
