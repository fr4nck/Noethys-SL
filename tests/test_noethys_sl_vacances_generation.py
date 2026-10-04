#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "noethys" / "Utils" / "UTILS_VacancesGeneration.py"
DLG_LOT = ROOT / "noethys" / "Dlg" / "DLG_Saisie_lot_ouvertures2.py"
DLG_OUVERTURES = ROOT / "noethys" / "Dlg" / "DLG_Ouvertures.py"

spec = importlib.util.spec_from_file_location("UTILS_VacancesGeneration", str(MODULE_PATH))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestVacancesGeneration(unittest.TestCase):

    def setUp(self):
        self.vacances = [
            ("2026-10-17", "2026-11-01", "Toussaint", "2026"),
        ]

    def test_samedi_de_depart_reste_scolaire(self):
        self.assertFalse(
            module.EstEnVacancesGeneration(datetime.date(2026, 10, 17), self.vacances)
        )

    def test_dimanche_suivant_commence_les_vacances(self):
        self.assertTrue(
            module.EstEnVacancesGeneration(datetime.date(2026, 10, 18), self.vacances)
        )

    def test_samedi_intermediaire_est_en_vacances(self):
        self.assertTrue(
            module.EstEnVacancesGeneration(datetime.date(2026, 10, 24), self.vacances)
        )

    def test_dernier_samedi_est_en_vacances(self):
        self.assertTrue(
            module.EstEnVacancesGeneration(datetime.date(2026, 10, 31), self.vacances)
        )

    def test_dimanche_fin_est_en_vacances(self):
        self.assertTrue(
            module.EstEnVacancesGeneration(datetime.date(2026, 11, 1), self.vacances)
        )

    def test_lundi_reprise_est_scolaire(self):
        self.assertFalse(
            module.EstEnVacancesGeneration(datetime.date(2026, 11, 2), self.vacances)
        )

    def test_si_le_debut_est_deja_un_dimanche_il_est_conserve(self):
        self.assertEqual(
            module.GetDebutVacancesGeneration(datetime.date(2026, 10, 18)),
            datetime.date(2026, 10, 18),
        )

    def test_aucune_option_specifique_n_est_affichee(self):
        source = DLG_LOT.read_text(encoding="utf-8")
        self.assertNotIn("Vacances sportives", source)
        self.assertNotIn("ctrl_vacances_dimanche", source)
        self.assertNotIn("vacances_dimanche_dimanche", source)

    def test_traitement_par_lot_applique_la_convention_systematiquement(self):
        source = DLG_OUVERTURES.read_text(encoding="utf-8")
        self.assertIn("UTILS_VacancesGeneration.EstEnVacancesGeneration(", source)
        self.assertNotIn("UTILS_VacancesSportives", source)
        self.assertNotIn("vacances_dimanche_dimanche", source)


if __name__ == "__main__":
    unittest.main()
