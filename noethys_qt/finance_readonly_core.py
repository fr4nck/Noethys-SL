"""Finance Qt — consultations STRICTEMENT en lecture seule (C13).

Portage limité aux champs source reconnus dans les listes wx :
OL_Factures, OL_Prestations, OL_Reglements, OL_Depots et
OL_Operations_tresorerie. Ne calcule ni solde ni ventilation,
ne rapproche ni facture ni règlement et ne fait aucun écrit SQL.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

MAX_FINANCE_ROWS = 250

# Dans l'ordre exact des SELECT statiques. Aucun nom de table/colonne
# n'est issu d'un utilisateur ou de la base.
FINANCE_DOMAINS = {
    "invoices": (
        "Factures",
        ("ID", "N°", "Date émission", "Échéance", "Famille",
         "Total enregistré", "Réglé enregistré", "Solde enregistré", "État"),
        ("id", "number", "date", "due", "family", "total", "paid", "balance", "status"),
        ("total", "paid", "balance"),
    ),
    "services": (
        "Prestations",
        ("ID", "Date", "Famille", "Individu", "Libellé", "Montant enregistré", "Facture"),
        ("id", "date", "family", "individual", "label", "amount", "invoice"),
        ("amount",),
    ),
    "payments": (
        "Règlements",
        ("ID", "Date", "Famille", "Mode", "Montant enregistré", "N° pièce", "Dépôt"),
        ("id", "date", "family", "mode", "amount", "piece", "deposit"),
        ("amount",),
    ),
    "allocations": (
        "Ventilation",
        ("ID", "Règlement", "Prestation", "Famille", "Montant enregistré", "Facture"),
        ("id", "payment", "service", "family", "amount", "invoice"),
        ("amount",),
    ),
    "treasury": (
        "Trésorerie",
        ("ID", "Date", "Type enregistré", "Libellé", "Montant enregistré",
         "Compte bancaire", "Relevé", "N° pièce"),
        ("id", "date", "type", "label", "amount", "bank", "statement", "piece"),
        ("amount",),
    ),
    "deposits": (
        "Dépôts",
        ("ID", "Date", "Nom", "Compte bancaire", "Verrouillage"),
        ("id", "date", "name", "bank", "locked"),
        (),
    ),
}
FAMILY_DOMAINS = frozenset(("invoices", "services", "payments", "allocations"))
YEAR_DOMAINS = frozenset(FINANCE_DOMAINS) - {'allocations'}
RELATED_FILTERS = {
    "services": ("invoice_id", "p.IDfacture"),
    "allocations": ("payment_id", "v.IDreglement"),
    "payments": ("deposit_id", "r.IDdepot"),
}

SQL_SOURCES = {
    "invoices": (
        "SELECT f.IDfacture, f.numero, f.date_edition, f.date_echeance, "
        "cp.IDfamille, f.total, f.regle, f.solde, f.etat "
        "FROM factures f "
        "LEFT JOIN comptes_payeurs cp ON cp.IDcompte_payeur=f.IDcompte_payeur",
        "f.IDfacture", "f.date_edition", "cp.IDfamille",
        ("CAST(f.numero AS CHAR)", "CAST(f.IDfacture AS CHAR)"),
    ),
    "services": (
        "SELECT p.IDprestation, p.date, cp.IDfamille, p.IDindividu, "
        "p.label, p.montant, p.IDfacture "
        "FROM prestations p "
        "LEFT JOIN comptes_payeurs cp ON cp.IDcompte_payeur=p.IDcompte_payeur",
        "p.IDprestation", "p.date", "cp.IDfamille",
        ("p.label", "CAST(p.IDprestation AS CHAR)"),
    ),
    "payments": (
        "SELECT r.IDreglement, r.date, cp.IDfamille, "
        "mr.label, r.montant, r.numero_piece, r.IDdepot "
        "FROM reglements r "
        "LEFT JOIN comptes_payeurs cp ON cp.IDcompte_payeur=r.IDcompte_payeur "
        "LEFT JOIN modes_reglements mr ON mr.IDmode=r.IDmode",
        "r.IDreglement", "r.date", "cp.IDfamille",
        ("r.numero_piece", "mr.label", "CAST(r.IDreglement AS CHAR)"),
    ),
    "allocations": (
        "SELECT v.IDventilation, v.IDreglement, v.IDprestation, "
        "cp.IDfamille, v.montant, p.IDfacture "
        "FROM ventilation v "
        "LEFT JOIN reglements r ON r.IDreglement=v.IDreglement "
        "LEFT JOIN comptes_payeurs cp ON cp.IDcompte_payeur=r.IDcompte_payeur "
        "LEFT JOIN prestations p ON p.IDprestation=v.IDprestation",
        "v.IDventilation", None, "cp.IDfamille",
        ("CAST(v.IDreglement AS CHAR)", "CAST(v.IDprestation AS CHAR)"),
    ),
    "treasury": (
        "SELECT o.IDoperation, o.date, o.type, o.libelle, o.montant, "
        "cb.nom, o.IDreleve, o.num_piece "
        "FROM compta_operations o "
        "LEFT JOIN comptes_bancaires cb ON cb.IDcompte=o.IDcompte_bancaire",
        "o.IDoperation", "o.date", None,
        ("o.libelle", "o.num_piece", "cb.nom"),
    ),
    "deposits": (
        "SELECT d.IDdepot, d.date, d.nom, cb.nom, d.verrouillage "
        "FROM depots d "
        "LEFT JOIN comptes_bancaires cb ON cb.IDcompte=d.IDcompte",
        "d.IDdepot", "d.date", None, ("d.nom", "cb.nom"),
    ),
}


@dataclass(frozen=True, slots=True)
class FinanceRow:
    kind: str
    id: int
    values: tuple[object, ...]

    def value(self, key: str):
        keys = FINANCE_DOMAINS[self.kind][2]
        if key not in keys:
            raise KeyError(key)
        return self.values[keys.index(key)]


@dataclass(frozen=True, slots=True)
class FinanceResult:
    rows: tuple[FinanceRow, ...]
    truncated: bool


def validate_finance_id(value: int | None, name: str) -> None:
    if value is not None and (
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
    ):
        raise ValueError(f"Identifiant {name} invalide")


def validate_finance_query(
    kind: str, *, family_id=None, year=None, text="", related_id=None,
    limit=MAX_FINANCE_ROWS, placeholder="?",
) -> None:
    if kind not in FINANCE_DOMAINS:
        raise ValueError("Domaine financier inconnu")
    if placeholder not in ("?", "%s"):
        raise ValueError("Marqueur SQL non autorisé")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_FINANCE_ROWS:
        raise ValueError("Limite invalide")
    validate_finance_id(family_id, "famille")
    validate_finance_id(related_id, "liaison")
    if year is not None and (
        not isinstance(year, int) or isinstance(year, bool)
        or not 1900 <= year <= 2098
    ):
        raise ValueError("Année invalide")
    if family_id is not None and kind not in FAMILY_DOMAINS:
        raise ValueError("Le domaine ne permet pas de filtrer par famille")
    if year is not None and kind not in YEAR_DOMAINS:
        raise ValueError("Le domaine ne possède pas de date")
    if related_id is not None and kind not in RELATED_FILTERS:
        raise ValueError("Liaison non disponible sur ce domaine")
    if not isinstance(text, str) or len(text) > 120:
        raise ValueError("Recherche trop longue ou invalide")


def _escape_like(text: str) -> str:
    return "%" + text.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def build_finance_query(
    kind: str, *, family_id=None, year=None, text="", related_id=None,
    limit=MAX_FINANCE_ROWS, placeholder="?",
):
    validate_finance_query(
        kind, family_id=family_id, year=year, text=text,
        related_id=related_id, limit=limit, placeholder=placeholder,
    )
    source, identity, date_col, family_col, search_fields = SQL_SOURCES[kind]
    where: list[str] = []
    args: list[object] = []
    if family_id is not None:
        where.append(f"{family_col} = {placeholder}")
        args.append(family_id)
    if year is not None:
        if date_col is None:
            raise ValueError("Ce domaine ne possède pas de date")
        # Une plage de dates indexable, identique sur SQLite et MySQL.
        where.append(f"{date_col} >= {placeholder} AND {date_col} < {placeholder}")
        args.extend((f"{year:04d}-01-01", f"{year+1:04d}-01-01"))
    if related_id is not None:
        where.append(f"{RELATED_FILTERS[kind][1]} = {placeholder}")
        args.append(related_id)
    if text.strip():
        where.append("(" + " OR ".join(
            f"{column} LIKE {placeholder} ESCAPE '!'"
            for column in search_fields
        ) + ")")
        args.extend([_escape_like(text.strip())] * len(search_fields))
    query = (
        source
        + (" WHERE " + " AND ".join(where) if where else "")
        + f" ORDER BY {date_col + ' DESC, ' if date_col else ''}{identity} DESC"
        + f" LIMIT {placeholder}"
    )
    args.append(limit + 1)
    return query, tuple(args)


def display_finance_value(value: object, *, amount=False) -> str:
    if value is None:
        return ""
    if not amount:
        return str(value)
    # Aucune somme, aucun arrondi de 12.005 vers 12.01 dans la UI.
    # Les montants enregistrés restent visibles avec leur précision.
    try:
        return format(Decimal(str(value)), "f").replace(".", ",")
    except (InvalidOperation, ValueError):
        return str(value)


class FinanceRepository:
    """Queries de lecture uniquement ; la source injectable est celle du projet Qt."""

    def __init__(self, editor_repository):
        self.editor_repository = editor_repository

    def search(
        self, kind: str, *, family_id=None, year=None, text="",
        related_id=None, limit=MAX_FINANCE_ROWS,
    ) -> FinanceResult:
        validate_finance_query(
            kind, family_id=family_id, year=year, text=text,
            related_id=related_id, limit=limit,
        )
        connection, placeholder = self.editor_repository._connect()
        try:
            if isinstance(connection, sqlite3.Connection):
                connection.execute("PRAGMA query_only=ON")
            sql, values = build_finance_query(
                kind, family_id=family_id, year=year, text=text,
                related_id=related_id, limit=limit, placeholder=placeholder,
            )
            cursor = connection.cursor()
            try:
                cursor.execute(sql, values)
                raw = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        rows = tuple(
            FinanceRow(kind, int(entry[0]), tuple(entry))
            for entry in raw[:limit]
        )
        return FinanceResult(rows, truncated=len(raw) > limit)
