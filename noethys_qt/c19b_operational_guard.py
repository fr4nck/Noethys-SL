"""C19b : lien Famille -> inscription -> consommations -> factures.

Garde de démonstration, PAS habilitation de production. N'ouvre jamais
le profil Noethys, le réseau ni des données utilisateur. Si le fichier
n'est pas la fixture C8+C13 éphémère attendue, ne pas exposer le lien.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


_C8 = "NOETHYS_QT_C8_ONLY_FAKE_FIXTURE_20261027"
_C13 = "C13_FINANCE_FICTIVE_ONLY"


def can_demo_inscription_invoices(path, *, read_only_demo: bool) -> bool:
    if not read_only_demo or path is None:
        return False
    try:
        source = Path(path)
        if (
            source.is_symlink()
            or source.parent.is_symlink()
            or not source.is_file()
            or source.name != "C8_DEMONSTRATION_FICTIVE.sqlite"
            or not source.parent.name.startswith("noethys-qt-c8-fictif-")
            or source.resolve().parent != source.parent.resolve()
        ):
            return False
        # URI en lecture seule : aucun fichier SQLite créé implicitement.
        with closing(sqlite3.connect(
            "file:" + source.resolve().as_posix() + "?mode=ro", uri=True
        )) as db:
            a = db.execute("SELECT token FROM c8_marker").fetchone()
            b = db.execute("SELECT token FROM c13_marker").fetchone()
        return a == (_C8,) and b == (_C13,)
    except (OSError, ValueError, sqlite3.DatabaseError):
        return False
