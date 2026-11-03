"""C19g: projection de tables du schema declare Noethys, hors Qt/wx.

Ne lit QUE noethys/Data/DATA_Tables.py via AST/literal_eval.
N'execute jamais ce module, ne se connecte a aucune base,
n'importe ni wx, ni le logiciel metier.
Cette projection ne certifie PAS le schema reel de SERVEURPMSL.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "noethys" / "Data" / "DATA_Tables.py"

# Champ et type exacts releves dans la declaration historique.
REQUIRED = {
    "comptes_payeurs": {
        "IDcompte_payeur": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "IDfamille": "INTEGER",
    },
    "inscriptions": {
        "IDinscription": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "IDindividu": "INTEGER",
        "IDfamille": "INTEGER",
        "IDactivite": "INTEGER",
        "IDcompte_payeur": "INTEGER",
    },
    "consommations": {
        "IDconso": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "IDindividu": "INTEGER",
        "IDinscription": "INTEGER",
        "IDactivite": "INTEGER",
        "date": "DATE",
        "etat": "VARCHAR(20)",
        "IDcompte_payeur": "INTEGER",
        "IDprestation": "INTEGER",
        "verrouillage": "INTEGER",
    },
    "prestations": {
        "IDprestation": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "IDcompte_payeur": "INTEGER",
        "date": "DATE",
        "montant": "FLOAT",
        "IDactivite": "INTEGER",
        "IDfacture": "INTEGER",
        "IDfamille": "INTEGER",
        "IDindividu": "INTEGER",
        "forfait": "INTEGER",
        "forfait_date_debut": "DATE",
        "forfait_date_fin": "DATE",
    },
    "factures": {
        "IDfacture": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "numero": "BIGINT",
        "IDcompte_payeur": "INTEGER",
        "date_edition": "DATE",
        "date_debut": "DATE",
        "date_fin": "DATE",
        "total": "FLOAT",
        "regle": "FLOAT",
        "solde": "FLOAT",
    },
    "ventilation": {
        "IDventilation": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "IDcompte_payeur": "INTEGER",
        "IDreglement": "INTEGER",
        "IDprestation": "INTEGER",
        "montant": "FLOAT",
    },
    "periodes_gestion": {
        "IDperiode": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "date_debut": "DATE",
        "date_fin": "DATE",
        "verrou_consommations": "INTEGER",
        "verrou_prestations": "INTEGER",
        "verrou_factures": "INTEGER",
    },
}

_SAFE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def extract_table_declarations(source: Path = SOURCE) -> dict:
    """Obtient le seul noeud de dictionnaire litteral, sans exec/import."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    defs = [
        item.value for item in tree.body
        if isinstance(item, ast.Assign)
        and len(item.targets) == 1
        and isinstance(item.targets[0], ast.Name)
        and item.targets[0].id == "DB_DATA"
    ]
    if len(defs) != 1:
        raise ValueError("Definition DB_DATA absente ou ambigue")
    data = ast.literal_eval(defs[0])
    if not isinstance(data, dict):
        raise ValueError("DB_DATA non litteral")
    return data


def declared_projection(source: Path = SOURCE) -> dict:
    data = extract_table_declarations(source)
    projection = {}
    for table, expected in REQUIRED.items():
        values = data.get(table)
        if not isinstance(values, list):
            raise ValueError("Table requise absente : " + table)
        cols = {}
        for triplet in values:
            if (
                not isinstance(triplet, tuple) or len(triplet) != 3
                or not isinstance(triplet[0], str)
                or not isinstance(triplet[1], str)
                or triplet[0] in cols
            ):
                raise ValueError("Structure de colonne invalide : " + table)
            cols[triplet[0]] = triplet[1]
        for name, typ in expected.items():
            if cols.get(name) != typ:
                raise ValueError(
                    "Derive schema : %s.%s attend %s, observe %s" %
                    (table, name, typ, cols.get(name))
                )
        projection[table] = tuple(
            (name, typ) for name, typ in cols.items() if name in expected
        )
    return projection


def _mysql_type(typ):
    if typ == "INTEGER PRIMARY KEY AUTOINCREMENT":
        return "INT NOT NULL AUTO_INCREMENT PRIMARY KEY"
    simple = {"INTEGER": "INT NULL", "BIGINT": "BIGINT NULL",
              "FLOAT": "FLOAT NULL", "DATE": "DATE NULL"}
    if typ in simple:
        return simple[typ]
    if re.fullmatch(r"VARCHAR\([1-9][0-9]{0,3}\)", typ):
        return typ + " NULL"
    raise ValueError("Type non prevu : " + typ)


def projection_ddl(source: Path = SOURCE):
    """Ne projette qu'un sous-ensemble de colonnes, sans FK inventee."""
    ddl = []
    quote = chr(96)
    for table, fields in declared_projection(source).items():
        if not _SAFE.fullmatch(table):
            raise ValueError("Table non sure")
        columns = []
        for name, typ in fields:
            if not _SAFE.fullmatch(name):
                raise ValueError("Colonne non sure")
            columns.append(
                "  %s%s%s %s" % (quote, name, quote, _mysql_type(typ))
            )
        ddl.append(
            "CREATE TABLE %s%s%s (\n%s\n) ENGINE=InnoDB" %
            (quote, table, quote, ",\n".join(columns))
        )
    return tuple(ddl)


def limitations():
    return (
        "FLOAT non monetaire exact: prestations.montant, "
        "factures.total/regle/solde, ventilation.montant",
        "PROJECTION PARTIELLE sans index, FOREIGN KEY ou migrations",
        "AUCUN ACCES PMSL, AUCUNE CREATION DE FACTURE NOETHYS",
    )
