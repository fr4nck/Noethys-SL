# -*- coding: utf-8 -*-
"""Contrats financiers purs des paniers familiaux ; aucune base ni facture."""
import unittest
from decimal import Decimal
from Utils import UTILS_Repas_tarification_2c as T


class SimulationSansRepasTests(unittest.TestCase):
    def test_repas_separe_panier_restauration_zero_accueil_inchange(self):
        resultat = T.EvaluerPanier("sans_repas_pmsl", "repas_separe", "14.50", "4.50")
        self.assertEqual(resultat, {
            "accueil": Decimal("14.50"), "repas": Decimal("0.00"),
            "total": Decimal("14.50"), "provenance": "panier_familial"})

    def test_repas_fournisseur_normal_facture(self):
        for regime in ("standard", "sans_porc", "vegetarien"):
            with self.subTest(regime=regime):
                resultat = T.EvaluerPanier(regime, "repas_separe", "14.50", "4.50")
                self.assertEqual((resultat["repas"], resultat["total"]),
                                 (Decimal("4.50"), Decimal("19.00")))

    def test_pas_de_suppression_automatique_apres_emission_ou_reglement(self):
        for kwargs in ({"facture_emise": True}, {"prestation_reglee": True}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(T.TarificationPanierInvalide):
                    T.EvaluerPanier("sans_repas_pmsl", "repas_separe",
                                   "14.50", "4.50", **kwargs)

    def test_forfait_panier_refuse_sans_tarif_alternatif_approuve(self):
        for options in ({}, {"tarif_journee_sans_repas": "15.00"},
                        {"tarif_journee_sans_repas": "15.00", "prix_sans_repas_approuve": False}):
            with self.subTest(options=options):
                with self.assertRaises(T.TarificationPanierInvalide):
                    T.EvaluerPanier("sans_repas_pmsl", "journee_avec_repas",
                                   "18.50", **options)

    def test_forfait_panier_tarif_explicite(self):
        resultat = T.EvaluerPanier("sans_repas_pmsl", "journee_avec_repas", "18.50",
                                   tarif_journee_sans_repas="14.00", prix_sans_repas_approuve=True)
        self.assertEqual((resultat["total"], resultat["repas"], resultat["provenance"]),
                         (Decimal("14.00"), Decimal("0.00"), "tarif_sans_repas_approuve"))

    def test_forfait_sans_panier_prealable_intact(self):
        resultat = T.EvaluerPanier("standard", "journee_avec_repas", "18.50")
        self.assertEqual((resultat["total"], resultat["repas"]),
                         (Decimal("18.50"), None))

    def test_refus_des_montants_flottants_et_incertains(self):
        for valeur in ("NaN", "Infinity", "-1", "2.345", 1.1, None, True):
            with self.subTest(valeur=valeur):
                with self.assertRaises(T.TarificationPanierInvalide):
                    T.EvaluerPanier("sans_repas_pmsl", "repas_separe", "14.50", valeur)

    def test_tarif_alternatif_non_supérieur(self):
        with self.assertRaises(T.TarificationPanierInvalide):
            T.EvaluerPanier("sans_repas_pmsl", "journee_avec_repas", "14.00",
                           tarif_journee_sans_repas="19.00", prix_sans_repas_approuve=True)

    def test_absence_de_base_et_d_effet_de_bord(self):
        self.assertFalse(hasattr(T, "GestionDB"))
        self.assertFalse(hasattr(T, "EnregistrerFacture"))
        self.assertEqual(T.TARIFS, ("repas_separe", "journee_avec_repas"))

if __name__ == "__main__":
    unittest.main()
