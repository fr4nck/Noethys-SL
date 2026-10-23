# -*- coding: utf-8 -*-
"""AFAS V2 -- règles contractuelles des conventions CAF ALSH 2025-2027.

Module pur (ni wx, ni base) : chaque règle reprend uniquement le texte des
conventions d'objectifs et de financement fournies (Caf d'Ille-et-Vilaine,
association Pêle-Mêle Sports et Loisirs) et cite sa source. Aucune règle
n'est déduite pour un accueil, une période ou une option non couverts : la
résolution échoue explicitement (ConventionNonApplicable).

Traçabilité détaillée : docs/afas/TRACABILITE_CONVENTIONS_2025_2027.md.
Les numéros de page sont ceux du PDF numérisé (« p. PDF ») suivis de la
pagination imprimée du document.
"""
import datetime

PERISCOLAIRE = "periscolaire"
EXTRASCOLAIRE = "extrascolaire"
MODES = (PERISCOLAIRE, EXTRASCOLAIRE)

EQUIPEMENT_BAIS = "BAIS"
EQUIPEMENT_LA_GUERCHE_MOUTIERS = "LA_GUERCHE_MOUTIERS"

EQUIPEMENTS = {
    EQUIPEMENT_BAIS: {"libelle": "Bais"},
    EQUIPEMENT_LA_GUERCHE_MOUTIERS: {"libelle": "La Guerche-de-Bretagne / Moutiers"},
}

SECONDES_HEURE = 3600
PLAFOND_PERISCOLAIRE_JOUR = 9 * SECONDES_HEURE
JOURNEE_OPTION2_MAX = 8 * SECONDES_HEURE
DEMI_JOURNEE_OPTION2_MAX = 4 * SECONDES_HEURE
SEJOUR_JOURNEE = 10 * SECONDES_HEURE
DUREE_MINIMALE_JOURNEE_EXTRA = 2 * SECONDES_HEURE

DEBUT_2025_2027 = datetime.date(2025, 1, 1)
FIN_2025_2027 = datetime.date(2027, 12, 31)


class ConventionNonApplicable(ValueError):
    """Aucune convention fournie ne couvre l'équipement, le mode ou la date demandés."""


def _source(fichier, article, page_pdf, page_imprimee, extrait):
    return {"fichier": fichier, "article": article, "page_pdf": page_pdf,
            "page_imprimee": page_imprimee, "extrait": extrait}


_REGLES_PERISCOLAIRE = {
    "definition_periode": "Semaines où les enfants vont à l'école, à l'exception des samedis sans école et des dimanches.",
    "unite_calcul": "heure",
    "presence": "Durée totale de la plage d'accueil dès lors que l'enfant a été présent sur cette plage.",
    "plafond_jour_secondes": PLAFOND_PERISCOLAIRE_JOUR,
    "temps_repas_meridien": "Financé dans son intégralité depuis le 1er janvier 2023.",
    "heures_facturees": None,
    "complement_inclusif": "Heure de présence effective éventuellement arrondie à l'heure supérieure, enfants bénéficiaires de l'AEEH uniquement.",
}

_REGLES_EXTRASCOLAIRE = {
    "definition_periode": "Vacances scolaires, samedis sans école, dimanche uniquement pour les séjours de 5 nuits et 6 jours maximum.",
    "unite_calcul": "heure",
    "actes_realises": "Heures de présence effective des enfants.",
    "option_facturation": 2,
    "option2": "Facturation à la demi-journée ou à la journée ; amplitude effective >= 8 h : journée = 8 h, demi-journée = 4 h ; sinon journée = amplitude, demi-journée = moitié de l'amplitude.",
    "duree_minimale_journee_secondes": DUREE_MINIMALE_JOURNEE_EXTRA,
    "sejours": "Séjours accessoires de 1 à 4 nuits et séjours de 5 nuits / 6 jours remplissant les conditions : 10 heures par journée réalisée et par enfant.",
    "complement_inclusif": "Heure de présence effective éventuellement arrondie à l'heure supérieure, enfants bénéficiaires de l'AEEH uniquement.",
}

CONVENTIONS = {
    "PERI_BAIS_2025_2027": {
        "fichier": "PERI_BAIS_.pdf",
        "structure": "ALSH Peri Ass Bais",
        "equipement": EQUIPEMENT_BAIS,
        "mode": PERISCOLAIRE,
        "date_debut": DEBUT_2025_2027,
        "date_fin": FIN_2025_2027,
        "signature_caf": datetime.date(2025, 3, 6),
        "regles": _REGLES_PERISCOLAIRE,
        "ctg_heures_existantes": 14115,
        "ctg_euros_par_heure": "0.15",
        "sites_nommes": ("Bais",),
    },
    "PERI_LA_GUERCHE_MOUTIERS_2025_2027": {
        "fichier": "PERI_LA_GUERCHE.pdf",
        "structure": "ALSH périscolaire La Guerche-Moutiers",
        "equipement": EQUIPEMENT_LA_GUERCHE_MOUTIERS,
        "mode": PERISCOLAIRE,
        "date_debut": DEBUT_2025_2027,
        "date_fin": FIN_2025_2027,
        "signature_caf": datetime.date(2025, 6, 6),
        "regles": _REGLES_PERISCOLAIRE,
        "ctg_heures_existantes": 19200,
        "ctg_euros_par_heure": "0.60",
        "sites_nommes": ("La Guerche", "Moutiers"),
    },
    "EXTRA_BAIS_2025_2027": {
        "fichier": "EXTRA_BAIS.pdf",
        "structure": "ALSH Extra Ass Bais",
        "equipement": EQUIPEMENT_BAIS,
        "mode": EXTRASCOLAIRE,
        "date_debut": DEBUT_2025_2027,
        "date_fin": FIN_2025_2027,
        "signature_caf": datetime.date(2025, 3, 3),
        "regles": _REGLES_EXTRASCOLAIRE,
        "ctg_heures_existantes": 14690,
        "ctg_euros_par_heure": "0.15",
        "sites_nommes": ("Bais",),
    },
    "EXTRA_LA_GUERCHE_MOUTIERS_2025_2027": {
        "fichier": "EXTRA_LA_GUERCHE.pdf",
        "structure": "ALSH Extrascolaire La Guerche-Moutiers",
        "equipement": EQUIPEMENT_LA_GUERCHE_MOUTIERS,
        "mode": EXTRASCOLAIRE,
        "date_debut": DEBUT_2025_2027,
        "date_fin": FIN_2025_2027,
        "signature_caf": datetime.date(2025, 3, 6),
        "regles": _REGLES_EXTRASCOLAIRE,
        "ctg_heures_existantes": 23111,
        "ctg_euros_par_heure": "0.60",
        "sites_nommes": ("La Guerche", "Moutiers"),
    },
}

# Version du jeu de règles : à incrémenter à chaque modification d'une règle
# ou d'une convention (tracée dans chaque instantané de calcul).
VERSION_REGLES = "2025-2027.1"

SOURCES = {
    "periscolaire_definition": [
        _source("PERI_BAIS_.pdf", "1.1", 4, "5/19", "L'ensemble des temps d'accueil se déroulant sur des semaines où les enfants vont à l'école sont qualifiés de temps périscolaires (à l'exception des samedis sans école et des dimanches)."),
        _source("PERI_LA_GUERCHE.pdf", "1.1", 4, "5/19", "Texte identique."),
    ],
    "periscolaire_plage_9h": [
        _source("PERI_BAIS_.pdf", "2-2", 7, "8/19", "Ces heures réalisées correspondent donc à la durée totale de la plage d'accueil dès lors que l'enfant a été présent sur cette plage. Le nombre d'heures maximum pouvant être pris en compte par jour et par enfant est limité à 9 heures."),
        _source("PERI_LA_GUERCHE.pdf", "2-2", 7, "8/19", "Texte identique."),
    ],
    "periscolaire_repas": [
        _source("PERI_BAIS_.pdf", "1.5", 6, "7/19", "La prise en compte du temps de repas dans la pause méridienne, désormais financée dans son intégralité depuis le 1er janvier 2023."),
        _source("PERI_LA_GUERCHE.pdf", "1.5", 6, "7/19", "Texte identique."),
    ],
    "complement_inclusif": [
        _source("PERI_BAIS_.pdf", "1.5", 6, "7/19", "Majorer la subvention Alsh par heure d'accueil réalisée (heure de présence effective éventuellement arrondie à l'heure supérieure) uniquement pour les enfants bénéficiaires de l'AEEH."),
        _source("EXTRA_BAIS.pdf", "1.3", 5, "6/20", "Texte équivalent pour l'Alsh extrascolaire."),
    ],
    "extrascolaire_definition": [
        _source("EXTRA_BAIS.pdf", "1.1", 4, "5/21", "L'accueil de loisirs Extrascolaire est celui qui se déroule pendant les vacances scolaires, les samedis sans école, le dimanche (uniquement pour les séjours d'une durée maximum de 5 nuits et 6 jours)."),
        _source("EXTRA_LA_GUERCHE.pdf", "1.1", 4, "5/21", "Texte identique."),
    ],
    "extrascolaire_actes": [
        _source("EXTRA_BAIS.pdf", "2-2", 6, "7/20", "Les actes réalisés sont les heures de présence effective des enfants des familles de tout régime. Les actes facturés sont la somme des heures facturées aux familles de tout régime."),
    ],
    "extrascolaire_option2": [
        _source("EXTRA_BAIS.pdf", "2-2 (tableau)", 7, "8/20", "Option 2 : si l'amplitude d'ouverture effective de l'équipement est égale ou supérieure à 8 heures pour une journée, alors la journée équivaut à 8 heures et la 1/2 journée équivaut à 4 heures ; si l'amplitude est inférieure à 8 heures, la journée équivaut à cette amplitude journalière et la 1/2 journée à la moitié."),
        _source("EXTRA_BAIS.pdf", "2-2 (encadré)", 8, "9/21", "Pour l'accueil de loisirs sans hébergement - extrascolaire, l'option n°2 est retenue."),
        _source("EXTRA_LA_GUERCHE.pdf", "2-2 (tableau et encadré)", 7, "8/20 et 9/21", "Texte identique, option n°2 retenue."),
    ],
    "extrascolaire_duree_minimale": [
        _source("EXTRA_BAIS.pdf", "2-1", 5, "6/20", "Sur une durée minimale de deux heures par journée de fonctionnement."),
    ],
    "sejours": [
        _source("EXTRA_BAIS.pdf", "2-1", 6, "7/20", "Activités accessoires (mini-camps) de quatre nuits maximum ... séjours d'une durée de cinq nuits et six jours au maximum, sous réserve qu'ils soient prévus dès la déclaration annuelle, intégrés au projet éducatif et déclarés en tant que séjour de vacances."),
        _source("EXTRA_BAIS.pdf", "2-2 (tableau séjours)", 8, "9/21", "En fonction du nombre de journées réalisées au profit des familles avec 1 journée = 10 heures."),
        _source("EXTRA_LA_GUERCHE.pdf", "2-1 et 2-2", 6, "7/20 et 9/21", "Texte identique."),
    ],
    "duree_conventions": [
        _source("PERI_BAIS_.pdf", "9", 18, "19/19", "Conclue du 1er janvier 2025 au 31 décembre 2027."),
        _source("PERI_LA_GUERCHE.pdf", "9", 18, "19/19", "Conclue du 1er janvier 2025 au 31 décembre 2027."),
        _source("EXTRA_BAIS.pdf", "9", 18, "19/20", "Conclue du 01/01/2025 au 31/12/2027."),
        _source("EXTRA_LA_GUERCHE.pdf", "9", 18, "19/20", "Conclue du 01/01/2025 au 31/12/2027."),
    ],
}


def ResoudreConvention(equipement, mode, date):
    """Convention applicable à un équipement, un mode et une date précise."""
    trouvees = [code for code, c in sorted(CONVENTIONS.items())
                if c["equipement"] == equipement and c["mode"] == mode
                and c["date_debut"] <= date <= c["date_fin"]]
    if len(trouvees) != 1:
        raise ConventionNonApplicable(
            "Aucune convention fournie ne couvre %s / %s au %s." % (
                EQUIPEMENTS.get(equipement, {}).get("libelle", equipement), mode, date.strftime("%d/%m/%Y")))
    return trouvees[0]


def ResoudreConventionAnnee(equipement, mode, annee):
    """Convention couvrant toute l'année civile, sinon ConventionNonApplicable.

    Une année partiellement couverte n'est jamais complétée par une autre règle."""
    debut = ResoudreConvention(equipement, mode, datetime.date(annee, 1, 1))
    fin = ResoudreConvention(equipement, mode, datetime.date(annee, 12, 31))
    if debut != fin:
        raise ConventionNonApplicable("L'année %d relève de plusieurs conventions." % annee)
    return debut


def DureeJourneeOption2(nature, amplitude_secondes):
    """Équivalence horaire option n°2 (conventions extrascolaires, art. 2-2).

    nature : "journee" ou "demi_journee" ; amplitude : amplitude effective
    d'ouverture de l'équipement ce jour-là, en secondes."""
    if type(amplitude_secondes) is not int or amplitude_secondes <= 0:
        raise ValueError("Amplitude d'ouverture absente ou invalide")
    if nature == "journee":
        return JOURNEE_OPTION2_MAX if amplitude_secondes >= JOURNEE_OPTION2_MAX else amplitude_secondes
    if nature == "demi_journee":
        return DEMI_JOURNEE_OPTION2_MAX if amplitude_secondes >= JOURNEE_OPTION2_MAX else amplitude_secondes // 2
    raise ValueError("Nature de facturation inconnue : %r" % (nature,))


def PresencePeriscolaireJour(plages_secondes):
    """Heures de présence périscolaires d'un enfant pour une journée.

    plages_secondes : plages d'accueil (debut, fin) en secondes depuis minuit
    sur lesquelles l'enfant a été présent. Chaque plage compte pour sa durée
    totale, les recouvrements ne comptent qu'une fois, plafond 9 h."""
    return min(DureeUnion(plages_secondes), PLAFOND_PERISCOLAIRE_JOUR)


def DureeUnion(plages):
    """Durée de l'union d'intervalles [debut, fin[ en secondes."""
    total = 0
    fin_courante = None
    for debut, fin in sorted(plages):
        if type(debut) is not int or type(fin) is not int or not 0 <= debut < fin <= 24 * SECONDES_HEURE:
            raise ValueError("Plage horaire invalide : %r" % ((debut, fin),))
        if fin_courante is None or debut >= fin_courante:
            total += fin - debut
            fin_courante = fin
        elif fin > fin_courante:
            total += fin - fin_courante
            fin_courante = fin
    return total


def ArrondiHeureSuperieure(secondes):
    """Arrondi à l'heure supérieure (complément inclusif, si retenu)."""
    if secondes <= 0:
        return 0
    return -(-secondes // SECONDES_HEURE) * SECONDES_HEURE
