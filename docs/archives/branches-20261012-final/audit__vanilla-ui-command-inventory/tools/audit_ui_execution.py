#!/usr/bin/env python3
"""Preuves d'execution controlees pour l'audit des commandes wxPython.

Ce module n'importe pas Noethys et n'instancie pas wx. Il n'execute qu'une
forme volontairement etroite de handlers originaux: delegation simple vers une
action attendue (Ajouter/Modifier/..., impression/export, rafraichissement) ou
fermeture modale/native. Toute branche, boucle, acces externe ou expression
complexe est refusee et reste a qualifier par une vraie recette GUI.
"""
from __future__ import annotations

import ast
import copy
import re
import unicodedata
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


FAMILY_KEYWORDS = {
    "add": ("ajouter", "nouveau", "nouvelle", "creer", "creation", "insérer", "inserer"),
    "modify": ("modifier", "editer", "edition"),
    "delete": ("supprimer", "effacer", "retirer", "detacher", "vider"),
    "validate": ("valider", "ok", "enregistrer", "appliquer"),
    "cancel": ("annuler", "cancel"),
    "close": ("fermer", "close", "quitter"),
    "search": ("rechercher", "recherche", "chercher"),
    "filter": ("filtrer", "filtre"),
    "refresh": ("rafraichir", "actualiser", "mise a jour", "maj"),
    "open": ("ouvrir", "visualiser", "afficher"),
    "print": ("imprimer", "impression"),
    "preview": ("apercu", "preview"),
    "export": ("exporter", "export"),
    "check": ("cocher", "decocher"),
}

METHOD_FAMILIES = {
    "Ajouter": "add", "Add": "add", "Nouveau": "add", "Creer": "add",
    "Modifier": "modify", "Editer": "modify", "Edit": "modify",
    "Supprimer": "delete", "Effacer": "delete", "Delete": "delete", "Retirer": "delete",
    "Valider": "validate", "Enregistrer": "validate", "Appliquer": "validate",
    "Annuler": "cancel", "Cancel": "cancel",
    "Fermer": "close", "Close": "close", "Destroy": "close",
    "Rechercher": "search", "Recherche": "search",
    "Filtrer": "filter", "Filtre": "filter",
    "MAJ": "refresh", "Maj": "refresh", "Refresh": "refresh", "Actualiser": "refresh",
    "Ouvrir": "open", "Open": "open", "Visualiser": "open",
    "Imprimer": "print", "Print": "print",
    "Apercu": "preview", "Preview": "preview",
    "Exporter": "export", "Export": "export", "ExportExcel": "export", "ExportTexte": "export",
    "Cocher": "check", "ToutCocher": "check", "ToutDecocher": "check", "CheckAll": "check",
}

WX_CONSTANT_VALUES = {
    "ID_OK": 5100,
    "ID_CANCEL": 5101,
    "ID_CLOSE": 5102,
    "ID_EXIT": 5103,
    "ID_YES": 5104,
    "ID_NO": 5105,
}


@dataclass(frozen=True)
class CallRecord:
    path: str
    args: Tuple[object, ...]
    kwargs: Tuple[Tuple[str, object], ...]


@dataclass(frozen=True)
class ExecutionProof:
    ok: bool
    family: str = ""
    action: str = ""
    calls: Tuple[CallRecord, ...] = ()
    detail: str = ""


class _Value:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"<{self.name}>"


class _Probe:
    def __init__(self, path: str, calls: List[CallRecord]) -> None:
        self._path = path
        self._calls = calls

    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Probe(f"{self._path}.{name}", self._calls)

    def __call__(self, *args, **kwargs):
        self._calls.append(CallRecord(self._path, tuple(args), tuple(sorted(kwargs.items()))))
        return _Value(self._path)


class _EventProbe(_Probe):
    pass


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("_", " ")
    return re.sub(r"\s+", " ", value).strip()


def infer_family(*texts: str) -> str:
    text = " ".join(normalize(x) for x in texts if x)
    for family, words in FAMILY_KEYWORDS.items():
        if any(normalize(word) in text for word in words):
            return family
    return ""


def _method_family(method_name: str) -> str:
    plain = normalize(method_name).replace(" ", "")
    for name, family in METHOD_FAMILIES.items():
        normalized = normalize(name).replace(" ", "")
        if plain == normalized or plain.startswith(normalized) or plain.endswith(normalized):
            return family
    return ""


def _strip_docstring(body: Sequence[ast.stmt]) -> List[ast.stmt]:
    items = list(body)
    if items and isinstance(items[0], ast.Expr) and isinstance(items[0].value, ast.Constant) and isinstance(items[0].value.value, str):
        items = items[1:]
    return items


def _call_from_stmt(stmt: ast.stmt) -> Optional[ast.Call]:
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return stmt.value
    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
        return stmt.value
    return None


def _attribute_path(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _attribute_path(node.value)
        if base:
            return f"{base}.{node.attr}"
    return None


def _safe_arg(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.Attribute):
        return _attribute_path(node) is not None
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(_safe_arg(x) for x in node.elts)
    return False


def _safe_call(call: ast.Call) -> Optional[str]:
    path = _attribute_path(call.func)
    if not path:
        return None
    if not (path.startswith("self.") or path.startswith("event.")):
        return None
    if any(not _safe_arg(arg) for arg in call.args):
        return None
    if any(kw.arg is None or not _safe_arg(kw.value) for kw in call.keywords):
        return None
    return path


def _execution_shape(node: ast.FunctionDef) -> Optional[List[Tuple[ast.Call, str]]]:
    body = _strip_docstring(node.body)
    if not body or len(body) > 2:
        return None
    result: List[Tuple[ast.Call, str]] = []
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        call = _call_from_stmt(stmt)
        if call is None:
            return None
        path = _safe_call(call)
        if path is None:
            return None
        result.append((call, path))
    action_calls = [(call, path) for call, path in result if path != "event.Skip"]
    if len(action_calls) != 1:
        return None
    return result


def _family_for_action(path: str, call: ast.Call) -> str:
    method = path.rsplit(".", 1)[-1]
    if method == "EndModal":
        if call.args:
            arg = _attribute_path(call.args[0])
            if arg == "wx.ID_CANCEL":
                return "cancel"
            if arg in {"wx.ID_OK", "wx.ID_YES"}:
                return "validate"
        return "close"
    return _method_family(method)


def _compatible(expected: str, actual: str, path: str) -> bool:
    if not expected or not actual:
        return False
    if expected == actual:
        return True
    if expected == "close" and path.endswith(".EndModal") and actual in {"validate", "cancel"}:
        return True
    if expected == "cancel" and actual == "close" and path.endswith((".Close", ".Destroy")):
        return True
    return False


def _namespace_for(node: ast.FunctionDef):
    calls: List[CallRecord] = []
    globals_ns: Dict[str, object] = {"wx": SimpleNamespace(**WX_CONSTANT_VALUES)}
    globals_ns["self"] = _Probe("self", calls)
    globals_ns["event"] = _EventProbe("event", calls)
    for name in {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}:
        if name not in globals_ns and name not in {arg.arg for arg in node.args.args}:
            globals_ns[name] = _Value(name)
    return globals_ns, calls


def execute_handler(node: ast.FunctionDef, command_label: str = "", command_source: str = "", handler_ref: str = "") -> ExecutionProof:
    """Execute le handler original seulement s'il appartient au sous-ensemble sur."""
    shape = _execution_shape(node)
    if shape is None:
        return ExecutionProof(False, detail="handler hors sous-ensemble d'execution controlee")

    action_call, action_path = next((item for item in shape if item[1] != "event.Skip"), (None, ""))
    if action_call is None:
        return ExecutionProof(False, detail="aucune action observable")

    expected = infer_family(command_label, command_source, handler_ref)
    actual = _family_for_action(action_path, action_call)
    if not _compatible(expected, actual, action_path):
        return ExecutionProof(False, detail=f"action {action_path} non compatible avec famille {expected or 'inconnue'}")

    module_node = ast.Module(body=[copy.deepcopy(node)], type_ignores=[])
    fn = module_node.body[0]
    assert isinstance(fn, ast.FunctionDef)
    fn.decorator_list = []
    ast.fix_missing_locations(module_node)
    globals_ns, calls = _namespace_for(node)
    try:
        exec(compile(module_node, filename="<noethys-audit-handler>", mode="exec"), globals_ns)
        function = globals_ns[node.name]
        args = []
        for arg in node.args.args:
            if arg.arg == "self":
                args.append(globals_ns["self"])
            elif arg.arg in {"event", "evt"}:
                args.append(globals_ns["event"])
            else:
                args.append(_Value(arg.arg))
        function(*args)
    except Exception as exc:
        return ExecutionProof(False, expected, action_path, tuple(calls), f"execution refusee/echouee: {type(exc).__name__}: {exc}")

    action_records = tuple(record for record in calls if record.path != "event.Skip")
    if len(action_records) != 1 or action_records[0].path != action_path:
        return ExecutionProof(False, expected, action_path, tuple(calls), "trace d'appel inattendue")
    return ExecutionProof(True, expected, action_path, tuple(calls), f"corps original execute; appel observe: {action_records[0].path}")
