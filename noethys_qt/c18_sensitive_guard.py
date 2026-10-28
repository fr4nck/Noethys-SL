"""C18 : garde d'exposition des dossiers personnels pour la démonstration.

Ne constitue PAS un contrôle d'habilitations réelles. Elle empêche qu'un
simple drapeau de code expose la scolarité / les pièces d'une vraie base.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


C18_MARKER = "C18_ONLY_FICTIVE_DOCUMENTS_AND_SCHOOL"


def require_c18_synthetic_source(path, *, read_only_demo, c18_enabled):
    if not read_only_demo or not c18_enabled or path is None:
        raise ValueError("C18 personnel interdit hors démonstration fictive")
    source = Path(path)
    if (
        source.is_symlink()
        or not source.is_file()
        or source.name != "C8_DEMONSTRATION_FICTIVE.sqlite"
        or not source.parent.name.startswith("noethys-qt-c8-fictif-")
        or source.parent.is_symlink()
        or source.resolve().parent != source.parent.resolve()
    ):
        raise ValueError("C18 source temporaire fictive obligatoire")
    with closing(sqlite3.connect(
        "file:" + source.resolve().as_posix() + "?mode=ro",
        uri=True,
    )) as connection:
        try:
            row = connection.execute(
                "SELECT token FROM c18_marker"
            ).fetchone()
            c16 = connection.execute(
                "SELECT token FROM c16_marker"
            ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise ValueError("C18 marqueurs de démonstration absents") from exc
    if row != (C18_MARKER,) or c16 != ("C16_ALL_FAKE_NOETHYS_ONLY",):
        raise ValueError("C18 jeu fictif non reconnu")
    return True
