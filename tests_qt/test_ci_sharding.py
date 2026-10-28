"""Contrat de la CI Qt C14 : sharding exhaustif sans altération des tests."""
from __future__ import annotations

import unittest

from tools.qt_ci_test_runner import (
    HOT_MODULE_SHARDS, MINIMUM_TOTAL_TESTS, SHARD_COUNT,
    iter_test_cases, shard_for_module,
)


class QtCiShardingContractTests(unittest.TestCase):
    def test_three_heavy_modules_have_distinct_shards(self):
        self.assertEqual(SHARD_COUNT, 3)
        self.assertEqual(MINIMUM_TOTAL_TESTS, 439)
        self.assertEqual(shard_for_module("test_native_c12_shell_routes"), 0)
        self.assertEqual(shard_for_module("test_finance_c13_readonly"), 1)
        self.assertEqual(shard_for_module("test_catalog_c14_readonly"), 2)
        self.assertEqual(shard_for_module("test_modules_c15_readonly"), 1)
        self.assertEqual(shard_for_module("test_modules_c16_readonly"), 0)
        self.assertEqual(shard_for_module("test_c17_shared_activity_overview"), 1)
        self.assertEqual(shard_for_module("test_c18_schools_products_documents"), 0)
        self.assertEqual(set(HOT_MODULE_SHARDS.values()), {0, 1, 2})

    def test_future_modules_use_stable_bounded_assignment(self):
        for module in (
            "test_new_consultations",
            "test_new_services",
            "test_next_milestone",
        ):
            bucket = shard_for_module(module)
            self.assertEqual(bucket, shard_for_module(module))
            self.assertIn(bucket, range(SHARD_COUNT))

    def test_rejects_invalid_shards_or_unqualified_modules(self):
        with self.assertRaises(ValueError):
            shard_for_module("test_next_milestone", 2)
        with self.assertRaises(ValueError):
            shard_for_module("noethys_private_data")

    def test_nested_unittest_suite_is_exhaustively_flattened(self):
        class Probe(unittest.TestCase):
            def runTest(self):
                pass
        cases = [Probe(), Probe(), Probe()]
        suite = unittest.TestSuite([
            unittest.TestSuite(cases[:2]), unittest.TestSuite(cases[2:])
        ])
        self.assertEqual(tuple(iter_test_cases(suite)), tuple(cases))


if __name__ == "__main__":
    unittest.main()
