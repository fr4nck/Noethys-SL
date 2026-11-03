# -*- coding: utf-8 -*-
"""Usage: python scripts/auditer_sauvegarde_rc105.py "archive.nod"

Controle LOCAL et LECTURE SEULE : aucun mot de passe demande, aucun acces MySQL.
Ne peut pas inspecter une sauvegarde chiffree .noc sans decrypter sa copie
dans un environnement de recette protege. La preuve finale est une restauration.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils.UTILS_Archive_audit_RC105 import InspecterArchive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Archive ZIP/.nod non chiffree sur copie locale")
    args = parser.parse_args(argv)
    bilan = InspecterArchive(args.archive)
    print(json.dumps(bilan, indent=2, ensure_ascii=False))
    return {"PASS": 0, "LEGACY": 2, "FAIL": 1}[bilan["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
