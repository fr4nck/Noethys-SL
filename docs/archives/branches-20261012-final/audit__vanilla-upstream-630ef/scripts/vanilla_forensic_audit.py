#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventaire statique conservateur de l'upstream Vanilla figé.

Ce script n'édite jamais ``noethys/``. Il produit uniquement une file de revue :
chaque signal doit être reproduit ou prouvé avant d'être qualifié comme bug.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "noethys"
MUTATORS = {
    "append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse",
    "update", "setdefault", "add", "discard", "difference_update",
    "intersection_update", "symmetric_difference_update",
}
UI_PREFIXES = ("On", "Timer", "Handle", "Refresh", "MAJ")


def rel(path):
    return str(path.relative_to(SOURCE)).replace("\\", "/")


def qualified_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def mutable_defaults(fn):
    positional = list(fn.args.posonlyargs) + list(fn.args.args)
    defaults = [None] * (len(positional) - len(fn.args.defaults)) + list(fn.args.defaults)
    pairs = list(zip(positional, defaults)) + list(zip(fn.args.kwonlyargs, fn.args.kw_defaults))
    for arg, default in pairs:
        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
            yield arg.arg, type(default).__name__.lower()


def mutated_in(fn, name):
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == name and node.func.attr in MUTATORS:
                return node.lineno, node.func.attr
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == name:
                    return node.lineno, "item_mutation"
    return None


def self_calls(fn, method):
    output = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != method:
            continue
        owner = node.func.value
        if isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name) and owner.value.id == "self":
            output.append((owner.attr, node.lineno))
    return output


def modal_names(fn):
    output = {}
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        callee = qualified_name(node.value.func)
        if "Dialog" in callee or "MessageDialog" in callee or "TextEntryDialog" in callee or "ChoiceDialog" in callee:
            output[node.targets[0].id] = node.lineno
    return output


def calls_on(fn, name, method):
    result = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == method and isinstance(node.func.value, ast.Name) and node.func.value.id == name:
                result.append(node.lineno)
    return result


def scan_ast(path, findings):
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return
    file = rel(path)

    for fn in (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        for name, default_type in mutable_defaults(fn):
            mutation = mutated_in(fn, name)
            if mutation:
                findings.append({
                    "kind": "mutable_default_mutated",
                    "priority": "review",
                    "file": file,
                    "function": fn.name,
                    "line": mutation[0],
                    "detail": {"parameter": name, "default": default_type, "operation": mutation[1]},
                })

        validations = self_calls(fn, "Validation")
        saves = self_calls(fn, "Sauvegarde")
        if validations and saves:
            save_names = {name for name, _ in saves}
            for name, line in validations:
                if name not in save_names:
                    findings.append({
                        "kind": "validation_save_asymmetry",
                        "priority": "review",
                        "file": file,
                        "function": fn.name,
                        "line": line,
                        "detail": {"control": name, "saved_siblings": sorted(save_names)},
                    })

        for name, created in modal_names(fn).items():
            shown = calls_on(fn, name, "ShowModal")
            destroyed = calls_on(fn, name, "Destroy")
            if shown and not destroyed:
                findings.append({
                    "kind": "modal_without_destroy",
                    "priority": "review",
                    "file": file,
                    "function": fn.name,
                    "line": shown[0],
                    "detail": {"dialog": name, "created": created},
                })

        if fn.name.startswith(UI_PREFIXES):
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and qualified_name(node.func) in {"time.sleep", "sleep"}:
                    findings.append({
                        "kind": "blocking_sleep_ui",
                        "priority": "review",
                        "file": file,
                        "function": fn.name,
                        "line": node.lineno,
                        "detail": qualified_name(node.func),
                    })


def scan_text(path, findings):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    file = rel(path)
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r"\.ResultatReq\s*\(\s*\)\s*\[\s*0\s*\]", line):
            findings.append({"kind": "resultatreq_direct_index", "priority": "review", "file": file, "line": number, "detail": stripped})
        if re.search(r"\b(?:UPDATE|DELETE\s+FROM)\b", line, re.I) and ("WHERE" not in line.upper()):
            findings.append({"kind": "sql_mutation_to_review", "priority": "review", "file": file, "line": number, "detail": stripped})
        if re.search(r"\bID\w*\s*>\s*0\b", line, re.I):
            findings.append({"kind": "broad_id_condition", "priority": "review", "file": file, "line": number, "detail": stripped})


def build_report():
    findings = []
    for path in SOURCE.rglob("*.py"):
        scan_ast(path, findings)
        scan_text(path, findings)
    findings.sort(key=lambda item: (item["kind"], item["file"], item["line"]))
    return {
        "count": len(findings),
        "kinds": dict(Counter(item["kind"] for item in findings)),
        "findings": findings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", default="")
    args = parser.parse_args(argv)
    report = build_report()
    print(f"VANILLA_FORENSIC={report['count']} {report['kinds']}")
    if args.json:
        output = Path(args.json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
