"""Liste les imports ReportLab du code qui ne se résolvent pas avec la version installée.

Usage : python3 -I imports_reportlab.py <dossier noethys/>"""
import ast, importlib, sys, pathlib
root = pathlib.Path(sys.argv[1])
manquants, total = [], 0
for p in sorted(root.rglob("*.py")):
    try: tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError: continue
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] == "reportlab":
            try: mod = importlib.import_module(n.module)
            except Exception as e:
                manquants.append((str(p.relative_to(root)), n.lineno, n.module, "MODULE: %s" % e)); continue
            for a in n.names:
                total += 1
                if a.name != "*" and not hasattr(mod, a.name):
                    try: importlib.import_module(n.module + "." + a.name)
                    except Exception: manquants.append((str(p.relative_to(root)), n.lineno, n.module, a.name))
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] == "reportlab":
                    total += 1
                    try: importlib.import_module(a.name)
                    except Exception as e: manquants.append((str(p.relative_to(root)), n.lineno, a.name, "MODULE"))
import reportlab
print("reportlab", reportlab.Version, "-", total, "imports analysés,", len(manquants), "introuvables")
for m in manquants: print("  ", m)
