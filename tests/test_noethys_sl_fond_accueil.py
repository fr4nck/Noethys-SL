#!/usr/bin/env python
# -*- coding: utf-8 -*-

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "noethys" / "Utils" / "UTILS_FondAccueil.py"
CTRL_ACCUEIL = ROOT / "noethys" / "Ctrl" / "CTRL_Accueil.py"
DLG_PREFERENCES = ROOT / "noethys" / "Dlg" / "DLG_Preferences.py"

spec = importlib.util.spec_from_file_location("UTILS_FondAccueil", str(MODULE_PATH))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestFondAccueil(unittest.TestCase):

    def test_remplir_un_ecran_2k_conserve_le_ratio_et_recadre(self):
        self.assertEqual(
            module.CalculerPlacementFond(1024, 768, 2560, 1440, "remplir"),
            (0, -240, 2560, 1920),
        )

    def test_adapter_un_ecran_2k_conserve_toute_image(self):
        self.assertEqual(
            module.CalculerPlacementFond(1024, 768, 2560, 1440, "adapter"),
            (320, 0, 1920, 1440),
        )

    def test_etirer_utilise_exactement_la_zone(self):
        self.assertEqual(
            module.CalculerPlacementFond(1024, 768, 2560, 1440, "etirer"),
            (0, 0, 2560, 1440),
        )

    def test_original_conserve_la_taille_native(self):
        self.assertEqual(
            module.CalculerPlacementFond(1024, 768, 2560, 1440, "original"),
            (0, 0, 1024, 768),
        )

    def test_mode_invalide_retombe_sur_remplir(self):
        self.assertEqual(
            module.CalculerPlacementFond(1024, 768, 2560, 1440, "inconnu"),
            module.CalculerPlacementFond(1024, 768, 2560, 1440, "remplir"),
        )

    def test_dimensions_invalides_ne_declenchent_pas_de_redimensionnement(self):
        self.assertEqual(
            module.CalculerPlacementFond(0, 768, 2560, 1440, "remplir"),
            (0, 0, 0, 0),
        )

    def test_accueil_utilise_le_moteur_adaptatif_et_un_cache(self):
        source = CTRL_ACCUEIL.read_text(encoding="utf-8")
        self.assertIn("UTILS_FondAccueil.CalculerPlacementFond", source)
        self.assertIn("wx.IMAGE_QUALITY_HIGH", source)
        self.assertIn("_bitmap_fond_cache", source)
        self.assertIn("fond_accueil_mode", source)
        self.assertIn("fond_accueil_attenuation", source)
        self.assertNotIn("dc.DrawBitmap(self.image_fond, 0, 0)", source)

    def test_preferences_exposent_les_quatre_modes_et_attenuation(self):
        source = DLG_PREFERENCES.read_text(encoding="utf-8")
        for code in ("remplir", "adapter", "etirer", "original"):
            self.assertIn('"%s"' % code, source)
        self.assertIn("fond_accueil_mode", source)
        self.assertIn("fond_accueil_attenuation", source)
        self.assertIn("Atténuation du fond", source)


if __name__ == "__main__":
    unittest.main()
