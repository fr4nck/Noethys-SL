"""C19 — référentiels comptables, budgets, encaissements et organismes.

Les colonnes reprennent DATA_Tables.py et les listes wx. Valeurs stockées,
sans calcul de solde, validation de pièce, exécution de formule ni mutation.
Les trois rubriques financières sont confinées aux fixtures synthétiques :
pas de consultation de référentiels comptables privés sans habilitation.
"""


def build_c19_domains(CatalogSpec):
    return {
        "accounting_periods": CatalogSpec(
            "Exercices comptables enregistrés",
            ("ID", "Exercice", "Début", "Fin", "Défaut stocké"),
            ("id", "name", "date", "end", "default"),
            "SELECT e.IDexercice, e.nom, e.date_debut, e.date_fin, e.defaut "
            "FROM compta_exercices e",
            "e.IDexercice",
            ("e.nom", "CAST(e.IDexercice AS CHAR)"),
            date_column="e.date_debut",
        ),
        "analytic_sections": CatalogSpec(
            "Postes analytiques enregistrés",
            ("ID", "Poste analytique", "Abrégé", "Défaut stocké"),
            ("id", "name", "short", "default"),
            "SELECT a.IDanalytique, a.nom, a.abrege, a.defaut "
            "FROM compta_analytiques a",
            "a.IDanalytique",
            ("a.nom", "a.abrege", "CAST(a.IDanalytique AS CHAR)"),
        ),
        "accounting_categories": CatalogSpec(
            "Catégories comptables enregistrées",
            ("ID", "Type source", "Catégorie", "Abrégé", "Journal",
             "Compte comptable ID"),
            ("id", "type", "name", "short", "journal", "ledger_id"),
            "SELECT c.IDcategorie, c.type, c.nom, c.abrege, "
            "c.journal, c.IDcompte FROM compta_categories c",
            "c.IDcategorie",
            ("c.nom", "c.type", "c.abrege", "c.journal",
             "CAST(c.IDcategorie AS CHAR)"),
        ),
        "ledger_accounts": CatalogSpec(
            "Comptes comptables enregistrés",
            ("ID", "N° de compte stocké", "Libellé"),
            ("id", "number", "name"),
            "SELECT c.IDcompte, c.numero, c.nom "
            "FROM compta_comptes_comptables c",
            "c.IDcompte",
            ("c.numero", "c.nom", "CAST(c.IDcompte AS CHAR)"),
        ),
        "budget_definitions": CatalogSpec(
            "Budgets enregistrés (sans réalisation)",
            ("ID", "Budget", "Exercice ID", "Début", "Fin",
             "IDs analytiques stockés"),
            ("id", "name", "period_id", "date", "end", "analytics"),
            "SELECT b.IDbudget, b.nom, b.IDexercice, "
            "b.date_debut, b.date_fin, b.analytiques "
            "FROM compta_budgets b",
            "b.IDbudget",
            ("b.nom", "CAST(b.IDbudget AS CHAR)"),
            date_column="b.date_debut",
        ),
        "budget_categories": CatalogSpec(
            "Catégories budgétaires (valeurs/formules brutes)",
            ("ID", "Budget ID", "Type source", "Catégorie ID",
             "Valeur/formule stockée (non exécutée)"),
            ("id", "budget_id", "type", "category_id", "stored_value"),
            "SELECT c.IDcategorie_budget, c.IDbudget, c.type, "
            "c.IDcategorie, c.valeur FROM compta_categories_budget c",
            "c.IDcategorie_budget",
            ("c.type", "c.valeur", "CAST(c.IDcategorie_budget AS CHAR)"),
            budget_column="c.IDbudget",
        ),
        "payment_modes_settings": CatalogSpec(
            "Modes de règlement (configuration brute)",
            ("ID", "Libellé", "Type comptable", "N° pièce : règle",
             "Frais : méthode", "Frais : montant source",
             "Frais : pourcentage source", "Code comptable"),
            ("id", "name", "accounting_type", "piece_rule",
             "fee_method", "fee_amount", "fee_percent", "account_code"),
            "SELECT m.IDmode, m.label, m.type_comptable, "
            "m.numero_piece, m.frais_gestion, m.frais_montant, "
            "m.frais_pourcentage, m.code_compta "
            "FROM modes_reglements m",
            "m.IDmode",
            ("m.label", "m.type_comptable", "CAST(m.IDmode AS CHAR)"),
            numeric_keys=("fee_amount", "fee_percent"),
        ),
        "bank_accounts_metadata": CatalogSpec(
            "Comptes bancaires (intitulés uniquement)",
            ("ID", "Intitulé", "Défaut stocké", "Raison sociale"),
            ("id", "name", "default", "company"),
            "SELECT b.IDcompte, b.nom, b.defaut, b.raison "
            "FROM comptes_bancaires b",
            "b.IDcompte",
            ("b.nom", "CAST(b.IDcompte AS CHAR)"),
        ),
        "banks_directory": CatalogSpec(
            "Établissements bancaires",
            ("ID", "Banque", "Code postal", "Ville"),
            ("id", "name", "postcode", "city"),
            "SELECT b.IDbanque, b.nom, b.cp_resid, b.ville_resid "
            "FROM banques b",
            "b.IDbanque",
            ("b.nom", "b.cp_resid", "b.ville_resid"),
        ),
        "social_regimes": CatalogSpec(
            "Régimes sociaux enregistrés",
            ("ID", "Régime"),
            ("id", "name"),
            "SELECT r.IDregime, r.nom FROM regimes r",
            "r.IDregime", ("r.nom", "CAST(r.IDregime AS CHAR)"),
        ),
        "allowance_funds": CatalogSpec(
            "Caisses d'allocations enregistrées",
            ("ID", "Caisse", "Régime ID", "Régime"),
            ("id", "name", "regime_id", "regime"),
            "SELECT c.IDcaisse, c.nom, c.IDregime, r.nom "
            "FROM caisses c "
            "LEFT JOIN regimes r ON r.IDregime=c.IDregime",
            "c.IDcaisse",
            ("c.nom", "r.nom", "CAST(c.IDcaisse AS CHAR)"),
        ),
        "geographic_sectors": CatalogSpec(
            "Secteurs géographiques enregistrés",
            ("ID", "Secteur"),
            ("id", "name"),
            "SELECT s.IDsecteur, s.nom FROM secteurs s",
            "s.IDsecteur",
            ("s.nom", "CAST(s.IDsecteur AS CHAR)"),
        ),
    }


C19_CATALOG_MODULES = {
    "accounting_settings": (
        "Référentiels comptables",
        ("accounting_periods", "analytic_sections",
         "accounting_categories", "ledger_accounts"),
    ),
    "budget_settings": (
        "Budgets enregistrés",
        ("budget_definitions", "budget_categories"),
    ),
    "payment_settings": (
        "Paramètres d'encaissement",
        ("payment_modes_settings", "bank_accounts_metadata",
         "banks_directory"),
    ),
    "organisation_settings": (
        "Organismes et secteurs",
        ("social_regimes", "allowance_funds", "geographic_sectors"),
    ),
}
C19_RESTRICTED_MODULES = frozenset((
    "accounting_settings", "budget_settings", "payment_settings",
))
C19_RESTRICTED_DOMAINS = frozenset(
    kind for module in C19_RESTRICTED_MODULES
    for kind in C19_CATALOG_MODULES[module][1]
)
C19_BUDGET_MODULE = "budget_settings"
C19_BUDGET_RECORD_DOMAIN = "budget_definitions"
C19_BUDGET_LINE_DOMAIN = "budget_categories"
