#!/usr/bin/env python3
"""Run unittest discovery on two revisions and retain failure identities/causes.

Each run writes its real result, including existing failures. The comparison
fails for a new failure or a changed exception type/message on a shared test.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import traceback
import unittest


def run(root, output):
    root = Path(root).resolve()
    os.chdir(root)
    sys.path[:0] = [str(root / 'tests'), str(root), str(root / 'noethys')]

    class Result(unittest.TextTestResult):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.problems = []

        def record(self, test, err, kind):
            typ, value, tb = err
            self.problems.append({
                'test': test.id(), 'kind': kind,
                'exception': typ.__module__ + '.' + typ.__name__,
                'message': str(value).replace(str(root), '<REPO>'),
                'traceback': ''.join(traceback.format_exception(typ, value, tb)).replace(str(root), '<REPO>'),
            })

        def addFailure(self, test, err):
            self.record(test, err, 'failure')
            super().addFailure(test, err)

        def addError(self, test, err):
            self.record(test, err, 'error')
            super().addError(test, err)

        def addSubTest(self, test, subtest, err):
            if err is not None:
                self.record(subtest, err, 'failure' if issubclass(err[0], test.failureException) else 'error')
            super().addSubTest(test, subtest, err)

    suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    import wx
    data = {
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'python': platform.python_version(), 'wx': wx.version(),
        'platform': platform.platform(), 'tests_run': result.testsRun,
        'successful': result.wasSuccessful(), 'problems': result.problems,
        'skipped': [{'test': t.id(), 'reason': reason} for t, reason in result.skipped],
        'expected_failures': [t.id() for t, _ in result.expectedFailures],
        'unexpected_successes': [t.id() for t in result.unexpectedSuccesses],
    }
    Path(output).resolve().write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # The comparison, rather than suppression of individual failures, decides
    # whether the second revision introduced a regression.


def compare(before, after, output):
    baseline = json.loads(Path(before).read_text(encoding='utf-8'))
    current = json.loads(Path(after).read_text(encoding='utf-8'))
    old = {p['test']: p for p in baseline['problems']}
    new = {p['test']: p for p in current['problems']}
    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    changed = sorted(t for t in new.keys() & old.keys()
                     if any(old[t][k] != new[t][k] for k in ('kind', 'exception', 'message')))
    unexpected = sorted(set(current['unexpected_successes']) - set(baseline['unexpected_successes']))
    data = {
        'baseline_commit': baseline['commit'], 'head_commit': current['commit'],
        'baseline_tests': baseline['tests_run'], 'head_tests': current['tests_run'],
        'baseline_problems': len(old), 'head_problems': len(new),
        'new_failures': added, 'fixed_failures': removed,
        'changed_causes': changed, 'new_unexpected_successes': unexpected,
        'unchanged_failures': sorted(new.keys() & old.keys() - set(changed)),
    }
    Path(output).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if current['tests_run'] < baseline['tests_run'] or not baseline['tests_run']:
        raise SystemExit('Test discovery incomplete: inspect both logs.')
    raise SystemExit(bool(added or changed or unexpected))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    execution = sub.add_parser('run')
    execution.add_argument('--root', required=True)
    execution.add_argument('--output', required=True)
    comparison = sub.add_parser('compare')
    comparison.add_argument('--before', required=True)
    comparison.add_argument('--after', required=True)
    comparison.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.action == 'run':
        run(args.root, args.output)
    else:
        compare(args.before, args.after, args.output)
