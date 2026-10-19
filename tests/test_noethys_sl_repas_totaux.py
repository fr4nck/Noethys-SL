# -*- coding: utf-8 -*-
"""Sommes coherentes avant email/PDF, sans base ni reseau."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "noethys"))
from Utils.UTILS_Repas_totaux import TotauxRepas


class TotauxRepasTests(unittest.TestCase):
    def test_exemple_metier(self):
        x = TotauxRepas(18, 32, animateurs_repas=3, direction_repas=1,
                        autres_adultes_repas=1, sans_porc=7)
        self.assertEqual((x["repas_6_et_plus"], x["total_repas"],
                          x["total_adultes"], x["sans_porc"]), (37, 55, 5, 7))

    def test_repas_adultes_exclus_du_nombre_enfants(self):
        x = TotauxRepas(0, 0, 3, 1, 1, 0)
        self.assertEqual((x["repas_6_et_plus"], x["total_repas"]), (5, 5))
        self.assertEqual(x["enfants_6_et_plus"], 0)

    def test_sans_porc_n_est_pas_un_supplement(self):
        x = TotauxRepas(10, 12, 2, 0, 0, 6)
        self.assertEqual(x["total_repas"], 24)

    def test_valeurs_invalides_rejetees(self):
        for mauvais in [-1, 1.5, "deux", None, True]:
            with self.subTest(mauvais=mauvais), self.assertRaises(ValueError):
                TotauxRepas(mauvais, 0)
        with self.assertRaises(ValueError):
            TotauxRepas(5, 5, sans_porc=11)

    def test_aucun_repas(self):
        x = TotauxRepas(0, 0)
        self.assertEqual((x["total_repas"], x["total_adultes"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
