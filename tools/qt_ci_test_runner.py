"""CI Qt : lancer l'intégralité des tests sur trois shards déterministes.

Un fichier de tests reste dans un seul processus (setUpModule, setUpClass
et état QApplication préservés). Toutes les données sont fictives ; aucun
accès à une configuration, une sauvegarde ou une base Noethys réelle.
Les durées proviennent des résultats CI C14-C18 du 28/10/2026.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import unittest
from collections import Counter
from pathlib import Path

SHARD_COUNT = 3
# Garde anti-perte de tests : CI C14 validée à 328 tests le 28 octobre 2026.
MINIMUM_TOTAL_TESTS = 439

# Rééquilibrage selon le run C18 40701384201 : shard 2 prenait 929 s ;
# déplacer les suites C15 et C18 sans retirer aucun test ni modifier leur ordre interne.
# Pour tout fichier nouveau, affectation stable par hachage, jamais ignoré.
HOT_MODULE_SHARDS = {
    "test_native_c12_shell_routes": 0,
    "test_consumptions_c10_business_details": 0,
    "test_finance_c13_readonly": 1,
    "test_consumptions_c11_exact_context": 1,
    "test_people_search": 1,
    "test_catalog_c14_readonly": 2,
    "test_modules_c15_readonly": 1,
    "test_modules_c16_readonly": 0,
    "test_c17_shared_activity_overview": 1,
    "test_c18_schools_products_documents": 0,
    "test_consumptions_c8_demo": 2,
    "test_consumptions_c9_navigation": 2,
}


def shard_for_module(module: str, shard_count: int = SHARD_COUNT) -> int:
    if shard_count != SHARD_COUNT:
        raise ValueError("Nombre de shards CI non qualifié")
    if not isinstance(module, str) or not module.startswith("test_"):
        raise ValueError("Nom de module de test non qualifié")
    if module in HOT_MODULE_SHARDS:
        return HOT_MODULE_SHARDS[module]
    digest = hashlib.sha256(module.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % shard_count


def iter_test_cases(suite):
    """Aplatir sans altérer l'ordre ou les classes des tests unittest."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_test_cases(item)
        else:
            yield item


def test_module(test: unittest.TestCase) -> str:
    module = test.__class__.__module__.rsplit(".", 1)[-1]
    if module.startswith("test_"):
        return module
    # unittest.loader._FailedTest : importer le module en erreur doit faire
    # échouer son shard, jamais disparaître de la découverte.
    failed_module = test.id().rsplit(".", 1)[-1]
    if failed_module.startswith("test_"):
        return failed_module
    raise RuntimeError("Test découvert sans module test_* : " + test.id())


def partition_cases(cases, shard_count=SHARD_COUNT):
    if shard_count != SHARD_COUNT:
        raise ValueError("Le nombre de shards doit être 3")
    groups = [[] for _ in range(shard_count)]
    seen = set()
    for case in cases:
        test_id = case.id()
        if test_id in seen:
            raise RuntimeError("Test découvert deux fois : " + test_id)
        seen.add(test_id)
        groups[shard_for_module(test_module(case), shard_count)].append(case)
    if len(seen) < MINIMUM_TOTAL_TESTS:
        raise RuntimeError(
            f"Couverture Qt réduite : {len(seen)} tests, "
            f"minimum qualifié {MINIMUM_TOTAL_TESTS}"
        )
    if any(not group for group in groups):
        raise RuntimeError("Un shard de tests Qt est vide")
    return tuple(tuple(group) for group in groups)


class TimedTestResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self._starts = {}
        self.timings = []

    def startTest(self, test):
        self._starts[id(test)] = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        started = self._starts.pop(id(test), time.perf_counter())
        elapsed = max(0.0, time.perf_counter() - started)
        self.timings.append((test.id(), elapsed))
        super().stopTest(test)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tests Noethys Qt shardés, 100 % fictifs")
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--shards", type=int, default=SHARD_COUNT)
    args = parser.parse_args(argv)
    if args.shards != SHARD_COUNT or not 0 <= args.shard < SHARD_COUNT:
        parser.error("Shard Qt invalide : 0, 1, 2 pour trois shards")

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests_qt", pattern="test_*.py")
    groups = partition_cases(tuple(iter_test_cases(suite)), args.shards)
    counts = [len(group) for group in groups]
    print(
        f"QT_CI_SHARD_PLAN total={sum(counts)} groups={counts} "
        f"active={args.shard} module_isolation=true",
        flush=True,
    )

    start = time.perf_counter()
    result = unittest.TextTestRunner(
        verbosity=2, resultclass=TimedTestResult
    ).run(unittest.TestSuite(groups[args.shard]))
    duration = time.perf_counter() - start
    passed = result.wasSuccessful() and result.testsRun == counts[args.shard]
    marker = "PASS" if passed else "FAIL"
    print(
        f"QT_CI_SHARD_{marker} shard={args.shard} "
        f"tests={result.testsRun} expected={counts[args.shard]} "
        f"seconds={duration:.2f} errors={len(result.errors)} "
        f"failures={len(result.failures)}",
        flush=True,
    )

    slowest = sorted(result.timings, key=lambda item: item[1], reverse=True)[:10]
    print("QT_CI_SLOWEST_TESTS (suites intégrales conservées)", flush=True)
    for name, elapsed in slowest:
        print(f"  {elapsed:.2f}s {name}", flush=True)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as stream:
            stream.write(
                f"### Qt — shard {args.shard + 1}/{SHARD_COUNT}: {marker}\n\n"
                f"Tests : {result.testsRun}/{counts[args.shard]} "
                f"— durée : {duration:.1f} s — "
                f"erreurs : {len(result.errors)} — "
                f"échecs : {len(result.failures)}\n\n"
            )
            stream.write("| Durée (s) | Test le plus lent |\n|---:|---|\n")
            for name, elapsed in slowest[:5]:
                stream.write(f"| {elapsed:.2f} | \`{name}\` |\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
