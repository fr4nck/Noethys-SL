"""Preuve C18 : 36 captures et deux traces, jamais de données PMSL.

Outil de CI sans accès aux profils, réseau ou bases réelles.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROFILES = ("light-100", "dark-150")
STAGES = (
    "accueil", "ecoles", "classes", "niveaux",
    "parcours-fictifs", "fiche-individu-fictif",
    "parcours-individu-filtre", "retour-fiche-individu",
    "produits", "categories-produits", "types-pieces",
    "pieces-fictives", "pieces-famille", "fiche-famille-fictive",
    "retour-pieces", "suivi-activites-c17",
    "etats-consommations-c16", "retour-accueil",
)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def verifier(root: Path) -> None:
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Répertoire de preuves C18 absent ou interdit")
    attendus = set()
    for profile in PROFILES:
        trace = root / (profile + "-trace.json")
        attendus.add(trace.name)
        if not trace.is_file() or trace.is_symlink():
            raise ValueError("Trace C18 manquante : " + trace.name)
        rapport = json.loads(trace.read_text(encoding="utf-8"))
        if (
            rapport.get("lot") != "C18"
            or rapport.get("source") != "C8_TO_C18_TEMPORARY_FICTIVE_ONLY"
            or rapport.get("profile") != profile
            or rapport.get("sqlite_unchanged") is not True
            or rapport.get("personal_history_enabled_on_production") is not False
            or rapport.get("pieces_enabled_on_production") is not False
            or rapport.get("not_qualified_for_production") is not True
        ):
            raise ValueError("Invariants de confidentialité C18 absents : " + profile)
        images = rapport.get("images")
        if not isinstance(images, list) or tuple(
            entry.get("stage") for entry in images if isinstance(entry, dict)
        ) != STAGES or len(images) != len(STAGES):
            raise ValueError("Parcours C18 incomplet : " + profile)
        for entry, stage in zip(images, STAGES):
            dimensions = entry.get("size")
            if (not isinstance(dimensions, list) or len(dimensions) != 2
                    or any(type(v) is not int or v < 1 for v in dimensions)):
                raise ValueError("Dimensions C18 invalides : " + stage)
            png = root / (profile + "-" + stage + ".png")
            attendus.add(png.name)
            if not png.is_file() or png.is_symlink() or png.stat().st_size < 3000:
                raise ValueError("Capture C18 absente ou trop petite : " + png.name)
            with png.open("rb") as fichier:
                if fichier.read(8) != PNG_MAGIC:
                    raise ValueError("Signature PNG invalide : " + png.name)
    presents = {item.name for item in root.iterdir()}
    if presents != attendus or any(item.is_symlink() for item in root.iterdir()):
        raise ValueError("Preuves C18 manquantes ou fichiers inattendus")
    print("C18_ARTIFACT_GATE_PASS images=36 traces=2 sqlite_unchanged=true")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/qt-c18"))
    args = parser.parse_args()
    verifier(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
