# -*- coding: utf-8 -*-
"""AFAS V2 -- jeu de données FICTIF commun à la qualification SQLite/MySQL et
à la recette visuelle Windows. Aucune donnée réelle : noms, dates et montants
sont inventés. Les résultats attendus sont calculés à la main ci-dessous.

Identifiants hauts (activité 90, groupes 911-916, unités 91xx/92xx,
individus 9001-9007) pour pouvoir compléter le fichier « Recette » créé par
tests/recette_creer_fichier_fictif.py sans collision.
"""
import datetime

H = 3600
M = 60
ANNEE = 2026
DATE_REFERENCE = datetime.date(2027, 2, 1)  # période 2026 terminée

ACTIVITE = 90
GROUPES = ((911, "Bais +6 ans"), (912, "Bais -6 ans"), (913, "Moutiers"), (914, "La Guerche"),
           (915, "Minicamps 6/8"), (916, "Minicamps 8/10"))
UNITES = (
    # (IDunite, nom, type, heure_debut, heure_fin)
    (9101, "Péri matin", "Unitaire", "07:30", "08:45"),
    (9102, "Péri soir", "Unitaire", "16:30", "18:30"),
    (9103, "Péri repas", "Unitaire", "12:00", "13:30"),
    (9104, "Garderie matin", "Horaire", "07:00", "07:30"),
    (9201, "Journée", "Unitaire", "08:30", "17:30"),
    (9202, "Matinée", "Unitaire", "08:30", "12:00"),
    (9203, "Après-midi", "Unitaire", "13:30", "17:30"),
    (9204, "Repas vacances", "Unitaire", "12:00", "13:30"),
    (9205, "Sortie", "Unitaire", None, None),
    (9206, "Minicamp", "Unitaire", None, None),
)
CLASSEMENT_PERI = {"9101": "accueil", "9102": "accueil", "9103": "repas", "9104": "garderie_matin"}
PLAGES_PERI = {"9101": "07:30-08:45", "9102": "16:30-18:30", "9103": "12:00-13:30", "9104": "07:00-07:30"}
CLASSEMENT_EXTRA = {"9201": "journee", "9202": "demi_journee", "9203": "demi_journee", "9204": "repas", "9205": "annexe",
                    "9206": "sejour"}
PLAGES_EXTRA = {"9201": "08:30-17:30", "9202": "08:30-12:00", "9203": "13:30-17:30", "9204": "12:00-13:30"}

ENFANTS = ((9001, "FICTIF", "Alix"), (9002, "FICTIF", "Basile"), (9003, "FICTIF", "Capucine"), (9004, "FICTIF", "Dorian"),
           (9005, "FICTIF", "Elsa"), (9006, "FICTIF", "Félix"), (9007, "FICTIF", "Gaëlle"))

# Calendrier fictif complet (cinq périodes par année scolaire, dates inventées).
VACANCES = (
    ("Toussaint", "2024-10-19", "2024-11-03"), ("Noël", "2024-12-21", "2025-01-05"),
    ("Hiver", "2025-02-15", "2025-03-02"), ("Printemps", "2025-04-12", "2025-04-27"), ("Été", "2025-07-05", "2025-08-31"),
    ("Toussaint", "2025-10-18", "2025-11-02"), ("Noël", "2025-12-20", "2026-01-04"),
    ("Hiver", "2026-02-14", "2026-03-01"), ("Printemps", "2026-04-11", "2026-04-26"), ("Été", "2026-07-04", "2026-08-31"),
    ("Toussaint", "2026-10-17", "2026-11-01"), ("Noël", "2026-12-19", "2027-01-03"),
    ("Hiver", "2027-02-13", "2027-02-28"), ("Printemps", "2027-04-10", "2027-04-25"), ("Été", "2027-07-03", "2027-08-31"),
)

FACTURES = ((9001, 9001, None), (9002, 9002, "annulation"), (9003, 9003, None))  # (IDfacture, numero, etat)

# Prestations : (IDprestation, IDindividu, IDfacture, montant, date, label)
PRESTATIONS = (
    (90001, 9001, 9001, 15.0, "2026-10-19", "Journée"),
    (90002, 9002, 9001, 8.0, "2026-10-19", "Matinée"),
    (90003, 9003, 9001, 15.0, "2026-10-19", "Journée (absence facturée)"),
    (90004, 9004, 9002, 15.0, "2026-10-20", "Journée (facture annulée)"),
    (90005, 9005, 9001, 15.0, "2026-10-20", "Journée"),
    (90006, 9001, 9001, 6.0, "2026-10-20", "Sortie"),
    (90007, 9001, 9001, 0.0, "2026-10-20", "Journée (remise 100 %)"),
)
# Avoir non rattaché à une consommation, qualifié dans le référentiel comme annulant la journée 9005 du 20/10.
REGULARISATION = (90090, 9005, 9003, -15.0, "2026-11-10", "Avoir absence enfant malade")

# Consommations : (IDconso, IDindividu, date, IDunite, IDgroupe, etat, heure_debut, heure_fin, IDprestation)
CONSOMMATIONS = (
    # Périscolaire (Bais +6 ans), semaines d'école
    (91001, 9001, "2026-03-03", 9101, 911, "present", "07:40", "08:30", None),
    (91002, 9001, "2026-03-03", 9102, 911, "present", "16:30", "18:00", None),
    (91003, 9001, "2026-03-03", 9104, 911, "present", "07:00", "07:30", None),
    (91004, 9002, "2026-03-03", 9101, 911, "present", "07:45", "08:30", None),
    (91005, 9001, "2026-03-05", 9103, 911, "present", "12:00", "13:30", None),
    (91006, 9003, "2026-03-05", 9102, 911, "absentj", None, None, None),
    # Extrascolaire (vacances de la Toussaint)
    (92001, 9001, "2026-10-19", 9201, 911, "present", "08:40", "17:10", 90001),
    (92002, 9002, "2026-10-19", 9202, 911, "present", "08:30", "12:00", 90002),
    (92003, 9003, "2026-10-19", 9201, 912, "absenti", None, None, 90003),
    (92004, 9004, "2026-10-20", 9201, 911, "present", "08:30", "17:30", 90004),
    (92005, 9005, "2026-10-20", 9201, 911, "present", "08:30", "17:30", 90005),
    (92006, 9001, "2026-10-20", 9205, 911, "present", None, None, 90006),
    (92007, 9001, "2026-10-20", 9201, 911, "present", "08:30", "17:30", 90007),
    # Minicamp qualifié (2 nuits, 21 au 23/10)
    (93001, 9006, "2026-10-21", 9206, 915, "present", None, None, None),
    (93002, 9006, "2026-10-22", 9206, 915, "present", None, None, None),
    (93003, 9006, "2026-10-23", 9206, 915, "present", None, None, None),
    (93004, 9007, "2026-10-21", 9206, 915, "present", None, None, None),
    (93005, 9007, "2026-10-22", 9206, 915, "present", None, None, None),
    (93006, 9007, "2026-10-23", 9206, 915, "absentj", None, None, None),
)
# Ouvertures : (IDunite, IDgroupe, date)
OUVERTURES = tuple(
    [(u, 911, d) for d in ("2026-03-03", "2026-03-05") for u in (9101, 9102, 9103, 9104)]
    + [(u, 911, d) for d in ("2026-10-19", "2026-10-20") for u in (9201, 9202, 9203, 9204, 9205)]
    + [(9201, 912, "2026-10-19")]
    + [(9206, 915, d) for d in ("2026-10-21", "2026-10-22", "2026-10-23")]
)
AEEH = ((1, 9002, "2026-01-01", None),)  # (IDperiode, IDindividu, debut, fin)

SEJOUR = {"id": "minicamp-toussaint-fictif", "libelle": "Minicamp fictif de la Toussaint", "site": "Minicamps 6/8",
          "date_debut": "2026-10-21", "date_fin": "2026-10-23", "nuits": 2, "prevu_declaration_annuelle": True,
          "integre_projet_educatif": True, "declare_sejour_vacances": False}

# Résultats attendus (calcul manuel, en secondes).
ATTENDU_PERI = {
    # 9001 : matin 1 h 15 + soir 2 h (plages entières) ; 9002 : matin 1 h 15 ; 9001 : repas 1 h 30.
    "heures_realisees": 6 * H, "heures_realisees_aeeh": H + 15 * M,
    # présence physique : 50 min + 1 h 30 + 30 min (garderie) ; 45 min ; 1 h 30.
    "heures_physiques": 5 * H + 5 * M, "complement_inclusif_brut": 45 * M, "complement_inclusif_arrondi": H,
    "garderie_matin": 30 * M, "garderie_soir": 0, "garderie_total": 30 * M,
    "heures_facturees": None, "heures_facturees_aeeh": None, "heures_sejours": None,
}
ATTENDU_EXTRA = {
    # facturé : 9001 journée 8 h ; 9002 matinée 4 h (ouverture continue 08:30-17:30 grâce au repas) ;
    # 9003 absence facturée 8 h ; 9004 facture annulée 0 ; 9005 annulée par l'avoir qualifié 0 ;
    # 9001 le 20/10 journée à 0 € (remise) 8 h ; sortie : annexe.
    "heures_facturees": 28 * H, "heures_facturees_aeeh": 4 * H,
    # réalisé (présence effective) : 8 h 30 + 3 h 30 + 0 + 9 h + 9 h + 9 h.
    "heures_realisees": 39 * H, "heures_realisees_aeeh": 3 * H + 30 * M, "heures_physiques": 39 * H,
    "complement_inclusif_brut": 3 * H + 30 * M, "complement_inclusif_arrondi": 4 * H,
    "garderie_matin": 0, "garderie_soir": 0, "garderie_total": 0, "heures_sejours": 0,
}
ATTENDU_SEJOURS = {"heures_sejours": 50 * H}  # 9006 : 3 journées, 9007 : 2 journées réalisées


def Referentiel():
    def lien(IDgroupe, nom, equipement):
        return {"IDactivite": ACTIVITE, "IDgroupe": IDgroupe, "nom_groupe": nom, "equipement": equipement}
    return {
        "format": 2, "moutiers_rattachement_confirme": False, "sejours": [dict(SEJOUR)],
        "samedis_avec_ecole": {"2024": [], "2025": [], "2026": []},
        "justificatifs": {"Minicamps 6/8": "Déclaration fictive de l'accueil n° 0000-FICTIF"},
        "regularisations": {str(REGULARISATION[0]): {"consommations_annulees": [92005],
                                                     "justification": "Avoir fictif n° A-1 : absence pour maladie"}},
        "sites": {"Bais +6 ans": lien(911, "Bais +6 ans", "BAIS"), "Bais -6 ans": lien(912, "Bais -6 ans", "BAIS"),
                  "Moutiers": lien(913, "Moutiers", "LA_GUERCHE_MOUTIERS"),
                  "La Guerche-de-Bretagne": lien(914, "La Guerche", "LA_GUERCHE_MOUTIERS"),
                  "Minicamps 6/8": lien(915, "Minicamps 6/8", "BAIS"), "Minicamps 8/10": lien(916, "Minicamps 8/10", None)},
    }


def Presets():
    """(péri Bais, extra Bais, extra Bais avec minicamps) -- noms sans année ni phase."""
    from Utils import UTILS_AFAS2_Presets as P
    peri = P.NouveauPreset("Bais périscolaire (fictif)", "periscolaire", "BAIS", sites=["Bais +6 ans"],
                           unites=CLASSEMENT_PERI, plages=PLAGES_PERI)
    extra = P.NouveauPreset("Bais extrascolaire (fictif)", "extrascolaire", "BAIS", sites=["Bais +6 ans", "Bais -6 ans"],
                            unites={k: v for k, v in CLASSEMENT_EXTRA.items() if v != "sejour"}, plages=PLAGES_EXTRA)
    minicamps = P.NouveauPreset("Bais extrascolaire avec minicamps (fictif)", "extrascolaire", "BAIS",
                                sites=["Bais +6 ans", "Bais -6 ans", "Minicamps 6/8"], unites=CLASSEMENT_EXTRA,
                                plages=PLAGES_EXTRA)
    return P.ValiderPreset(peri), P.ValiderPreset(extra), P.ValiderPreset(minicamps)


TABLES = ("familles", "individus", "activites", "groupes", "unites", "consommations", "prestations", "factures",
          "ouvertures", "vacances", "aeeh_periodes", "profils", "profils_parametres")


def _valeur(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'%s'" % str(v).replace("'", "''")


def _inserer(db, table, colonnes, lignes):
    for ligne in lignes:
        db.cursor.execute("INSERT INTO %s (%s) VALUES (%s);" % (table, ", ".join(colonnes), ", ".join(_valeur(v) for v in ligne)))


def Peupler(db, creer_tables=False):
    """Insère le jeu fictif dans une base GestionDB ouverte (SQLite ou MySQL)."""
    from Data import DATA_Tables as Tables
    if creer_tables:
        for table in TABLES:
            db.CreationTable(table, dicoDB=Tables.DB_DATA)
    _inserer(db, "familles", ["IDfamille"], [(i,) for i, nom, prenom in ENFANTS])
    _inserer(db, "individus", ["IDindividu", "IDcivilite", "nom", "prenom"], [(i, 4, nom, prenom) for i, nom, prenom in ENFANTS])
    _inserer(db, "activites", ["IDactivite", "nom", "abrege"], [(ACTIVITE, "ALSH (fictif AFAS)", "AFAS")])
    _inserer(db, "groupes", ["IDgroupe", "IDactivite", "nom", "ordre"], [(g, ACTIVITE, nom, i) for i, (g, nom) in enumerate(GROUPES, 1)])
    _inserer(db, "unites", ["IDunite", "IDactivite", "nom", "abrege", "type", "heure_debut", "heure_fin", "ordre"],
             [(u, ACTIVITE, nom, nom[:6].upper(), t, d, f, i) for i, (u, nom, t, d, f) in enumerate(UNITES, 1)])
    _inserer(db, "vacances", ["IDvacance", "nom", "annee", "date_debut", "date_fin"],
             [(9000 + i, nom, int(d[:4]), d, f) for i, (nom, d, f) in enumerate(VACANCES, 1)])
    _inserer(db, "factures", ["IDfacture", "numero", "etat", "date_edition"], [(i, n, e, "2026-11-05") for i, n, e in FACTURES])
    _inserer(db, "prestations", ["IDprestation", "IDindividu", "IDfamille", "IDactivite", "IDfacture", "montant", "montant_initial",
                                 "date", "label", "categorie"],
             [(p, i, i, ACTIVITE, f, m, m, d, l, "consommation") for p, i, f, m, d, l in PRESTATIONS + (REGULARISATION,)])
    _inserer(db, "consommations", ["IDconso", "IDindividu", "IDactivite", "date", "IDunite", "IDgroupe", "etat", "heure_debut",
                                   "heure_fin", "IDprestation"],
             [(c, i, ACTIVITE, d, u, g, e, hd, hf, p) for c, i, d, u, g, e, hd, hf, p in CONSOMMATIONS])
    _inserer(db, "ouvertures", ["IDactivite", "IDunite", "IDgroupe", "date"], [(ACTIVITE, u, g, d) for u, g, d in OUVERTURES])
    _inserer(db, "aeeh_periodes", ["IDperiode", "IDindividu", "date_debut", "date_fin"], AEEH)
    db.Commit()
