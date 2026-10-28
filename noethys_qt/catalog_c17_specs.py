"""C17 — suivi transversal brut des activités, sans décisions métier.

Chaque colonne numérique est un COUNT(*) de lignes enregistrées.
Les sous-requêtes indépendantes évitent le fan-out de jointures.
Le comptage n'est ni une jauge de capacité, ni un effectif CAF/AFAS.
"""


def build_c17_domains(CatalogSpec):
    return {
        "activity_overview": CatalogSpec(
            "Lignes stockées par activité (sans période)",
            (
                "ID", "Activité", "Inscriptions", "Statut 'ok'",
                "Consommations", "État 'present'",
                "Ouvertures", "Événements", "Tarifs",
            ),
            (
                "id", "name", "enrollments", "status_ok",
                "consumptions", "present", "openings", "events", "tariffs",
            ),
            "SELECT a.IDactivite, a.nom, "
            "(SELECT COUNT(*) FROM inscriptions i "
            " WHERE i.IDactivite=a.IDactivite), "
            "(SELECT COUNT(*) FROM inscriptions i "
            " WHERE i.IDactivite=a.IDactivite AND i.statut='ok'), "
            "(SELECT COUNT(*) FROM consommations c "
            " WHERE c.IDactivite=a.IDactivite), "
            "(SELECT COUNT(*) FROM consommations c "
            " WHERE c.IDactivite=a.IDactivite AND c.etat='present'), "
            "(SELECT COUNT(*) FROM ouvertures o "
            " WHERE o.IDactivite=a.IDactivite), "
            "(SELECT COUNT(*) FROM evenements e "
            " WHERE e.IDactivite=a.IDactivite), "
            "(SELECT COUNT(*) FROM tarifs t "
            " WHERE t.IDactivite=a.IDactivite) "
            "FROM activites a",
            "a.IDactivite",
            ("a.nom", "CAST(a.IDactivite AS CHAR)"),
            activity_column="a.IDactivite",
        ),
    }


C17_CATALOG_MODULES = {
    "activity_overview": (
        "Suivi transversal des activités",
        ("activity_overview",),
    ),
}

# Destinations exactes autorisées depuis une activité sélectionnée :
# les liens n'inférent jamais un ID à partir du nom d'une activité.
C17_ACTIVITY_DESTINATIONS = frozenset((
    "planning", "tariff_records", "consumption_reports",
))
C17_ACTIVITY_LINK_DOMAINS = frozenset(("activity_overview",))
