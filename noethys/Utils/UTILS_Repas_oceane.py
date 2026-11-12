# -*- coding: utf-8 -*-
"""Projection controlee des commandes du mercredi vers le bordereau Oceane.

Bordereau source : "Tableau de commandes CLSH VAC NB repas vierge.xlsx"
Onglets LGB/MOUT/Bais, blocs de semaine 1/2 (25 lignes d'ecart).
La colonne P du restaurateur est la portion 6 ans et plus ; les repas
du personnel y sont ajoutes. La colonne A n'est jamais commandee.
Ce module prepare les cellules mais ne cree pas de commande, n'envoie pas
de courriel et ne modifie aucun fichier fourni par le restaurateur.
"""

from datetime import date

from Utils.UTILS_Repas_totaux import EntierNaturel, TotauxRepas


SITES = {
    "LGB": ("LGB", 7011),
    "LA GUERCHE": ("LGB", 7011),
    "LA GUERCHE DE BRETAGNE": ("LGB", 7011),
    "MOUT": ("MOUT", 7012),
    "MOUTIERS": ("MOUT", 7012),
    "BAIS": ("Bais", 7077),
}
COMPOSANTES = ("entree", "plat", "garniture", "laitage", "dessert")
VARIANTES = ("sans_porc", "sans_viande", "vegetarien", "sans_allergene")
ROLES = ("enfants_moins_6", "enfants_6_et_plus", "animateurs_repas",
         "direction_repas", "autres_adultes_repas", "sans_porc")
CHAMPS_CONTROLE = ("total_adultes", "repas_6_et_plus", "total_repas")


def _site(valeur):
    if not isinstance(valeur, str):
        raise ValueError("Site Oceane non reconnu")
    ident = " ".join(valeur.upper().split())
    if ident not in SITES:
        raise ValueError("Site Oceane non reconnu : %s" % valeur)
    return SITES[ident]


def _mercredi(valeur):
    if isinstance(valeur, str):
        try:
            valeur = date.fromisoformat(valeur)
        except ValueError:
            raise ValueError("Date de mercredi invalide")
    if type(valeur) is not date or valeur.weekday() != 2:
        raise ValueError("La commande attend un mercredi")
    return valeur


def _colonnes_tranches(valeurs):
    if not isinstance(valeurs, dict):
        raise ValueError("Quantites M/P invalides")
    if set(valeurs) != {"M", "P"}:
        raise ValueError("Indiquez les quantites M et P, sans colonne A")
    return {role: EntierNaturel(valeurs[role], role) for role in ("M", "P")}


def RepartitionFournisseur(totaux):
    """M et P pour Oceane, adultes conserves en detail interne seulement.

    Recalcule les totaux depuis les roles sources et detecte un recapitulatif
    perime (totaux mis a jour sans revalidation).
    """
    if not isinstance(totaux, dict):
        raise ValueError("Totaux de repas non renseignes")
    calcules = TotauxRepas(**{nom: totaux[nom] for nom in ROLES
                             if nom in totaux})
    if ("enfants_moins_6" not in totaux
            or "enfants_6_et_plus" not in totaux):
        raise ValueError("Totaux enfants par age requis")
    for champ in CHAMPS_CONTROLE:
        if champ in totaux and calcules[champ] != EntierNaturel(totaux[champ], champ):
            raise ValueError("Recapitulatif de commande perime : %s" % champ)
    return {
        "M": calcules["enfants_moins_6"],
        "P": calcules["repas_6_et_plus"],
        "A": 0,  # jamais de portion adulte chez Oceane
        "adultes_dans_P": calcules["total_adultes"],
        "total_repas": calcules["total_repas"],
    }


def PreparerMercredi(ligne, bloc, composantes=None, variantes=None,
                     allergenes_valides=False):
    """Prepare la position exacte des cellules du bordereau fournisseur.

    Le tableau est compose de deux blocs de cinq jours.
    I/J/K sont les colonnes M/P/A du mercredi.
    Les sous-categories sont des "dont" : jamais additionnees aux repas.
    Aucune ventilation M/P ne peut etre deduite d'un total global de
    sans porc ou d'une preference alimentaire non renseignee.
    """
    if not isinstance(ligne, dict):
        raise ValueError("Ligne de commande invalide")
    if type(bloc) is not int or bloc not in (1, 2):
        raise ValueError("Bloc de commande Oceane inconnu")
    if str(ligne.get("service", "midi")).strip().lower() != "midi":
        raise ValueError("Une commande Oceane concerne le repas de midi")
    jour = _mercredi(ligne.get("date"))
    feuille, code_client = _site(ligne.get("site"))
    repartition = RepartitionFournisseur(ligne.get("totaux"))
    quantites_defaut = {"M": repartition["M"], "P": repartition["P"]}
    if composantes is not None:
        if not isinstance(composantes, dict) or set(composantes) != set(COMPOSANTES):
            raise ValueError("Les cinq composantes du repas sont requises")
        quantites = {nom: _colonnes_tranches(composantes[nom])
                     for nom in COMPOSANTES}
    else:
        quantites = {nom: dict(quantites_defaut) for nom in COMPOSANTES}

    if variantes is not None:
        if not isinstance(variantes, dict) or not set(variantes).issubset(VARIANTES):
            raise ValueError("Sous-categories alimentaires inconnues")
        repartitions = {}
        for nom, effectifs in variantes.items():
            ventil = _colonnes_tranches(effectifs)
            for tranche in ("M", "P"):
                if ventil[tranche] > repartition[tranche]:
                    raise ValueError("Sous-categorie %s superieure aux repas %s"
                                     % (nom, tranche))
            repartitions[nom] = ventil
        if ("sans_allergene" in repartitions
                and any(repartitions["sans_allergene"].values())
                and allergenes_valides is not True):
            raise ValueError("Repas sans allergene : dossier a faire accepter par la dieteticienne")
    else:
        repartitions = {}

    # Les variantes sans porc et vegetarien sont des sous-totaux exclusifs
    # lorsque la commande comporte une repartition alimentaire validee.
    # Refuser toute ressaisie M/P qui differerait du controle humain.
    regimes = ligne.get("regimes")
    if regimes:
        for categorie in ("sans_porc", "vegetarien"):
            if categorie not in regimes:
                raise ValueError("Repartition validee incomplete : %s" % categorie)
            attendu = EntierNaturel(regimes[categorie], categorie)
            detail = repartitions.get(categorie)
            if detail is None:
                raise ValueError("Ventilation M/P manquante pour %s" % categorie)
            obtenu = detail["M"] + detail["P"]
            if obtenu != attendu:
                raise ValueError(
                    "Ventilation %s incoherente : %d en M/P pour %d repas valides"
                    % (categorie, obtenu, attendu))

    decalage = 25 * (bloc - 1)
    cellules = {}
    for index, nom in enumerate(COMPOSANTES):
        ligne_excel = 8 + decalage + index
        cellules["I%d" % ligne_excel] = quantites[nom]["M"]
        cellules["J%d" % ligne_excel] = quantites[nom]["P"]
    for index, nom in enumerate(VARIANTES):
        if nom in repartitions:
            ligne_excel = 17 + decalage + index
            cellules["I%d" % ligne_excel] = repartitions[nom]["M"]
            cellules["J%d" % ligne_excel] = repartitions[nom]["P"]
    return {
        "date": jour, "site": feuille, "code_client": code_client,
        "bloc": bloc, "cellules": cellules,
        "colonne_adulte_a_vider": tuple("K%d" % (8 + decalage + i)
                                       for i in range(5))
                                  + tuple("K%d" % (17 + decalage + i)
                                          for i in range(4)),
        "adultes_dans_P": repartition["adultes_dans_P"],
        "repas_M": repartition["M"], "repas_P": repartition["P"],
        "repartition_alimentaire_a_completer":
            variantes is None or set(variantes) != set(VARIANTES),
    }


def PreparerLotsMercredis(lignes):
    """Refuse deux commandes pour un meme site / semaine de modele."""
    sorties, vus = [], set()
    for ligne in lignes:
        proposition = PreparerMercredi(
            ligne, ligne["bloc"], ligne.get("composantes"),
            ligne.get("variantes"), ligne.get("allergenes_valides", False))
        cle = (proposition["site"], proposition["bloc"])
        if cle in vus:
            raise ValueError("Deux commandes pour le meme site / bloc de semaine")
        vus.add(cle)
        sorties.append(proposition)
    return sorties
