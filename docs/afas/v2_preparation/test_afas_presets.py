import copy
import unittest
from afas_presets import (PresetError, validate_preset, serialize_preset,
                          deserialize_preset, duplicate_preset, calculation_request, PHASES)

def fixture():
    return {"profile_id":"alsh-peri","name":"ALSH Bais periscolaire",
            "activity":"ALSH","mode":"Périscolaire",
            "sites":["Bais +6 ans","Bais -6 ans"],"included_units":[1],
            "excluded_units":[2],"garderie_units":[3],
            "realised_states":["Présent"],"caf_billed_states":["Présent"],
            "period_criteria":{"school_days":True,"vacations":False},
            "rules":{"qualified":False},"version":1}

class Tests(unittest.TestCase):
    def test_serialisation(self):
        self.assertEqual(deserialize_preset(serialize_preset(fixture())),fixture())
    def test_year_forbidden(self):
        p=fixture();p["annee"]=2026
        with self.assertRaises(PresetError): validate_preset(p)
    def test_phase_forbidden(self):
        p=fixture();p["phase"]="reel"
        with self.assertRaises(PresetError): validate_preset(p)
    def test_date_forbidden(self):
        p=fixture();p["date_debut"]="2026-01-01"
        with self.assertRaises(PresetError): validate_preset(p)
    def test_each_phase_same_preset(self):
        p=fixture()
        for phase in PHASES:
            with self.subTest(phase=phase):
                self.assertEqual(calculation_request(p,2026,phase)["preset_snapshot"],p)
    def test_year_reuse_unchanged(self):
        p=fixture()
        for year in (2024,2025,2026,2027):
            self.assertEqual(calculation_request(p,year,"reel")["preset_snapshot"],p)
        self.assertEqual(p,fixture())
    def test_report_trace_includes_execution(self):
        r=calculation_request(fixture(),2026,"actualisation_septembre",now="fixture-time")
        self.assertEqual((r["year"],r["phase"],r["created_at"]),
                         (2026,"actualisation_septembre","fixture-time"))
    def test_snapshot_immutable_against_edit(self):
        p=fixture();r=calculation_request(p,2026,"reel")
        p["sites"].append("Moutiers")
        self.assertEqual(len(r["preset_snapshot"]["sites"]),2)
    def test_duplicate_stable_separate_id(self):
        p=duplicate_preset(fixture(),"copy-1","Copie")
        self.assertEqual((p["profile_id"],p["version"]),("copy-1",1))
    def test_overlap_units_rejected(self):
        p=fixture();p["garderie_units"]=[1]
        with self.assertRaises(PresetError): validate_preset(p)
    def test_duplicate_sites_rejected(self):
        p=fixture();p["sites"].append("Bais +6 ans")
        with self.assertRaises(PresetError): validate_preset(p)
    def test_unknown_state_rejected(self):
        p=fixture();p["caf_billed_states"]=["Refusé"]
        with self.assertRaises(PresetError): validate_preset(p)
    def test_separate_state_lists(self):
        p=fixture();p["caf_billed_states"]=["Absence justifiée"]
        self.assertEqual(validate_preset(p)["realised_states"],["Présent"])
    def test_invalid_year_rejected(self):
        with self.assertRaises(PresetError): calculation_request(fixture(),"2026","reel")
    def test_invalid_phase_rejected(self):
        with self.assertRaises(PresetError): calculation_request(fixture(),2026,"octobre")
    def test_corrupted_profile_rejected(self):
        with self.assertRaises(PresetError): deserialize_preset('{"profile_id":')
    def test_missing_rule_rejected(self):
        p=fixture();del p["period_criteria"]
        with self.assertRaises(PresetError): validate_preset(p)

if __name__=="__main__": unittest.main()
