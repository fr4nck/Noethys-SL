# -*- coding: utf-8 -*-
"""Bordereau de menus Oceane : adultes inclus en P, jamais en A.

Cas purement fictifs sans base PMSL, sans fournisseur et sans envoi.
"""
from datetime import date
import unittest

from Utils import UTILS_Repas_oceane as O
from Utils.UTILS_Repas_totaux import TotauxRepas


JOUR = date(2026, 11, 4)  # mercredi


def commande(site="Bais", **champs):
    valeurs = {"date": JOUR, "site": site, "service": "midi",
               "totaux": TotauxRepas(
                   8, 25, animateurs_repas=3, direction_repas=1,
                   autres_adultes_repas=0, sans_porc=4)}
    valeurs.update(champs)
    return valeurs


class TotauxOceane(unittest.TestCase):
    def test_animateurs_et_direction_sont_en_p_jamais_en_a(self):
        repart = O.RepartitionFournisseur(commande()["totaux"])
        self.assertEqual(
            (repart["M"], repart["P"], repart["A"], repart["adultes_dans_P"]),
            (8, 29, 0, 4))
        self.assertEqual(repart["M"] + repart["P"], repart["total_repas"])
        self.assertEqual(repart["total_repas"], 37)

    def test_25_enfants_plus_de_6_ans_et_4_animateurs(self):
        t = TotauxRepas(0, 25, animateurs_repas=4)
        self.assertEqual(O.RepartitionFournisseur(t)["P"], 29)
        self.assertEqual(O.RepartitionFournisseur(t)["A"], 0)

    def test_autres_adultes_separes_en_interne(self):
        t = TotauxRepas(3, 20, animateurs_repas=4, direction_repas=1,
                        autres_adultes_repas=2, sans_porc=6)
        r = O.RepartitionFournisseur(t)
        self.assertEqual((r["M"], r["P"], r["A"]), (3, 27, 0))
        self.assertEqual(r["adultes_dans_P"], 7)

    def test_refuse_totaux_perimes_ou_invalides(self):
        t = TotauxRepas(0, 25, animateurs_repas=4)
        for mauvais in (
            dict(t, repas_6_et_plus=25),
            dict(t, total_repas=25),
            dict(t, animateurs_repas=-1),
            dict(t, enfants_6_et_plus=None),
        ):
            with self.subTest(t=mauvais), self.assertRaises(ValueError):
                O.RepartitionFournisseur(mauvais)


class CellulesBordereau(unittest.TestCase):
    def test_site_codes_et_deux_blocs(self):
        for nom, onglet, code in (
            ("La Guerche", "LGB", 7011),
            ("MOUTIERS", "MOUT", 7012),
            ("Bais", "Bais", 7077),
        ):
            with self.subTest(site=nom):
                p = O.PreparerMercredi(commande(nom), 1)
                self.assertEqual((p["site"], p["code_client"]), (onglet, code))
                self.assertEqual(p["cellules"]["I8"], 8)
                self.assertEqual(p["cellules"]["J9"], 29)
                self.assertNotIn("K9", p["cellules"])
                self.assertIn("K9", p["colonne_adulte_a_vider"])
                self.assertTrue(p["repartition_alimentaire_a_completer"])

        p = O.PreparerMercredi(commande(), 2)
        self.assertEqual((p["cellules"]["I33"], p["cellules"]["J37"]), (8, 29))
        self.assertIn("K34", p["colonne_adulte_a_vider"])
        self.assertNotIn("J9", p["cellules"])

    def test_cinq_composantes_modifiables_sans_toucher_au_p(self):
        quantites = {k: {"M": 8, "P": 29} for k in O.COMPOSANTES}
        quantites["garniture"] = {"M": 7, "P": 26}
        p = O.PreparerMercredi(commande(), 1, composantes=quantites)
        self.assertEqual(p["cellules"]["I10"], 7)
        self.assertEqual(p["cellules"]["J10"], 26)
        self.assertEqual(p["repas_P"], 29)
        self.assertEqual(p["adultes_dans_P"], 4)
        self.assertEqual(p["cellules"]["J9"], 29)

    def test_sous_categories_sont_des_dont_non_additifs(self):
        p = O.PreparerMercredi(commande(), 1, variantes={
            "sans_porc": {"M": 1, "P": 3},
            "sans_viande": {"M": 0, "P": 2},
            "vegetarien": {"M": 1, "P": 4},
            "sans_allergene": {"M": 0, "P": 0},
        })
        c = p["cellules"]
        self.assertEqual((c["I17"], c["J17"]), (1, 3))
        self.assertEqual((c["I18"], c["J18"]), (0, 2))
        self.assertEqual((c["I19"], c["J19"]), (1, 4))
        self.assertEqual((c["I20"], c["J20"]), (0, 0))
        self.assertEqual(c["J9"], 29)
        self.assertFalse(p["repartition_alimentaire_a_completer"])

    def test_variantes_bordereau_identiques_aux_regimes_valides(self):
        # Une somme M/P differente du controle de la commande doit bloquer.
        # Le restaurateur ne doit jamais recevoir un faux sous-total.
        entree = commande(regimes={
            "standard": 28, "sans_porc": 4, "vegetarien": 5,
            "non_renseignes": 0,
        })
        variantes = {
            "sans_porc": {"M": 1, "P": 3},
            "sans_viande": {"M": 0, "P": 0},
            "vegetarien": {"M": 1, "P": 4},
            "sans_allergene": {"M": 0, "P": 0},
        }
        correct = O.PreparerMercredi(entree, 1, variantes=variantes)
        self.assertEqual(correct["cellules"]["J17"], 3)
        self.assertEqual(correct["cellules"]["J19"], 4)
        sans_porc_incorrect = dict(variantes,
                                  sans_porc={"M": 1, "P": 2})
        with self.assertRaises(ValueError):
            O.PreparerMercredi(entree, 1, variantes=sans_porc_incorrect)
        vegetarien_incorrect = dict(variantes,
                                   vegetarien={"M": 1, "P": 3})
        with self.assertRaises(ValueError):
            O.PreparerMercredi(entree, 1, variantes=vegetarien_incorrect)

    def test_dossier_allergene_doit_etre_accepte(self):
        entree = commande()
        variantes = {"sans_allergene": {"M": 1, "P": 0}}
        with self.assertRaises(ValueError):
            O.PreparerMercredi(entree, 1, variantes=variantes)
        accepte = O.PreparerMercredi(
            entree, 1, variantes=variantes, allergenes_valides=True)
        self.assertEqual(accepte["cellules"]["I20"], 1)

    def test_pas_de_regimes_devines_a_partir_d_un_total_global(self):
        entree = commande()
        p = O.PreparerMercredi(entree, 1)
        self.assertNotIn("I17", p["cellules"])
        self.assertNotIn("J17", p["cellules"])
        self.assertTrue(p["repartition_alimentaire_a_completer"])

    def test_invalides_refuses(self):
        with self.assertRaises(ValueError):
            O.PreparerMercredi(commande("Inconnu"), 1)
        with self.assertRaises(ValueError):
            O.PreparerMercredi(commande(date=date(2026, 11, 3)), 1)
        with self.assertRaises(ValueError):
            O.PreparerMercredi(commande(service="gouter"), 1)
        with self.assertRaises(ValueError):
            O.PreparerMercredi(commande(), 3)
        with self.assertRaises(ValueError):
            O.PreparerMercredi(commande(), 1,
                              composantes={"plat": {"P": 29}})
        with self.assertRaises(ValueError):
            O.PreparerMercredi(commande(), 1,
                              variantes={"vegetarien": {"M": 9, "P": 0}})
        with self.assertRaises(ValueError):
            O.PreparerMercredi(commande(), 1,
                              variantes={"sans_viande": {"M": 0, "A": 4}})

    def test_un_bloc_un_site_une_commande(self):
        a, b = commande("LGB"), commande("Bais")
        a["bloc"] = b["bloc"] = 1
        r = O.PreparerLotsMercredis([a, b])
        self.assertEqual(len(r), 2)
        with self.assertRaises(ValueError):
            O.PreparerLotsMercredis([a, a])


if __name__ == "__main__":
    unittest.main()
