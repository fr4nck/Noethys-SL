"""C18 — référentiels scolaires, produits et pièces en lecture seule.

Déclarations SQL statiques dérivées des colonnes DATA_Tables.py.
Aucun BLOB, coordonnées individuelles, contenu documentaire ni analyse
de validité ; les lignes personnelles sont masquées hors fixture C18.
"""


def build_c18_domains(CatalogSpec):
    return {
        "schools": CatalogSpec(
            "Écoles enregistrées",
            ("ID", "École", "Code postal", "Ville", "IDs secteurs stockés"),
            ("id", "name", "postcode", "city", "sectors"),
            "SELECT e.IDecole, e.nom, e.cp, e.ville, e.secteurs FROM ecoles e",
            "e.IDecole",
            ("e.nom", "e.cp", "e.ville", "CAST(e.IDecole AS CHAR)"),
        ),
        "school_classes": CatalogSpec(
            "Classes enregistrées",
            ("ID", "École ID", "Classe", "Début", "Fin", "IDs niveaux stockés"),
            ("id", "school_id", "name", "date", "end", "levels"),
            "SELECT c.IDclasse, c.IDecole, c.nom, c.date_debut, "
            "c.date_fin, c.niveaux FROM classes c",
            "c.IDclasse",
            ("c.nom", "CAST(c.IDclasse AS CHAR)", "CAST(c.IDecole AS CHAR)"),
            date_column="c.date_debut",
        ),
        "school_levels": CatalogSpec(
            "Niveaux scolaires",
            ("ID", "Ordre source", "Nom", "Abrégé"),
            ("id", "position", "name", "short"),
            "SELECT n.IDniveau, n.ordre, n.nom, n.abrege "
            "FROM niveaux_scolaires n",
            "n.IDniveau",
            ("n.nom", "n.abrege", "CAST(n.IDniveau AS CHAR)"),
        ),
        "school_history": CatalogSpec(
            "Parcours individuels enregistrés (accès restreint)",
            ("ID", "Individu ID", "Début", "Fin", "École ID",
             "École", "Classe ID", "Classe", "Niveau ID", "Niveau"),
            ("id", "individual", "date", "end", "school_id",
             "school", "class_id", "class", "level_id", "level"),
            "SELECT s.IDscolarite, s.IDindividu, s.date_debut, s.date_fin, "
            "s.IDecole, e.nom, s.IDclasse, c.nom, s.IDniveau, n.nom "
            "FROM scolarite s "
            "LEFT JOIN ecoles e ON e.IDecole=s.IDecole "
            "LEFT JOIN classes c ON c.IDclasse=s.IDclasse "
            "LEFT JOIN niveaux_scolaires n ON n.IDniveau=s.IDniveau",
            "s.IDscolarite",
            ("e.nom", "c.nom", "n.nom", "CAST(s.IDscolarite AS CHAR)"),
            date_column="s.date_debut", individual_column="s.IDindividu",
        ),
        "product_inventory": CatalogSpec(
            "Produits enregistrés (quantités et montant source)",
            ("ID", "Catégorie ID", "Nom", "Quantité stockée",
             "Montant enregistré", "Partage activé"),
            ("id", "category_id", "name", "quantity", "amount", "sharing"),
            "SELECT p.IDproduit, p.IDcategorie, p.nom, p.quantite, "
            "p.montant, p.activation_partage FROM produits p",
            "p.IDproduit",
            ("p.nom", "CAST(p.IDproduit AS CHAR)", "CAST(p.IDcategorie AS CHAR)"),
            numeric_keys=("amount",),
        ),
        "product_categories": CatalogSpec(
            "Catégories de produits",
            ("ID", "Catégorie"),
            ("id", "name"),
            "SELECT c.IDcategorie, c.nom FROM produits_categories c",
            "c.IDcategorie",
            ("c.nom", "CAST(c.IDcategorie AS CHAR)"),
        ),
        "document_types": CatalogSpec(
            "Types de pièces configurés",
            ("ID", "Type", "Public", "Durée stockée",
             "Valide en rattachement"),
            ("id", "name", "public", "duration", "attachment_validity"),
            "SELECT t.IDtype_piece, t.nom, t.public, t.duree_validite, "
            "t.valide_rattachement FROM types_pieces t",
            "t.IDtype_piece",
            ("t.nom", "t.public", "CAST(t.IDtype_piece AS CHAR)"),
        ),
        "documents_metadata": CatalogSpec(
            "Pièces enregistrées (métadonnées restreintes)",
            ("ID", "Famille ID", "Individu ID", "Type ID", "Type",
             "Début", "Fin", "Titre enregistré"),
            ("id", "family", "individual", "type_id", "type",
             "date", "end", "title"),
            "SELECT p.IDpiece, p.IDfamille, p.IDindividu, "
            "p.IDtype_piece, t.nom, p.date_debut, p.date_fin, p.titre "
            "FROM pieces p "
            "LEFT JOIN types_pieces t ON t.IDtype_piece=p.IDtype_piece",
            "p.IDpiece",
            ("p.titre", "t.nom", "CAST(p.IDpiece AS CHAR)"),
            date_column="p.date_debut", family_column="p.IDfamille",
            individual_column="p.IDindividu",
        ),
    }


C18_CATALOG_MODULES = {
    "school_registry": (
        "Écoles, classes et niveaux",
        ("schools", "school_classes", "school_levels"),
    ),
    "school_history": ("Parcours de scolarité", ("school_history",)),
    "product_registry": (
        "Produits et ressources",
        ("product_inventory", "product_categories"),
    ),
    "document_type_registry": (
        "Référentiel de pièces",
        ("document_types",),
    ),
    "document_records": ("Pièces enregistrées", ("documents_metadata",)),
}

C18_RESTRICTED_MODULES = frozenset(("school_history", "document_records"))
C18_RESTRICTED_DOMAINS = frozenset(
    kind for module in C18_RESTRICTED_MODULES
    for kind in C18_CATALOG_MODULES[module][1]
)
C18_PERSON_MODULES = frozenset(("school_history", "document_records"))
C18_INDIVIDUAL_LINK_DOMAINS = frozenset(
    ("school_history", "documents_metadata")
)
C18_FAMILY_MODULES = frozenset(("document_records",))
