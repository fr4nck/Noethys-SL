#!/usr/bin/env python3
"""Second passage automatise de l'audit des commandes wxPython Noethys Vanilla.

Ce module se superpose au scanner du passage 1 sans importer Noethys. Il
corrige les faux positifs de l'inventaire, resout des liaisons wx statiquement
certaines et execute un sous-ensemble volontairement etroit de handlers
originaux dans un bac a sable de sondes inertes.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

try:
    from tools.audit_ui_execution import execute_handler
except ImportError:
    from audit_ui_execution import execute_handler

PASS1 = {
    "PASS": 0,
    "FAIL": 4,
    "BLOCKED": 5497,
    "STATIC_BIND_UNRESOLVED": 2416,
    "HUMAN_RECIPE_REQUIRED": 3076,
    "EMPTY_HANDLER_REVIEW": 4,
    "HANDLER_ON_UNBOUND_STATIC": 628,
}

FRAMEWORK_OVERRIDES = {
    "OnCompareItems", "OnGetItemText", "OnGetItemImage", "OnGetItemAttr",
    "OnGetItemColumnImage", "OnGetItemColumnAttr", "OnPrintPage",
    "OnBeginDocument", "OnEndDocument", "OnBeginPrinting", "OnEndPrinting",
    "OnPreparePrinting", "OnDraw", "OnPaint", "OnEraseBackground",
    "OnMeasureItem", "OnDrawItem",
}

SYNTHETIC_EVENTS = {
    "wx.EVT_CLOSE": ("Fermer (croix fenêtre)", "window_close"),
    "wx.EVT_LIST_ITEM_ACTIVATED": ("Double-clic / activer l'élément", "double_click"),
    "wx.EVT_TREE_ITEM_ACTIVATED": ("Double-clic / activer l'élément", "double_click"),
    "wx.EVT_LEFT_DCLICK": ("Double-clic", "double_click"),
    "wx.EVT_GRID_CELL_LEFT_DCLICK": ("Double-clic cellule", "double_click"),
}

NATIVE_EMPTY = {
    ("noethys/Dlg/DLG_Badgeage_saisie_procedure.py", "CTRL_Interface", "OnChoixIdentification"):
        ("A", "EMPTY_HANDLER_NATIVE_WX", "NOT_TESTABLE", "",
         "Handler vide volontaire : la sélection du wx.RadioButton reste gérée nativement; l'ancien code secondaire est commenté."),
    ("noethys/Dlg/DLG_Updater.py", "Page_installation", "Onbouton_annuler"):
        ("D", "EMPTY_HANDLER_INACCESSIBLE", "NOT_TESTABLE", "",
         "Commande créée mais désactivée par Installation() avant le lancement asynchrone; handler vide inatteignable par clic utilisateur normal."),
}


@dataclass
class BetterBinding:
    path: str
    class_name: str
    function_name: str
    line: int
    source: str
    command_id: str
    event: str
    handler: str
    conditional: bool = False


@dataclass
class FunctionInfo:
    class_name: str
    name: str
    node: ast.FunctionDef
    parent_function: str = ""


@dataclass
class FileMeta:
    path: str
    tree: ast.AST
    classes: Dict[str, List[str]] = field(default_factory=dict)
    functions: Dict[Tuple[str, str], List[FunctionInfo]] = field(default_factory=lambda: defaultdict(list))
    bindings: List[BetterBinding] = field(default_factory=list)
    menu_owners: Set[str] = field(default_factory=set)
    aliases: Dict[Tuple[str, str, str], str] = field(default_factory=dict)
    menuitem_ids: Dict[Tuple[str, int], str] = field(default_factory=dict)
    referenced_handlers: Set[Tuple[str, str]] = field(default_factory=set)


@dataclass
class Pass2Stats:
    filtered_false_commands: int = 0
    rebound_commands: int = 0
    inherited_handlers: int = 0
    automated_execution_proofs: int = 0
    synthetic_event_commands: int = 0
    direct_handler_correlations: int = 0
    framework_overrides_classified: int = 0
    empty_native: int = 0
    empty_inaccessible: int = 0


def expr_text(node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = expr_text(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Constant):
        return repr(node.value) if not isinstance(node.value, str) else node.value
    if isinstance(node, ast.Call):
        if expr_text(node.func) == "getattr" and len(node.args) >= 2:
            owner = expr_text(node.args[0])
            name = node.args[1].value if isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str) else ""
            if owner and name:
                return f"{owner}.{name}"
        return expr_text(node.func)
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def keyword_expr(call: ast.Call, name: str) -> str:
    for kw in call.keywords:
        if kw.arg == name:
            return expr_text(kw.value)
    return ""


def target_text(node: ast.AST) -> str:
    return expr_text(node) if isinstance(node, (ast.Name, ast.Attribute)) else ""


def is_menu_ctor(call: ast.Call) -> bool:
    name = expr_text(call.func)
    short = name.rsplit(".", 1)[-1]
    return short in {"Menu", "MenuBar"} or name.endswith("Adaptations.Menu")


def normalize_id(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("id="):
        value = value[3:].strip()
    return value


def resolve_alias(meta: FileMeta, class_name: str, function_name: str, value: str) -> str:
    current = value
    seen: Set[str] = set()
    for _ in range(5):
        if not current or current in seen:
            break
        seen.add(current)
        candidates = [
            (class_name, function_name, current),
            (class_name, "", current),
            ("<module>", "", current),
        ]
        replacement = next((meta.aliases[key] for key in candidates if key in meta.aliases), "")
        if not replacement or replacement == current:
            break
        current = replacement
    return current


class MetaVisitor(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.meta = FileMeta(path=path, tree=None)  # type: ignore[arg-type]
        self.class_stack: List[str] = []
        self.function_stack: List[str] = []
        self.conditional_depth = 0

    @property
    def class_name(self) -> str:
        return self.class_stack[-1] if self.class_stack else "<module>"

    @property
    def function_name(self) -> str:
        return self.function_stack[-1] if self.function_stack else ""

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.meta.classes[node.name] = [expr_text(base) for base in node.bases]
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        parent = self.function_name
        self.meta.functions[(self.class_name, node.name)].append(FunctionInfo(self.class_name, node.name, node, parent))
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def _visit_conditional(self, node: ast.AST) -> None:
        self.conditional_depth += 1
        self.generic_visit(node)
        self.conditional_depth -= 1

    visit_If = _visit_conditional
    visit_For = _visit_conditional
    visit_While = _visit_conditional
    visit_Try = _visit_conditional
    visit_With = _visit_conditional

    def _record_alias(self, target: ast.AST, value: ast.AST) -> None:
        target_name = target_text(target)
        if not target_name:
            return
        if isinstance(value, (ast.Name, ast.Attribute, ast.Constant)):
            source = expr_text(value)
            if source:
                local = self.function_name if not target_name.startswith("self.") else ""
                self.meta.aliases[(self.class_name, local, target_name)] = source
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "GetId":
            owner = expr_text(value.func.value)
            if owner:
                local = self.function_name if not target_name.startswith("self.") else ""
                self.meta.aliases[(self.class_name, local, target_name)] = f"GETID:{owner}"

    def visit_Assign(self, node: ast.Assign) -> None:
        if node.targets:
            self._record_alias(node.targets[0], node.value)
        if isinstance(node.value, ast.Call) and is_menu_ctor(node.value) and node.targets:
            owner = target_text(node.targets[0])
            if owner:
                self.meta.menu_owners.add(owner)
        if isinstance(node.value, ast.Call) and expr_text(node.value.func).endswith("MenuItem") and len(node.value.args) >= 2:
            self.meta.menuitem_ids[(self.class_name, node.lineno)] = expr_text(node.value.args[1])
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._record_alias(node.target, node.value)
            if isinstance(node.value, ast.Call) and is_menu_ctor(node.value):
                owner = target_text(node.target)
                if owner:
                    self.meta.menu_owners.add(owner)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        for candidate in [node.func, *node.args, *(kw.value for kw in node.keywords)]:
            text = expr_text(candidate)
            name = text.rsplit(".", 1)[-1]
            if name.startswith("On"):
                self.meta.referenced_handlers.add((self.class_name, name))

        if isinstance(node.func, ast.Attribute) and node.func.attr == "Bind" and len(node.args) >= 2:
            owner = expr_text(node.func.value)
            source = keyword_expr(node, "source")
            if not source and len(node.args) >= 3:
                source = expr_text(node.args[2])
            if not source and owner not in {"self", "wx.EvtHandler"}:
                source = owner
            self.meta.bindings.append(BetterBinding(
                self.meta.path, self.class_name, self.function_name, node.lineno,
                source, keyword_expr(node, "id"), expr_text(node.args[0]), expr_text(node.args[1]),
                conditional=self.conditional_depth > 0,
            ))
        self.generic_visit(node)


def build_meta(root: Path, path: Path) -> Optional[FileMeta]:
    rel = str(path.relative_to(root)).replace("\\", "/")
    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=rel)
    except (SyntaxError, UnicodeDecodeError):
        return None
    visitor = MetaVisitor(rel)
    visitor.meta.tree = tree
    visitor.visit(tree)
    return visitor.meta


def class_is_menu(meta: FileMeta, class_name: str, seen: Optional[Set[str]] = None) -> bool:
    seen = set() if seen is None else seen
    if class_name in seen:
        return False
    seen.add(class_name)
    for base in meta.classes.get(class_name, []):
        short = base.rsplit(".", 1)[-1]
        if short in {"Menu", "MenuBar"}:
            return True
        if short in meta.classes and class_is_menu(meta, short, seen):
            return True
    return False


def menu_append_is_real(meta: FileMeta, command) -> bool:
    if "#menu@" not in command.source:
        return True
    owner = command.source.split("#menu@", 1)[0]
    if owner in meta.menu_owners:
        return True
    if owner == "self" and class_is_menu(meta, command.class_name):
        return True
    resolved = resolve_alias(meta, command.class_name, command.function_name, owner)
    return resolved in meta.menu_owners


def handler_name(ref: str) -> str:
    return (ref or "").rsplit(".", 1)[-1]


def find_handler(meta: FileMeta, class_name: str, ref: str, binding_line: int = 0) -> Tuple[Optional[ast.FunctionDef], bool]:
    name = handler_name(ref)
    if not name:
        return None, False
    choices = meta.functions.get((class_name, name), [])
    if choices:
        choices = sorted(choices, key=lambda item: (abs(item.node.lineno - binding_line), item.node.lineno))
        return choices[0].node, False

    seen: Set[str] = set()
    queue = [base.rsplit(".", 1)[-1] for base in meta.classes.get(class_name, [])]
    while queue:
        base = queue.pop(0)
        if base in seen:
            continue
        seen.add(base)
        choices = meta.functions.get((base, name), [])
        if choices:
            return sorted(choices, key=lambda item: item.node.lineno)[0].node, True
        queue.extend(parent.rsplit(".", 1)[-1] for parent in meta.classes.get(base, []))
    return None, False


def better_id_for_command(meta: FileMeta, command) -> str:
    return meta.menuitem_ids.get((command.class_name, command.line), command.command_id)


def source_candidates(meta: FileMeta, command) -> Set[str]:
    raw = command.source or ""
    result = {raw} if raw else set()
    if raw:
        resolved = resolve_alias(meta, command.class_name, command.function_name, raw)
        result.add(resolved)
        if resolved.startswith("GETID:"):
            result.add(resolved.split(":", 1)[1])
    return {item for item in result if item}


def binding_candidates(meta: FileMeta, command) -> List[BetterBinding]:
    sources = source_candidates(meta, command)
    cid = normalize_id(better_id_for_command(meta, command))
    found: List[BetterBinding] = []
    for binding in meta.bindings:
        if binding.class_name != command.class_name:
            continue
        bsource = binding.source
        if bsource:
            bsource = resolve_alias(meta, binding.class_name, binding.function_name, bsource)
        bid = normalize_id(binding.command_id)
        if (sources and bsource in sources) or (cid and bid and cid == bid):
            found.append(binding)
    return sorted(found, key=lambda b: (0 if b.function_name == command.function_name else 1, abs(b.line - command.line), b.line))


def apply_empty_classification(command, node: ast.FunctionDef, stats: Pass2Stats) -> bool:
    info = NATIVE_EMPTY.get((command.path, command.class_name, node.name))
    if not info:
        return False
    category, defect, status, severity, detail = info
    command.status = status
    command.defect_type = defect
    command.severity = severity
    command.result_obtained = f"Classification {category} — {detail}"
    command.trace = f"{command.path}:{command.line}; handler:{node.lineno}; EMPTY-{category}"
    if category == "A":
        stats.empty_native += 1
    elif category == "D":
        stats.empty_inaccessible += 1
    return True


def command_already_represents_binding(commands: Sequence, binding: BetterBinding) -> bool:
    for command in commands:
        if command.path != binding.path or command.class_name != binding.class_name:
            continue
        if command.handler == binding.handler and command.event == binding.event:
            return True
        if binding.source and command.source == binding.source and command.event == binding.event:
            return True
    return False


def add_synthetic_events(result, metas: Dict[str, FileMeta], Command, stats: Pass2Stats) -> None:
    additions = []
    for path, meta in metas.items():
        for binding in meta.bindings:
            descriptor = SYNTHETIC_EVENTS.get(binding.event)
            if not descriptor or command_already_represents_binding(result.commands, binding):
                continue
            label, kind = descriptor
            command = Command(path=path, class_name=binding.class_name, function_name=binding.function_name or "<module>",
                              line=binding.line, kind=kind, source=binding.source or binding.event,
                              command_id=binding.command_id, label=label)
            command.event = binding.event
            command.handler = binding.handler
            node, inherited = find_handler(meta, binding.class_name, binding.handler, binding.line)
            if node is not None:
                proof = execute_handler(node, label, command.source, binding.handler)
                if proof.ok:
                    command.status = "PASS"
                    command.defect_type = "AUTOMATED_EXECUTION_PROOF"
                    command.result_obtained = proof.detail
                    command.trace = f"tests/test_vanilla_ui_second_pass.py; {path}:{binding.line}; handler:{node.lineno}; {proof.action}"
                    stats.automated_execution_proofs += 1
                else:
                    command.status = "BLOCKED"
                    command.defect_type = "HUMAN_RECIPE_REQUIRED"
                    command.result_obtained = f"Événement résolu vers {binding.handler}; {proof.detail}"
                    command.trace = f"{path}:{binding.line}; handler:{node.lineno}; HUMAN_RECIPE_REQUIRED"
                if inherited:
                    stats.inherited_handlers += 1
            else:
                command.status = "BLOCKED"
                command.defect_type = "HUMAN_RECIPE_REQUIRED"
                command.result_obtained = f"Événement résolu vers {binding.handler}; cible non exécutable sans runtime GUI"
                command.trace = f"{path}:{binding.line}; HUMAN_RECIPE_REQUIRED"
            additions.append(command)
            stats.synthetic_event_commands += 1
    result.commands.extend(additions)


def refine_diagnostics(result, metas: Dict[str, FileMeta], stats: Pass2Stats) -> None:
    refined = []
    for diag in result.diagnostics:
        if diag.kind != "HANDLER_ON_UNBOUND_STATIC":
            refined.append(diag)
            continue
        meta = metas.get(diag.path)
        if meta is None:
            refined.append(diag)
            continue
        match = re.search(r"([^\.\s]+)\.([A-Za-z_][A-Za-z0-9_]*)", diag.message)
        if not match:
            refined.append(diag)
            continue
        class_name, name = match.group(1), match.group(2)
        if (class_name, name) in meta.referenced_handlers:
            stats.direct_handler_correlations += 1
            continue
        if name in FRAMEWORK_OVERRIDES:
            stats.framework_overrides_classified += 1
            continue
        refined.append(diag)
    result.diagnostics = refined


def enhance(root: Path, result, Command) -> Pass2Stats:
    metas: Dict[str, FileMeta] = {}
    for path in sorted((root / "noethys").rglob("*.py")):
        meta = build_meta(root, path)
        if meta is not None:
            metas[meta.path] = meta

    stats = Pass2Stats()
    filtered = []
    for command in result.commands:
        meta = metas.get(command.path)
        if meta is None:
            filtered.append(command)
            continue
        if command.kind == "menu" and not menu_append_is_real(meta, command):
            stats.filtered_false_commands += 1
            continue

        corrected_id = better_id_for_command(meta, command)
        if corrected_id:
            command.command_id = corrected_id

        candidates = binding_candidates(meta, command)
        if candidates:
            binding = candidates[0]
            was_unresolved = command.defect_type == "STATIC_BIND_UNRESOLVED"
            command.event = binding.event or "Bind"
            command.handler = binding.handler
            node, inherited = find_handler(meta, command.class_name, binding.handler, binding.line)
            if inherited:
                stats.inherited_handlers += 1
            if node is not None and apply_empty_classification(command, node, stats):
                pass
            elif command.status != "FAIL":
                if node is not None:
                    proof = execute_handler(node, command.label, command.source, binding.handler)
                    if proof.ok:
                        command.status = "PASS"
                        command.defect_type = "AUTOMATED_EXECUTION_PROOF"
                        command.severity = ""
                        cond = " (binding conditionnel)" if binding.conditional else ""
                        command.result_obtained = f"{proof.detail}{cond}"
                        command.trace = f"tests/test_vanilla_ui_second_pass.py; {command.path}:{command.line}; bind:{binding.line}; handler:{node.lineno}; {proof.action}"
                        stats.automated_execution_proofs += 1
                    else:
                        command.status = "BLOCKED"
                        command.defect_type = "HUMAN_RECIPE_REQUIRED"
                        command.result_obtained = f"Liaison résolue vers {binding.handler}; {proof.detail}"
                        command.trace = f"{command.path}:{command.line}; bind:{binding.line}; handler:{node.lineno}; HUMAN_RECIPE_REQUIRED"
                else:
                    command.status = "BLOCKED"
                    command.defect_type = "HUMAN_RECIPE_REQUIRED"
                    command.result_obtained = f"Liaison résolue vers {binding.handler}; cible héritée/externe non exécutable de façon sûre"
                    command.trace = f"{command.path}:{command.line}; bind:{binding.line}; HUMAN_RECIPE_REQUIRED"
            if was_unresolved:
                stats.rebound_commands += 1
        elif command.status == "BLOCKED" and command.defect_type == "EMPTY_HANDLER_REVIEW":
            node, _ = find_handler(meta, command.class_name, command.handler, command.line)
            if node is not None:
                apply_empty_classification(command, node, stats)
        elif command.status == "BLOCKED" and command.defect_type == "HUMAN_RECIPE_REQUIRED" and command.handler:
            node, inherited = find_handler(meta, command.class_name, command.handler, command.line)
            if node is not None:
                if apply_empty_classification(command, node, stats):
                    pass
                else:
                    proof = execute_handler(node, command.label, command.source, command.handler)
                    if proof.ok:
                        command.status = "PASS"
                        command.defect_type = "AUTOMATED_EXECUTION_PROOF"
                        command.result_obtained = proof.detail
                        command.trace = f"tests/test_vanilla_ui_second_pass.py; {command.path}:{command.line}; handler:{node.lineno}; {proof.action}"
                        stats.automated_execution_proofs += 1
                if inherited:
                    stats.inherited_handlers += 1
        filtered.append(command)

    result.commands = filtered
    refine_diagnostics(result, metas, stats)
    add_synthetic_events(result, metas, Command, stats)
    result.commands.sort(key=lambda c: (c.path.lower(), c.class_name.lower(), c.line, c.label.lower()))
    result.pass2_stats = stats
    return stats


def load_first_pass(root: Path):
    path = root / "tools" / "audit_ui_commands.py"
    spec = importlib.util.spec_from_file_location("audit_ui_commands_pass1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Impossible de charger le scanner du passage 1")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def a5134_row() -> Dict[str, str]:
    return {
        "Écran / module": "Procédures historiques / état global des consommations",
        "Commande": "A5134 — ancien état global des consommations",
        "Déclencheur": "Procédure A5134 (accessibilité UI à confirmer)",
        "Précondition": "Procédure effectivement exposée à l'utilisateur",
        "Résultat attendu": "Ouvrir le dialogue historique d'archives ou échouer proprement",
        "Résultat obtenu": "La procédure importe Dlg.DLG_Etat_global_archives, module absent de maintenance/vanilla; accessibilité utilisateur non démontrée",
        "Statut": "BLOCKED",
        "Type de défaut": "KNOWN_PROCEDURE_TARGET_MISSING",
        "Gravité": "P2",
        "Trace / test associé": "noethys/Utils/UTILS_Procedures.py:374; HUMAN_RECIPE_REQUIRED",
    }


def known_rows_pass2(first) -> List[Dict[str, str]]:
    rows = first.known_rows()
    for row in rows:
        if row.get("Type de défaut") == "NATIVE_WX_LIFECYCLE_CRASH":
            row["Résultat obtenu"] = "Historique: crash Windows 0xc0000005 reproduit sur maintenance/vanilla. CORRECTIF EXISTANT — VALIDATION RUNTIME REQUISE (PR #359)."
            row["Trace / test associé"] = "PR #359; CORRECTIF EXISTANT — VALIDATION RUNTIME REQUISE"
    rows.append(a5134_row())
    return rows


def manual_scenarios() -> List[Tuple[str, str]]:
    return [
        ("WIN-01", "Démarrage/accueil + menus principaux en thème Windows clair et sombre; Vanilla doit rester clair."),
        ("WIN-02", "Navigation famille/individu : ouvrir fiche, Ajouter/Modifier/Annuler/Fermer, double-clic et croix."),
        ("WIN-03", "Activités/inscriptions : navigation, CRUD non destructif sur données jetables, listes contextuelles."),
        ("WIN-04", "Consommations : chargement, fermeture pendant chargement, réouverture répétée; valider PR #359."),
        ("WIN-05", "Consommations/questionnaires : mesurer le temps de chargement sur volume représentatif Docker."),
        ("WIN-06", "Listes d'attente/refus : reproduire le bouton sans effet et vérifier les menus contextuels associés."),
        ("WIN-07", "Facturation/devis/factures : aperçu/impression/export; toute écriture uniquement sur données jetables."),
        ("WIN-08", "Règlements/prélèvements : parcours lecture/édition contrôlée, confirmations et annulation; aucune production."),
        ("WIN-09", "Documents/pièces jointes/photos : ouvrir/visualiser/importer sur fichiers temporaires puis nettoyer."),
        ("WIN-10", "Impression/Aperçu/Export génériques ObjectListView : PDF, texte, Excel avec répertoire temporaire."),
        ("WIN-11", "Recherche/filtre/rafraîchissement : listes représentatives famille, activités, facturation."),
        ("WIN-12", "Menus contextuels et doubles-clics sur ObjectListView/FastObjectListView avec et sans sélection."),
        ("WIN-13", "Cycle de vie wx : bouton Fermer, Annuler, croix, double fermeture, fermer/réouvrir sur dialogues à timer/liste virtuelle."),
        ("WIN-14", "Badgeage : vérifier les trois RadioButton d'identification; sélection native + état des contrôles secondaires."),
        ("WIN-15", "Lot Trésor public : confirmer que 'Générer le fichier d'export...' ne produit aucune action/voie alternative."),
        ("WIN-16", "Procédure A5134 : déterminer si elle est encore accessible depuis l'UI; si oui, constater l'échec du module manquant."),
        ("WIN-17", "Commande 'Voir tout' : localiser les écrans restants et vérifier le comportement attendu d'affichage direct."),
        ("WIN-18", "Fonctions dépendantes Windows/périphérique : webcam, imprimante, ouverture de fichiers externes, shell."),
        ("WIN-19", "Portail/réseau/Connecthys : uniquement dépendance indisponible/mock/recette isolée, jamais production."),
        ("WIN-20", "Permissions : utilisateur restreint, commandes désactivées/cachées et échec propre sans droit."),
    ]


def comparison_rows(counts: Counter, defect_counts: Counter, diag_counts: Counter) -> List[Tuple[str, int, int]]:
    return [
        ("PASS", PASS1["PASS"], counts.get("PASS", 0)),
        ("FAIL", PASS1["FAIL"], counts.get("FAIL", 0)),
        ("BLOCKED", PASS1["BLOCKED"], counts.get("BLOCKED", 0)),
        ("STATIC_BIND_UNRESOLVED", PASS1["STATIC_BIND_UNRESOLVED"], defect_counts.get("STATIC_BIND_UNRESOLVED", 0)),
        ("HUMAN_RECIPE_REQUIRED", PASS1["HUMAN_RECIPE_REQUIRED"], defect_counts.get("HUMAN_RECIPE_REQUIRED", 0)),
        ("EMPTY_HANDLER_REVIEW", PASS1["EMPTY_HANDLER_REVIEW"], defect_counts.get("EMPTY_HANDLER_REVIEW", 0)),
        ("Handlers On... non corrélés", PASS1["HANDLER_ON_UNBOUND_STATIC"], diag_counts.get("HANDLER_ON_UNBOUND_STATIC", 0)),
    ]


def render(root: Path, first, result, baseline_sha: str) -> str:
    stats: Pass2Stats = result.pass2_stats
    rows = [first.command_to_row(command) for command in result.commands] + known_rows_pass2(first)
    counts = Counter(row["Statut"] for row in rows)
    defects = Counter(row["Type de défaut"] for row in rows if row["Type de défaut"])
    severities = Counter(row["Gravité"] for row in rows if row["Gravité"])
    diags = Counter(item.kind for item in result.diagnostics)

    lines = [
        "# Audit fonctionnel systématique des commandes — Noethys Vanilla", "",
        f"Baseline auditée : `maintenance/vanilla` / `{baseline_sha or 'SHA_NON_FOURNI'}`.", "",
        "## Passage 2 — règle de preuve", "",
        "Le passage 2 repart du scanner du passage 1, corrige les faux positifs d'inventaire (notamment `PropertyGrid.Append`) et les IDs de `wx.MenuItem`, suit des aliases et héritages statiquement certains, puis exécute uniquement des handlers originaux appartenant à un sous-ensemble contrôlé. Un `PASS` signifie que le corps AST original du handler a été compilé et exécuté avec des sondes inertes, et que l'appel actionnel attendu a effectivement été observé. Une simple présence de bouton ou de `Bind` ne donne jamais PASS.", "",
        "Aucun module métier `noethys/` n'est importé par le harnais d'exécution. Aucune BDD, production, Connecthys, impression, export, fichier utilisateur ou réseau n'est touché.", "",
        "## Synthèse passage 2", "",
        f"- Fichiers Python analysés : **{result.python_files}**",
        f"- Commandes wx recensées après nettoyage : **{len(result.commands)}**",
        f"- Scénarios/observations connus ajoutés : **{len(known_rows_pass2(first))}**",
        f"- Lignes de la matrice : **{len(rows)}**",
        f"- Bind recensés au passage 1 : **{result.binding_count}**",
        f"- Fonctions/handlers recensés : **{result.handler_count}**",
        f"- PASS : **{counts.get('PASS', 0)}**",
        f"- FAIL : **{counts.get('FAIL', 0)}**",
        f"- BLOCKED : **{counts.get('BLOCKED', 0)}**",
        f"- NOT_TESTABLE : **{counts.get('NOT_TESTABLE', 0)}**",
        f"- `STATIC_BIND_UNRESOLVED` restant : **{defects.get('STATIC_BIND_UNRESOLVED', 0)}**",
        f"- `HUMAN_RECIPE_REQUIRED` restant : **{defects.get('HUMAN_RECIPE_REQUIRED', 0)}**",
        f"- `EMPTY_HANDLER_REVIEW` restant : **{defects.get('EMPTY_HANDLER_REVIEW', 0)}**",
        f"- Handlers `On...` toujours non corrélés : **{diags.get('HANDLER_ON_UNBOUND_STATIC', 0)}**",
        f"- Nouvelles preuves d'exécution automatisées : **{stats.automated_execution_proofs}**",
        f"- Faux positifs de commandes supprimés de l'inventaire : **{stats.filtered_false_commands}**",
        f"- Commandes auparavant `STATIC_BIND_UNRESOLVED` reliées avec certitude : **{stats.rebound_commands}**",
        f"- Événements fermeture/double-clic ajoutés explicitement : **{stats.synthetic_event_commands}**",
        "- Nouveaux défauts réellement confirmés pendant ce passage : **0**", "",
        "### Comparaison chiffrée", "",
        "| Catégorie | Passage 1 | Passage 2 | Écart |", "|---|---:|---:|---:|",
    ]
    for name, p1, p2 in comparison_rows(counts, defects, diags):
        lines.append(f"| {name} | {p1} | {p2} | {p2-p1:+d} |")

    lines.extend(["", "### Gravités détectées / connues", ""])
    for severity in ("P0", "P1", "P2", "P3"):
        lines.append(f"- {severity} : **{severities.get(severity, 0)}**")
    lines.extend(["", "### Types de défaut / blocage", ""])
    for name, count in sorted(defects.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{name}` : {count}")
    lines.extend(["", "### Diagnostics statiques complémentaires", ""])
    for name, count in sorted(diags.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{name}` : {count}")

    lines.extend(["", "## Qualification des handlers vides", "",
        "- **A — wx natif** : `CTRL_Interface.OnChoixIdentification` (3 RadioButton de badgeage). La sélection du radio est native; le code secondaire ancien est commenté. Statut `NOT_TESTABLE` en CI headless, scénario WIN-14.",
        "- **D — inaccessible** : `Page_installation.Onbouton_annuler` de l'Updater. `Installation()` désactive explicitement le bouton avant `wx.CallLater`; le handler vide n'est pas une commande utilisateur active pendant l'installation. Statut `NOT_TESTABLE`.",
        "- **C — action attendue absente** : `Dialog.OnBoutonFichier` du Lot Trésor public reste le défaut P2 déjà identifié; aucun correctif n'est inclus.",
        "- Aucun handler vide n'est promu en PASS par simple interprétation statique.", "",
        "## Nouveaux défauts réellement confirmés au passage 2", "",
        "- **Aucun nouveau défaut confirmé.** Les ambiguïtés restantes restent BLOCKED/NOT_TESTABLE.", "",
        "## Tests automatisés associés", "",
        "- `python -m compileall -q -x 'C866CA3A-32F7-11D2-9602-00C04F8EE628x0x5x0\\.py$' noethys` : compilation syntaxique; wrapper COM Windows historique exclu sur Linux.",
        "- `python -m unittest tests.test_vanilla_ui_command_audit tests.test_vanilla_ui_second_pass` : invariants du passage 1 + corrélation MenuItem/aliases, filtrage des faux Append, exécution contrôlée et cycle de vie simulable.",
        "- `python tools/audit_ui_second_pass.py --root . --output docs/VANILLA_UI_COMMAND_AUDIT.md` : régénération déterministe du rapport du passage 2.", "",
        "## Diagnostics statiques hors matrice", "",
    ])
    if result.parse_errors:
        for item in result.parse_errors:
            lines.append(f"- `{first.md_escape(item)}`")
    elif result.diagnostics:
        for item in result.diagnostics:
            lines.append(f"- `{item.path}:{item.line}` — `{item.kind}` — {first.md_escape(item.message)}")
    else:
        lines.append("Aucune erreur de parsing ni diagnostic statique restant.")

    lines.extend(["", "## Matrice exhaustive des commandes recensées", "",
                  "| " + " | ".join(first.COLUMNS) + " |",
                  "| " + " | ".join("---" for _ in first.COLUMNS) + " |"])
    for row in rows:
        lines.append("| " + " | ".join(first.md_escape(row.get(column, "")) for column in first.COLUMNS) + " |")

    lines.extend(["", "## Recette humaine restante — scénarios groupés", "",
                  "Les milliers de lignes BLOCKED ne sont **pas** transformées en autant de scénarios humains. Elles sont regroupées par contrat fonctionnel et dépendance runtime. Les scénarios ci-dessous couvrent la recette Windows + base Docker réellement nécessaire :", ""])
    for sid, text in manual_scenarios():
        lines.append(f"- `{sid}` — {text}")
    lines.extend(["", "Pour Supprimer / Envoyer / Facturer / Publier : mocks, transaction annulée ou données jetables uniquement. Production interdite.", "",
        "## Recommandations de PR séparées — sans ouverture dans cet audit", "",
        "1. PR #359 reste isolée pour le crash consommation; **CORRECTIF EXISTANT — VALIDATION RUNTIME REQUISE**.",
        "2. Liste d'attente : PR dédiée uniquement après reproduction WIN-06 et localisation précise.",
        "3. Lot Trésor public : PR dédiée si WIN-15 confirme l'absence de voie alternative.",
        "4. `Voir tout` : PR UI Vanilla distincte après localisation WIN-17.",
        "5. Performance questionnaires/consommations : PR performance séparée après mesure WIN-05.",
        "6. `A5134` / `DLG_Etat_global_archives` : PR uniquement si WIN-16 confirme que la procédure est encore accessible.",
        "7. Aucun autre correctif ne doit être déduit automatiquement des lignes BLOCKED de ce rapport.", ""])
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--baseline-sha", default="")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    first = load_first_pass(root)
    result = first.scan(root)
    enhance(root, result, first.Command)
    text = render(root, first, result, args.baseline_sha)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 2 if result.parse_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
