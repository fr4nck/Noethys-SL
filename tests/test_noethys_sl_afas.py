#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "noethys" / "Utils" / "UTILS_AFAS.py"

spec = importlib.util.spec_from_file_location("UTILS_AFAS", str(MODULE_PATH))
afas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(afas)


class TestAFAS(unittest.TestCase):

    def test_cycle_afas_annee_civile(self):
        cycle = afas.GetCycleAFAS(2026)
        self.assertEqual(cycle["previsionnel"]["date_debut"], datetime.date(2026, 1, 1))
        self.assertEqual(cycle["previsionnel"]["date_fin"], datetime.date(2026, 12, 31))
        self.assertEqual(cycle["actualisation_juin"]["date_situation"], datetime.date(2026, 6, 30))
        self.assertEqual(cycle["actualisation_septembre"]["date_situation"], datetime.date(2026, 9, 30))
        self.assertEqual(cycle["reel"]["date_situation"], datetime.date(2026, 12, 31))

    def test_n1_ajuste_par_nombre_de_jours(self):
        estimation = afas.EstimerPeriode(
            methode=afas.METHODE_N1_AJUSTE,
            historique=[{"heures": 12600, "jours_ouverts": 20}],
            jours_ouverts_cible=22,
        )
        self.assertEqual(estimation, 13860.0)

    def test_moyenne_deux_ans_compare_les_taux_journaliers(self):
        estimation = afas.EstimerPeriode(
            methode=afas.METHODE_MOYENNE_2_ANS,
            historique=[
                {"heures": 12600, "jours_ouverts": 20},
                {"heures": 11800, "jours_ouverts": 20},
            ],
            jours_ouverts_cible=22,
        )
        self.assertEqual(estimation, 13420.0)

    def test_moyenne_deux_ans_accepte_des_calendriers_differents(self):
        estimation = afas.EstimerPeriode(
            methode=afas.METHODE_MOYENNE_2_ANS,
            historique=[
                {"heures": 12600, "jours_ouverts": 20},
                {"heures": 11400, "jours_ouverts": 19},
            ],
            jours_ouverts_cible=22,
        )
        self.assertEqual(estimation, 13530.0)

    def test_moyenne_trois_ans_utilise_les_annees_disponibles(self):
        comparaison = afas.ConstruireComparaison(
            historique=[
                {"heures": 12600, "jours_ouverts": 20},
                {"heures": 11400, "jours_ouverts": 19},
            ],
            jours_ouverts_cible=22,
        )
        self.assertIsNotNone(comparaison[afas.METHODE_MOYENNE_3_ANS])

    def test_valeur_manuelle(self):
        estimation = afas.EstimerPeriode(
            methode=afas.METHODE_MANUEL,
            historique=[],
            jours_ouverts_cible=22,
            valeur_manuelle=15000,
        )
        self.assertEqual(estimation, 15000.0)

    def test_historique_inexploitable_est_refuse(self):
        with self.assertRaises(ValueError):
            afas.EstimerPeriode(
                methode=afas.METHODE_N1_AJUSTE,
                historique=[{"heures": 12000, "jours_ouverts": 0}],
                jours_ouverts_cible=20,
            )

    def test_actualisation_additionne_realise_et_restant(self):
        resultat = afas.CalculerActualisation(18430, 21200)
        self.assertEqual(resultat["total_actualise"], 39630.0)


if __name__ == "__main__":
    unittest.main()
