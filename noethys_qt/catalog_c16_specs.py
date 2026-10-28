"""C16 — définition fermée des consultations planning, tarifs et badgeage.

Les tableaux sont des enregistrements source, sans valorisation, capacité
réelle, règle de calcul, facturation, décompte AFAS ni droit métier.
Le badgeage journal est protégé par un drapeau UI et non qualifié sur réel.
"""


def build_c16_domains(CatalogSpec):
    return {
        "openings": CatalogSpec(
            "Ouvertures enregistrées",
            ("ID", "Date", "Activité", "Unité", "Groupe"),
            ("id", "date", "activity_id", "unit_id", "group_id"),
            "SELECT o.IDouverture, o.date, o.IDactivite, o.IDunite, o.IDgroupe "
            "FROM ouvertures o",
            "o.IDouverture",
            ("CAST(o.IDouverture AS CHAR)",),
            date_column="o.date", activity_column="o.IDactivite",
        ),
        "events": CatalogSpec(
            "Événements enregistrés",
            ("ID", "Date", "Activité", "Nom", "Unité", "Groupe",
             "Heure début", "Heure fin", "Capacité stockée", "Montant stocké"),
            ("id", "date", "activity_id", "name", "unit_id", "group_id",
             "time_start", "time_end", "capacity", "amount"),
            "SELECT e.IDevenement, e.date, e.IDactivite, e.nom, e.IDunite, "
            "e.IDgroupe, e.heure_debut, e.heure_fin, e.capacite_max, e.montant "
            "FROM evenements e",
            "e.IDevenement",
            ("e.nom", "CAST(e.IDevenement AS CHAR)"),
            date_column="e.date", activity_column="e.IDactivite",
            numeric_keys=("amount",),
        ),
        "tariffs": CatalogSpec(
            "Tarifs enregistrés (sans simulation)",
            ("ID", "Activité", "Début", "Fin", "Méthode stockée", "Type",
             "Catégories enregistrées", "Événement"),
            ("id", "activity_id", "date", "end", "method", "type",
             "categories", "event_id"),
            "SELECT t.IDtarif, t.IDactivite, t.date_debut, t.date_fin, "
            "t.methode, t.type, t.categories_tarifs, t.IDevenement "
            "FROM tarifs t",
            "t.IDtarif",
            ("t.methode", "t.type", "CAST(t.IDtarif AS CHAR)"),
            date_column="t.date_debut", activity_column="t.IDactivite",
        ),
        "tariff_lines": CatalogSpec(
            "Lignes tarifaires enregistrées",
            ("ID", "Activité", "Tarif", "Rang", "Code", "QF min", "QF max",
             "Montant unique", "Min", "Max", "Ajustement"),
            ("id", "activity_id", "tariff_id", "position", "code",
             "quotient_min", "quotient_max", "amount", "minimum",
             "maximum", "adjustment"),
            "SELECT l.IDligne, l.IDactivite, l.IDtarif, l.num_ligne, "
            "l.code, l.qf_min, l.qf_max, l.montant_unique, "
            "l.montant_min, l.montant_max, l.ajustement "
            "FROM tarifs_lignes l",
            "l.IDligne",
            ("l.code", "CAST(l.IDligne AS CHAR)", "CAST(l.IDtarif AS CHAR)"),
            activity_column="l.IDactivite",
            numeric_keys=(
                "quotient_min", "quotient_max", "amount",
                "minimum", "maximum", "adjustment",
            ),
        ),
        "badge_actions": CatalogSpec(
            "Journal de badgeage (accès non qualifié)",
            ("ID", "Date", "Heure", "Individu ID",
             "Individu saisi", "Action", "Résultat enregistré"),
            ("id", "date", "hour", "individual_id",
             "individual", "action", "outcome"),
            "SELECT b.IDaction, b.date, b.heure, b.IDindividu, "
            "b.individu, b.action, b.resultat "
            "FROM badgeage_journal b",
            "b.IDaction",
            ("b.individu", "b.action", "CAST(b.IDaction AS CHAR)"),
            date_column="b.date",
        ),
    }


C16_CATALOG_MODULES = {
    "planning": ("Planning / événements", ("openings", "events")),
    "tariff_records": ("Tarification enregistrée", ("tariffs", "tariff_lines")),
    "badge_journal": ("Journal de badgeage", ("badge_actions",)),
}

# Le module état des consommations est un widget consultatif distinct,
# pas un onglet du catalogue (agrégation par code d'état SQL).
C16_MODULE_CODES = frozenset(
    (*C16_CATALOG_MODULES, "consumption_reports")
)
C16_ACTIVITY_LINK_DOMAINS = frozenset((
    "openings", "events", "tariffs", "tariff_lines",
))
C16_RESTRICTED_MODULES = frozenset(("badge_journal",))
