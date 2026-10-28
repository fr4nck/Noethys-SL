"""C15 — consultations de grands modules wx dans la coque Qt.

Les colonnes dérivent des listes wx existantes ; les compteurs C15 ne sont
pas des statistiques réglementaires ni des règles de facturation.
Aucun import wx, aucune génération de document ou adhésion.
"""


def build_c15_domains(CatalogSpec):
    return {
        "membership_expiries": CatalogSpec(
            "Dates de fin d'adhésion enregistrées",
            ("ID", "Fin stockée", "Début stocké", "Famille", "Individu",
             "Type", "Unité", "N° carte"),
            ("id", "date", "start", "family", "individual",
             "type", "unit", "number"),
            "SELECT c.IDcotisation, c.date_fin, c.date_debut, c.IDfamille, "
            "c.IDindividu, t.nom, u.nom, c.numero "
            "FROM cotisations c "
            "LEFT JOIN types_cotisations t ON t.IDtype_cotisation=c.IDtype_cotisation "
            "LEFT JOIN unites_cotisations u ON u.IDunite_cotisation=c.IDunite_cotisation",
            "c.IDcotisation",
            ("t.nom", "u.nom", "CAST(c.numero AS CHAR)", "CAST(c.IDcotisation AS CHAR)"),
            date_column="c.date_fin", family_column="c.IDfamille",
        ),
        "membership_units": CatalogSpec(
            "Unités de cotisation (configuration)",
            ("ID", "Type ID", "Type", "Unité", "Montant stocké",
             "Durée stockée", "Défaut"),
            ("id", "type_id", "type", "name", "amount", "duration", "default"),
            "SELECT u.IDunite_cotisation, u.IDtype_cotisation, t.nom, "
            "u.nom, u.montant, u.duree, u.defaut "
            "FROM unites_cotisations u "
            "LEFT JOIN types_cotisations t ON t.IDtype_cotisation=u.IDtype_cotisation",
            "u.IDunite_cotisation", ("u.nom", "t.nom", "CAST(u.IDunite_cotisation AS CHAR)"),
            numeric_keys=("amount",),
        ),
        "certificates": CatalogSpec(
            "Attestations enregistrées",
            ("ID", "Numéro", "Famille", "Édition", "Début", "Fin",
             "Total stocké", "Réglé stocké", "Solde stocké"),
            ("id", "number", "family", "date", "start", "end",
             "total", "paid", "balance"),
            "SELECT a.IDattestation, a.numero, a.IDfamille, a.date_edition, "
            "a.date_debut, a.date_fin, a.total, a.regle, a.solde "
            "FROM attestations a",
            "a.IDattestation",
            ("CAST(a.numero AS CHAR)", "CAST(a.IDattestation AS CHAR)"),
            date_column="a.date_edition", family_column="a.IDfamille",
            numeric_keys=("total", "paid", "balance"),
        ),
        "activity_units": CatalogSpec(
            "Unités d'activité",
            ("ID", "Activité ID", "Activité", "Unité", "Abrégé",
             "Type", "Début", "Fin", "Ordre", "Auto-génération"),
            ("id", "activity_id", "activity", "name", "short",
             "type", "start", "end", "order", "automatic"),
            "SELECT u.IDunite, u.IDactivite, a.nom, u.nom, u.abrege, "
            "u.type, u.date_debut, u.date_fin, u.ordre, u.autogen_active "
            "FROM unites u LEFT JOIN activites a ON a.IDactivite=u.IDactivite",
            "u.IDunite",
            ("u.nom", "a.nom", "CAST(u.IDunite AS CHAR)"),
            date_column="u.date_debut", activity_column="u.IDactivite",
        ),
        "activity_groups": CatalogSpec(
            "Groupes d'activité",
            ("ID", "Activité ID", "Activité", "Groupe", "Abrégé",
             "Ordre", "Capacité enregistrée"),
            ("id", "activity_id", "activity", "name", "short",
             "order", "capacity"),
            "SELECT g.IDgroupe, g.IDactivite, a.nom, g.nom, "
            "g.abrege, g.ordre, g.nbre_inscrits_max "
            "FROM groupes g LEFT JOIN activites a ON a.IDactivite=g.IDactivite",
            "g.IDgroupe",
            ("g.nom", "a.nom", "CAST(g.IDgroupe AS CHAR)"),
            activity_column="g.IDactivite",
        ),
        "activity_tariff_categories": CatalogSpec(
            "Catégories tarifaires d'activité",
            ("ID", "Activité ID", "Activité", "Nom enregistré"),
            ("id", "activity_id", "activity", "name"),
            "SELECT c.IDcategorie_tarif, c.IDactivite, a.nom, c.nom "
            "FROM categories_tarifs c "
            "LEFT JOIN activites a ON a.IDactivite=c.IDactivite",
            "c.IDcategorie_tarif",
            ("c.nom", "a.nom", "CAST(c.IDcategorie_tarif AS CHAR)"),
            activity_column="c.IDactivite",
        ),
        "enrollment_counts": CatalogSpec(
            "Comptage brut des inscriptions",
            ("Activité ID", "Activité", "Inscriptions stockées", "Statut 'ok' stocké"),
            ("id", "activity", "enrollments", "status_ok"),
            "SELECT a.IDactivite, a.nom, "
            "(SELECT COUNT(*) FROM inscriptions i WHERE i.IDactivite=a.IDactivite), "
            "(SELECT COUNT(*) FROM inscriptions i "
            " WHERE i.IDactivite=a.IDactivite AND i.statut='ok') "
            "FROM activites a",
            "a.IDactivite",
            ("a.nom", "CAST(a.IDactivite AS CHAR)"),
            activity_column="a.IDactivite",
        ),
        "consumption_counts": CatalogSpec(
            "Comptage brut des consommations",
            ("Activité ID", "Activité", "Consommations stockées",
             "État 'present' stocké"),
            ("id", "activity", "consumptions", "present"),
            "SELECT a.IDactivite, a.nom, "
            "(SELECT COUNT(*) FROM consommations c WHERE c.IDactivite=a.IDactivite), "
            "(SELECT COUNT(*) FROM consommations c "
            " WHERE c.IDactivite=a.IDactivite AND c.etat='present') "
            "FROM activites a",
            "a.IDactivite",
            ("a.nom", "CAST(a.IDactivite AS CHAR)"),
            activity_column="a.IDactivite",
        ),
    }


C15_MODULES = {
    "renewals": ("Échéances d'adhésion", ("membership_expiries", "membership_units")),
    "certificates": ("Attestations", ("certificates",)),
    "activity_settings": (
        "Paramètres d'activités",
        ("activity_units", "activity_groups", "activity_tariff_categories"),
    ),
    "headcounts": (
        "Effectifs bruts",
        ("enrollment_counts", "consumption_counts"),
    ),
}

C15_FAMILY_MODULES = frozenset(("renewals", "certificates"))
C15_ACTIVITY_MODULES = frozenset(("activity_settings", "headcounts"))
C15_ACTIVITY_LINK_DOMAINS = frozenset((
    "activity_units", "activity_groups", "activity_tariff_categories",
    "enrollment_counts", "consumption_counts",
))
