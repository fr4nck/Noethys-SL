#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run Q442 J3+J4+J5 SQLite-synthetic suites only; no production access."""
import json
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import test_q442_jalon4
from source_j3 import test_q442_jalon3
import test_q442_jalon5

suite=unittest.TestSuite()
for mod in (test_q442_jalon4,test_q442_jalon3,test_q442_jalon5):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(mod))
result=unittest.TextTestRunner(verbosity=1).run(suite)
print(json.dumps({'tests':result.testsRun,'failures':len(result.failures),
                  'errors':len(result.errors),'skipped':len(result.skipped),
                  'scope':'SQLite fictif, aucun GUI wx/MySQL reel',
                  'status':'PASS' if result.wasSuccessful() else 'FAIL'},ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() else 1)
