# -*- coding: utf-8 -*-
"""Read-only, non-nominative preflight for Noethys .nod ALSH meal ordering.

This is NOT a meal calculator and NEVER validates a supplier order.
Only names of known SQL tables, column names and aggregate row counts leave
this function. Values from INSERT statements are never decoded or returned.
"""

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

MAX_SQL_BYTES = 150 * 1024 * 1024
SOURCE_MEMBER = "mad_data.sql"
TABLES = (
    "activites", "unites", "ouvertures", "inscriptions", "consommations",
    "restaurateurs", "modeles_commandes", "modeles_commandes_colonnes",
    "commandes", "commandes_valeurs", "questionnaire_categories",
    "questionnaire_questions", "questionnaire_choix", "questionnaire_reponses",
    "tarifs", "combi_tarifs", "combi_tarifs_unites", "prestations",
)
CREATE_RE = re.compile(rb"(?im)^CREATE TABLE\s+`([A-Za-z0-9_]+)`\s*\(")
INSERT_RE = re.compile(
    rb"(?im)^INSERT INTO\s+`([A-Za-z0-9_]+)`\s+(?:\([^\n;]*\)\s+)?VALUES\s*"
)


class AuditLotCInvalide(ValueError):
    """The backup cannot be safely inspected."""


def _insert_row_count(sql, start):
    """Count top-level tuples until the closing semicolon of one INSERT.

    MySQL string escaping, parentheses inside strings, and nested SQL
    functions cannot create phantom rows. Fail closed on invalid syntax.
    """
    quoted = False
    depth = 0
    count = 0
    i = start
    size = len(sql)
    while i < size:
        char = sql[i]
        if quoted:
            if char == 92:  # MySQL backslash-escaped next byte
                i += 2
                continue
            if char == 39:  # SQL doubled quote
                if i + 1 < size and sql[i + 1] == 39:
                    i += 2
                    continue
                quoted = False
        elif char == 39:
            quoted = True
        elif char == 40:
            if depth == 0:
                count += 1
            depth += 1
        elif char == 41:
            depth -= 1
            if depth < 0:
                raise AuditLotCInvalide("SQL INSERT mal forme")
        elif char == 59 and depth == 0:
            return count
        i += 1
    raise AuditLotCInvalide("SQL INSERT sans terminateur")


def _inventory(sql):
    tables = {m.group(1).decode("ascii") for m in CREATE_RE.finditer(sql)}
    rows = {table: 0 for table in TABLES}
    for match in INSERT_RE.finditer(sql):
        name = match.group(1).decode("ascii")
        if name in rows:
            rows[name] += _insert_row_count(sql, match.end())
    return {name: {"schema": name in tables, "lignes": rows[name]}
            for name in TABLES}


def _controle(inventaire, tables):
    if not all(inventaire[t]["schema"] for t in tables):
        return "SCHEMA_INCOMPLET"
    if any(inventaire[t]["lignes"] == 0 for t in tables):
        return "CONFIGURATION_ABSENTE"
    return "A_QUALIFIER"


def AuditerSauvegarde(chemin):
    """Return only aggregate metadata, never rows, names, health or contacts."""
    chemin = Path(chemin)
    try:
        with zipfile.ZipFile(chemin, "r") as archive:
            info = archive.getinfo(SOURCE_MEMBER)
            if info.file_size > MAX_SQL_BYTES:
                raise AuditLotCInvalide("SQL trop volumineux pour le prevol")
            with archive.open(info) as stream:
                sql = stream.read(MAX_SQL_BYTES + 1)
            if len(sql) > MAX_SQL_BYTES or len(sql) != info.file_size:
                raise AuditLotCInvalide("Taille SQL incoherente ou excessive")
    except (FileNotFoundError, OSError, zipfile.BadZipFile, KeyError, RuntimeError, EOFError) as exc:
        raise AuditLotCInvalide("Archive Noethys .nod absente ou illisible") from exc
    inv = _inventory(sql)
    return {
        "outil": "Noethys-SL Lot C - prevol commandes ALSH",
        "lecture_seule": True,
        "portee": "compteurs de toutes les activites, pas seulement ALSH",
        "configuration_fournisseur": _controle(inv, (
            "restaurateurs", "modeles_commandes", "modeles_commandes_colonnes")),
        "configuration_questionnaire": _controle(inv, (
            "questionnaire_questions", "questionnaire_choix")),
        "remarque": (
            "La presence de questions ne prouve pas l'existence de la question Type de repas. "
            "Aucune commande ne doit etre emise sur la base de ce prevol."
        ),
        "tables": inv,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sauvegarde", help="Chemin d'une sauvegarde .nod (lecture seule)")
    parser.add_argument("--sortie", help="Fichier JSON agrege, sans donnees nominatives")
    args = parser.parse_args(argv)
    try:
        rapport = AuditerSauvegarde(args.sauvegarde)
    except AuditLotCInvalide as exc:
        print(str(exc), file=sys.stderr)
        return 2
    contenu = json.dumps(rapport, indent=2, ensure_ascii=False) + "\n"
    if args.sortie:
        Path(args.sortie).write_text(contenu, encoding="utf-8")
    else:
        sys.stdout.write(contenu)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
