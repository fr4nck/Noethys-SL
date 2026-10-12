from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "tools" / "windows_ui_recipe"
sys.path.insert(0, str(RECIPE))

from noethys_ui_driver import DriverError, NoethysUiDriver
from recipe_recorder import NonAutomatable, PilotStatus


class RecipeContractTests(unittest.TestCase):
    def test_all_requested_statuses_exist(self):
        self.assertEqual(
            {item.value for item in PilotStatus},
            {"PASS", "FAIL", "TIMEOUT", "CRASH", "NON_AUTOMATISABLE"},
        )

    def test_network_descriptor_is_parsed(self):
        parsed = NoethysUiDriver._parse_network_db("3306;127.0.0.1;recipe;secret[RESEAU]NOETHYS_RECETTE")
        self.assertEqual(parsed["port"], 3306)
        self.assertEqual(parsed["host"], "127.0.0.1")
        self.assertEqual(parsed["database"], "NOETHYS_RECETTE")

    def test_non_network_descriptor_is_rejected(self):
        with self.assertRaises(DriverError):
            NoethysUiDriver._parse_network_db("production.sqlite")

    def test_loopback_guard(self):
        self.assertTrue(NoethysUiDriver._is_loopback("127.0.0.1"))
        self.assertTrue(NoethysUiDriver._is_loopback("::1"))
        self.assertTrue(NoethysUiDriver._is_loopback("localhost"))
        self.assertFalse(NoethysUiDriver._is_loopback("192.0.2.10"))

    def test_non_automatable_is_not_a_failure_alias(self):
        self.assertTrue(issubclass(NonAutomatable, RuntimeError))
        self.assertNotEqual(PilotStatus.NON_AUTOMATISABLE, PilotStatus.FAIL)

    def test_scenario_maps_first_pilot_lot_to_existing_win_recipes(self):
        source = (RECIPE / "scenario_minimal.py").read_text(encoding="utf-8")
        for win in ("WIN-01", "WIN-04", "WIN-06", "WIN-13"):
            self.assertIn(win, source)
        for section in ('"A"', '"B"', '"C"', '"D"', '"E"'):
            self.assertIn(section, source)

    def test_scenario_has_no_fixed_screen_coordinates(self):
        tree = ast.parse((RECIPE / "scenario_minimal.py").read_text(encoding="utf-8"))
        forbidden_calls = {"click", "move", "moveTo"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                self.assertNotIn(name, forbidden_calls)

    def test_profile_helper_targets_real_roaming_noethys_path(self):
        source = (RECIPE / "prepare_profile.ps1").read_text(encoding="utf-8-sig")
        self.assertIn('"Roaming\\noethys"', source)
        self.assertIn("NOETHYS_UI_RECIPE_PROFILE=1", source)

    def test_timer_observation_exceeds_real_maximum_search_delay(self):
        source = (RECIPE / "scenario_minimal.py").read_text(encoding="utf-8")
        self.assertIn("observe_after_destroy(driver, CONSUMPTION_TITLE, 1.25)", source)


if __name__ == "__main__":
    unittest.main()
