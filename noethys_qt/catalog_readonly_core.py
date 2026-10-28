"""C14 : référentiel des grandes listes métier Qt en consultation stricte.

Les SELECT proviennent des tables et clés des OL wx existantes. Aucun moteur
métier (tarification, contrat, cotisation, commande) n'est exécuté ici.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .finance_readonly_core import display_finance_value, validate_finance_id

MAX_CATALOG_ROWS = 250


@dataclass(frozen=True, slots=True)
class CatalogSpec:
    label: str
    headers: tuple[str, ...]
    keys: tuple[str, ...]
    sql: str
    identity: str
    search_columns: tuple[str, ...]
    date_column: str | None = None
    family_column: str | None = None
    numeric_keys: tuple[str, ...] = ()


# Déclarations fermées : le nom d'un domaine reçu ne produit jamais un nom SQL.
CATALOG_DOMAINS = {
    "fees": CatalogSpec(
        "Cotisations",
        ("ID", "Saisie", "Famille", "Individu", "Type", "Unité",
         "Début", "Fin", "N° carte"),
        ("id", "date", "family", "individual", "type", "unit",
         "start", "end", "number"),
        "SELECT c.IDcotisation, c.date_saisie, c.IDfamille, c.IDindividu, "
        "t.nom, u.nom, c.date_debut, c.date_fin, c.numero "
        "FROM cotisations c "
        "LEFT JOIN types_cotisations t ON t.IDtype_cotisation=c.IDtype_cotisation "
        "LEFT JOIN unites_cotisations u ON u.IDunite_cotisation=c.IDunite_cotisation",
        "c.IDcotisation", ("t.nom", "u.nom", "CAST(c.numero AS CHAR)",
                           "CAST(c.IDcotisation AS CHAR)"),
        "c.date_saisie", "c.IDfamille",
    ),
    "fee_types": CatalogSpec(
        "Types de cotisations",
        ("ID", "Nom", "Type", "Défaut"),
        ("id", "name", "type", "default"),
        "SELECT t.IDtype_cotisation, t.nom, t.type, t.defaut "
        "FROM types_cotisations t",
        "t.IDtype_cotisation", ("t.nom", "t.type"),
    ),
    "contracts": CatalogSpec(
        "Contrats",
        ("ID", "Début", "Fin", "Famille", "Individu", "Activité",
         "Type enregistré", "Inscription"),
        ("id", "date", "end", "family", "individual", "activity",
         "type", "inscription"),
        "SELECT c.IDcontrat, c.date_debut, c.date_fin, i.IDfamille, "
        "c.IDindividu, a.nom, c.type, c.IDinscription "
        "FROM contrats c "
        "LEFT JOIN inscriptions i ON i.IDinscription=c.IDinscription "
        "LEFT JOIN activites a ON a.IDactivite=i.IDactivite",
        "c.IDcontrat", ("a.nom", "c.type", "CAST(c.IDcontrat AS CHAR)"),
        "c.date_debut", "i.IDfamille",
    ),
    "quotients": CatalogSpec(
        "Quotients familiaux",
        ("ID", "Famille", "Début", "Fin", "Quotient enregistré",
         "Revenu enregistré", "Type"),
        ("id", "family", "date", "end", "quotient", "income", "type"),
        "SELECT q.IDquotient, q.IDfamille, q.date_debut, q.date_fin, "
        "q.quotient, q.revenu, t.nom "
        "FROM quotients q "
        "LEFT JOIN types_quotients t ON t.IDtype_quotient=q.IDtype_quotient",
        "q.IDquotient", ("t.nom", "CAST(q.IDquotient AS CHAR)"),
        "q.date_debut", "q.IDfamille", ("quotient", "income"),
    ),
    "quotient_types": CatalogSpec(
        "Types de quotients",
        ("ID", "Nom"), ("id", "name"),
        "SELECT t.IDtype_quotient, t.nom FROM types_quotients t",
        "t.IDtype_quotient", ("t.nom",),
    ),
    "rentals": CatalogSpec(
        "Locations",
        ("ID", "Famille", "Début", "Fin", "Produit", "Quantité", "ID produit"),
        ("id", "family", "date", "end", "product", "quantity", "product_id"),
        "SELECT l.IDlocation, l.IDfamille, l.date_debut, l.date_fin, "
        "p.nom, l.quantite, l.IDproduit "
        "FROM locations l LEFT JOIN produits p ON p.IDproduit=l.IDproduit",
        "l.IDlocation", ("p.nom", "CAST(l.IDlocation AS CHAR)"),
        "l.date_debut", "l.IDfamille",
    ),
    "rental_requests": CatalogSpec(
        "Demandes de location",
        ("ID", "Date", "Famille", "Statut", "Catégories enregistrées",
         "Produits enregistrés"),
        ("id", "date", "family", "status", "categories", "products"),
        "SELECT d.IDdemande, d.date, d.IDfamille, d.statut, "
        "d.categories, d.produits FROM locations_demandes d",
        "d.IDdemande", ("d.statut", "CAST(d.IDdemande AS CHAR)"),
        "d.date", "d.IDfamille",
    ),
    "orders": CatalogSpec(
        "Commandes",
        ("ID", "Nom", "Début", "Fin", "Modèle"),
        ("id", "name", "date", "end", "template"),
        "SELECT c.IDcommande, c.nom, c.date_debut, c.date_fin, c.IDmodele "
        "FROM commandes c",
        "c.IDcommande", ("c.nom", "CAST(c.IDcommande AS CHAR)"),
        "c.date_debut",
    ),
    "quotes": CatalogSpec(
        "Devis",
        ("ID", "Numéro", "Famille", "Édition", "Début", "Fin",
         "Total enregistré", "Réglé enregistré", "Solde enregistré"),
        ("id", "number", "family", "date", "start", "end",
         "total", "paid", "balance"),
        "SELECT d.IDdevis, d.numero, d.IDfamille, d.date_edition, "
        "d.date_debut, d.date_fin, d.total, d.regle, d.solde FROM devis d",
        "d.IDdevis", ("CAST(d.numero AS CHAR)", "CAST(d.IDdevis AS CHAR)"),
        "d.date_edition", "d.IDfamille", ("total", "paid", "balance"),
    ),
}

CATALOG_MODULES = {
    "memberships": ("Cotisations", ("fees", "fee_types")),
    "contracts": ("Contrats", ("contracts",)),
    "quotients": ("Quotients familiaux", ("quotients", "quotient_types")),
    "rentals": ("Locations", ("rentals", "rental_requests")),
    "orders": ("Commandes", ("orders",)),
    "quotes": ("Devis", ("quotes",)),
}
FAMILY_CATALOG_MODULES = frozenset(
    ("memberships", "contracts", "quotients", "rentals", "quotes")
)


@dataclass(frozen=True, slots=True)
class CatalogRow:
    kind: str
    id: int
    values: tuple[object, ...]

    def value(self, key: str):
        keys = CATALOG_DOMAINS[self.kind].keys
        if key not in keys:
            raise KeyError(key)
        return self.values[keys.index(key)]


@dataclass(frozen=True, slots=True)
class CatalogResult:
    rows: tuple[CatalogRow, ...]
    truncated: bool


def validate_catalog_query(
    kind: str, *, family_id=None, year=None, text="",
    limit=MAX_CATALOG_ROWS, placeholder="?",
) -> None:
    if kind not in CATALOG_DOMAINS:
        raise ValueError("Domaine métier Qt inconnu")
    if placeholder not in ("?", "%s"):
        raise ValueError("Marqueur SQL non autorisé")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_CATALOG_ROWS:
        raise ValueError("Limite de consultation invalide")
    validate_finance_id(family_id, "famille")
    spec = CATALOG_DOMAINS[kind]
    if family_id is not None and spec.family_column is None:
        raise ValueError("Filtre famille indisponible pour ce domaine")
    if year is not None:
        if not isinstance(year, int) or isinstance(year, bool) or not 1900 <= year <= 2098:
            raise ValueError("Année invalide")
        if spec.date_column is None:
            raise ValueError("Ce domaine ne possède pas de date")
    if not isinstance(text, str) or len(text) > 120:
        raise ValueError("Recherche invalide ou trop longue")


def _escape_like(text: str) -> str:
    return "%" + text.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def build_catalog_query(
    kind: str, *, family_id=None, year=None, text="",
    limit=MAX_CATALOG_ROWS, placeholder="?",
):
    validate_catalog_query(
        kind, family_id=family_id, year=year, text=text,
        limit=limit, placeholder=placeholder,
    )
    spec = CATALOG_DOMAINS[kind]
    where = []
    params = []
    if family_id is not None:
        where.append(f"{spec.family_column} = {placeholder}")
        params.append(family_id)
    if year is not None:
        where.append(
            f"{spec.date_column} >= {placeholder} AND {spec.date_column} < {placeholder}"
        )
        params.extend((f"{year:04d}-01-01", f"{year + 1:04d}-01-01"))
    if text.strip():
        where.append("(" + " OR ".join(
            f"{column} LIKE {placeholder} ESCAPE '!'"
            for column in spec.search_columns
        ) + ")")
        params.extend([_escape_like(text.strip())] * len(spec.search_columns))
    sql = (
        spec.sql + (" WHERE " + " AND ".join(where) if where else "")
        + f" ORDER BY {spec.date_column + ' DESC, ' if spec.date_column else ''}"
        + f"{spec.identity} DESC LIMIT {placeholder}"
    )
    params.append(limit + 1)
    return sql, tuple(params)


class CatalogRepository:
    """Pont vers la connexion Qt existante, SELECT uniquement."""

    def __init__(self, editor_repository):
        self.editor_repository = editor_repository

    def search(
        self, kind: str, *, family_id=None, year=None, text="",
        limit=MAX_CATALOG_ROWS,
    ) -> CatalogResult:
        validate_catalog_query(
            kind, family_id=family_id, year=year, text=text, limit=limit,
        )
        connection, placeholder = self.editor_repository._connect()
        try:
            if isinstance(connection, sqlite3.Connection):
                connection.execute("PRAGMA query_only=ON")
            sql, params = build_catalog_query(
                kind, family_id=family_id, year=year, text=text,
                limit=limit, placeholder=placeholder,
            )
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params)
                raw = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
        rows = tuple(
            CatalogRow(kind, int(row[0]), tuple(row))
            for row in raw[:limit]
        )
        return CatalogResult(rows, truncated=len(raw) > limit)
