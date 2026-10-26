# -*- coding: utf-8 -*-
"""Politique pure de tarification d'un repas apporte par la famille (#433).

Ne modifie jamais prestations, factures ou consommations. C'est un garde-fou
de calcul, pas un moteur de facturation connecte a la grille Noethys.
Les prix forfaitaires doivent etre explicitement approuves en amont.
"""
from decimal import Decimal, InvalidOperation

SANS_REPAS = "sans_repas_pmsl"
TARIF_REPAS_SEPARE = "repas_separe"
TARIF_JOURNEE_COMPOSITE = "journee_avec_repas"
TARIFS = (TARIF_REPAS_SEPARE, TARIF_JOURNEE_COMPOSITE)


class TarificationPanierInvalide(ValueError):
    """La facturation ne peut pas etre calculee sans decision tarifaire."""


def _montant(valeur, nom):
    if isinstance(valeur, bool) or valeur is None or isinstance(valeur, float):
        raise TarificationPanierInvalide("%s non qualifie (Decimal/centimes requis)" % nom)
    try:
        resultat = Decimal(str(valeur))
    except (InvalidOperation, ValueError, TypeError):
        raise TarificationPanierInvalide("%s illisible" % nom)
    if not resultat.is_finite() or resultat < 0 or resultat.as_tuple().exponent < -2:
        raise TarificationPanierInvalide("%s doit etre positif au centime" % nom)
    return resultat.quantize(Decimal("0.01"))


def EvaluerPanier(type_repas, type_tarif, montant_accueil, montant_repas=None,
                  tarif_journee_sans_repas=None, prix_sans_repas_approuve=False,
                  facture_emise=False, prestation_reglee=False):
    """Simulation, jamais persistance ; 0 EUR sur la composante repas.

    - Tarif separe : accueil conserve + repas gratuit uniquement pour panier.
    - Tarif composite : tarif explicite "journee sans repas" indispensable.
      Ne jamais retirer un prix hypothetique du tarif global.
    - Facture deja emise ou prestation reglee : STOP + avoir explicite.
    """
    if type_repas not in ("standard", "sans_porc", "vegetarien", SANS_REPAS):
        raise TarificationPanierInvalide("Type de repas inconnu")
    if type_tarif not in TARIFS:
        raise TarificationPanierInvalide("Modele tarifaire inconnu")
    accueil = _montant(montant_accueil, "Montant accueil")
    if type_tarif == TARIF_REPAS_SEPARE:
        repas = _montant(montant_repas, "Montant repas")
        if type_repas != SANS_REPAS:
            return {"accueil": accueil, "repas": repas,
                    "total": accueil + repas, "provenance": "tarif_existant"}
        if facture_emise or prestation_reglee:
            raise TarificationPanierInvalide("Facture/prestation existante : regularisation humaine obligatoire")
        return {"accueil": accueil, "repas": Decimal("0.00"),
                "total": accueil, "provenance": "panier_familial"}
    if type_repas != SANS_REPAS:
        return {"accueil": accueil, "repas": None, "total": accueil,
                "provenance": "forfait_existant"}
    if facture_emise or prestation_reglee:
        raise TarificationPanierInvalide("Forfait deja facture/regle : regularisation obligatoire")
    if prix_sans_repas_approuve is not True:
        raise TarificationPanierInvalide("Tarif journee sans repas non approuve")
    alternative = _montant(tarif_journee_sans_repas, "Tarif journee sans repas")
    if alternative > accueil:
        raise TarificationPanierInvalide("Tarif alternatif superieur au forfait de reference")
    return {"accueil": alternative, "repas": Decimal("0.00"),
            "total": alternative, "provenance": "tarif_sans_repas_approuve"}
