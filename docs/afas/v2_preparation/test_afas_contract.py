import unittest
from afas_contract import *

class TestAFAS(unittest.TestCase):
    def setUp(self):
        # IDs volontairement fictifs et explicites : AUCUN lien a la base PMSL.
        self.catalog = {}
        n = 100
        for key, labels in MATRIX.items():
            rows = {}
            for label in labels:
                n += 1
                rows[label] = {'IDactivite': 1 if key[0] == ALSH else 2, 'IDgroupe': n}
            self.catalog[key] = rows
        self.profile = dict(profile_id='fixture-01', activity=ALSH, mode=PERI,
                            selected_sites=['Bais +6 ans', 'Bais -6 ans'], included_units=[1],
                            excluded_units=[2], garderie_units=[3], admissible_states=['Présent'],
                            rules={'qualified': True}, config_version=1)

    def test_four_exact_combinations(self):
        self.assertEqual([len(options_for(*key)) for key in MATRIX], [4,6,1,2])
    def test_no_generic_bais(self):
        self.assertFalse(any('Bais' == x for sites in MATRIX.values() for x in sites))
    def test_ados_exact_label(self):
        self.assertEqual(MATRIX[(ADOS,PERI)], ('Bais Club Ados',))
    def test_no_minicamp_peri(self):
        self.assertTrue(all('Minicamps' not in x for mode in (ALSH, ADOS) for x in MATRIX[(mode,PERI)]))
    def test_incompatible_removed(self):
        self.assertEqual(change_context(['Bais +6 ans','Minicamps 6/8'],ALSH,PERI), ['Bais +6 ans'])
    def test_cross_activity_removed(self):
        self.assertEqual(change_context(['Bais Club Ados'],ALSH,EXTRA), [])
    def test_roundtrip(self):
        self.assertEqual(self.profile,load_profile(save_profile(self.profile)))
    def test_duplicate(self):
        self.assertEqual(duplicate_profile(self.profile,'fixture-02')['profile_id'],'fixture-02')
    def test_ids_resolved(self):
        self.assertEqual(len(resolve_pairs(ALSH, PERI, self.profile['selected_sites'], self.catalog)),2)
    def test_no_duplicate_selection(self):
        with self.assertRaises(ConfigurationError): resolve_pairs(ALSH, PERI, ['Moutiers','Moutiers'],self.catalog)
    def test_missing_ids_fails(self):
        self.catalog[(ALSH, PERI)]['Moutiers'] = {'IDactivite':None,'IDgroupe':None}
        with self.assertRaises(ConfigurationError): resolve_pairs(ALSH,PERI,['Moutiers'],self.catalog)
    def test_unit_categories_disjoint(self):
        self.assertTrue(validate_units([1],[2],[3],['Présent'],{'qualified':True}))
        with self.assertRaises(ConfigurationError): validate_units([1,2],[2],[3],['Présent'],{'qualified':True})
    def test_no_rule_blocks(self):
        with self.assertRaises(ConfigurationError): validate_units([1],[2],[3],['Présent'],{'qualified':False})
    def test_no_states_blocks(self):
        with self.assertRaises(ConfigurationError): validate_units([1],[2],[3],[],{'qualified':True})
    def test_stale_selection_rejected(self):
        self.profile['selected_sites']=['Minicamps Ados']
        with self.assertRaises(ConfigurationError): load_profile(save_profile(self.profile))

if __name__ == '__main__': unittest.main()
