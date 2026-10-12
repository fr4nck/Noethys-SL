from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path("noethys")
findings = []
syntax_errors = []


def add(category, path, line, detail, severity="candidate"):
    findings.append(
        {
            "category": category,
            "path": str(path).replace("\\", "/"),
            "line": int(line or 0),
            "detail": detail,
            "severity": severity,
        }
    )


def call_name(node):
    if not isinstance(node, ast.Call):
        return ""
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        parts = []
        cur = f
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


for path in sorted(ROOT.rglob("*.py")):
    try:
        src = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            src = path.read_text(encoding="latin-1")
        except Exception as exc:
            add("decode-error", path, 0, repr(exc), "confirmed")
            continue

    lines = src.splitlines()
    regexes = [
        ("resultatreq-index0", re.compile(r"ResultatReq\s*\(\s*\)\s*\[\s*0\s*\]")),
        ("legacy-isAlive", re.compile(r"\.isAlive\s*\(")),
        ("py2-dict-view-index", re.compile(r"\.(?:items|keys|values)\s*\(\s*\)\s*\[\s*0\s*\]")),
    ]
    for lineno, line in enumerate(lines, 1):
        for category, rx in regexes:
            if rx.search(line):
                add(category, path, lineno, line.strip())
        if ("time.sleep(" in line or "sleep(" in line) and "def " not in line:
            add("sleep-call", path, lineno, line.strip())
        if ".Rescale(" in line or ".Scale(" in line:
            add(
                "image-rescale-scale",
                path,
                lineno,
                line.strip(),
                "high-candidate" if "/" in line else "candidate",
            )

    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as exc:
        syntax_errors.append(
            {"path": str(path), "line": exc.lineno or 0, "msg": exc.msg}
        )
        continue

    for fn in [
        n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]:
        defaults = list(fn.args.defaults) + [d for d in fn.args.kw_defaults if d is not None]
        for d in defaults:
            if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                add(
                    "mutable-default",
                    path,
                    fn.lineno,
                    f"{fn.name} has mutable default {ast.unparse(d)}",
                )

        nodes = []

        class Collector(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                if node is fn:
                    self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node):
                if node is fn:
                    self.generic_visit(node)

            def visit_Lambda(self, node):
                return

            def visit_ClassDef(self, node):
                return

            def visit_Call(self, node):
                nodes.append(node)
                self.generic_visit(node)

        Collector().visit(fn)

        calls_by_var = {}
        for c in nodes:
            if isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name):
                calls_by_var.setdefault(c.func.value.id, []).append((c.lineno, c.func.attr))

        for stmt in ast.walk(fn):
            value = None
            var = None
            if isinstance(stmt, ast.Assign):
                value = stmt.value
                if len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    var = stmt.targets[0].id
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                value, var = stmt.value, stmt.target.id
            if not var or not isinstance(value, ast.Call):
                continue
            cname = call_name(value)
            if cname in ("GestionDB.DB", "sqlite3.connect", "zipfile.ZipFile"):
                methods = calls_by_var.get(var, [])
                if not any(m in ("Close", "close") for _, m in methods):
                    add(
                        "resource-no-close",
                        path,
                        stmt.lineno,
                        f"{fn.name}: {var} = {cname}(...) has no explicit close in function",
                        "high-candidate",
                    )

        for var, methods in calls_by_var.items():
            if any(m == "ShowModal" for _, m in methods) and not any(
                m == "Destroy" for _, m in methods
            ):
                first = min(l for l, m in methods if m == "ShowModal")
                add(
                    "modal-no-destroy",
                    path,
                    first,
                    f"{fn.name}: {var}.ShowModal() without {var}.Destroy()",
                )

            destroy_lines = [l for l, m in methods if m == "Destroy"]
            if destroy_lines:
                first_destroy = min(destroy_lines)
                later = [
                    (l, m)
                    for l, m in methods
                    if l > first_destroy and m not in ("Destroy",)
                ]
                if later:
                    l, m = min(later)
                    add(
                        "use-after-destroy",
                        path,
                        l,
                        f"{fn.name}: {var}.{m}() after Destroy() at line {first_destroy}",
                        "high-candidate",
                    )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in ("Rescale", "Scale"):
            continue
        for arg in node.args[:2]:
            if any(
                isinstance(x, ast.BinOp) and isinstance(x.op, ast.Div)
                for x in ast.walk(arg)
            ):
                add(
                    "image-float-dimension",
                    path,
                    node.lineno,
                    ast.get_source_segment(src, node) or node.func.attr,
                    "confirmed-pattern",
                )
                break

findings.sort(key=lambda x: (x["category"], x["path"], x["line"]))
counts = {}
for finding in findings:
    counts[finding["category"]] = counts.get(finding["category"], 0) + 1

report = {
    "summary": {
        "python_files": len(list(ROOT.rglob("*.py"))),
        "findings": len(findings),
        "syntax_errors": len(syntax_errors),
        "counts": counts,
    },
    "syntax_errors": syntax_errors,
    "findings": findings,
}
Path("audit_report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)

md = [
    "# Vanilla deep static scan",
    "",
    f"Python files: {report['summary']['python_files']}",
    f"Findings: {len(findings)}",
    f"Syntax errors: {len(syntax_errors)}",
    "",
    "## Counts",
]
for category, count in sorted(counts.items()):
    md.append(f"- {category}: {count}")
if syntax_errors:
    md += ["", "## Syntax errors"]
    for err in syntax_errors:
        md.append(f"- `{err['path']}:{err['line']}` — {err['msg']}")
md += ["", "## Findings"]
for finding in findings:
    md.append(
        f"- **{finding['category']}** [{finding['severity']}] "
        f"`{finding['path']}:{finding['line']}` — {finding['detail']}"
    )
Path("audit_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n".join(md[:160]))
