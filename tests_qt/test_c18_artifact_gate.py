"""C18 : invariants des preuves générées, sans PySide6 ni données réelles."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.qt_c18_artifact_gate import PNG_MAGIC, PROFILES, STAGES, verifier


class C18ArtifactGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="qt-c18-artifact-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for profile in PROFILES:
            evidence = []
            for stage in STAGES:
                png = self.root / (profile + "-" + stage + ".png")
                # Seul le contrôle de la présence, taille et signature est
                # qualifié ici. Les images réelles sont produites par Qt CI.
                png.write_bytes(PNG_MAGIC + b"0" * 3200)
                evidence.append({"stage": stage, "size": [1024, 768]})
            self._trace(profile, evidence)

    def _trace(self, profile, images, **changes):
        data = {
            "lot": "C18",
            "source": "C8_TO_C18_TEMPORARY_FICTIVE_ONLY",
            "profile": profile,
            "images": images,
            "sqlite_unchanged": True,
            "personal_history_enabled_on_production": False,
            "pieces_enabled_on_production": False,
            "not_qualified_for_production": True,
        }
        data.update(changes)
        (self.root / (profile + "-trace.json")).write_text(
            json.dumps(data), encoding="utf-8"
        )

    def test_deux_traces_et_36_captures_acceptes(self):
        verifier(self.root)

    def test_capture_manquante_refusee(self):
        (self.root / "dark-150-accueil.png").unlink()
        with self.assertRaisesRegex(ValueError, "Capture"):
            verifier(self.root)

    def test_source_alteree_refusee(self):
        self._trace("light-100", [
            {"stage": stage, "size": [1024, 768]} for stage in STAGES
        ], sqlite_unchanged=False)
        with self.assertRaisesRegex(ValueError, "confidentialité"):
            verifier(self.root)

    def test_fichier_supplementaire_refuse(self):
        (self.root / "source-personnelle.txt").write_text("interdit", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inattendus"):
            verifier(self.root)


if __name__ == "__main__":
    unittest.main()
