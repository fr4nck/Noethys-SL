# -*- coding: utf-8 -*-
"""Decompte coherent des repas : regles transversales RC8 #430.

Les nombres de repas adultes sont explicites, jamais derives du nombre
d'animateurs requis pour l'encadrement. Sans porc reste un sous-ensemble.
"""


def EntierNaturel(valeur, nom):
    if isinstance(valeur, bool):
        raise ValueError("%s invalide" % nom)
    try:
        entier = int(valeur)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("%s invalide" % nom)
    if entier < 0 or str(valeur).strip() != str(entier):
        raise ValueError("%s doit etre un entier positif ou zero" % nom)
    return entier


def TotauxRepas(enfants_moins_6, enfants_6_et_plus, animateurs_repas=0,
                direction_repas=0, autres_adultes_repas=0, sans_porc=0):
    """Retourne les totaux a valider avant toute emission de document.

    Le repas du directeur mutualise doit etre affecte a un seul site
    avant cet appel; aucun complement automatique n'est fait ici.
    """
    valeurs = {}
    for nom, valeur in (
        ("enfants_moins_6", enfants_moins_6),
        ("enfants_6_et_plus", enfants_6_et_plus),
        ("animateurs_repas", animateurs_repas),
        ("direction_repas", direction_repas),
        ("autres_adultes_repas", autres_adultes_repas),
        ("sans_porc", sans_porc),
    ):
        valeurs[nom] = EntierNaturel(valeur, nom)
    adultes = (valeurs["animateurs_repas"] + valeurs["direction_repas"]
               + valeurs["autres_adultes_repas"])
    six_plus = valeurs["enfants_6_et_plus"] + adultes
    total = valeurs["enfants_moins_6"] + six_plus
    if valeurs["sans_porc"] > total:
        raise ValueError("Le nombre sans porc ne peut pas depasser le total")
    valeurs.update({"total_adultes": adultes, "repas_6_et_plus": six_plus,
                    "total_repas": total})
    return valeurs
