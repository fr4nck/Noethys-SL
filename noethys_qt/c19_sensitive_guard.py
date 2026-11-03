"""C19 : garder les référentiels financiers hors des bases réelles.

La garde n'est PAS une habilitation métier. Elle permet seulement les
tests Qt sur la fixture temporaire issue de C8/C18 et marquée C19.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from .c18_sensitive_guard import require_c18_synthetic_source


C19_MARKER = "C19_FINANCE_ORGANISATION_100_PERCENT_SYNTHETIC"


def require_c19_synthetic_source(
    path, *, read_only_demo, c18_enabled, c19_enabled,
):
    if not read_only_demo or not c19_enabled or not c18_enabled:
        raise ValueError("C19 financier interdit hors recette fictive")
    require_c18_synthetic_source(
        path, read_only_demo=read_only_demo,
        c18_enabled=c18_enabled,
    )
    source = Path(path)
    if source.is_symlink() or source.parent.is_symlink():
        raise ValueError("C19 refuse les liens symboliques")
    with closing(sqlite3.connect(
        "file:" + source.resolve().as_posix() + "?mode=ro",
        uri=True,
    )) as db:
        try:
            marker = db.execute(
                "SELECT token FROM c19_marker"
            ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise ValueError("C19 : marqueur fictif absent") from exc
    if marker != (C19_MARKER,):
        raise ValueError("C19 : jeu fictif inconnu")
    return True
